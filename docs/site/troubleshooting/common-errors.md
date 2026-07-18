---
title: Common errors
description: Fixes for missing words, GPU access, and missing model weights.
order: 10
status: stable
---

# Common errors

## Missing or rewritten words

Text normalization can occasionally drop or rewrite phrases (for example expanding
numbers, URLs, or units). Disable it per request:

```json
{
  "model": "kokoro",
  "input": "Ver. 2.0 ships at 3pm.",
  "voice": "af_heart",
  "normalization_options": { "normalize": false }
}
```

This also affects captioned-speech timestamps, since timestamps track the normalized
text. See [Extended API](../reference/extended-api.md#post-devcaptioned_speech).

## GPU not accessible

If the container starts but cannot use the GPU:

1. Confirm the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
   is installed and the runtime is configured.
2. Confirm you passed `--gpus all` (Docker) or reserved a GPU (Compose/Kubernetes).
3. On Linux, if the non-root container user cannot open the GPU devices, add it to the
   `video` and `render` groups:
   - `docker run`: `--group-add video --group-add render`
   - Compose: `group_add: ["video", "render"]`
4. As a fallback, run on CPU with `-e USE_GPU=false` to confirm the rest of the stack
   works. See [Hardware profiles](../deployment/hardware-profiles.md).

## Model weights not found (container exits)

If the container logs a `model weights not found` error and exits, a volume mount is
almost certainly shadowing the baked-in weights (for example a bind mount over
`/app/api`). The weights are baked into published images at build time.

Fix one of:

- Remove the bind mount over `/app/api` (the production and local Compose files do not
  mount source over it).
- Set `DOWNLOAD_MODEL=true` to download weights at container start (requires network
  access).

This preflight is deliberate: a failed model load exits the container non-zero so
orchestrators surface it. See
[Health and readiness](../operations/health-and-readiness.md#warmup-failure-exits-the-container).

## Requests return 503 while starting

A `503` with `Retry-After` right after startup means the model is still warming. Poll
`/ready` until it returns `200` before sending synthesis traffic. See
[Health and readiness](../operations/health-and-readiness.md).

## Audio issues

For WAV durations that look wrong, or format-specific playback questions, see
[Audio formats](./audio-formats.md).
