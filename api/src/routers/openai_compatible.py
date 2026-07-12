"""OpenAI-compatible router for text-to-speech"""

import json
import os
import re
from typing import AsyncGenerator, Dict, List, Union

import aiofiles
import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger

from ..core.audio_formats import content_type_for
from ..core.config import settings
from ..core.model_status import require_model_ready
from ..inference.base import AudioChunk
from ..services.audio import AudioService
from ..services.streaming_audio_writer import StreamingAudioWriter
from ..services.tts_service import TTSService
from ..structures import OpenAISpeechRequest
from ..structures.schemas import CaptionedSpeechRequest
from .common import map_speech_exception


# Load OpenAI mappings
def load_openai_mappings() -> Dict:
    """Load OpenAI voice and model mappings from JSON"""
    api_dir = os.path.dirname(os.path.dirname(__file__))
    mapping_path = os.path.join(api_dir, "core", "openai_mappings.json")
    try:
        with open(mapping_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load OpenAI mappings: {e}")
        return {"models": {}, "voices": {}}


# Global mappings
_openai_mappings = load_openai_mappings()


router = APIRouter(
    tags=["OpenAI Compatible TTS"],
    responses={404: {"description": "Not found"}},
)

# Global TTSService instance with lock
_tts_service = None
_init_lock = None


async def get_tts_service() -> TTSService:
    """Get global TTSService instance"""
    global _tts_service, _init_lock

    # Create lock if needed
    if _init_lock is None:
        import asyncio

        _init_lock = asyncio.Lock()

    # Initialize service if needed
    if _tts_service is None:
        async with _init_lock:
            # Double check pattern
            if _tts_service is None:
                _tts_service = await TTSService.create()
                logger.info("Created global TTSService instance")

    return _tts_service


async def process_and_validate_voices(
    voice_input: Union[str, List[str]], tts_service: TTSService
) -> str:
    """Process voice input, handling both string and list formats

    Returns:
        Voice name to use (with weights if specified)
    """
    voices = []
    # Convert input to list of voices
    if isinstance(voice_input, str):
        voice_input = voice_input.replace(" ", "").strip()

        if not voice_input:
            raise ValueError("No voice provided")

        if voice_input[-1] in "+-" or voice_input[0] in "+-":
            raise ValueError(f"Voice combination contains empty combine items")

        if re.search(r"[+-]{2,}", voice_input) is not None:
            raise ValueError(f"Voice combination contains empty combine items")
        voices = re.split(r"([-+])", voice_input)
    else:
        # List form (e.g. ["af_bella", "af_sky"]): normalize into the same flat
        # [voice, sep, voice, ...] token stream the string branch produces, so
        # the shared parsing loop below works for both. Joining with "+" also
        # preserves any per-voice weight syntax like "af_bella(2)".
        cleaned = [v.replace(" ", "").strip() for v in voice_input if v and v.strip()]
        if not cleaned:
            raise ValueError("No voice provided")
        voices = re.split(r"([-+])", "+".join(cleaned))

    available_voices = await tts_service.list_voices()

    for voice_index in range(0, len(voices), 2):
        mapped_voice = voices[voice_index].split("(")
        mapped_voice = list(map(str.strip, mapped_voice))

        if len(mapped_voice) > 2:
            raise ValueError(
                f"Voice '{voices[voice_index]}' contains too many weight items"
            )

        if mapped_voice.count(")") > 1:
            raise ValueError(
                f"Voice '{voices[voice_index]}' contains too many weight items"
            )

        mapped_voice[0] = _openai_mappings["voices"].get(
            mapped_voice[0], mapped_voice[0]
        )

        if mapped_voice[0] not in available_voices:
            raise ValueError(
                f"Voice '{mapped_voice[0]}' not found. Available voices: {', '.join(sorted(available_voices))}"
            )

        voices[voice_index] = "(".join(mapped_voice)

    return "".join(voices)


async def stream_audio_chunks(
    tts_service: TTSService,
    request: Union[OpenAISpeechRequest, CaptionedSpeechRequest],
    client_request: Request,
    writer: StreamingAudioWriter,
    voice_name: str,
) -> AsyncGenerator[AudioChunk, None]:
    """Stream audio chunks as they're generated with client disconnect handling.

    voice_name must already be validated (the endpoint does it once; doing it
    again here re-scanned the voices directory on every streaming request).
    """
    try:
        async for chunk_data in tts_service.generate_audio_stream(
            text=request.input,
            voice=voice_name,
            writer=writer,
            speed=request.speed,
            output_format=request.response_format,
            lang_code=request.lang_code,
            volume_multiplier=request.volume_multiplier,
            normalization_options=request.normalization_options,
            return_timestamps=getattr(request, "return_timestamps", False),
        ):
            # Check if client is still connected
            is_disconnected = client_request.is_disconnected
            if callable(is_disconnected):
                is_disconnected = await is_disconnected()
            if is_disconnected:
                logger.info("Client disconnected, stopping audio generation")
                break

            yield chunk_data
    except Exception as e:
        logger.error(f"Error in audio streaming: {str(e)}")
        # Let the exception propagate to trigger cleanup
        raise


@router.post("/audio/speech", dependencies=[Depends(require_model_ready)])
async def create_speech(
    request: OpenAISpeechRequest,
    client_request: Request,
    x_raw_response: str = Header(None, alias="x-raw-response"),
):
    """OpenAI-compatible endpoint for text-to-speech"""
    # Validate model before processing request
    if request.model not in _openai_mappings["models"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_model",
                "message": f"Unsupported model: {request.model}",
                "type": "invalid_request_error",
            },
        )

    writer = None
    try:
        tts_service = await get_tts_service()
        voice_name = await process_and_validate_voices(request.voice, tts_service)

        # Set content type based on format
        content_type = content_type_for(request.response_format)

        writer = StreamingAudioWriter(
            request.response_format, sample_rate=settings.sample_rate
        )

        # Check if streaming is requested (default for OpenAI client)
        if request.stream:
            # Create generator but don't start it yet
            generator = stream_audio_chunks(
                tts_service, request, client_request, writer, voice_name
            )

            # If download link requested, wrap generator with temp file writer
            if request.return_download_link:
                from ..services.temp_manager import TempFileWriter

                # Use download_format if specified, otherwise use response_format
                output_format = request.download_format or request.response_format
                temp_writer = TempFileWriter(output_format)
                await temp_writer.__aenter__()  # Initialize temp file

                # Get download path immediately after temp file creation
                download_path = temp_writer.download_path

                # Create response headers with download path
                headers = {
                    "Content-Disposition": f"attachment; filename=speech.{output_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                    "X-Download-Path": download_path,
                }

                # Add header to indicate if temp file writing is available
                if temp_writer._write_error:
                    headers["X-Download-Status"] = "unavailable"

                # The downloaded file must actually be encoded in
                # download_format — the suffix alone doesn't transcode. When
                # formats differ, re-encode the raw chunk audio through a
                # second writer.
                needs_transcode = output_format != request.response_format
                download_writer = (
                    StreamingAudioWriter(
                        output_format, sample_rate=settings.sample_rate
                    )
                    if needs_transcode
                    else None
                )

                # Create async generator for streaming
                async def dual_output():
                    try:
                        # Write chunks to temp file and stream
                        async for chunk_data in generator:
                            if needs_transcode:
                                if (
                                    chunk_data.audio is not None
                                    and len(chunk_data.audio) > 0
                                ):
                                    download_bytes = download_writer.write_chunk(
                                        chunk_data.audio
                                    )
                                    if download_bytes:
                                        await temp_writer.write(download_bytes)
                            elif chunk_data.output:
                                await temp_writer.write(chunk_data.output)
                            if chunk_data.output:  # Skip empty chunks
                                yield chunk_data.output

                        if needs_transcode:
                            final_bytes = download_writer.write_chunk(finalize=True)
                            if final_bytes:
                                await temp_writer.write(final_bytes)

                        # Finalize the temp file
                        await temp_writer.finalize()
                    except Exception as e:
                        logger.error(f"Error in dual output streaming: {e}")
                        await temp_writer.__aexit__(type(e), e, e.__traceback__)
                        raise
                    finally:
                        # Ensure temp writer is closed
                        if not temp_writer._finalized:
                            await temp_writer.__aexit__(None, None, None)
                        writer.close()
                        if download_writer is not None:
                            download_writer.close()

                # Stream with temp file writing
                return StreamingResponse(
                    dual_output(), media_type=content_type, headers=headers
                )

            async def single_output():
                try:
                    # Stream chunks
                    async for chunk_data in generator:
                        if chunk_data.output:  # Skip empty chunks
                            yield chunk_data.output
                except Exception as e:
                    logger.error(f"Error in single output streaming: {e}")
                    raise
                finally:
                    # Runs on normal completion, client disconnect (the
                    # generator is closed without an exception), and errors —
                    # an except-only close leaked the PyAV encoder on every
                    # aborted stream.
                    writer.close()

            # Standard streaming without download link
            return StreamingResponse(
                single_output(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            headers = {
                "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                "Cache-Control": "no-cache",  # Prevent caching
            }

            # Generate complete audio using public interface
            audio_data = await tts_service.generate_audio(
                text=request.input,
                voice=voice_name,
                writer=writer,
                speed=request.speed,
                volume_multiplier=request.volume_multiplier,
                normalization_options=request.normalization_options,
                lang_code=request.lang_code,
            )

            audio_data = await AudioService.convert_audio(
                audio_data,
                request.response_format,
                writer,
                is_last_chunk=False,
                trim_audio=False,
            )

            # Convert to requested format with proper finalization
            final = await AudioService.convert_audio(
                AudioChunk(np.array([], dtype=np.int16)),
                request.response_format,
                writer,
                is_last_chunk=True,
            )
            output = audio_data.output + final.output

            if request.return_download_link:
                from ..services.temp_manager import TempFileWriter

                # Use download_format if specified, otherwise use response_format
                output_format = request.download_format or request.response_format

                # The download file must be encoded in download_format — the
                # temp file's suffix alone doesn't transcode the bytes.
                if output_format != request.response_format:
                    download_writer = StreamingAudioWriter(
                        output_format, sample_rate=settings.sample_rate
                    )
                    try:
                        download_chunk = await AudioService.convert_audio(
                            AudioChunk(audio_data.audio),
                            output_format,
                            download_writer,
                            is_last_chunk=False,
                            trim_audio=False,
                        )
                        download_final = await AudioService.convert_audio(
                            AudioChunk(np.array([], dtype=np.int16)),
                            output_format,
                            download_writer,
                            is_last_chunk=True,
                        )
                        download_output = (
                            download_chunk.output + download_final.output
                        )
                    finally:
                        download_writer.close()
                else:
                    download_output = output

                temp_writer = TempFileWriter(output_format)
                await temp_writer.__aenter__()  # Initialize temp file

                # Get download path immediately after temp file creation
                download_path = temp_writer.download_path
                headers["X-Download-Path"] = download_path

                try:
                    # Write chunks to temp file
                    logger.info("Writing chunks to tempory file for download")
                    await temp_writer.write(download_output)
                    # Finalize the temp file
                    await temp_writer.finalize()

                except Exception as e:
                    logger.error(f"Error in dual output: {e}")
                    await temp_writer.__aexit__(type(e), e, e.__traceback__)
                    raise
                finally:
                    # Ensure temp writer is closed
                    if not temp_writer._finalized:
                        await temp_writer.__aexit__(None, None, None)

            # Always release the streaming writer (PyAV container + buffer);
            # the non-download path previously returned without closing it.
            writer.close()
            return Response(
                content=output,
                media_type=content_type,
                headers=headers,
            )

    except Exception as e:
        raise map_speech_exception(e, writer)


@router.get("/download/{filename}")
async def download_audio_file(filename: str):
    """Download a generated audio file from temp storage"""
    try:
        from ..core.paths import _find_file, get_content_type

        # Search for file in temp directory
        file_path = await _find_file(
            filename=filename, search_paths=[settings.temp_file_dir]
        )

        # Get content type from path helper
        content_type = await get_content_type(file_path)

        return FileResponse(
            file_path,
            media_type=content_type,
            filename=filename,
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except FileNotFoundError:
        logger.warning(f"Download file not found: {filename}")
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error serving download file {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to serve audio file",
                "type": "server_error",
            },
        )


def _model_entry(model_id: str) -> Dict:
    """Model metadata derived from openai_mappings.json — the single source
    both /models endpoints share, so list and retrieve can't disagree."""
    return {
        "id": model_id,
        "object": "model",
        "created": 1686935002,
        "owned_by": "kokoro",
    }


@router.get("/models")
async def list_models():
    """List all available models"""
    return {
        "object": "list",
        "data": [_model_entry(model_id) for model_id in _openai_mappings["models"]],
    }


@router.get("/models/{model}")
async def retrieve_model(model: str):
    """Retrieve a specific model"""
    if model not in _openai_mappings["models"]:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "model_not_found",
                "message": f"Model '{model}' not found",
                "type": "invalid_request_error",
            },
        )
    return _model_entry(model)


