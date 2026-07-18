---
title: Environment variables
description: The complete environment-variable reference, verified against the server configuration.
order: 20
status: stable
---

# Environment variables

The canonical list of runtime environment variables. Names are case-insensitive and
carry no prefix. Defaults reflect the server configuration
([`api/src/core/config.py`](https://github.com/forgeguard-ai/kokoro-server/blob/main/api/src/core/config.py))
and the container startup scripts.

## Server

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8880` | Bind port. |
| `API_LOG_LEVEL` | `INFO` | Application (loguru) log level: `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`. |
| `UVICORN_LOG_LEVEL` | `info` | Uvicorn server log level. |
| `UVICORN_ROOT_PATH` | *(unset)* | Root path prefix when served behind a reverse proxy; surfaced to the web console via `/web/config`. |

## Authentication

| Variable | Default | Purpose |
|---|---|---|
| `API_KEY` | *(unset)* | When set, `/v1`, `/dev`, and `/debug` require `Authorization: Bearer <key>`. Unset leaves the API open. `/health`, `/ready`, `/system`, and `/web` always stay open. |

## TLS / HTTPS

| Variable | Default | Purpose |
|---|---|---|
| `TLS_ENABLED` | `false` | Serve HTTPS directly via uvicorn. |
| `TLS_SELF_SIGNED` | `true` | Generate a self-signed certificate on first run if none is supplied. |
| `TLS_CN` | `localhost` | Common name (and a SAN) of the generated certificate. |
| `TLS_SAN` | *(unset)* | Extra SANs, **comma-separated** (e.g. `host.local,10.0.0.5`). |
| `TLS_CERT_FILE` | `{OUTPUT_DIR}/tls/cert.pem` | Path to an existing certificate to use instead of self-signing. |
| `TLS_KEY_FILE` | `{OUTPUT_DIR}/tls/key.pem` | Path to an existing private key. |

See [Security hardening](../operations/security-hardening.md) for the full TLS behavior.

## Model and device

| Variable | Default | Purpose |
|---|---|---|
| `USE_GPU` | `true` | Use CUDA/MPS if available; `false` forces CPU inference. |
| `DEVICE_TYPE` | *(auto)* | Force `cuda`, `mps`, or `cpu`; auto-detected when unset. |
| `WARMUP_ON_START` | `true` | Eagerly load and warm the model in a background task at startup; `false` defers loading to the first request. |
| `DEFAULT_VOICE` | `af_heart` | Voice used for warmup and when a request omits one. |
| `DEFAULT_VOICE_CODE` | *(unset)* | Overrides the language code otherwise derived from the voice name (a request `lang_code` still wins). |

## Storage

| Variable | Default | Purpose |
|---|---|---|
| `OUTPUT_DIR` | `output` | Where generated audio and the self-signed TLS certificate are written. Mount a volume here (e.g. `OUTPUT_DIR=/data`) to persist both. |

## Web console and CORS

| Variable | Default | Purpose |
|---|---|---|
| `ENABLE_WEB_PLAYER` | `true` | Serve the web console at `/web`. |
| `CORS_ENABLED` | `true` | Enable CORS middleware. |
| `CORS_ORIGINS` | `["*"]` | Allowed origins, **JSON** array. |

## Text chunking (advanced)

| Variable | Default | Purpose |
|---|---|---|
| `TARGET_MIN_TOKENS` | `175` | Target minimum tokens per synthesis chunk. |
| `TARGET_MAX_TOKENS` | `250` | Target maximum tokens per chunk. |
| `ABSOLUTE_MAX_TOKENS` | `450` | Hard cap on tokens per chunk. |

## Model download (build / first run)

Published images already bake in the weights; these apply when building an image or when
`DOWNLOAD_MODEL=true`.

| Variable | Default | Purpose |
|---|---|---|
| `DOWNLOAD_MODEL` | *(unset)* | `true` downloads weights at container start (otherwise the baked-in weights are used). |
| `MODEL_DOWNLOAD_BASE_URL` | Hugging Face `hexgrad/Kokoro-82M` | Where weights are fetched from. |
| `MODEL_SHA256` | pinned for the default URL | SHA-256 checksum verification. Required if you set a custom base URL. |
| `MODEL_DOWNLOAD_TIMEOUT` | `120` | Per-attempt download timeout (seconds). |
| `MODEL_DOWNLOAD_RETRIES` | `4` | Download attempts with exponential backoff. |

## Additional settings

The server exposes further advanced settings (audio sample rate, volume multiplier,
normalization toggles, gap-trim padding, temp-file limits, combined-voice saving, and
container model/voice paths) with sensible defaults. These rarely need changing; the
authoritative source is
[`api/src/core/config.py`](https://github.com/forgeguard-ai/kokoro-server/blob/main/api/src/core/config.py).
Notable ones:

| Variable | Default | Purpose |
|---|---|---|
| `ALLOW_LOCAL_VOICE_SAVING` | `false` | Allow `POST /v1/audio/voices/combine` to persist a combined voicepack (returns `403` when disabled). |
| `VOICE_WEIGHT_NORMALIZATION` | `true` | Normalize combined-voice weights to sum to 1. |
| `DEFAULT_VOLUME_MULTIPLIER` | `1.0` | Global output volume multiplier. |
