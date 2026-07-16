"""Tests for the open /system telemetry endpoint (GPU + activity metadata)."""

import pytest
from fastapi.testclient import TestClient

from api.src.core import model_status
from api.src.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_model_status():
    model_status.reset()
    yield
    model_status.reset()


def test_system_endpoint_shape():
    res = client.get("/system")
    assert res.status_code == 200
    body = res.json()

    # Top-level contract the web monitor depends on.
    assert set(body) >= {"version", "status", "gpu", "activity", "model"}
    assert isinstance(body["version"], str)
    assert isinstance(body["status"], str)

    # gpu is either None (CPU/mock host) or a dict with memory fields.
    assert body["gpu"] is None or isinstance(body["gpu"], dict)
    if isinstance(body["gpu"], dict):
        assert "memory_total_bytes" in body["gpu"]
        assert "memory_used_bytes" in body["gpu"]

    # activity always present with integer counters.
    activity = body["activity"]
    assert isinstance(activity, dict)
    assert isinstance(activity["active"], int)
    assert isinstance(activity["waiting"], int)


def test_system_endpoint_is_unauthenticated():
    # No Authorization header — must stay open like /health and /ready.
    res = client.get("/system")
    assert res.status_code == 200


def test_system_reports_model_metadata_when_ready():
    model_status.set_ready(device="cpu", backend="kokoro_v1", voicepack_count=54)
    res = client.get("/system")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["model"]["device"] == "cpu"
    assert body["model"]["backend"] == "kokoro_v1"
    assert body["model"]["voicepack_count"] == 54
