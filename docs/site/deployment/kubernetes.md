---
title: Kubernetes (Helm)
description: Deploy on Kubernetes with the published Helm chart.
order: 30
status: stable
---

# Kubernetes (Helm)

The server ships a Helm chart, published as an OCI artifact and also available in the
repository under
[`charts/kokoro-server`](https://github.com/forgeguard-ai/kokoro-server/tree/main/charts/kokoro-server).

## Prerequisites

- A Kubernetes cluster with GPU nodes and the NVIDIA device plugin / GPU Operator, so
  `nvidia.com/gpu` is schedulable.
- Helm 3.8+ (OCI support).

## Install

```bash
helm install kokoro \
  oci://ghcr.io/forgeguard-ai/charts/kokoro-server --version 1.1.0
```

Pin `--version` to a released chart version for reproducible deployments.

## Health probes

The chart wires the server's health contract into probes so pods receive traffic only
after warmup and are not restarted during it:

- `startupProbe` → `GET /ready` (allows a long cold-load window).
- `readinessProbe` → `GET /ready`.
- `livenessProbe` → `GET /health`.

See [Health and readiness](../operations/health-and-readiness.md).

## Key values

Configuration lives under the `kokoroTTS` key (and a few top-level keys). Defaults:

| Value | Default | Purpose |
|---|---|---|
| `kokoroTTS.repository` | `ghcr.io/forgeguard-ai/kokoro-server` | Image repository. |
| `kokoroTTS.tag` | `""` | Image tag; empty resolves to the chart `appVersion` (a pinned release). |
| `kokoroTTS.replicaCount` | `1` | Replicas (ignored when autoscaling is enabled). |
| `kokoroTTS.port` | `8880` | Container/service port. |
| `kokoroTTS.resources.limits.nvidia.com/gpu` | `1` | GPUs requested/limited per pod. |
| `kokoroTTS.apiKey.enabled` | `false` | Inject `API_KEY` from an existing Secret. |
| `kokoroTTS.apiKey.existingSecret` / `.secretKey` | `""` / `api-key` | Secret name and key holding the bearer token. |
| `kokoroTTS.extraEnv` | `[]` | Extra environment variables (name/value pairs). |
| `service.type` | `ClusterIP` | Service type. |
| `ingress.enabled` | `false` | Enable an Ingress (class, hosts, and TLS are configurable). |
| `autoscaling.enabled` | `false` | Enable an HPA (`minReplicas`/`maxReplicas`/CPU target). |
| `podSecurityContext` / `securityContext` | non-root uid 1001, drop ALL caps, no privilege escalation | Hardened defaults. |

Set the full env reference from [Environment variables](../configuration/environment-variables.md)
through `kokoroTTS.extraEnv`.

## Authentication from a Secret

```bash
kubectl create secret generic kokoro-auth --from-literal=api-key=REPLACE_ME

helm install kokoro oci://ghcr.io/forgeguard-ai/charts/kokoro-server \
  --version 1.1.0 \
  --set kokoroTTS.apiKey.enabled=true \
  --set kokoroTTS.apiKey.existingSecret=kokoro-auth
```

## Ingress and TLS

For public exposure, enable `ingress` and terminate TLS at the ingress with a
CA-issued certificate (for example via cert-manager) rather than the server's
self-signed certificate. An example values file for AKS with cert-manager and
external-dns is provided under
[`charts/kokoro-server/examples/`](https://github.com/forgeguard-ai/kokoro-server/tree/main/charts/kokoro-server/examples).

## Persistence

The chart does not provision a volume for `OUTPUT_DIR` by default, so generated audio is
**ephemeral** and lost on pod restart. If you need durable output (or a persisted TLS
certificate), add your own volume and set `OUTPUT_DIR` accordingly through `extraEnv`
and a pod spec override. For most API workloads, ephemeral output is fine — audio is
streamed back to the client.

## Upgrades and the chart rename

The chart was renamed from `kokoro-fastapi` to `kokoro-server` in 1.1.0 and its selector
labels changed. When migrating from the old chart, `helm uninstall` the old release and
install this chart fresh rather than upgrading in place. See
[Upgrades](../operations/upgrades.md).
