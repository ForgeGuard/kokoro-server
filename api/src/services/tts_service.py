"""TTS service using model and voice managers."""

import asyncio
import os
import re
import tempfile
import time
from typing import AsyncGenerator, List, Optional, Tuple

import numpy as np
import torch
from loguru import logger

from ..core.config import settings
from ..inference.base import AudioChunk
from ..inference.model_manager import (
    ModelManager,
    get_manager as get_model_manager,
)
from ..inference.voice_manager import get_manager as get_voice_manager
from ..structures.schemas import NormalizationOptions
from .audio import AudioNormalizer, AudioService
from .streaming_audio_writer import StreamingAudioWriter
from .text_processing.text_processor import smart_split


class TTSService:
    """Text-to-speech service."""

    # Limit concurrent chunk processing
    _chunk_semaphore = asyncio.Semaphore(4)

    def __init__(self, output_dir: str = None):
        """Initialize service."""
        self.output_dir = output_dir
        self.model_manager: Optional[ModelManager] = None
        self._voice_manager = None

    @classmethod
    async def create(cls, output_dir: str = None) -> "TTSService":
        """Create and initialize TTSService instance."""
        service = cls(output_dir)
        service.model_manager = await get_model_manager()
        service._voice_manager = await get_voice_manager()
        return service

    async def _process_chunk(
        self,
        chunk_text: str,
        tokens: List[int],
        voice_name: str,
        voice_path: str,
        speed: float,
        writer: StreamingAudioWriter,
        output_format: Optional[str] = None,
        is_first: bool = False,
        is_last: bool = False,
        volume_multiplier: Optional[float] = None,
        normalizer: Optional[AudioNormalizer] = None,
        lang_code: Optional[str] = None,
        return_timestamps: Optional[bool] = False,
    ) -> AsyncGenerator[AudioChunk, None]:
        """Process tokens into audio.

        Errors propagate to the caller: swallowing them here produced HTTP 200
        responses containing silently truncated or empty audio.
        """
        # The request value wins; None falls back to the server-wide default.
        volume = (
            volume_multiplier
            if volume_multiplier is not None
            else settings.default_volume_multiplier
        )
        async with self._chunk_semaphore:
            # Handle stream finalization
            if is_last:
                # Skip format conversion for raw audio mode
                if not output_format:
                    yield AudioChunk(np.array([], dtype=np.int16), output=b"")
                    return
                chunk_data = await AudioService.convert_audio(
                    AudioChunk(
                        np.array([], dtype=np.float32)
                    ),  # Dummy data for type checking
                    output_format,
                    writer,
                    speed,
                    "",
                    normalizer=normalizer,
                    is_last_chunk=True,
                )
                yield chunk_data
                return

            # Skip empty chunks
            if not tokens and not chunk_text:
                return

            await self.model_manager.ensure_backend()

            async for chunk_data in self.model_manager.generate(
                chunk_text,
                (voice_name, voice_path),
                speed=speed,
                lang_code=lang_code,
                return_timestamps=return_timestamps,
            ):
                if volume != 1.0:
                    chunk_data.audio = chunk_data.audio * volume
                # For streaming, convert to bytes
                if output_format:
                    chunk_data = await AudioService.convert_audio(
                        chunk_data,
                        output_format,
                        writer,
                        speed,
                        chunk_text,
                        is_last_chunk=is_last,
                        normalizer=normalizer,
                    )
                    yield chunk_data
                else:
                    chunk_data = AudioService.trim_audio(
                        chunk_data, chunk_text, speed, is_last, normalizer
                    )
                    yield chunk_data

    # Combined-voice tensors are deterministic for a given voice string, so
    # rebuilding (N torch.loads + a torch.save) on every request is waste.
    _combined_voice_paths: dict = {}

    async def _load_voice_from_path(self, path: str, weight: float):
        # Check if the path is None and raise a ValueError if it is not
        if not path:
            raise ValueError(f"Voice not found at path: {path}")

        logger.debug(f"Loading voice tensor from path: {path}")
        tensor = await asyncio.to_thread(
            torch.load, path, map_location="cpu", weights_only=True
        )
        return tensor * weight

    async def _get_voices_path(self, voice: str) -> Tuple[str, str]:
        """Get voice path, handling combined voices.

        Args:
            voice: Voice name or combined voice names (e.g., 'af_jadzia+af_jessica')

        Returns:
            Tuple of (voice name to use, voice path to use)

        Raises:
            RuntimeError: If voice not found
        """
        try:
            # Split the voice on + and - and ensure that they get added to the list eg: hi+bob = ["hi","+","bob"]
            split_voice = re.split(r"([-+])", voice)

            # If it is only once voice there is no point in loading it up, doing nothing with it, then saving it
            if len(split_voice) == 1:
                # Since its a single voice the only time that the weight would matter is if voice_weight_normalization is off
                if (
                    "(" not in voice and ")" not in voice
                ) or settings.voice_weight_normalization == True:
                    # Strip a weight suffix like "af_bella(2)" — with
                    # normalization on it is a no-op, but the raw string is
                    # not a real voice file name.
                    base_name = voice.split("(")[0].strip()
                    path = await self._voice_manager.get_voice_path(base_name)
                    if not path:
                        raise RuntimeError(f"Voice not found: {base_name}")
                    logger.debug(f"Using single voice path: {path}")
                    return base_name, path

            # Reuse an already-built combination for this exact voice string.
            cached_path = self._combined_voice_paths.get(voice)
            if cached_path is not None and os.path.exists(cached_path):
                return voice, cached_path

            total_weight = 0

            for voice_index in range(0, len(split_voice), 2):
                voice_object = split_voice[voice_index]

                if "(" in voice_object and ")" in voice_object:
                    voice_name = voice_object.split("(")[0].strip()
                    voice_weight = float(voice_object.split("(")[1].split(")")[0])
                else:
                    voice_name = voice_object
                    voice_weight = 1

                total_weight += voice_weight
                split_voice[voice_index] = (voice_name, voice_weight)

            # If voice_weight_normalization is false prevent normalizing the weights by setting the total_weight to 1 so it divides each weight by 1
            if settings.voice_weight_normalization == False:
                total_weight = 1

            # Load the first voice as the starting point for voices to be combined onto
            path = await self._voice_manager.get_voice_path(split_voice[0][0])
            combined_tensor = await self._load_voice_from_path(
                path, split_voice[0][1] / total_weight
            )

            # Loop through each + or - in split_voice so they can be applied to combined voice
            for operation_index in range(1, len(split_voice) - 1, 2):
                # Get the voice path of the voice 1 index ahead of the operator
                path = await self._voice_manager.get_voice_path(
                    split_voice[operation_index + 1][0]
                )
                voice_tensor = await self._load_voice_from_path(
                    path, split_voice[operation_index + 1][1] / total_weight
                )

                # Either add or subtract the voice from the current combined voice
                if split_voice[operation_index] == "+":
                    combined_tensor += voice_tensor
                else:
                    combined_tensor -= voice_tensor

            # Save the new combined voice so it can be loaded latter
            temp_dir = tempfile.gettempdir()
            combined_path = os.path.join(temp_dir, f"{voice}.pt")
            logger.debug(f"Saving combined voice to: {combined_path}")
            await asyncio.to_thread(torch.save, combined_tensor, combined_path)
            self._combined_voice_paths[voice] = combined_path
            return voice, combined_path
        except Exception as e:
            logger.error(f"Failed to get voice path: {e}")
            raise

    async def generate_audio_stream(
        self,
        text: str,
        voice: str,
        writer: StreamingAudioWriter,
        speed: float = 1.0,
        output_format: str = "wav",
        lang_code: Optional[str] = None,
        volume_multiplier: Optional[float] = None,
        normalization_options: Optional[NormalizationOptions] = NormalizationOptions(),
        return_timestamps: Optional[bool] = False,
    ) -> AsyncGenerator[AudioChunk, None]:
        """Generate and stream audio chunks.

        Chunk-level failures propagate: a mid-stream error aborts the response
        instead of returning silently truncated audio with a 200 status.
        """
        stream_normalizer = AudioNormalizer()
        chunk_index = 0
        current_offset = 0.0
        try:
            await self.model_manager.ensure_backend()
            backend = self.model_manager.get_backend()

            # Get voice path, handling combined voices
            voice_name, voice_path = await self._get_voices_path(voice)
            logger.debug(f"Using voice path: {voice_path}")

            # Use provided lang_code or determine from voice name
            pipeline_lang_code = lang_code if lang_code else voice[:1].lower()
            logger.info(
                f"Using lang_code '{pipeline_lang_code}' for voice '{voice_name}' in audio stream"
            )

            # Process text in chunks with smart splitting, handling pause tags
            async for chunk_text, tokens, pause_duration_s in smart_split(
                text,
                lang_code=pipeline_lang_code,
                normalization_options=normalization_options,
            ):
                if pause_duration_s is not None and pause_duration_s > 0:
                    # --- Handle Pause Chunk ---
                    try:
                        logger.debug(f"Generating {pause_duration_s}s silence chunk")
                        silence_samples = int(
                            pause_duration_s * settings.sample_rate
                        )
                        # Create proper silence as int16 zeros to avoid normalization artifacts
                        silence_audio = np.zeros(silence_samples, dtype=np.int16)
                        pause_chunk = AudioChunk(
                            audio=silence_audio, word_timestamps=[]
                        )  # Empty timestamps for silence

                        # Format and yield the silence chunk
                        if output_format:
                            formatted_pause_chunk = await AudioService.convert_audio(
                                pause_chunk,
                                output_format,
                                writer,
                                speed=speed,
                                chunk_text="",
                                is_last_chunk=False,
                                trim_audio=False,
                                normalizer=stream_normalizer,
                            )
                            if formatted_pause_chunk.output:
                                yield formatted_pause_chunk
                        else:  # Raw audio mode
                            # For raw audio mode, silence is already in the correct format (int16)
                            # Skip normalization to avoid any potential artifacts
                            if len(pause_chunk.audio) > 0:
                                yield pause_chunk

                        # Update offset based on silence duration
                        current_offset += pause_duration_s
                        chunk_index += 1  # Count pause as a yielded chunk

                    except Exception as e:
                        logger.error(f"Failed to process pause chunk: {str(e)}")
                        raise

                elif (
                    tokens or chunk_text.strip()
                ):  # Process if there are tokens OR non-whitespace text
                    # --- Handle Text Chunk ---
                    try:
                        # Process audio for chunk
                        async for chunk_data in self._process_chunk(
                            chunk_text,  # Pass text for Kokoro V1
                            tokens,  # Pass tokens for legacy backends
                            voice_name,  # Pass voice name
                            voice_path,  # Pass voice path
                            speed,
                            writer,
                            output_format,
                            is_first=(chunk_index == 0),
                            volume_multiplier=volume_multiplier,
                            is_last=False,  # We'll update the last chunk later
                            normalizer=stream_normalizer,
                            lang_code=pipeline_lang_code,  # Pass lang_code
                            return_timestamps=return_timestamps,
                        ):
                            if chunk_data.word_timestamps is not None:
                                for timestamp in chunk_data.word_timestamps:
                                    timestamp.start_time += current_offset
                                    timestamp.end_time += current_offset

                            # Update offset based on the actual duration of the generated audio chunk
                            chunk_duration = 0
                            if (
                                chunk_data.audio is not None
                                and len(chunk_data.audio) > 0
                            ):
                                chunk_duration = (
                                    len(chunk_data.audio) / settings.sample_rate
                                )
                                current_offset += chunk_duration

                            # Yield the processed chunk (either formatted or raw)
                            if chunk_data.output is not None:
                                yield chunk_data
                            elif (
                                chunk_data.audio is not None
                                and len(chunk_data.audio) > 0
                            ):
                                yield chunk_data
                            else:
                                logger.warning(
                                    f"No audio generated for chunk: '{chunk_text[:100]}...'"
                                )

                        chunk_index += 1  # Increment chunk index after processing text
                    except Exception as e:
                        logger.error(
                            f"Failed to process audio for chunk: '{chunk_text[:100]}...'. Error: {str(e)}"
                        )
                        raise

            # Only finalize if we successfully processed at least one chunk
            if chunk_index > 0:
                try:
                    # Empty tokens list to finalize audio
                    async for chunk_data in self._process_chunk(
                        "",  # Empty text
                        [],  # Empty tokens
                        voice_name,
                        voice_path,
                        speed,
                        writer,
                        output_format,
                        is_first=False,
                        is_last=True,  # Signal this is the last chunk
                        volume_multiplier=volume_multiplier,
                        normalizer=stream_normalizer,
                        lang_code=pipeline_lang_code,  # Pass lang_code
                    ):
                        if chunk_data.output is not None:
                            yield chunk_data
                except Exception as e:
                    logger.error(f"Failed to finalize audio stream: {str(e)}")
                    raise

        except Exception as e:
            logger.error(f"Error in audio stream generation: {str(e)}")
            raise e

    async def generate_audio(
        self,
        text: str,
        voice: str,
        writer: StreamingAudioWriter,
        speed: float = 1.0,
        return_timestamps: bool = False,
        volume_multiplier: Optional[float] = None,
        normalization_options: Optional[NormalizationOptions] = NormalizationOptions(),
        lang_code: Optional[str] = None,
    ) -> AudioChunk:
        """Generate complete audio for text using streaming internally."""
        audio_data_chunks = []

        try:
            async for audio_stream_data in self.generate_audio_stream(
                text,
                voice,
                writer,
                speed=speed,
                volume_multiplier=volume_multiplier,
                normalization_options=normalization_options,
                return_timestamps=return_timestamps,
                lang_code=lang_code,
                output_format=None,
            ):
                if len(audio_stream_data.audio) > 0:
                    audio_data_chunks.append(audio_stream_data)

            combined_audio_data = AudioChunk.combine(audio_data_chunks)
            return combined_audio_data
        except Exception as e:
            logger.error(f"Error in audio generation: {str(e)}")
            raise

    async def resolve_voice_path(self, voice: str) -> Tuple[str, str]:
        """Resolve a (possibly combined/weighted) voice string to a .pt path."""
        return await self._get_voices_path(voice)

    async def combine_voices(self, voices: List[str]) -> torch.Tensor:
        """Combine multiple voices.

        Returns:
            Combined voice tensor
        """

        return await self._voice_manager.combine_voices(voices)

    async def list_voices(self) -> List[str]:
        """List available voices."""
        return await self._voice_manager.list_voices()

    async def generate_from_phonemes(
        self,
        phonemes: str,
        voice: str,
        speed: float = 1.0,
        lang_code: Optional[str] = None,
    ) -> Tuple[np.ndarray, float]:
        """Generate audio directly from phonemes.

        Args:
            phonemes: Phonemes in Kokoro format
            voice: Voice name
            speed: Speed multiplier
            lang_code: Optional language code override

        Returns:
            Tuple of (audio array, processing time)
        """
        start_time = time.time()
        try:
            await self.model_manager.ensure_backend()
            backend = self.model_manager.get_backend()
            voice_name, voice_path = await self._get_voices_path(voice)

            # Use provided lang_code or determine from voice name
            pipeline_lang_code = lang_code if lang_code else voice[:1].lower()
            logger.info(
                f"Using lang_code '{pipeline_lang_code}' for voice '{voice_name}' in phoneme pipeline"
            )

            # Register with the manager's inflight guard so /dev/unload waits
            # for this generation instead of freeing the model under it.
            async with self.model_manager.track_inflight():
                audio_parts = []
                try:
                    async for part in backend.generate_from_tokens(
                        tokens=phonemes,  # Pass raw phonemes string
                        voice=(voice_name, voice_path),
                        speed=speed,
                        lang_code=pipeline_lang_code,
                    ):
                        audio_parts.append(part)
                except Exception as e:
                    logger.error(f"Failed to generate from phonemes: {e}")
                    raise RuntimeError(f"Phoneme generation failed: {e}")

            if not audio_parts:
                raise ValueError("No audio generated")

            audio = (
                np.concatenate(audio_parts) if len(audio_parts) > 1 else audio_parts[0]
            )
            processing_time = time.time() - start_time
            return audio, processing_time

        except Exception as e:
            logger.error(f"Error in phoneme audio generation: {str(e)}")
            raise
