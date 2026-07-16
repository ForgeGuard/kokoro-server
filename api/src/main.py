"""
FastAPI OpenAI Compatible API
"""

import asyncio
import contextlib
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import torch
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from .core import model_status
from .core.auth import require_api_key
from .core.config import settings
from .core.model_status import ModelStatus
from .routers.debug import router as debug_router
from .routers.development import router as dev_router
from .routers.openai_compatible import router as openai_router
from .routers.web_player import router as web_router


def setup_logger():
    """Configure loguru logger with custom formatting"""
    valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
    level = os.getenv("API_LOG_LEVEL", "INFO").upper()
    if level not in valid_levels:
        level = "INFO"
    print(f"Global API loguru logger level: {level}")
    config = {
        "handlers": [
            {
                "sink": sys.stdout,
                "format": "<fg #2E8B57>{time:hh:mm:ss A}</fg #2E8B57> | "
                "{level: <8} | "
                "<fg #4169E1>{module}:{line}</fg #4169E1> | "
                "{message}",
                "colorize": True,
                "level": level,
            },
        ],
    }
    logger.remove()
    logger.configure(**config)
    logger.level("ERROR", color="<red>")


# Configure logger
setup_logger()


async def _warmup(app: FastAPI):
    """Load and warm the model in the background so the server can accept
    connections (and answer /health) immediately after the socket opens.

    A permanent warmup failure exits the process with a non-zero code: a plain
    raise inside a background task is swallowed by the event loop, and a
    healthy-looking server with no model is worse for orchestrators than a
    dead container they can see and restart.
    """
    from .inference.model_manager import get_manager
    from .inference.voice_manager import get_manager as get_voice_manager

    logger.info("Loading TTS model and voice packs...")

    try:
        model_manager = await get_manager()
        voice_manager = await get_voice_manager()

        device, model, voicepack_count = await model_manager.initialize_with_warmup(
            voice_manager
        )
    except Exception as e:
        model_status.set_failed(str(e))
        logger.error(f"Failed to initialize model, exiting: {e}")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    model_status.set_ready(device, model, voicepack_count)

    boundary = "░" * 2 * 12
    startup_msg = f"""

{boundary}

    ╔═╗┌─┐┌─┐┌┬┐
    ╠╣ ├─┤└─┐ │
    ╚  ┴ ┴└─┘ ┴
    ╦╔═┌─┐┬┌─┌─┐
    ╠╩╗│ │├┴┐│ │
    ╩ ╩└─┘┴ ┴└─┘

{boundary}
                """
    startup_msg += f"\nModel warmed up on {device}: {model}"
    if device == "mps":
        startup_msg += "\nUsing Apple Metal Performance Shaders (MPS)"
    elif device == "cuda":
        startup_msg += f"\nCUDA: {torch.cuda.is_available()}"
    else:
        startup_msg += "\nRunning on CPU"
    startup_msg += f"\n{voicepack_count} voice packs loaded"

    # Add web player info if enabled
    if settings.enable_web_player:
        startup_msg += f"\n\nWeb Console: http://{settings.host}:{settings.port}/web/"
        startup_msg += f"\nor http://localhost:{settings.port}/web/"
    else:
        startup_msg += "\n\nWeb Console: disabled"

    startup_msg += f"\n{boundary}\n"
    logger.info(startup_msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start serving immediately; model warmup runs as a background task."""
    from .services.temp_manager import cleanup_temp_files

    # Clean old temp files on startup
    await cleanup_temp_files()

    if settings.warmup_on_start:
        model_status.set_warming()
        # Held on app.state so the task isn't garbage-collected mid-flight
        app.state.warmup_task = asyncio.create_task(_warmup(app))
        logger.info("Server accepting connections; model warming in background")
    else:
        logger.info("WARMUP_ON_START disabled; model will load on first request")

    yield

    warmup_task = getattr(app.state, "warmup_task", None)
    if warmup_task is not None and not warmup_task.done():
        warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warmup_task


# Initialize FastAPI app
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan,
    openapi_url="/openapi.json",  # Explicitly enable OpenAPI schema
)

# Add CORS middleware if enabled
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers. The optional API key is applied at include time so every
# endpoint on these routers is protected without touching each handler; when
# `settings.api_key` is unset the dependency is a no-op. The health check and
# web player (plus /web/config) are intentionally left open.
_auth = [Depends(require_api_key)]
app.include_router(openai_router, prefix="/v1", dependencies=_auth)
app.include_router(
    dev_router, dependencies=_auth
)  # Development endpoints (e.g. /dev/unload)
app.include_router(debug_router, dependencies=_auth)  # Debug endpoints (host info)
if settings.enable_web_player:
    app.include_router(web_router, prefix="/web")  # Web player static files


# Health/readiness endpoints. Both stay unauthenticated and at the root:
# orchestrators poll /health right after `docker run`, before any API key is
# known, and Kubernetes probes cannot send bearer headers from values alone.
@app.get("/health")
async def health_check():
    """Liveness: 200 as soon as the server accepts connections.

    Reports "warming" (model_loaded: false) while the background warmup runs
    and "healthy" (model_loaded: true) once synthesis is possible. Only a
    permanently failed warmup returns 503 — and that window is brief, since a
    failed warmup exits the process. Note model_loaded means "warmed up", not
    "currently resident": /dev/unload frees the model but the next request
    lazily reloads it.
    """
    status = model_status.get_status()
    if status is ModelStatus.FAILED:
        return JSONResponse(
            status_code=503,
            content={"status": "failed", "error": model_status.get_error()},
        )
    if status is ModelStatus.WARMING:
        return {"status": "warming", "model_loaded": False}
    return {"status": "healthy", "model_loaded": status is ModelStatus.READY}


@app.get("/system")
async def system_info():
    """Live server + GPU + activity telemetry for the web monitor.

    Unauthenticated like /health and /ready: the browser console polls this to
    render the GPU/activity bar before any API key is entered, and it exposes
    no secrets — only version, model state, GPU utilization/VRAM/temp/power, and
    in-flight request counts. GPU fields are null on CPU-only hosts.
    """
    from .core.telemetry import activity_info, gpu_info

    status = model_status.get_status()
    return {
        "version": settings.api_version,
        "status": status.value,
        "gpu": gpu_info(),
        "activity": activity_info(),
        "model": model_status.get_metadata(),
    }


@app.get("/ready")
async def readiness_check():
    """Readiness: 200 only once the model is warmed and synthesis will succeed.

    Strict counterpart to /health for Kubernetes readiness/startup probes and
    test harnesses that need "actually able to serve", not "process alive".
    """
    status = model_status.get_status()
    if status is ModelStatus.READY:
        return {"status": "ready"}
    return JSONResponse(
        status_code=503,
        content={"status": status.value},
        headers={"Retry-After": "10"},
    )


if __name__ == "__main__":
    # Dev launcher (auto-reload). Production uses `python -m api.src.serve`.
    # Honor TLS_ENABLED here too so `python -m api.src.main` also serves HTTPS.
    from .serve import tls_kwargs

    uvicorn.run(
        "api.src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        **tls_kwargs(),
    )
