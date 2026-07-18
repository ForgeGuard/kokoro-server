---
title: Observability
description: System telemetry, the web console monitor, debug endpoints, and logging.
order: 20
status: stable
---

# Observability

## System telemetry: `GET /system`

An unauthenticated endpoint that returns version, model state, GPU telemetry, and
in-flight activity. The web console polls it to render its monitor, and it exposes no
secrets.

```json
{
  "version": "1.1.0",
  "status": "ready",
  "gpu": {
    "name": "NVIDIA ...",
    "memory_used_bytes": 0,
    "memory_total_bytes": 0,
    "utilization_pct": 0,
    "temperature_c": 0,
    "power_w": 0.0
  },
  "activity": { "active": 0, "waiting": 0 },
  "model": { "device": "cuda", "backend": "kokoro_v1", "voicepack_count": 0 }
}
```

- `gpu` is `null` on CPU-only hosts. Memory always comes from the framework; utilization,
  temperature, and power are added best-effort via NVML and may be absent without a
  driver.
- `activity.active` is the number of in-flight synthesis requests. `waiting` is always
  `0` (there is no bounded queue; the field is kept for parity with sibling servers).
- `model` is populated only once the model is `ready`.

## Web console

When `ENABLE_WEB_PLAYER=true` (the default), a browser console is served at `/web`. It
lets you try voices with weighted blending, adjust format and speed, play back and
download audio, watch warming status, and enter an API key when authentication is
enabled. The console renders a live GPU/activity monitor from `/system`. Disable it with
`ENABLE_WEB_PLAYER=false`.

## Debug endpoints

Authenticated `GET` endpoints for operational inspection (subject to `API_KEY` when set):

| Endpoint | Returns |
|---|---|
| `GET /debug/threads` | Thread count, names, and per-thread details plus process memory. |
| `GET /debug/storage` | Mounted-filesystem usage (total/used/free/percent). |
| `GET /debug/system` | CPU, memory, process, network, and GPU information. |

## Logging

- `API_LOG_LEVEL` controls the application (loguru) log level; `UVICORN_LOG_LEVEL`
  controls the uvicorn server logs. See
  [Environment variables](../configuration/environment-variables.md).
- On successful warmup the server prints a boxed ForgeGuard startup panel summarizing the
  version, endpoint, auth state, device and GPU/VRAM, model, voice-pack count, and web
  console URL — a quick at-a-glance confirmation of how the container came up.
- At the default level, application logs do not record full request text. See
  [Security hardening](./security-hardening.md#data-handling).
