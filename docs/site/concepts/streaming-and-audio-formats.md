---
title: Streaming and audio formats
description: Supported output formats, streaming versus complete responses, and long-form chunking.
order: 20
status: stable
---

# Streaming and audio formats

The server encodes synthesized audio on the fly and can either stream it as it is
produced or return a complete response.

## Supported formats

| Format | `response_format` | Notes |
|---|---|---|
| MP3 | `mp3` | Default. VBR Xing header disabled for correct playback timelines. |
| WAV | `wav` | 16-bit PCM in a RIFF container. |
| Opus | `opus` | Ogg/Opus, 128 kbps. |
| FLAC | `flac` | Lossless. |
| PCM | `pcm` | Raw signed 16-bit little-endian, 24 kHz, mono — no header. |

All output is 24 kHz mono. `aac` is accepted by the request schema but is **not
currently supported** for synthesis; use one of the formats above.

> See [Troubleshooting: audio formats](../troubleshooting/audio-formats.md) for the
> WAV duration/header behavior and how to read exact durations.

## Streaming versus complete responses

`POST /v1/audio/speech` streams by default (`stream: true`). Streaming returns audio
chunks as they are encoded, which lowers time-to-first-byte and memory use; the
response uses chunked transfer encoding with `X-Accel-Buffering: no` so proxies do not
buffer it. Set `stream: false` to receive a single complete response body instead.

Raw PCM is the simplest format to play incrementally, since it has no container or
headers:

```python
from openai import OpenAI
import pyaudio  # requires PyAudio

client = OpenAI(base_url="http://localhost:8880/v1", api_key="not-needed")
player = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)

with client.audio.speech.with_streaming_response.create(
    model="kokoro", voice="af_bella", response_format="pcm", input="Hello world!",
) as response:
    for chunk in response.iter_bytes(chunk_size=1024):
        player.write(chunk)
```

## Long-form input

Input is automatically split and stitched at sentence boundaries. The base model is
tuned for roughly 30-second outputs, so the server re-chunks longer text using the
token bounds `TARGET_MIN_TOKENS`, `TARGET_MAX_TOKENS`, and `ABSOLUTE_MAX_TOKENS`
(defaults 175 / 250 / 450). You normally do not need to change these; see
[Environment variables](../configuration/environment-variables.md).

## See also

- [OpenAI-compatible API](../reference/openai-api.md)
- [Voices and languages](./voices-and-languages.md)
