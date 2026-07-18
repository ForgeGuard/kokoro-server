---
title: Container deployment
description: Run the server as a single container with GPU or CPU inference.
order: 10
status: stable
---

# Container deployment

Running a single container is the fastest way to stand up the server for local testing
or a single-service deployment.

## Prerequisites

- Docker or another OCI container engine.
- For GPU inference: an NVIDIA GPU with drivers and the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

## Run (NVIDIA GPU)

```bash
docker run -d --name kokoro --gpus all -p 8880:8880 \
  ghcr.io/forgeguard-ai/kokoro-server:latest
```

Verify:

```bash
curl --fail http://localhost:8880/health   # 200 immediately (warming -> healthy)
curl --fail http://localhost:8880/ready    # 200 once the model can synthesize
```

## Run on CPU

The CUDA (cu128) image also runs without a GPU. Omit `--gpus` and force CPU:

```bash
docker run -d --name kokoro -p 8880:8880 -e USE_GPU=false \
  ghcr.io/forgeguard-ai/kokoro-server:latest
```

CPU inference works but is considerably slower. See
[Hardware profiles](./hardware-profiles.md).

## Persist output

Generated audio and the self-signed TLS certificate live under `OUTPUT_DIR`. To keep
them across container restarts, mount a volume and point `OUTPUT_DIR` at it:

```bash
docker run -d --name kokoro --gpus all -p 8880:8880 \
  -e OUTPUT_DIR=/data \
  -v kokoro-data:/data \
  ghcr.io/forgeguard-ai/kokoro-server:latest
```

The container runs as a non-root user (uid 1001); the mounted volume must be writable
by that user.

## Enable authentication

Set `API_KEY` to require a bearer token on the API routes:

```bash
docker run -d --name kokoro --gpus all -p 8880:8880 \
  -e API_KEY=change-me \
  ghcr.io/forgeguard-ai/kokoro-server:latest

curl -H 'Authorization: Bearer change-me' http://localhost:8880/v1/models
```

`/health`, `/ready`, `/system`, and the web console stay open. See
[Security hardening](../operations/security-hardening.md).

## Linux GPU permissions

If the container cannot access the GPU as a non-root user, add it to the `video` and
`render` groups (for `docker run`, `--group-add video --group-add render`), and confirm
the NVIDIA Container Toolkit is installed and configured. See
[Common errors](../troubleshooting/common-errors.md#gpu-not-accessible).

## Next steps

- Use [Docker Compose](./compose.md) for a durable single-host setup with a volume.
- Deploy on [Kubernetes](./kubernetes.md) with the Helm chart.
