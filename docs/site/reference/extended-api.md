---
title: Extended API
description: Captioned speech, phonemes, inline control tokens, and operational endpoints under /dev and /debug.
order: 20
status: stable
---

# Extended API

Endpoints beyond the OpenAI surface live under `/dev` (text processing and model
control) and `/debug` (inspection). They are **not** under `/v1`. When `API_KEY` is set,
these routes require `Authorization: Bearer <key>`.

## POST /dev/captioned_speech

Same request body as [`/v1/audio/speech`](./openai-api.md#post-v1audiospeech), but returns
base64-encoded audio plus word-level timestamps.

```python
import base64, requests

r = requests.post("http://localhost:8880/dev/captioned_speech", json={
    "model": "kokoro", "input": "Hello world!", "voice": "af_bella",
    "response_format": "mp3", "stream": False,
})
payload = r.json()
open("output.mp3", "wb").write(base64.b64decode(payload["audio"]))
print(payload["timestamps"])
# [{"word": "Hello", "start_time": ..., "end_time": ...}, ...]
```

- With `"stream": false` you get a single JSON object.
- With `"stream": true` (the default) the response is newline-delimited JSON, one object
  per chunk, with timestamps accumulated across chunks.
- The response `audio_format` field carries the MIME content type (e.g. `audio/mpeg`).

## POST /dev/phonemize

Convert text to phonemes for a language code (`a` = American English by default).

```python
import requests

r = requests.post("http://localhost:8880/dev/phonemize",
                  json={"text": "Hello world!", "language": "a"})
phonemes = r.json()["phonemes"]
```

The response includes a `tokens` field, which is currently always an empty list.

## POST /dev/generate_from_phonemes

Synthesize audio directly from phonemes. Output is always **WAV**.

```python
import requests

audio = requests.post("http://localhost:8880/dev/generate_from_phonemes",
                      json={"phonemes": phonemes, "voice": "af_bella"}).content
open("speech.wav", "wb").write(audio)
```

## Inline control tokens

Two tokens can be embedded directly in the `input` text and are parsed server-side:

- **Pause** — `[pause:1.5s]` inserts that much silence. It must be exactly this form
  (colon, trailing `s`, case-insensitive). SSML `<break/>` is not recognized.
- **Pronunciation** — `[Worcester](/wˈʊstər/)` speaks the IPA between the slashes instead
  of the word. English only; use `/dev/phonemize` to find the IPA.

```text
The city of [Worcester](/wˈʊstər/) is easy. [pause:1s] See?
```

## POST /dev/unload

Release the model from VRAM without stopping the container; it reloads lazily on the next
request. Returns `{"status":"unloaded"}`. Note that `/health` continues to report
`model_loaded: true` (it means "warmed", not "resident").

## Debug endpoints

Authenticated `GET` inspection endpoints:

| Endpoint | Returns |
|---|---|
| `GET /debug/threads` | Thread info and per-thread details, plus process memory. |
| `GET /debug/storage` | Temp/output directory and filesystem usage. |
| `GET /debug/system` | CPU, memory, process, network, and GPU information. |

See [Observability](../operations/observability.md) for `/system` and logging.
