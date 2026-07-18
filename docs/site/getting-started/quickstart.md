---
title: Quickstart
description: Run the server in a container and synthesize your first clip.
order: 10
status: stable
---

# Quickstart

Get from zero to a synthesized audio file in a few minutes.

## Prerequisites

- Docker (or another OCI container engine).
- For GPU inference: an NVIDIA GPU with recent drivers and the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  installed and configured. The CUDA (cu128) image also runs on CPU with `USE_GPU=false`.

## 1. Start the server

Run the CUDA (cu128) image, which covers NVIDIA RTX 3000 through RTX 5000 GPUs:

```bash
docker run -d --name kokoro --gpus all -p 8880:8880 \
  ghcr.io/forgeguard-ai/kokoro-server:latest
```

The server binds `0.0.0.0:8880` and accepts connections immediately while it warms
the model in the background. Model weights are baked into the image, so nothing is
downloaded at container start.

> Running on a host without an NVIDIA GPU? Drop `--gpus all` and add `-e USE_GPU=false`.
> See [Hardware profiles](../deployment/hardware-profiles.md) for Jetson and CPU details.

## 2. Check health and readiness

`/health` answers `200` as soon as the socket is open; `/ready` answers `200` only
once the model is warmed and can synthesize:

```bash
curl http://localhost:8880/health
# {"status":"warming","model_loaded":false}   -> then {"status":"healthy","model_loaded":true}

curl http://localhost:8880/ready
# 503 while warming, then {"status":"ready"}
```

Warmup takes a few seconds on datacenter GPUs and longer on edge devices. See
[Health and readiness](../operations/health-and-readiness.md) for the full contract.

## 3. Synthesize speech

Once `/ready` returns `200`, request audio from the OpenAI-compatible endpoint:

```bash
curl -X POST http://localhost:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","input":"Hello world!","voice":"af_heart","response_format":"mp3"}' \
  -o hello.mp3
```

You should get a playable `hello.mp3` (a few kilobytes for this short phrase). Play it
with any audio player, or inspect it with `ffprobe hello.mp3`.

## 4. Use the OpenAI SDK

Any OpenAI speech client works — point it at `/v1` and use any API key value when auth
is disabled:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8880/v1", api_key="not-needed")

with client.audio.speech.with_streaming_response.create(
    model="kokoro",
    voice="af_sky+af_bella",   # a single voice, or a weighted combination
    input="Hello world!",
) as response:
    response.stream_to_file("output.mp3")
```

## Explore from the browser

- Interactive API docs: `http://localhost:8880/docs`
- Web console: `http://localhost:8880/web`

The [web console](../operations/observability.md#web-console) lets you try voices,
adjust format and speed, watch warming status, and enter an API key when auth is on.

## Next steps

- [Deploy with Compose](../deployment/compose.md) for durable single-host operation.
- [Deploy on Kubernetes](../deployment/kubernetes.md) with the Helm chart.
- [Enable authentication and HTTPS](../operations/security-hardening.md) before exposing the server.
- Browse the full [OpenAI-compatible API](../reference/openai-api.md) and
  [extended API](../reference/extended-api.md).
