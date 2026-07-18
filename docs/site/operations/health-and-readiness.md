---
title: Health and readiness
description: Liveness, readiness, warmup, and failure behavior — the exact probe contract.
order: 10
status: stable
---

# Health and readiness

The server binds `0.0.0.0:8880` and accepts connections immediately; the model loads and
warms in a background task. This keeps orchestrator health polls happy during warmup
while a strict readiness endpoint gates real traffic.

## Endpoints

All three endpoints are unauthenticated so orchestrators and Kubernetes probes can reach
them before any API key is known.

| Endpoint | While warming | Ready | Failed warmup |
|---|---|---|---|
| `GET /health` (liveness) | `200` `{"status":"warming","model_loaded":false}` | `200` `{"status":"healthy","model_loaded":true}` | `503` `{"status":"failed","error":"..."}` (then the process exits) |
| `GET /ready` (readiness) | `503` + `Retry-After: 10` | `200` `{"status":"ready"}` | `503` |
| `POST /v1/audio/speech` | `503` + `Retry-After: 10`, error `model_warming` | normal | `503`, error `model_failed` |

`model_loaded` means "warmed", not "currently resident": [`POST /dev/unload`](../reference/extended-api.md#post-devunload)
frees the model from VRAM but the flag stays `true`, and the next request lazily reloads.

## Warmup failure exits the container

A warmup that fails permanently (for example, missing or shadowed weights) sets the
status to `failed` and then exits the process with a non-zero code. This is deliberate:
an orchestrator should see a dead container it can restart or surface, not a
healthy-looking server that cannot synthesize. The `/health` `503` window is therefore
brief.

## Lazy loading

Set `WARMUP_ON_START=false` to skip eager loading. The model then loads on the first
synthesis request instead of at startup. With warmup disabled, `/ready` reports not-ready
until that first request has loaded the model.

## Using the contract

**Kubernetes** (wired by the Helm chart):

```yaml
startupProbe:   { httpGet: { path: /ready,  port: 8880 }, periodSeconds: 5, failureThreshold: 60 }
readinessProbe: { httpGet: { path: /ready,  port: 8880 }, periodSeconds: 10 }
livenessProbe:  { httpGet: { path: /health, port: 8880 }, periodSeconds: 30 }
```

The generous `startupProbe.failureThreshold` allows a long cold-load window (up to ~300s)
without the liveness probe restarting the pod mid-warmup.

**Docker / Compose** — poll `/health` for liveness and `/ready` before sending traffic:

```bash
until curl -fsS http://localhost:8880/ready >/dev/null; do sleep 2; done
echo "ready"
```

## See also

- [Observability](./observability.md) for `/system` telemetry.
- [Kubernetes deployment](../deployment/kubernetes.md).
