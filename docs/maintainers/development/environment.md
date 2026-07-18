# Development environment

Maintainer-facing setup for building and running the server from source. This material
is intentionally kept out of the published site (`docs/site/`) — it is for contributors,
not end users.

> Distribution is container-only. There is no supported bare-metal install path; the
> commands below are for development and image building.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python dependency management.
- Docker with the Compose plugin (and the NVIDIA Container Toolkit for GPU builds).
- Node 22+ if you build the web console outside Docker.
- System packages matching the runtime image: `espeak-ng`, `espeak-ng-data`,
  `libsndfile1`, `ffmpeg`, plus `git`, `curl`, `g++`, `cmake`.

## Python dependencies

The project defines conflicting `cpu` and `gpu` extras (they pin different PyTorch
builds) plus a `test` extra. For local CPU work and tests:

```bash
uv sync --extra test --extra cpu
```

Torch wheels come from custom indexes declared in `pyproject.toml` (`pytorch-cpu`,
`pytorch-cu128`, and a JetPack-6 index for aarch64).

## Run the server from source

```bash
# Dev launcher with auto-reload (honors TLS_ENABLED)
uv run --extra cpu python -m api.src.main

# Production launcher (used by the container entrypoint)
uv run --extra cpu python -m api.src.serve
```

The server reads configuration from the environment and an optional `.env`; see the
published [configuration overview](../../site/configuration/overview.md) and
[`.env.example`](../../../.env.example).

## Build the images

```bash
# amd64 CUDA (cu128)
docker build -f docker/gpu/Dockerfile.optimized -t kokoro-server:dev .

# Jetson (arm64, on-device or on an arm64 builder)
docker build -f docker/jetson/Dockerfile -t kokoro-server-jetson:dev .

# Helper wrapping both variants
docker/build.sh amd64 dev
docker/build.sh jetson dev
```

Both images:

- Build the web console in a Node stage (`web/` → `/web/dist`).
- Bake model weights at build time via `download_model.py` (build arg
  `DOWNLOAD_MODEL=true`), with SHA-256 verification.
- Optionally bake the Japanese UniDic dictionary (`INCLUDE_JAPANESE=true`).
- Run as non-root uid 1001 and set offline Hugging Face flags.

No network access is required at container start.

## Compose stacks

The `docker/gpu/` Compose files cover development (build + bind-mount source, so it sets
`DOWNLOAD_MODEL=true`), production (pull published image), and a local HTTPS single-GPU
stack. See the published [Compose deployment](../../site/deployment/compose.md) page.

## Linting

Ruff is configured for import sorting (`.ruff.toml`, `select = ["I"]`, line length 88):

```bash
uvx ruff check .
```

## See also

- [Testing](./testing.md)
- [Release process](../release/release-process.md)
- Architecture notes: [espeak integration](../architecture-notes/espeak-integration.md),
  [streaming audio writer](../architecture-notes/streaming-audio-writer.md).
