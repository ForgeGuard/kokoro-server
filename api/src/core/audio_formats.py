"""Single source of truth for audio format response metadata.

Three hand-maintained format→MIME maps had already drifted apart (aac vs m4a
coverage); every consumer derives from this table instead.
"""

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "m4a": "audio/mp4",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


def content_type_for(audio_format: str) -> str:
    """Content-Type for an audio format/extension (sans leading dot)."""
    return CONTENT_TYPES.get(audio_format.lower(), f"audio/{audio_format.lower()}")
