# Changelog

Notable changes to this project will be documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/) and this project follows
[Semantic Versioning](https://semver.org/).

Per-PR attribution and contributor credits are published automatically on the corresponding GitHub release page; this file is the curated, human-readable summary.

## [1.1.0] - 2026-07-16

Cross-cutting parity pass to bring this server in line with the sibling
ForgeGuard inference servers (one look, one deployment story, one quality bar).

### Added
- **Built-in HTTPS.** Set `TLS_ENABLED=true` to serve HTTPS directly (uvicorn
  SSL) — no reverse proxy, no manual `openssl`, no extra container. When no cert
  is provided and `TLS_SELF_SIGNED=true` (default), a self-signed cert (RSA 2048,
  ~10y validity, SANs for `TLS_CN` + `localhost` + loopback + `TLS_SAN`) is
  generated on first run and persisted under `{OUTPUT_DIR}/tls` so restarts reuse
  it. New config: `TLS_ENABLED`, `TLS_SELF_SIGNED`, `TLS_CERT_FILE`,
  `TLS_KEY_FILE`, `TLS_CN`, `TLS_SAN`. Adds `cryptography` as a dependency.
- **Live GPU + activity telemetry** on a new open `GET /system` endpoint:
  GPU name, VRAM used/total, and (via optional `nvidia-ml-py`) utilization,
  temperature, and power — best-effort, degrading to torch memory or omitting
  gracefully — plus in-flight request counts. Unauthenticated like `/health`.
- **GPU + activity monitor in the web console:** a compact, theme-matched bar
  (GPU/VRAM/temp/power meters + running/queued) polling `/system` every ~3s.
- **Local single-GPU deploy stack** (`docker/gpu/docker-compose.local.yml`):
  builds the image, reserves one NVIDIA GPU, enables self-signed TLS, publishes
  HTTPS on 8443, mounts a persistent data volume, and overrides the healthcheck
  to speak HTTPS. Plus a complete `.env.example` and `docs/security.md` /
  `docs/responsible-use.md`.
- Web console: capability-aware voice states (loading / empty / error+retry) and
  a two-tier title with the browser tab set to `Console · ForgeGuard Kokoro
  Server`.

### Changed
- Container launches via `python -m api.src.serve` (generates + wires the TLS
  cert before binding); a default HTTP healthcheck is baked into the image.
- Helm chart now enforces `runAsNonRoot` / `runAsUser` / `fsGroup`, drops all
  capabilities, and disallows privilege escalation by default.

## [1.0.1] - 2026-07-12

First ForgeGuard release. Versioning starts at `1.0.1`; entries below the
"Pre-1.0 (upstream)" heading are the inherited upstream history for reference.

### Added
- Optional API-key authentication. Set `API_KEY` to require
  `Authorization: Bearer <key>` on the `/v1`, `/dev`, and `/debug` routers; the
  health check and web console stay open. Unset leaves the server open
  (unchanged default).
- New web console: a modern Vite + React + TypeScript + Tailwind TTS interface
  served at `/web`, with light/dark themes, an in-app API-key dialog, a
  warming-status banner, voice search with language grouping, format/speed
  controls, and a download button.
- Jetson (arm64) container image (`docker/jetson/Dockerfile`), published as
  `ghcr.io/forgeguard/kokoro-server-jetson`.
- `GET /ready` readiness endpoint: 200 only once the model is warmed, 503 with
  `Retry-After` otherwise — the strict counterpart to `/health` for Kubernetes
  probes and deploy tooling.
- `/health` now reports warmup progress: `{"status":"warming","model_loaded":false}`
  during background load, `{"status":"healthy","model_loaded":true}` once ready.
- Inference endpoints (`/v1/audio/speech`, `/dev/captioned_speech`,
  `/dev/generate_from_phonemes`) return `503` with an OpenAI-style
  `model_warming` error and `Retry-After` header while the model is loading,
  instead of hitting an unloaded backend.
- `WARMUP_ON_START` env var (default `true`): eagerly load + warm the model in
  a background task at startup; set `false` to defer to first request.
- `UVICORN_LOG_LEVEL` env var for the server log level (default `info`).
- amd64 images now also publish as `ghcr.io/forgeguard/kokoro-server`
  (alias of `-cu128`) so hosts can pull an unsuffixed tag.
- Release CI: CPU smoke test that boots the amd64 image and asserts the
  health/readiness contract plus a real synthesis before the GitHub Release is
  created; Helm chart published as OCI to `ghcr.io/forgeguard/charts`.
- `NOTICE` file with Apache-2.0 attribution for the upstream project, the
  Kokoro-82M model, and StyleTTS2.

### Changed
- **Non-blocking startup.** The server accepts connections (and answers
  `/health`) immediately; model load + warmup runs as a background task. A
  permanently failed warmup exits the container non-zero so orchestrators see
  the failure.
- Helm chart renamed `kokoro-fastapi` → `kokoro-server` (`charts/kokoro-server`).
  Probes are built around the health contract (`startupProbe` + `readinessProbe`
  on `/ready`, `livenessProbe` on `/health`), image defaults to
  `ghcr.io/forgeguard/kokoro-server` pinned to the chart appVersion, and API
  keys can be injected from a Secret via `kokoroTTS.apiKey.existingSecret`.
- Distribution is container images + Helm chart only; no bare-metal run path.
- Container lineup simplified to two images: an amd64 CUDA **cu128** image
  (`-cu128`, covering RTX 3000 through RTX 5000 in one build) and the Jetson
  image. CPU, ROCm, and generic-arm64 variants were removed.
- Dependencies modernized: PyTorch `2.8.0` → `2.9.0`, FastAPI `0.115.6` →
  `0.139.0`, Pydantic `2.10.4` → `2.13.4`, plus uvicorn/pydantic-settings.
- Model weights download (at image build) from the canonical Hugging Face
  `hexgrad/Kokoro-82M` repo with a pinned SHA-256, and are baked into the
  image — the container runs fully offline once pulled (`HF_HUB_OFFLINE=1`
  and telemetry disabled; a preflight check gives a clear error if a volume
  mount shadows the baked weights).
- Release pipeline replaced `docker buildx bake` + multi-arch manifests with
  tag-triggered `docker/build-push-action` jobs publishing to
  `ghcr.io/forgeguard/kokoro-server-*`. The GitHub Release lists image
  tags/digests and pull commands.
- CORS no longer pairs a wildcard origin with `allow_credentials=True`
  (`cors_allow_credentials` defaults to `False`).
- Default log levels quieted from `DEBUG` to `INFO` (`API_LOG_LEVEL`,
  `UVICORN_LOG_LEVEL`).
- README rewritten around the container/Helm workflow with the health contract,
  environment reference, and attribution; project identity is now
  "ForgeGuard Kokoro Server" (upstream banner and badges removed).
- Integration test harness gates on real readiness (`/ready` /
  `status == "healthy"`) instead of any 200 from `/health`.
- The blocking TTS inference and phonemization loop now runs on a worker
  thread instead of the event loop, so a single generation no longer stalls
  concurrent requests, `/health`, or client-disconnect handling.
- `default_volume_multiplier` acts as a true default: an explicit per-request
  `volume_multiplier` now overrides it instead of stacking multiplicatively.

### Removed
- Legacy Gradio UI (`ui/`) and the vanilla-JS web player, superseded by the
  React console.
- `docker-bake.hcl`, the CPU/ROCm Docker build dirs, the `test_build` /
  `test_client_image` workflows, and the `start-*.sh`/`.ps1` scripts,
  `examples/`, `dev/`, `debug.http`, `scripts/fix_misaki.py`, root
  `package.json`, and local-install documentation.
- `/debug/session_pools`: dead code inspecting an ONNX session-pool field the
  Kokoro-V1 backend never has.

### Fixed
- **Security:** path traversal / arbitrary file read in the `/web` and
  `/v1/download` file-serving paths (`_find_file` now rejects absolute paths
  and `..` escapes).
- Missing model files at startup exited the container with code 0
  (`exit(0)`), causing a silent restart loop under `--restart unless-stopped`.
  Warmup failures now raise and terminate with a non-zero exit code.
- Requests arriving mid-warmup could reach a backend whose weights were still
  loading and fail with a 500 (or mid-stream) — now cleanly rejected with 503.
- A failed model load left the server permanently wedged ("Model not loaded")
  instead of retrying; a concurrent request could also grab a half-initialized
  backend mid-load.
- CUDA OOM retry no longer emits a duplicate audio stream, drops word
  timestamps, or raises a spurious 500 after a successful retry.
- `/dev/unload` no longer races in-flight generation, including the
  phoneme-based generation endpoint that previously bypassed the guard.
- Per-chunk generation failures no longer return a silently truncated
  HTTP 200; a `null` `volume_multiplier` no longer crashes generation.
- List-form `voice` input (e.g. `["af_bella","af_sky"]`), empty/whitespace
  voice input, and a single weighted voice (e.g. `af_bella(2)`) now parse
  correctly instead of raising a 500.
- Temp-file cleanup no longer deletes every file (including ones just handed
  out as download links) once the file-count cap is exceeded, and no longer
  freezes on an idle server; `X-Download-Path` now points at the real
  `/v1/download/...` route; `download_format` now actually re-encodes the
  download instead of just renaming the file.
- Non-English (CJK) text is tokenized with the correct language during chunk
  packing instead of always using English phonemization; Mandarin ('z')
  phonemization uses the correct espeak-ng language code.
- `100 F` no longer normalizes to "100 farads" (duplicate unit-table key);
  very large numbers no longer crash text normalization.
- `/v1/audio/voices/combine` now honors weighted voice syntax and no longer
  leaks a file into `/tmp` on every call.
- `/v1/models` and `/v1/models/{id}` no longer disagree on which models exist.
- Non-streaming responses no longer leak the audio writer; missing
  web/download files return 404 instead of 500; the streaming audio writer no
  longer leaks a PyAV encoder/buffer on client disconnect.
- Removed the unauthenticated stray `/v1/test` route.
- The Helm chart's `HorizontalPodAutoscaler` used a removed Kubernetes API
  version and targeted the wrong Deployment name; `helm test` targeted the
  wrong Service name.

---

## Pre-1.0 (upstream history)

## [v0.6.0] - Unreleased
### Fixed
- OpenAI voice aliases pointed at legacy v0.19 voicepacks that sound degraded on the v1.0 model. Added the proper v1.0 `bf_isabella` and repointed `nova` (`bf_v0isabella` -> `bf_isabella`), `alloy`, `ash`, `coral`, `echo` to their v1.0 voices. The `v0*` voices stay available by explicit name. (#479)

## [v0.5.0] - 2026-06-06
### Added
- `POST /dev/unload` release model from VRAM without stopping container; lazy reload on next request. For freeing a shared GPU while idle. Reclaim scale with load (~0.7 GB; ~1.6 GB via long-form test on 4060Ti). (#474)
### Fixed
- Web UI long-playback bugfix around the 10-minute mark; in-browser audio buffer is now bounded ahead of `currentTime` with trailing eviction behind it, so long generations stop overflowing the SourceBuffer.
- Web UI stays responsive on extended sessions; waveform animation is transition-gated and `PlayerState` short-circuits no-op updates, so controls don't drift into lag after 10+ minutes of playback.
- Web UI MP3 seek/scrub works after stream completes; pausing or playback end auto-swaps to the full server file, allowing timeline navigation.

## [v0.4.0] - 2026-05-24
### Added
- GPU image variants for Blackwell / RTX 50-series (`:latest-cu128`, `:vX.Y.Z-cu128`, amd64 only) with PyTorch cu128 wheels (#443). Default `:latest` and new `:latest-cu126` alias stay on cu126 for Maxwell/Pascal compatibility.
- Integration test suite (`api/tests/integration/`, opt-in `integration` marker) and a `tts-api-test-client` image that round-trips speech through faster-whisper against a live server. Run via `docker/docker-compose.test.yml`.
- Web UI footer badge showing the server version from `/config`.

### Breaking changes
- `/v1/audio/voices` items in the `voices` array changed from plain strings to `{"id", "name"}` objects (#462) to match OpenWebUI/similar clients, and allow metadata in the response. Clients reading entries as strings will break; pass `?legacy=true` to restore the old item shape.
  - Old: `{"voices": ["af_heart", ...]}`
  - New: `{"voices": [{"id": "af_heart", "name": "af_heart"}, ...]}`

### Changed
- `api_version` now read from the `VERSION` file instead of hardcoded.
- Removed the legacy `docker/{cpu,gpu}/Dockerfile`; the `.optimized` variants are the only build files now.
- Docker images carry OCI metadata so GHCR pages render properly. Integration compose defaults to the published test-client image.
- ROCm image defaults to `MIOPEN_FIND_MODE=2` so the on-disk kernel cache is reused instead of re-searched per process, and ships an opt-in warmup script at `docker/rocm/warmup_miopen.py` to pre-populate it. Recipe and benchmarks from @realugbun in #454.

### Fixed
- WAV responses drop junk size-field trailer that decoded as a click at chunk end. (#463)
- ROCm MIOpen cache set to persist across compose restarts; switched bind mounts to named volumes at the path MIOpen writes to (prior mounts targeted an inaccessible location).
- cpu/gpu composes set `DOWNLOAD_MODEL=true` for an idempotent model fetch on startup.
- `VERSION` shipped into images so `/config` reports the real server version.
- Silence trimming no longer treats full-scale-negative samples as silent (`int16` `abs()` overflow).
- Fixed invalid escape sequences in the text-normalizer URL regex.
- CI test job uses the CPU PyTorch build and excludes integration tests by default.

## [v0.3.0] - 2026-05-15
### Added
- AMD GPU support via ROCm (`docker/rocm/` build, `rocm` extra in `pyproject.toml`). Also explored/proposed via @asheghi in #393.
- `gpt-4o-mini-tts` model alias for OpenAI-compatible clients.
- Reverse-proxy support for the Web UI (new `/config` endpoint exposing `UVICORN_ROOT_PATH`).
- Configurable logging level via the `API_LOG_LEVEL` environment variable.
- `INCLUDE_JAPANESE` Docker build flag for opt-in Japanese support.
- Transcription accuracy test harness under `examples/assorted_checks/test_transcription/` (baselines, multilingual reports, long-form runner).
- Override of `docker-bake.hcl` variables through GitHub Actions environment variables.

### Changed
- PyTorch bumped to 2.8.0 (x86_64: cu126, aarch64: cu129). x86_64 settled on cu126 to keep Maxwell/Pascal cards working, which drops native Blackwell (RTX 50-series) kernel support. Blackwell users need to override the torch index manually. See #443.
- `kokoro` bumped to 0.9.4 and `misaki` to 0.9.4 (proposed by @jcheek in #371, superceded).
- New optimized multi-stage Dockerfiles (`docker/{cpu,gpu}/Dockerfile.optimized`) become the default bake target. Reported image sizes: CPU 5.6 → 4.9 GB, GPU 14.8 → 9.9 GB.
- Parallelized Docker bake targets per architecture for faster CI.
- ROCBlas version pinned; ROCm docker-compose now builds locally.
- CI/release workflow hardening: pinned BuildKit/runners, branch-tagged builds, manifest fixes, `workflow_dispatch` ref and tag-check race fixed, `latest` tag gated.

### Fixed
- OGG/Opus audio truncation where the final page was lost during `write_chunk` finalize.
- Voice tensor loading hardened with `weights_only=True` (avoids unsafe pickle in `torch.load`).
- Per-request voice-tensor memory leak resolved via caching (#453), with cache cleared on unload.
- Custom phoneme handling made significantly more robust.
- Firefox Web UI playback falls back gracefully when `audio/mpeg` MSE is unsupported; waveform rendering bugfix bundled in the same web rewrite.
- CPU Docker builds: Rust now installed for `appuser` with proper `PATH` and longer `uv` timeouts.
- `cmake` added to CI deps to unblock `pyopenjtalk` builds (proposed by @jcheek in #371; superceded).
- `start-gpu.sh` uses `#!/usr/bin/env bash` for broader compatibility.
- Apple Silicon: `test_initial_state()` no longer fails.

## [v0.2.4] - 2025-06-18
### Added
- Apple Silicon (MPS) acceleration support for macOS users.
- Voice subtraction capability for creating unique voice effects.
- Windows PowerShell start scripts (`start-cpu.ps1`, `start-gpu.ps1`).
- Automatic model downloading integrated into all start scripts.
- Example Helm chart values for Azure AKS and Nvidia GPU Operator deployments.
- Volume multiplier setting.
- Chinese punctuation-based sentence splitting.
- `CONTRIBUTING.md` guidelines for developers.

### Changed
- Version bump of underlying Kokoro and Misaki libraries.
- Default API port reverted to 8880.
- Docker containers now run as a non-root user.
- Improved text normalization for numbers, currency, and time formats.
- Improved MP3 encoding and audio-pause handling.
- Updated and improved Helm chart configurations and documentation.
- Enhanced temporary file management with better error tracking.
- Web UI dependencies (Siriwave) are now served locally.
- Standardized environment variable handling across shell/PowerShell scripts.
- Rust installed in Dockerfile for builds requiring it.

### Fixed
- Download links no longer dropped when `streaming=false` and `return_download_link=true`.
- Windows PowerShell start scripts fixed around virtual-environment activation order.
- Potential segfaults during inference addressed.
- Helm chart issues around health checks, ingress, and default values.
- Audio-quality degradation from incorrect bitrate settings in some paths.
- Custom phonemes provided in input text are now preserved end-to-end.
- 'MediaSource' error affecting playback stability in the web player.
- CRLF line endings in `custom_responses.py` converted to LF.
- Money parsing and related tests.
- Additional safety checks on captioned-speech generation.
- Phoneme handling fixes.

### Removed
- Obsolete GitHub Actions build workflow; build and publish now occurs on merge to `Release` branch.

## [v0.2.3] - 2025-03-06
### Added
- Streaming word timestamps.
- `.gitattributes` for consistent line endings.

### Changed
- Text normalization improvements.

### Fixed
- Audio-quality regression caused by lower-bitrate encoding.
- Disabled uvicorn/FastAPI `--reload` to avoid pegging a CPU core.

## [v0.2.2] - 2025-02-13
### Added
- Helm chart.
- Settings-based override of the default `lang_code`.
- Advanced normalization settings.

### Fixed
- Speech not engaging reliably on the CPU image fallback.
- Audio quality bumped via adjusted compression settings.
- Web UI format-selection bug.

## [v0.2.1] - 2025-02-10
### Added
- Dummy `/v1/models` endpoint for OpenAI compatibility (#144).

### Changed
- Caption flow now streams audio with tempfile download at completion, removing duplicate captions (#139).

### Fixed
- Compatibility with the `espeak-loader` dependency on misaki (#127).
- Build system and model-download issues.

## [v0.2.0post1] - 2025-02-07
- Fix: Building Kokoro from source with adjustments, to avoid CUDA lock 
- Fixed ARM64 compatibility on Spacy dep to avoid emulation slowdown
- Added g++ for Japanese language support
- Temporarily disabled Vietnamese language support due to ARM64 compatibility issues

## [v0.2.0-pre] - 2025-02-06
### Added
- Complete Model Overhaul:
  - Upgraded to Kokoro v1.0 model architecture
  - Pre-installed multi-language support from Misaki:
    - English (en), Japanese (ja), Korean (ko),Chinese (zh), Vietnamese (vi)
  - All voice packs included for supported languages, along with the original versions.
- Enhanced Audio Generation Features:
  - Per-word timestamped caption generation
  - Phoneme-based audio generation capabilities
  - Detailed phoneme generation
- Web UI Improvements:
  - Improved voice mixing with weighted combinations
  - Text file upload support
  - Enhanced formatting and user interface
  - Cleaner UI (in progress)
  - Integration with https://github.com/hexgrad/kokoro and https://github.com/hexgrad/misaki packages

### Removed
- Deprecated support for Kokoro v0.19 model

### Changes
- Combine Voices endpoint now returns a .pt file, with generation combinations generated on the fly otherwise 


## [v0.1.4] - 2025-01-30
### Added
- Smart Chunking System:
  - New text_processor with smart_split for improved sentence boundary detection
  - Dynamically adjusts chunk sizes based on sentence structure, using phoneme/token information in an intial pass
  - Should avoid ever going over the 510 limit per chunk, while preserving natural cadence
- Web UI Added (To Be Replacing Gradio):
  - Integrated streaming with tempfile generation
  - Download links available in X-Download-Path header
  - Configurable cleanup triggers for temp files
- Debug Endpoints:
  - /debug/threads for thread information and stack traces
  - /debug/storage for temp file and output directory monitoring
  - /debug/system for system resource information
  - /debug/session_pools for ONNX/CUDA session status
- Automated Model Management:
  - Auto-download from releases page
  - Included download scripts for manual installation
  - Pre-packaged voice models in repository

### Changed
- Significant architectural improvements:
  - Multi-model architecture support
  - Enhanced concurrency handling
  - Improved streaming header management
  - Better resource/session pool management


## [v0.1.2] - 2025-01-23
### Structural Improvements
- Models can be manually download and placed in api/src/models, or use included script
- TTSGPU/TPSCPU/STTSService classes replaced with a ModelManager service
  - CPU/GPU of each of ONNX/PyTorch (Note: Only Pytorch GPU, and ONNX CPU/GPU have been tested)
  - Should be able to improve new models as they become available, or new architectures, in a more modular way
- Converted a number of internal processes to async handling to improve concurrency
- Improving separation of concerns towards plug-in and modular structure, making PR's and new features easier

### Web UI (test release)
- An integrated simple web UI has been added on the FastAPI server directly
  - This can be disabled via core/config.py or ENV variables if desired. 
  - Simplifies deployments, utility testing, aesthetics, etc 
  - Looking to deprecate/collaborate/hand off the Gradio UI


## [v0.1.0] - 2025-01-13
### Changed
- Major Docker improvements:
  - Baked model directly into Dockerfile for improved deployment reliability
  - Switched to uv for dependency management
  - Streamlined container builds and reduced image sizes
- Dependency Management:
  - Migrated from pip/poetry to uv for faster, more reliable package management
  - Added uv.lock for deterministic builds
  - Updated dependency resolution strategy

## [v0.0.5post1] - 2025-01-11
### Fixed
- Docker image tagging and versioning improvements (-gpu, -cpu, -ui)
- Minor vram management improvements
- Gradio bugfix causing crashes and errant warnings
- Updated GPU and UI container configurations

## [v0.0.5] - 2025-01-10
### Fixed
- Stabilized issues with images tagging and structures from v0.0.4
- Added automatic master to develop branch synchronization
- Improved release tagging and structures
- Initial CI/CD setup

## 2025-01-04
### Added
- ONNX Support:
  - Added single batch ONNX support for CPU inference
  - Roughly 0.4 RTF (2.4x real-time speed)

### Modified
- Code Refactoring:
  - Work on modularizing phonemizer and tokenizer into separate services
  - Incorporated these services into a dev endpoint
- Testing and Benchmarking:
  - Cleaned up benchmarking scripts
  - Cleaned up test scripts
  - Added auto-WAV validation scripts

## 2025-01-02
- Audio Format Support:
  - Added comprehensive audio format conversion support (mp3, wav, opus, flac)

## 2025-01-01
### Added
- Gradio Web Interface:
  - Added simple web UI utility for audio generation from input or txt file

### Modified
#### Configuration Changes
- Updated Docker configurations:
  - Changes to `Dockerfile`:
    - Improved layer caching by separating dependency and code layers
  - Updates to `docker-compose.yml` and `docker-compose.cpu.yml`:
    - Removed commit lock from model fetching to allow automatic model updates from HF
    - Added git index lock cleanup

#### API Changes
- Modified `api/src/main.py`
- Updated TTS service implementation in `api/src/services/tts.py`:
  - Added device management for better resource control:
    - Voices are now copied from model repository to api/src/voices directory for persistence
  - Refactored voice pack handling:
    - Removed static voice pack dictionary
    - On-demand voice loading from disk
  - Added model warm-up functionality:
    - Model now initializes with a dummy text generation
    - Uses default voice (af.pt) for warm-up
    - Model is ready for inference on first request
