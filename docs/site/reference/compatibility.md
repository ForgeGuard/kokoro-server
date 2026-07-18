---
title: Compatibility
description: Hardware, runtime, API, and audio-format compatibility.
order: 30
status: stable
---

# Compatibility

## Hardware and runtime

| Target | Status | Notes |
|---|---|---|
| NVIDIA RTX 3000 → 5000 (x86_64, CUDA cu128) | Supported | Single cu128 image, compute capability sm_86–sm_120. |
| NVIDIA Jetson Orin (arm64) | Supported | JetPack 6 / L4T r36 (CUDA 12.6, cuDNN 9.3); use the Jetson image. |
| CPU (x86_64) | Supported | `USE_GPU=false`; reduced throughput. |
| Apple Silicon (MPS) | Experimental | Auto-detected for local runs; not a published container target. |
| AMD (ROCm), Intel | Planned | Not currently supported. |

See [Hardware profiles](../deployment/hardware-profiles.md) for image selection.

## Container engines and orchestration

- Docker / OCI engines with the NVIDIA Container Toolkit for GPU access.
- Docker Compose (files provided) for single-host operation.
- Kubernetes 1.25+ with the NVIDIA device plugin / GPU Operator; Helm 3.8+ (OCI) for the
  chart.

## API compatibility

- OpenAI-compatible `/v1/audio/speech`, `/v1/audio/voices`, and `/v1/models` — usable with
  the OpenAI SDKs by setting `base_url` to `.../v1`.
- Standard OpenAI voice names are accepted and mapped to designed voices. See
  [Voices and languages](../concepts/voices-and-languages.md).
- Extended, non-OpenAI endpoints are under `/dev` and `/debug`. See
  [Extended API](./extended-api.md).

## Audio formats

| Format | Supported | Notes |
|---|---|---|
| `mp3` | Yes | Default. |
| `wav` | Yes | 16-bit PCM RIFF. |
| `opus` | Yes | Ogg/Opus. |
| `flac` | Yes | Lossless. |
| `pcm` | Yes | Raw signed 16-bit LE, 24 kHz, mono. |
| `aac` | No | Accepted by the request schema but not currently produced. |

All output is 24 kHz mono. See
[Streaming and audio formats](../concepts/streaming-and-audio-formats.md).

## Runtime versions

- Python 3.10 in the images.
- PyTorch cu128 on x86_64; a JetPack-6-matched PyTorch build on Jetson.

The authoritative dependency set is
[`pyproject.toml`](https://github.com/forgeguard-ai/kokoro-server/blob/main/pyproject.toml).
