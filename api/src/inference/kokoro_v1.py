"""Clean Kokoro implementation with controlled resource management."""

import asyncio
import os
from typing import AsyncGenerator, Dict, Optional, Tuple, Union

import numpy as np
import torch
from kokoro import KModel, KPipeline
from loguru import logger

from ..core import paths
from ..core.config import settings
from ..core.model_config import model_config
from ..structures.schemas import WordTimestamp
from .base import AudioChunk, BaseModelBackend


class KokoroV1(BaseModelBackend):
    """Kokoro backend with controlled resource management."""

    def __init__(self):
        """Initialize backend with environment-based configuration."""
        super().__init__()
        # Strictly respect settings.use_gpu
        self._device = settings.get_device()
        self._model: Optional[KModel] = None
        self._pipelines: Dict[str, KPipeline] = {}  # Store pipelines by lang_code
        self._voice_cache: Dict[str, torch.Tensor] = {}  # Cache voice tensors by path

    async def _get_voice_tensor(self, voice_path: str) -> torch.Tensor:
        """Load voice tensor with in-memory caching to avoid repeated file I/O.

        Args:
            voice_path: Path to the .pt voice file

        Returns:
            Voice tensor on CPU (KPipeline moves it to the model device itself)
        """
        # Key by mtime as well as path so a replaced voice file is picked up
        # instead of serving a stale cached tensor forever.
        try:
            mtime = os.stat(voice_path).st_mtime_ns
        except OSError:
            mtime = -1
        cache_key = f"{voice_path}:{mtime}"
        if cache_key not in self._voice_cache:
            self._voice_cache[cache_key] = await paths.load_voice_tensor(
                voice_path, device="cpu"
            )
            logger.debug(f"Cached voice tensor from {voice_path}")
        return self._voice_cache[cache_key]

    async def _resolve_voice(
        self, voice: Union[str, Tuple[str, Union[torch.Tensor, str]]]
    ) -> Tuple[str, torch.Tensor]:
        """Resolve a voice path or (name, tensor/path) tuple to (name, tensor).

        The tensor is returned on CPU as float32: KPipeline.load_voice only
        recognizes CPU float tensors (isinstance torch.FloatTensor) and moves
        the pack to the model device per call.
        """
        if isinstance(voice, tuple):
            voice_name, voice_data = voice
            if isinstance(voice_data, str):
                voice_tensor = await self._get_voice_tensor(voice_data)
            else:
                voice_tensor = voice_data.detach().cpu().float()
        else:
            voice_name = os.path.splitext(os.path.basename(voice))[0]
            voice_tensor = await self._get_voice_tensor(voice)
        return voice_name, voice_tensor

    def _resolve_lang_code(self, lang_code: Optional[str], voice_name: str) -> str:
        """Priority: explicit request > settings override > voice-name prefix."""
        return lang_code or settings.default_voice_code or voice_name[0].lower()

    @staticmethod
    async def _iter_in_thread(sync_iterable):
        """Drive a blocking generator on a worker thread.

        Model inference (and espeak G2P inside KPipeline) is synchronous;
        iterating it inline would freeze the event loop for the full forward
        pass of every chunk, stalling health probes and concurrent requests.
        """
        iterator = iter(sync_iterable)
        sentinel = object()
        while True:
            result = await asyncio.to_thread(next, iterator, sentinel)
            if result is sentinel:
                return
            yield result

    async def load_model(self, path: str) -> None:
        """Load pre-baked model.

        Args:
            path: Path to model file

        Raises:
            RuntimeError: If model loading fails
        """
        try:
            # Get verified model path
            model_path = await paths.get_model_path(path)
            config_path = os.path.join(os.path.dirname(model_path), "config.json")

            if not os.path.exists(config_path):
                raise RuntimeError(f"Config file not found: {config_path}")

            logger.info(f"Loading Kokoro model on {self._device}")
            logger.info(f"Config path: {config_path}")
            logger.info(f"Model path: {model_path}")

            # Load model and let KModel handle device mapping
            self._model = KModel(config=config_path, model=model_path).eval()
            # For MPS, manually move ISTFT layers to CPU while keeping rest on MPS
            if self._device == "mps":
                logger.info(
                    "Moving model to MPS device with CPU fallback for unsupported operations"
                )
                self._model = self._model.to(torch.device("mps"))
            elif self._device == "cuda":
                self._model = self._model.cuda()
            else:
                self._model = self._model.cpu()

        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load Kokoro model: {e}")

    def _get_pipeline(self, lang_code: str) -> KPipeline:
        """Get or create pipeline for language code.

        Args:
            lang_code: Language code to use

        Returns:
            KPipeline instance for the language
        """
        if not self._model:
            raise RuntimeError("Model not loaded")

        if lang_code not in self._pipelines:
            logger.info(f"Creating new pipeline for language code: {lang_code}")
            self._pipelines[lang_code] = KPipeline(
                lang_code=lang_code, model=self._model, device=self._device
            )
        return self._pipelines[lang_code]

    async def generate_from_tokens(
        self,
        tokens: str,
        voice: Union[str, Tuple[str, Union[torch.Tensor, str]]],
        speed: float = 1.0,
        lang_code: Optional[str] = None,
    ) -> AsyncGenerator[np.ndarray, None]:
        """Generate audio from phoneme tokens.

        Args:
            tokens: Input phoneme tokens to synthesize
            voice: Either a voice path string or a tuple of (voice_name, voice_tensor/path)
            speed: Speed multiplier
            lang_code: Optional language code override

        Yields:
            Generated audio chunks

        Raises:
            RuntimeError: If generation fails
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        chunks_yielded = False
        try:
            # Memory management for GPU
            if self._device == "cuda":
                if self._check_memory():
                    self._clear_memory()

            voice_name, voice_tensor = await self._resolve_voice(voice)
            pipeline_lang_code = self._resolve_lang_code(lang_code, voice_name)
            pipeline = self._get_pipeline(pipeline_lang_code)

            logger.debug(
                f"Generating audio from tokens with lang_code '{pipeline_lang_code}': '{tokens[:100]}{'...' if len(tokens) > 100 else ''}'"
            )
            async for result in self._iter_in_thread(
                pipeline.generate_from_tokens(
                    tokens=tokens, voice=voice_tensor, speed=speed, model=self._model
                )
            ):
                if result.audio is not None:
                    logger.debug(f"Got audio chunk with shape: {result.audio.shape}")
                    chunks_yielded = True
                    yield result.audio.numpy()
                else:
                    logger.warning("No audio in chunk")

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            if (
                self._device == "cuda"
                and model_config.pytorch_gpu.retry_on_oom
                and "out of memory" in str(e).lower()
                and not chunks_yielded
            ):
                # Retrying after chunks were already emitted would duplicate
                # audio in the output stream, so only retry a clean failure.
                self._clear_memory()
                async for chunk in self.generate_from_tokens(
                    tokens, voice, speed, lang_code
                ):
                    yield chunk
                # Retry succeeded — do not fall through to re-raise, which
                # would fail the request after the audio was fully streamed.
                return
            raise

    async def generate(
        self,
        text: str,
        voice: Union[str, Tuple[str, Union[torch.Tensor, str]]],
        speed: float = 1.0,
        lang_code: Optional[str] = None,
        return_timestamps: Optional[bool] = False,
    ) -> AsyncGenerator[AudioChunk, None]:
        """Generate audio using model.

        Args:
            text: Input text to synthesize
            voice: Either a voice path string or a tuple of (voice_name, voice_tensor/path)
            speed: Speed multiplier
            lang_code: Optional language code override

        Yields:
            Generated audio chunks

        Raises:
            RuntimeError: If generation fails
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        chunks_yielded = False
        try:
            # Memory management for GPU
            if self._device == "cuda":
                if self._check_memory():
                    self._clear_memory()

            voice_name, voice_tensor = await self._resolve_voice(voice)
            pipeline_lang_code = self._resolve_lang_code(lang_code, voice_name)
            pipeline = self._get_pipeline(pipeline_lang_code)

            logger.debug(
                f"Generating audio for text with lang_code '{pipeline_lang_code}': '{text[:100]}{'...' if len(text) > 100 else ''}'"
            )
            async for result in self._iter_in_thread(
                pipeline(text, voice=voice_tensor, speed=speed, model=self._model)
            ):
                if result.audio is not None:
                    logger.debug(f"Got audio chunk with shape: {result.audio.shape}")
                    word_timestamps = None
                    if (
                        return_timestamps
                        and hasattr(result, "tokens")
                        and result.tokens
                    ):
                        word_timestamps = []
                        current_offset = 0.0
                        logger.debug(
                            f"Processing chunk timestamps with {len(result.tokens)} tokens"
                        )
                        if result.pred_dur is not None:
                            try:
                                # Add timestamps with offset
                                for token in result.tokens:
                                    if not all(
                                        hasattr(token, attr)
                                        for attr in [
                                            "text",
                                            "start_ts",
                                            "end_ts",
                                        ]
                                    ):
                                        continue
                                    if not token.text or not token.text.strip():
                                        continue

                                    start_time = float(token.start_ts) + current_offset
                                    end_time = float(token.end_ts) + current_offset
                                    word_timestamps.append(
                                        WordTimestamp(
                                            word=str(token.text).strip(),
                                            start_time=start_time,
                                            end_time=end_time,
                                        )
                                    )
                                    logger.debug(
                                        f"Added timestamp for word '{token.text}': {start_time:.3f}s - {end_time:.3f}s"
                                    )

                            except Exception as e:
                                logger.error(
                                    f"Failed to process timestamps for chunk: {e}"
                                )

                    chunks_yielded = True
                    yield AudioChunk(
                        result.audio.numpy(), word_timestamps=word_timestamps
                    )
                else:
                    logger.warning("No audio in chunk")

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            if (
                self._device == "cuda"
                and model_config.pytorch_gpu.retry_on_oom
                and "out of memory" in str(e).lower()
                and not chunks_yielded
            ):
                # Retrying after chunks were already emitted would duplicate
                # audio in the output stream, so only retry a clean failure.
                self._clear_memory()
                async for chunk in self.generate(
                    text, voice, speed, lang_code, return_timestamps
                ):
                    yield chunk
                # Retry succeeded — do not fall through to re-raise, which would
                # emit a duplicate audio stream followed by a spurious 500.
                return
            raise

    def _check_memory(self) -> bool:
        """Check if memory usage is above threshold."""
        if self._device == "cuda":
            memory_gb = torch.cuda.memory_allocated() / 1e9
            return memory_gb > model_config.pytorch_gpu.memory_threshold
        # MPS doesn't provide memory management APIs
        return False

    def _clear_memory(self) -> None:
        """Clear device memory."""
        if self._device == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        elif self._device == "mps":
            # Empty cache if available (future-proofing)
            if hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()

    def unload(self) -> None:
        """Unload model and free resources."""
        if self._model is not None:
            del self._model
            self._model = None
        for pipeline in self._pipelines.values():
            del pipeline
        self._pipelines.clear()
        self._voice_cache.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    @property
    def device(self) -> str:
        """Get device model is running on."""
        return self._device
