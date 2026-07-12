"""Shared helpers for the API routers."""

from typing import Optional

from fastapi import HTTPException
from loguru import logger

from ..services.streaming_audio_writer import StreamingAudioWriter


def map_speech_exception(
    e: Exception, writer: Optional[StreamingAudioWriter] = None
) -> HTTPException:
    """Translate an exception into the standard error envelope.

    Releases the streaming writer (PyAV container + buffer) first so no error
    path leaks it. Returns the HTTPException for the caller to raise.
    """
    if writer is not None:
        try:
            writer.close()
        except Exception:
            pass

    if isinstance(e, HTTPException):
        return e
    if isinstance(e, ValueError):
        logger.warning(f"Invalid request: {str(e)}")
        return HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(e),
                "type": "invalid_request_error",
            },
        )
    if isinstance(e, RuntimeError):
        logger.error(f"Processing error: {str(e)}")
    else:
        logger.error(f"Unexpected error: {str(e)}")
    return HTTPException(
        status_code=500,
        detail={
            "error": "processing_error",
            "message": str(e),
            "type": "server_error",
        },
    )