@router.get("/audio/voices")
async def list_voices(legacy: bool = False):
    """List all available voices for text-to-speech.

    Returns `[{"id": ..., "name": ...}, ...]` by default so OpenAI-compatible
    clients (Open WebUI in particular, which does `voice['id']` directly and
    silently falls back to a hardcoded 6-voice list otherwise) can render the
    full voice list. Pass `?legacy=true` for the pre-0.3.x plain-string shape.
    """
    try:
        tts_service = await get_tts_service()
        voices = await tts_service.list_voices()
        if legacy:
            return {"voices": voices}
        return {"voices": [{"id": v, "name": v} for v in voices]}
    except Exception as e:
        logger.error(f"Error listing voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to retrieve voice list",
                "type": "server_error",
            },
        )


@router.post("/audio/voices/combine")
async def combine_voices(request: Union[str, List[str]]):
    """Combine multiple voices into a new voice and return the .pt file.

    Args:
        request: Either a string with voices separated by + (e.g. "voice1+voice2")
                or a list of voice names to combine

    Returns:
        FileResponse with the combined voice .pt file

    Raises:
        HTTPException:
            - 400: Invalid request (wrong number of voices, voice not found)
            - 500: Server error (file system issues, combination failed)
    """
    # Check if local voice saving is allowed
    if not settings.allow_local_voice_saving:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "permission_denied",
                "message": "Local voice saving is disabled",
                "type": "permission_error",
            },
        )

    try:
        # Convert input to list of voices
        if isinstance(request, str):
            # Check if it's an OpenAI voice name
            mapped_voice = _openai_mappings["voices"].get(request)
            if mapped_voice:
                request = mapped_voice
            voices = [v.strip() for v in request.split("+") if v.strip()]
        else:
            # For list input, map each voice if it's an OpenAI voice name
            voices = [_openai_mappings["voices"].get(v, v) for v in request]
            voices = [v.strip() for v in voices if v.strip()]

        if not voices:
            raise ValueError("No voices provided")

        # Validate base voices exist; a "voice(weight)" suffix is allowed and
        # honored by the combination parser below.
        tts_service = await get_tts_service()
        available_voices = await tts_service.list_voices()
        for voice in voices:
            base_name = voice.split("(")[0].strip()
            if base_name not in available_voices:
                raise ValueError(
                    f"Base voice '{base_name}' not found. Available voices: {', '.join(sorted(available_voices))}"
                )

        # Build the combined tensor with the same parser /v1/audio/speech
        # uses, so weighted syntax like "af_bella(2)+af_sky(1)" works here too.
        combined_name = "+".join(voices)
        _, combined_source_path = await tts_service.resolve_voice_path(combined_name)

        # Serve a copy from the managed temp dir so the standard temp-file
        # reaper cleans it up instead of it accumulating in /tmp forever.
        os.makedirs(settings.temp_file_dir, exist_ok=True)
        served_path = os.path.join(settings.temp_file_dir, f"{combined_name}.pt")
        async with aiofiles.open(combined_source_path, "rb") as src:
            voice_bytes = await src.read()
        async with aiofiles.open(served_path, "wb") as dst:
            await dst.write(voice_bytes)

        return FileResponse(
            served_path,
            media_type="application/octet-stream",
            filename=f"{combined_name}.pt",
            headers={
                "Content-Disposition": f"attachment; filename={combined_name}.pt",
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        raise map_speech_exception(e)
