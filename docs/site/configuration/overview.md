---
title: Configuration overview
description: How the server is configured through environment variables and an optional .env file.
order: 10
status: stable
---

# Configuration overview

All runtime settings are environment variables. There is no configuration file format
to learn beyond an optional `.env`.

## How settings are read

Configuration is loaded by [pydantic-settings]. Variable names are **case-insensitive**
and carry **no prefix**, so the environment variable is the uppercased field name — for
example the `default_voice` setting is `DEFAULT_VOICE`. Values are read, in order of
precedence:

1. Process environment variables (including `-e VAR=value` on `docker run` and container
   orchestrator env).
2. A `.env` file in the working directory, if present.
3. Built-in defaults.

A commented [`.env.example`](https://github.com/forgeguard-ai/kokoro-server/blob/main/.env.example)
in the repository lists the common variables with their defaults; copy it to `.env` and
uncomment only what you need to change.

## Setting variables

In a container:

```bash
docker run -d --gpus all -p 8880:8880 \
  -e API_KEY=change-me \
  -e DEFAULT_VOICE=af_bella \
  ghcr.io/forgeguard-ai/kokoro-server:latest
```

In Docker Compose, use the `environment:` block; on Kubernetes, use
`kokoroTTS.extraEnv` (and `kokoroTTS.apiKey` for the bearer token) in the Helm values.

## What you can configure

- **Server** — bind host/port, application and uvicorn log levels.
- **Authentication** — the optional `API_KEY` bearer token.
- **TLS/HTTPS** — built-in HTTPS with self-signed or supplied certificates.
- **Model and device** — GPU vs CPU, warmup behavior, default voice.
- **Storage** — the output directory for generated audio and the TLS certificate.
- **Web console** — enable/disable and CORS.
- **Text chunking** — long-form token bounds (advanced).
- **Model download** — build/first-run weight fetching and checksum (weights are baked
  into published images).

See the complete list, with types and defaults, in
[Environment variables](./environment-variables.md).

## A note on list-valued variables

Two list settings are parsed differently, which is easy to get wrong:

- `TLS_SAN` is **comma-separated**, e.g. `TLS_SAN=host.local,10.0.0.5`.
- `CORS_ORIGINS` is **JSON**, e.g. `CORS_ORIGINS=["https://app.example.com"]`.

[pydantic-settings]: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
