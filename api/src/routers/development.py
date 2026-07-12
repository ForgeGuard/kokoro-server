import asyncio
import base64
from typing import Dict

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from kokoro import KPipeline
from loguru import logger

from ..core.audio_formats import content_type_for
from ..core.config import settings
from ..core.model_status import require_model_ready
from ..inference.base import AudioChunk
from ..services.audio import AudioNormalizer, AudioService
from ..services.streaming_audio_writer import StreamingAudioWriter
from ..services.temp_manager import TempFileWriter
from ..services.tts_service import TTSService
from ..structures import CaptionedSpeechRequest, CaptionedSpeechResponse
from ..structures.custom_responses import JSONStreamingResponse
from ..structures.text_schemas import (
    GenerateFromPhonemesRequest,
    PhonemeRequest,
    PhonemeResponse,
)
from .common import map_speech_exception
from .openai_compatible import (
    get_tts_service,
    process_and_validate_voices,
    stream_audio_chunks,
)

router = APIRouter(tags=["text processing"])

# Quiet (model-less) G2P pipelines are expensive to construct — cache per
# language instead of rebuilding one on every /dev/phonemize call.
_phoneme_pipelines: Dict[str, KPipeline] = {}


def _get_quiet_pipeline(lang_code: str) -> KPipeline:
    if lang_code not in _phoneme_pipelines:
        _phoneme_pipelines[lang_code] = KPipeline(lang_code=lang_code, model=False)
    return _phoneme_pipelines[lang_code]


@router.post("/dev/phonemize", response_model=PhonemeResponse)
async def phonemize_text(request: PhonemeRequest) -> PhonemeResponse:
    """Convert text to phonemes using Kokoro's quiet mode.

    Args:
        request: Request containing text and language

    Returns:
        Phonemes and token IDs
    """
    try:
        if not request.text:
            raise ValueError("Text cannot be empty")

        def _phonemize():
            # G2P is blocking (espeak/lexicon work) — keep it off the loop.
            pipeline = _get_quiet_pipeline(request.language)
            for result in pipeline(request.text):
                # result.phonemes = phonemized text
                return result.phonemes
            return None

        phonemes = await asyncio.to_thread(_phonemize)
        if phonemes is None:
            raise ValueError("Failed to generate phonemes")
        return PhonemeResponse(phonemes=phonemes, tokens=[])
    except Exception as e:
        raise map_speech_exception(e)


@router.post("/dev/generate_from_phonemes", dependencies=[Depends(require_model_ready)])
async def generate_from_phonemes(
    request: GenerateFromPhonemesRequest,
    client_request: Request,
    tts_service: TTSService = Depends(get_tts_service),
) -> StreamingResponse:
    """Generate audio directly from phonemes using Kokoro's phoneme format"""
    writer = None
    try:
        # Basic validation
        if not isinstance(request.phonemes, str):
            raise ValueError("Phonemes must be a string")
        if not request.phonemes:
            raise ValueError("Phonemes cannot be empty")

        # Create streaming audio writer and normalizer
        writer = StreamingAudioWriter(
            format="wav", sample_rate=settings.sample_rate, channels=1
        )
        normalizer = AudioNormalizer()

        async def generate_chunks():
            try:
                # Generate audio from phonemes
                chunk_audio, _ = await tts_service.generate_from_phonemes(
                    phonemes=request.phonemes,  # Pass complete phoneme string
                    voice=request.voice,
                    speed=1.0,
                )

                if chunk_audio is not None:
                    # Normalize audio before writing
                    normalized_audio = normalizer.normalize(chunk_audio)
                    # Write chunk and yield bytes
                    chunk_bytes = writer.write_chunk(normalized_audio)
                    if chunk_bytes:
                        yield chunk_bytes

                    # Finalize and yield remaining bytes
                    final_bytes = writer.write_chunk(finalize=True)
                    if final_bytes:
                        yield final_bytes
                else:
                    raise ValueError("Failed to generate audio data")

            except Exception as e:
                logger.error(f"Error in audio generation: {str(e)}")
                raise
            finally:
                # Runs on completion, error, AND client disconnect — an
                # except-only close leaked the PyAV encoder on aborts.
                writer.close()

        return StreamingResponse(
            generate_chunks(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav",
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Transfer-Encoding": "chunked",
            },
        )

    except Exception as e:
        raise map_speech_exception(e, writer)


