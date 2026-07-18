---
title: OpenAI-compatible API
description: The /v1 endpoints — speech synthesis, voices, models, and downloads.
order: 10
status: stable
---

# OpenAI-compatible API

Everything under `/v1` follows OpenAI conventions. When `API_KEY` is set, these routes
require `Authorization: Bearer <key>`. The full interactive schema is at `/docs`.

## POST /v1/audio/speech

Synthesize speech from text.

### Request body

| Field | Type | Default | Notes |
|---|---|---|---|
| `model` | string | `kokoro` | One of `tts-1`, `tts-1-hd`, `kokoro`, `gpt-4o-mini-tts`. Unknown → `400`. |
| `input` | string | *(required)* | Text to synthesize. |
| `voice` | string | `af_heart` | A voice name or a weighted combination (see [Voices](../concepts/voices-and-languages.md)). |
| `response_format` | string | `mp3` | `mp3`, `opus`, `flac`, `wav`, `pcm`. (`aac` is accepted by the schema but not currently supported.) |
| `download_format` | string | `null` | Optional alternate format for a download link. |
| `speed` | number | `1.0` | Range `0.25`–`4.0`. |
| `stream` | boolean | `true` | Stream chunks as encoded, or return one complete body. |
| `return_download_link` | boolean | `false` | Also write a file and return its path in `X-Download-Path`. |
| `lang_code` | string | `null` | Override the pipeline language; otherwise derived from the voice name. |
| `volume_multiplier` | number | `1.0` | Output volume multiplier. |
| `normalization_options` | object | *(defaults)* | Text-normalization toggles; set `{"normalize": false}` to disable. |

### Example

```bash
curl -X POST http://localhost:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","input":"Hello world!","voice":"af_heart","response_format":"mp3"}' \
  -o hello.mp3
```

Streaming responses use chunked transfer encoding with `X-Accel-Buffering: no`. See
[Streaming and audio formats](../concepts/streaming-and-audio-formats.md).

### Errors

| Status | When |
|---|---|
| `400` | Unknown model, unknown/malformed voice, or invalid input. |
| `401` | Missing/invalid bearer token (when `API_KEY` is set). |
| `503` | Model warming (`model_warming`, `Retry-After: 10`) or failed (`model_failed`). |
| `500` | Unexpected processing error. |

## GET /v1/audio/voices

List available voices.

```bash
curl http://localhost:8880/v1/audio/voices
# {"voices":[{"id":"af_heart","name":"af_heart"}, ...]}
```

Pass `?legacy=true` to get a flat array of voice-name strings instead.

## POST /v1/audio/voices/combine

Persist a weighted voice combination as a reusable `.pt` voicepack. **Disabled by
default** — returns `403` unless `ALLOW_LOCAL_VOICE_SAVING=true`.

```bash
curl -X POST http://localhost:8880/v1/audio/voices/combine \
  -H 'Content-Type: application/json' \
  -d '"af_bella(2)+af_sky(1)"' -o combined.pt
```

## GET /v1/models and /v1/models/{model}

List the model catalog, or fetch one entry. Unknown model IDs return `404`.

```bash
curl http://localhost:8880/v1/models
# {"object":"list","data":[{"id":"kokoro","object":"model","owned_by":"kokoro"}, ...]}
```

## GET /v1/download/{filename}

Download a file previously produced with `return_download_link` (served from the temp
directory; path-traversal-guarded). Missing files return `404`.

## OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8880/v1", api_key="not-needed")

with client.audio.speech.with_streaming_response.create(
    model="kokoro", voice="af_bella", input="Hello world!",
) as response:
    response.stream_to_file("output.mp3")
```

When authentication is enabled, pass the real key as `api_key`.

## See also

- [Extended API](./extended-api.md) — captions, phonemes, inline controls, operations.
- [Voices and languages](../concepts/voices-and-languages.md)
