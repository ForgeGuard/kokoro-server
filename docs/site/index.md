---
title: ForgeGuard Kokoro Server
description: Container-native, OpenAI-compatible text-to-speech built on Kokoro-82M, for self-hosted and Kubernetes deployments.
order: 0
status: stable
---

# ForgeGuard Kokoro Server

ForgeGuard Kokoro Server is a container-native, OpenAI-compatible text-to-speech
service built around the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
model. Point any OpenAI speech client at it, deploy it as a container or Helm
release, and run natural-sounding speech synthesis on infrastructure you control.

It is designed for operators: the server accepts connections immediately and warms
the model in the background, exposes distinct liveness and readiness contracts,
ships model weights baked into the images, and offers optional bearer authentication
and built-in HTTPS.

![ForgeGuard Kokoro Server web console](./assets/screenshots/web-console.png)

## Find your path

**Get running**

- [Quickstart](./getting-started/quickstart.md) — one container, a health check, and your first synthesized clip.
- [Container deployment](./deployment/container.md) · [Docker Compose](./deployment/compose.md) · [Kubernetes (Helm)](./deployment/kubernetes.md)
- [Hardware profiles](./deployment/hardware-profiles.md) — supported GPUs and CPU fallback.

**Operate safely**

- [Health and readiness](./operations/health-and-readiness.md) — the exact probe contract.
- [Security hardening](./operations/security-hardening.md) — authentication, TLS, container posture.
- [Observability](./operations/observability.md) · [Upgrades](./operations/upgrades.md)
- [Responsible use](./concepts/responsible-use.md) — synthetic-media disclosure guidance.

**Integrate**

- [OpenAI-compatible API](./reference/openai-api.md) — `/v1/audio/speech`, voices, models.
- [Extended API](./reference/extended-api.md) — captions, phonemes, inline controls, operational endpoints.
- [Configuration](./configuration/overview.md) · [Environment variables](./configuration/environment-variables.md)
- [Compatibility](./reference/compatibility.md)

**Understand the system**

- [Architecture overview](./architecture/overview.md) · [Request lifecycle](./architecture/request-lifecycle.md)
- [Voices and languages](./concepts/voices-and-languages.md) · [Streaming and audio formats](./concepts/streaming-and-audio-formats.md)

## What you get

| Capability | What it provides |
|---|---|
| OpenAI-compatible API | A drop-in `/v1/audio/speech` endpoint any OpenAI SDK can target. |
| Designed multi-language voices | English (US/GB), Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese, and Mandarin Chinese. |
| Voice mixing and controls | Weighted voice combinations, per-word timestamps, phoneme in/out, and inline pause/pronunciation tokens. |
| Streaming output | `mp3`, `wav`, `opus`, `flac`, and raw `pcm`. |
| Orchestrator-friendly startup | Immediate liveness, background warmup, and a strict readiness contract. |
| Self-hosted control | Baked-in weights, offline by default, optional bearer auth, and built-in HTTPS. |

## Distribution

ForgeGuard Kokoro Server is distributed as **container images and a Helm chart
only**. There is no supported bare-metal install path. Images are published to the
GitHub Container Registry under `ghcr.io/forgeguard-ai/`. `latest` tracks the newest
stable release; pin a release tag (for example `1.1.0`) for persistent deployments.

## Roadmap

The following are planned, not current, functionality:

- **Real-time voice endpoints** — low-latency incremental synthesis over a persistent
  connection (WebSocket/SSE) with barge-in-friendly cancellation.
- **More inference backends** — AMD (ROCm) and Intel images as hardware becomes
  available to develop and validate against.

## Lineage and license

This is an original ForgeGuard AI project with documented lineage, derived from
[remsky/Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI). It is licensed
under Apache-2.0. See the repository `LICENSE` and `NOTICE` for full attribution to
Kokoro-82M, the kokoro/misaki libraries, and StyleTTS2.
