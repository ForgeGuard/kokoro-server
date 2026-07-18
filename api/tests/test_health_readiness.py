"""Tests for the model readiness state machine, /health + /ready semantics,
and the 503 warming guard on inference routes.

IMPORTANT: never let the real warmup run inside `with TestClient(app)` — a
failed warmup calls os._exit(1), which would kill the pytest process. Every
lifespan-entering test patches the manager factories.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.src.core import model_status
from api.src.core.config import settings
from api.src.core.model_status import ModelStatus
from api.src.main import _startup_banner, _warmup, app

client = TestClient(app)

SPEECH_BODY = {"model": "kokoro", "input": "hello", "voice": "af_heart"}


@pytest.fixture(autouse=True)
def reset_model_status():
    """Module-level state must never leak between tests."""
    model_status.reset()
    yield
    model_status.reset()


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_initial_state_uninitialized():
    assert model_status.get_status() is ModelStatus.UNINITIALIZED
    assert model_status.get_error() is None
    assert model_status.get_metadata() == {}


def test_transitions():
    model_status.set_warming()
    assert model_status.get_status() is ModelStatus.WARMING

    model_status.set_ready("cuda", "kokoro_v1", 54)
    assert model_status.get_status() is ModelStatus.READY
    assert model_status.get_metadata() == {
        "device": "cuda",
        "backend": "kokoro_v1",
        "voicepack_count": 54,
    }

    model_status.set_failed("boom")
    assert model_status.get_status() is ModelStatus.FAILED
    assert model_status.get_error() == "boom"
    assert model_status.get_metadata() == {}

    model_status.reset()
    assert model_status.get_status() is ModelStatus.UNINITIALIZED


# ---------------------------------------------------------------------------
# /health and /ready per state (no lifespan)
# ---------------------------------------------------------------------------


def test_health_uninitialized():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "model_loaded": False}


def test_health_warming():
    model_status.set_warming()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "warming", "model_loaded": False}


def test_health_ready():
    model_status.set_ready("cpu", "kokoro_v1", 5)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "model_loaded": True}


def test_health_failed():
    model_status.set_failed("model exploded")
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "failed", "error": "model exploded"}


def test_ready_only_when_ready():
    for state_setter, expected in [
        (lambda: None, 503),  # UNINITIALIZED
        (model_status.set_warming, 503),
        (lambda: model_status.set_ready("cpu", "kokoro_v1", 5), 200),
        (lambda: model_status.set_failed("x"), 503),
    ]:
        model_status.reset()
        state_setter()
        r = client.get("/ready")
        assert r.status_code == expected
        if expected == 503:
            assert r.headers["Retry-After"] == "10"


# ---------------------------------------------------------------------------
# Warming guard on inference routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/v1/audio/speech", SPEECH_BODY),
        ("post", "/dev/captioned_speech", SPEECH_BODY),
        (
            "post",
            "/dev/generate_from_phonemes",
            {"phonemes": "h@loU", "voice": "af_heart"},
        ),
    ],
)
def test_inference_routes_503_while_warming(method, path, body):
    model_status.set_warming()
    r = getattr(client, method)(path, json=body)
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "model_warming"
    assert r.headers["Retry-After"] == "10"


def test_inference_routes_503_when_failed():
    model_status.set_failed("no weights")
    r = client.post("/v1/audio/speech", json=SPEECH_BODY)
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "model_failed"


def test_guard_passes_when_ready():
    """When READY the guard lets the request through to normal validation
    (422 on a garbage body proves we got past the 503 gate)."""
    model_status.set_ready("cpu", "kokoro_v1", 5)
    r = client.post("/v1/audio/speech", json={"voice": 42})
    assert r.status_code == 422


def test_non_model_routes_open_while_warming():
    """Routes without a model dependency keep working during warmup."""
    model_status.set_warming()
    r = client.get("/v1/models")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Auth interaction: 401 wins over warming 503; health/ready stay open
# ---------------------------------------------------------------------------


def test_auth_beats_warming_503():
    model_status.set_warming()
    with patch.object(settings, "api_key", "sekrit"):
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503  # open, but not ready

        r = client.post("/v1/audio/speech", json=SPEECH_BODY)
        assert r.status_code == 401

        r = client.post(
            "/v1/audio/speech",
            json=SPEECH_BODY,
            headers={"Authorization": "Bearer sekrit"},
        )
        assert r.status_code == 503
        assert r.json()["detail"]["error"] == "model_warming"


# ---------------------------------------------------------------------------
# Lifespan behavior
# ---------------------------------------------------------------------------


def _mock_managers(release: threading.Event):
    """Manager factories whose warmup completes when `release` is set.

    A threading.Event polled from the event loop keeps the signal thread-safe
    (TestClient runs the app loop in a worker thread).
    """

    async def slow_warmup(voice_manager):
        while not release.is_set():
            await asyncio.sleep(0.01)
        return ("cpu", "kokoro_v1", 5)

    manager = AsyncMock()
    manager.initialize_with_warmup = AsyncMock(side_effect=slow_warmup)
    return (
        patch(
            "api.src.inference.model_manager.get_manager",
            new=AsyncMock(return_value=manager),
        ),
        patch(
            "api.src.inference.voice_manager.get_manager",
            new=AsyncMock(return_value=AsyncMock()),
        ),
        patch(
            "api.src.services.temp_manager.cleanup_temp_files",
            new=AsyncMock(),
        ),
    )


def _wait_for_healthy(c: TestClient, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = c.get("/health").json()
        if body["status"] == "healthy" and body["model_loaded"]:
            return body
        time.sleep(0.02)
    raise AssertionError("server never reported healthy/model_loaded")


def test_lifespan_serves_while_warming_then_ready():
    release = threading.Event()
    p1, p2, p3 = _mock_managers(release)
    with p1, p2, p3:
        with TestClient(app) as c:
            # Serving immediately, still warming
            r = c.get("/health")
            assert r.status_code == 200
            assert r.json() == {"status": "warming", "model_loaded": False}
            assert c.get("/ready").status_code == 503

            release.set()
            _wait_for_healthy(c)
            assert c.get("/ready").status_code == 200


def test_lifespan_warmup_disabled(monkeypatch):
    monkeypatch.setattr(settings, "warmup_on_start", False)
    release = threading.Event()
    release.set()
    p1, p2, p3 = _mock_managers(release)
    with p1, p2, p3:
        with TestClient(app) as c:
            r = c.get("/health")
            assert r.status_code == 200
            assert r.json() == {"status": "healthy", "model_loaded": False}
            assert model_status.get_status() is ModelStatus.UNINITIALIZED


def test_lifespan_shutdown_cancels_pending_warmup():
    release = threading.Event()  # never set: warmup stays pending
    p1, p2, p3 = _mock_managers(release)
    with p1, p2, p3:
        with TestClient(app) as c:
            assert c.get("/health").json()["status"] == "warming"
        # exiting the context runs shutdown; the pending task must be
        # cancelled without hanging or raising
    assert app.state.warmup_task.cancelled()


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


class _Exit(Exception):
    def __init__(self, code):
        self.code = code


def test_warmup_failure_sets_failed_and_exits(monkeypatch):
    def fake_exit(code):
        raise _Exit(code)

    monkeypatch.setattr("os._exit", fake_exit)

    failing_manager = AsyncMock()
    failing_manager.initialize_with_warmup = AsyncMock(
        side_effect=RuntimeError("Warmup failed: no weights")
    )
    with (
        patch(
            "api.src.inference.model_manager.get_manager",
            new=AsyncMock(return_value=failing_manager),
        ),
        patch(
            "api.src.inference.voice_manager.get_manager",
            new=AsyncMock(return_value=AsyncMock()),
        ),
    ):
        with pytest.raises(_Exit) as exc_info:
            asyncio.run(_warmup(app))

    assert exc_info.value.code == 1
    assert model_status.get_status() is ModelStatus.FAILED
    assert "no weights" in model_status.get_error()


@pytest.mark.asyncio
async def test_missing_model_files_raise_instead_of_exit_zero():
    """Regression: FileNotFoundError used to exit(0) and silently restart-loop."""
    from api.src.inference.model_manager import ModelManager

    manager = ModelManager()
    with (
        patch.object(manager, "initialize", new_callable=AsyncMock),
        patch.object(
            manager,
            "load_model",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("kokoro-v1_0.pth"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Model files not found"):
            await manager.initialize_with_warmup(voice_manager=AsyncMock())


# ---------------------------------------------------------------------------
# ForgeGuard startup banner
# ---------------------------------------------------------------------------

CUDA_GPU = {
    "name": "NVIDIA GeForce RTX 4090",
    "memory_used_bytes": 2 * 1024**3,
    "memory_total_bytes": 24 * 1024**3,
}


def test_startup_banner_is_forgeguard_branded():
    """The banner carries ForgeGuard identity, not the upstream kokoro-fastapi art."""
    banner = _startup_banner(
        device="cuda",
        model="kokoro_v1",
        voicepack_count=54,
        gpu=CUDA_GPU,
        scheme="https",
        color=False,
    )
    assert "ForgeGuard Kokoro Server" in banner
    assert f"v{settings.api_version}" in banner
    assert "54 packs loaded" in banner
    # The old upstream splash must be gone.
    assert "FAST" not in banner
    assert "░" not in banner
    assert "╔" not in banner


def test_startup_banner_reports_runtime_facts():
    """Enriched content: endpoint, auth state, device/VRAM, and console URL."""
    banner = _startup_banner(
        device="cuda",
        model="kokoro_v1",
        voicepack_count=54,
        gpu=CUDA_GPU,
        scheme="https",
        color=False,
    )
    assert f"https://{settings.host}:{settings.port}" in banner
    assert "NVIDIA GeForce RTX 4090" in banner
    assert "2.0 / 24.0 GiB" in banner  # bytes -> GiB
    auth_expected = "bearer token (enabled)" if settings.api_key else "open (disabled)"
    assert auth_expected in banner


def test_startup_banner_cpu_has_no_gpu_rows():
    """On CPU there is no GPU/VRAM line and the device reads plainly."""
    banner = _startup_banner(
        device="cpu",
        model="kokoro_v1",
        voicepack_count=1,
        gpu=None,
        scheme="http",
        color=False,
    )
    assert "cpu" in banner
    assert "VRAM" not in banner


def test_startup_banner_color_markup_is_balanced():
    """Colored output must be valid loguru markup (balanced <fg ...> tags)."""
    banner = _startup_banner(
        device="cuda",
        model="kokoro_v1",
        voicepack_count=54,
        gpu=CUDA_GPU,
        scheme="https",
        color=True,
    )
    assert banner.count("<fg #6366F1>") == banner.count("</fg #6366F1>")
    assert "<fg #6366F1>" in banner
