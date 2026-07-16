# Contributing to ForgeGuard Kokoro Server

Contributions are welcome. This project ships as **container images and a Helm
chart only** — there is no supported bare-metal run path, and the development
workflow reflects that: run tests with `uv`, exercise the server in a container.

## Dev container (recommended)

The repo ships a multi-arch dev container (`.devcontainer/`, amd64 + arm64 —
it works on x86 workstations and on Jetson devices directly). Open the folder
in VS Code and "Reopen in Container": you get Python 3.10 + uv (deps synced
automatically), Node 22 for the web console, helm, espeak-ng/ffmpeg for the
test suite, and docker-outside-of-docker so `docker build`/`docker compose`
drive the host daemon (including its GPU runtime).

## Prerequisites

- [Docker](https://docs.docker.com/engine/install/) (with the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  if you want to exercise GPU inference)
- [uv](https://docs.astral.sh/uv/) for Python environments (tests and linting)
- `espeak-ng` and `libsndfile1` system packages if you run the unit tests
  directly on your machine (the containers include them)

```bash
git clone https://github.com/forgeguard-ai/kokoro-server.git
cd kokoro-server
```

## Running tests

Unit tests run against CPU torch (this is what CI does):

```bash
uv run --extra test --extra cpu pytest api/tests/
```

No local espeak/torch setup? Run the suite inside the server image instead:

```bash
docker build -f docker/gpu/Dockerfile.optimized -t kokoro-server:dev .
docker run --rm -u root -v "$PWD:/work" -w /work \
  -e PYTHONPATH=/work:/work/api -e USE_GPU=false kokoro-server:dev \
  bash -c 'uv pip install --python /app/.venv/bin/python ".[test]" && \
           /app/.venv/bin/python -m pytest api/tests/ --no-cov'
```

End-to-end integration tests (server + Whisper round-trip with WER checks):

```bash
docker compose -f docker/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from test-client
```

## Running the server

The dev loop is the container:

```bash
docker compose -f docker/gpu/docker-compose.yml up --build
```

or a plain build + run:

```bash
docker build -f docker/gpu/Dockerfile.optimized -t kokoro-server:dev .
docker run --rm --gpus all -p 8880:8880 kokoro-server:dev
```

For the Jetson image, build `docker/jetson/Dockerfile` on an arm64 machine (or
the device itself) and run with `--runtime nvidia`.

The web console lives in `web/` (Vite + React). `npm ci && npm run dev` inside
`web/` gives a hot-reloading UI against a running server; production builds are
done inside the Docker build (`web/dist` is baked into the image).

## Formatting and linting

`ruff` handles both:

```bash
uv run --extra test --extra cpu ruff format .
uv run --extra test --extra cpu ruff check . --fix
```

## Submitting changes

1. Create a branch for your feature or fix.
2. Make your changes; keep them modular and in line with the current design.
   If you can't test on CUDA hardware, say so in the PR so a maintainer can.
3. Ensure `pytest` passes and the affected image still builds.
4. Open a Pull Request against `main`.

Thank you for contributing!
