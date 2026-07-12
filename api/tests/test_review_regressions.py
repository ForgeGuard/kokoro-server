"""Regression tests for the code-review fixes."""

import time

import numpy as np
import pytest

from api.src.inference.base import AudioChunk
from api.src.services.audio import AudioNormalizer, AudioService
from api.src.services.streaming_audio_writer import StreamingAudioWriter


def test_combine_empty_list_raises_valueerror():
    """Whitespace/punctuation-only input yields zero chunks; combine must give
    a clear ValueError instead of an IndexError from list[0]."""
    with pytest.raises(ValueError):
        AudioChunk.combine([])


def test_audiochunk_default_timestamps_not_shared():
    """The default word_timestamps list must be per-instance, not a shared
    mutable default that combine()'s += would corrupt."""
    a = AudioChunk(np.zeros(1, dtype=np.int16))
    b = AudioChunk(np.zeros(1, dtype=np.int16))
    a.word_timestamps.append("x")
    assert b.word_timestamps == []


@pytest.mark.asyncio
async def test_convert_audio_empty_nonlast_chunk_no_unbound_error():
    """An empty, non-last chunk (e.g. a sub-sample pause) must not raise
    UnboundLocalError on chunk_data."""
    writer = StreamingAudioWriter("mp3", sample_rate=24000)
    try:
        result = await AudioService.convert_audio(
            AudioChunk(np.array([], dtype=np.int16)),
            "mp3",
            writer,
            is_last_chunk=False,
            normalizer=AudioNormalizer(),
        )
        assert result.output == b""
    finally:
        writer.close()


@pytest.mark.asyncio
async def test_temp_cleanup_keeps_newest_within_count(monkeypatch, tmp_path):
    """Exceeding max_temp_dir_count must delete only the oldest overflow, not
    every file (which used to wipe just-issued download links)."""
    from api.src.services import temp_manager
    from api.src.core.config import settings

    monkeypatch.setattr(settings, "temp_file_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_temp_dir_count", 3)
    monkeypatch.setattr(settings, "max_temp_dir_age_hours", 24)
    monkeypatch.setattr(settings, "max_temp_dir_size_mb", 1024)

    now = time.time()
    for i in range(5):
        f = tmp_path / f"speech_{i}.mp3"
        f.write_bytes(b"x" * 10)
        import os

        os.utime(f, (now - (5 - i) * 60, now - (5 - i) * 60))  # 0 oldest, 4 newest

    await temp_manager.cleanup_temp_files()

    remaining = sorted(p.name for p in tmp_path.iterdir())
    # The 2 oldest removed, the 3 newest (incl. the most recent) kept.
    assert remaining == ["speech_2.mp3", "speech_3.mp3", "speech_4.mp3"]


def test_download_path_uses_v1_prefix(monkeypatch, tmp_path):
    """X-Download-Path must point at the real /v1/download route."""
    import asyncio

    from api.src.services.temp_manager import TempFileWriter
    from api.src.core.config import settings

    monkeypatch.setattr(settings, "temp_file_dir", str(tmp_path))

    async def _run():
        writer = TempFileWriter("mp3")
        await writer.__aenter__()
        try:
            assert writer.download_path.startswith("/v1/download/")
        finally:
            await writer.__aexit__(None, None, None)

    asyncio.run(_run())
