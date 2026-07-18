---
title: Voices and languages
description: Designed voices, language codes, OpenAI voice aliases, and weighted voice mixing.
order: 10
status: stable
---

# Voices and languages

Kokoro ships a fixed set of *designed* voices — it does not clone a specific real
person from a sample. Voices are selected by name, and several map to OpenAI voice
aliases for drop-in compatibility.

## Voice naming

Each voice name encodes its language and gender through a two-letter prefix, for
example `af_heart` (American English, female) or `bm_george` (British English, male).

| Prefix | Language | Gender |
|---|---|---|
| `af_` / `am_` | American English | female / male |
| `bf_` / `bm_` | British English | female / male |
| `ef_` / `em_` | Spanish | female / male |
| `ff_` / `fm_` | French | female / male |
| `hf_` / `hm_` | Hindi | female / male |
| `if_` / `im_` | Italian | female / male |
| `jf_` / `jm_` | Japanese | female / male |
| `pf_` / `pm_` | Brazilian Portuguese | female / male |
| `zf_` / `zm_` | Mandarin Chinese | female / male |

The default voice is `af_heart` (configurable with `DEFAULT_VOICE`). List the voices
available in your image at runtime:

```bash
curl http://localhost:8880/v1/audio/voices
# {"voices":[{"id":"af_heart","name":"af_heart"}, ...]}
```

## OpenAI voice aliases

Requests may use the standard OpenAI voice names, which are mapped to designed voices:

| OpenAI name | Maps to |
|---|---|
| `alloy` | `am_adam` |
| `ash` | `af_nicole` |
| `coral` | `bf_emma` |
| `echo` | `af_bella` |
| `fable` | `af_sarah` |
| `onyx` | `bm_george` |
| `nova` | `bf_isabella` |
| `sage` | `am_michael` |
| `shimmer` | `af_sky` |

## Language codes

The pipeline language is resolved in this order: an explicit `lang_code` on the
request, then `DEFAULT_VOICE_CODE` if set, then the **first letter of the voice name**.
So `af_heart` implies language `a` (American English) unless you override it.

Common codes: `a` (American English), `b` (British English), `z` (Mandarin Chinese).
Other designed-voice languages are driven by their voice prefix. Use
[`/dev/phonemize`](../reference/extended-api.md#post-devphonemize) to inspect how text
is converted for a given language.

## Weighted voice mixing

The `voice` field accepts a single voice or a combination. Combine with `+`,
subtract with `-`, and weight individual voices with `name(weight)`:

```python
import requests

# Equal 50/50 mix
requests.post("http://localhost:8880/v1/audio/speech", json={
    "input": "Hello world!", "voice": "af_bella+af_sky", "response_format": "mp3",
})

# Weighted 2:1 mix (about 67% / 33%) — weights normalize automatically
requests.post("http://localhost:8880/v1/audio/speech", json={
    "input": "Hello world!", "voice": "af_bella(2)+af_sky(1)", "response_format": "mp3",
})
```

Weights are normalized to sum to 1 by default (`VOICE_WEIGHT_NORMALIZATION=true`). With
normalization disabled, the raw weights are applied as-is. Unknown voices, empty
operands (a leading/trailing `+`/`-`), or malformed weights return `400`.

### Persisting a combination

When `ALLOW_LOCAL_VOICE_SAVING=true`, you can save a combination as a reusable
voicepack (returns a `.pt` file). This is **disabled by default** and returns `403`
when off:

```python
requests.post("http://localhost:8880/v1/audio/voices/combine",
              json="af_bella(2)+af_sky(1)")
```

## See also

- [Streaming and audio formats](./streaming-and-audio-formats.md)
- [OpenAI-compatible API](../reference/openai-api.md)