@router.post("/dev/captioned_speech", dependencies=[Depends(require_model_ready)])
async def create_captioned_speech(
    request: CaptionedSpeechRequest,
    client_request: Request,
    x_raw_response: str = Header(None, alias="x-raw-response"),
    tts_service: TTSService = Depends(get_tts_service),
):
    """Generate audio with word-level timestamps using streaming approach"""

    writer = None
    try:
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

                temp_writer = TempFileWriter(request.response_format)
                await temp_writer.__aenter__()  # Initialize temp file

                # Get download path immediately after temp file creation
                download_path = temp_writer.download_path

                # Create response headers with download path
                headers = {
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                    "X-Download-Path": download_path,
                }

                # Create async generator for streaming
                async def dual_output():
                    try:
                        # The timestamp acumulator is only used when word level
                        # time stamps are generated but no audio is returned.
                        # It must live OUTSIDE the loop: resetting it per
                        # iteration silently dropped the timestamps carried by
                        # chunks whose encoder output was empty.
                        timestamp_acumulator = []

                        # Write chunks to temp file and stream
                        async for chunk_data in generator:
                            if chunk_data.output:  # Skip empty chunks
                                await temp_writer.write(chunk_data.output)
                                base64_chunk = base64.b64encode(
                                    chunk_data.output
                                ).decode("utf-8")

                                # Add any chunks that may be in the acumulator into the return word_timestamps
                                if chunk_data.word_timestamps is not None:
                                    chunk_data.word_timestamps = (
                                        timestamp_acumulator
                                        + chunk_data.word_timestamps
                                    )
                                    timestamp_acumulator = []
                                else:
                                    chunk_data.word_timestamps = []

                                yield CaptionedSpeechResponse(
                                    audio=base64_chunk,
                                    audio_format=content_type,
                                    timestamps=chunk_data.word_timestamps,
                                )
                            else:
                                if (
                                    chunk_data.word_timestamps is not None
                                    and len(chunk_data.word_timestamps) > 0
                                ):
                                    timestamp_acumulator += chunk_data.word_timestamps

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

                # Stream with temp file writing
                return JSONStreamingResponse(
                    dual_output(), media_type="application/json", headers=headers
                )

            async def single_output():
                try:
                    # The timestamp acumulator is only used when word level time stamps are generated but no audio is returned.
                    timestamp_acumulator = []

                    # Stream chunks
                    async for chunk_data in generator:
                        if chunk_data.output:  # Skip empty chunks
                            # Encode the chunk bytes into base 64
                            base64_chunk = base64.b64encode(chunk_data.output).decode(
                                "utf-8"
                            )

                            # Add any chunks that may be in the acumulator into the return word_timestamps
                            if chunk_data.word_timestamps is not None:
                                chunk_data.word_timestamps = (
                                    timestamp_acumulator + chunk_data.word_timestamps
                                )
                            else:
                                chunk_data.word_timestamps = []
                            timestamp_acumulator = []

                            yield CaptionedSpeechResponse(
                                audio=base64_chunk,
                                audio_format=content_type,
                                timestamps=chunk_data.word_timestamps,
                            )
                        else:
                            if (
                                chunk_data.word_timestamps is not None
                                and len(chunk_data.word_timestamps) > 0
                            ):
                                timestamp_acumulator += chunk_data.word_timestamps

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
            return JSONStreamingResponse(
                single_output(),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            # Generate complete audio using public interface
            audio_data = await tts_service.generate_audio(
                text=request.input,
                voice=voice_name,
                writer=writer,
                speed=request.speed,
                return_timestamps=request.return_timestamps,
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

            base64_output = base64.b64encode(output).decode("utf-8")

            content = CaptionedSpeechResponse(
                audio=base64_output,
                audio_format=content_type,
                timestamps=audio_data.word_timestamps,
            ).model_dump()

            writer.close()

            return JSONResponse(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                    "Cache-Control": "no-cache",  # Prevent caching
                },
            )

    except Exception as e:
        raise map_speech_exception(e, writer)


@router.post("/dev/unload")
async def unload_model(
    tts_service: TTSService = Depends(get_tts_service),
):
    """Release the model from GPU VRAM without stopping the container.

    The model reloads automatically on the next inference request.
    Useful for homelab deployments where GPU memory is shared across services.
    """
    try:
        if tts_service.model_manager is None:
            raise HTTPException(status_code=503, detail={"error": "Model manager not initialized"})
        await tts_service.model_manager.unload()
        return JSONResponse({"status": "unloaded"})
    except Exception as e:
        logger.error(f"Error unloading model: {e}")
        raise map_speech_exception(e)
