"""Model readiness state shared between the warmup task, health endpoints, and routes.

The server accepts connections as soon as uvicorn binds the socket; the model
loads in a background task (see ``main.py``). This module records where that
task is so ``/health`` and ``/ready`` can report it and inference routes can
reject early with 503 instead of hitting an unloaded backend mid-warmup.

``UNINITIALIZED`` means the lifespan never ran (unit tests, or
``WARMUP_ON_START=false``); it passes the readiness gate so the existing
lazy-load path in ``ModelManager.ensure_backend`` keeps working.
"""

from enum import Enum
from typing import Optional

from fastapi import HTTPException


class ModelStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    WARMING = "warming"
    READY = "ready"
    FAILED = "failed"


_status: ModelStatus = ModelStatus.UNINITIALIZED
_error: Optional[str] = None
_device: Optional[str] = None
_backend: Optional[str] = None
_voicepack_count: int = 0


def get_status() -> ModelStatus:
    return _status


def get_error() -> Optional[str]:
    return _error


def get_metadata() -> dict:
    """Device/backend/voice info recorded by set_ready (empty until then)."""
    if _status is not ModelStatus.READY:
        return {}
    return {
        "device": _device,
        "backend": _backend,
        "voicepack_count": _voicepack_count,
    }


def set_warming() -> None:
    global _status, _error
    _status = ModelStatus.WARMING
    _error = None


def set_ready(device: str, backend: str, voicepack_count: int) -> None:
    global _status, _error, _device, _backend, _voicepack_count
    _status = ModelStatus.READY
    _error = None
    _device = device
    _backend = backend
    _voicepack_count = voicepack_count


def set_failed(error: str) -> None:
    global _status, _error
    _status = ModelStatus.FAILED
    _error = error


def reset() -> None:
    """Restore the initial state (test isolation)."""
    global _status, _error, _device, _backend, _voicepack_count
    _status = ModelStatus.UNINITIALIZED
    _error = None
    _device = None
    _backend = None
    _voicepack_count = 0


def require_model_ready() -> None:
    """Route dependency: reject inference requests until the model is usable.

    Must run as a dependency (before the handler) because streaming responses
    commit their 200 status line before generation starts — an unload/warmup
    failure inside the stream can't change the status code anymore.
    """
    if _status is ModelStatus.WARMING:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model_warming",
                "message": "TTS model is still loading; retry shortly.",
                "type": "server_error",
            },
            headers={"Retry-After": "10"},
        )
    if _status is ModelStatus.FAILED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model_failed",
                "message": f"TTS model failed to load: {_error}",
                "type": "server_error",
            },
        )
    # READY and UNINITIALIZED both pass; UNINITIALIZED falls through to the
    # lazy-load path in ModelManager.ensure_backend.
