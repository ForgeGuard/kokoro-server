---
title: Docker Compose
description: Durable single-host deployment with the provided Compose files.
order: 20
status: stable
---

# Docker Compose

The repository ships three Compose files under
[`docker/gpu/`](https://github.com/forgeguard-ai/kokoro-server/tree/main/docker/gpu),
each for a different use case. All map container port `8880`.

## Prerequisites

- Docker with the Compose plugin.
- An NVIDIA GPU with the Container Toolkit for the GPU stacks.

## Production: pull and run

`docker-compose.prod.yml` pulls the published image with weights baked in — no source
mounts, no downloads at start, GPU reserved:

```bash
docker compose -f docker/gpu/docker-compose.prod.yml up -d
```

This is the offline-capable path suitable for a persistent single host. Uncomment
`API_KEY` in the file (or supply it via your own env) to require authentication.

## Local single-GPU with HTTPS

`docker-compose.local.yml` builds the image and runs it with built-in HTTPS (self-signed
on first run), a persistent named volume, and the container's HTTPS exposed on host port
`8443` (override with `KOKORO_HTTPS_PORT`):

```bash
docker compose -f docker/gpu/docker-compose.local.yml up -d --build
# then open https://localhost:8443/web/
```

The named volume `kokoro-data` is mounted at `/data` (`OUTPUT_DIR=/data`), so generated
audio and the self-signed certificate under `/data/tls` survive restarts. Browsers warn
on self-signed certificates — expected for local use. See
[Security hardening](../operations/security-hardening.md).

## Development: build from source

`docker-compose.yml` builds from the local checkout and bind-mounts `api/`, so it sets
`DOWNLOAD_MODEL=true` to fetch weights (the mount would otherwise shadow the baked-in
ones). Use it when iterating on the server code:

```bash
docker compose -f docker/gpu/docker-compose.yml up --build
```

> The `DOWNLOAD_MODEL=true` path fetches weights at start and needs network access. The
> production and local files use baked-in weights and run offline.

## Common overrides

- **Authentication** — add `API_KEY=...` to the service `environment`.
- **CPU only** — set `USE_GPU=false` and remove the `deploy.resources.reservations`
  GPU block.
- **Persistence** — the local file already mounts a volume; for prod, add a volume and
  `OUTPUT_DIR=/data`.

## Next steps

- Move to [Kubernetes](./kubernetes.md) for clustered/production operation.
- Review [Upgrades](../operations/upgrades.md) for tag pinning.
