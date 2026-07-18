# Testing

## Unit tests (CPU)

The unit suite runs on CPU PyTorch and is what CI executes:

```bash
uv run --extra test --extra cpu pytest api/tests/
```

`pytest.ini` sets the defaults (`testpaths = api/tests`, coverage on, and `-m "not
integration"` so the integration marker is excluded by default). CI
(`.github/workflows/ci.yml`) runs the same command with `--asyncio-mode=auto` on
`ubuntu-24.04`, Python 3.10, after apt-installing the espeak/ffmpeg/sndfile system
packages.

## Integration tests (end-to-end)

The integration harness builds the server plus a Whisper-equipped test client, then
round-trips audio through faster-whisper and checks word error rate. It is defined in
`docker/docker-compose.test.yml`:

```bash
docker compose -f docker/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from test-client
```

Notes:

- The `server` service's healthcheck hits `/ready` (not `/health`), so
  `service_healthy` means "model warmed", and the client only starts once synthesis is
  possible.
- `USE_GPU` defaults to `false` in this stack, so it runs on plain (CPU) runners.
- Point it at a published image instead of building by setting `SERVER_IMAGE=...`.
- The test client (`docker/test-client/`) is a portable OpenAI-compatible TTS validator:
  it asserts format-correct audio bytes, streaming, valid phonemes, word timestamps, and
  intelligibility (faster-whisper transcription + jiwer WER). Its integration tests are
  mounted at run time; the Whisper weights are baked into the client image.

## What to run when changing examples or config

If a change touches documented request/response examples or configuration defaults,
re-run the unit suite and, where the behavior is end-to-end (audio format, streaming,
timestamps), the integration harness. Keep documentation examples in sync with verified
behavior.
