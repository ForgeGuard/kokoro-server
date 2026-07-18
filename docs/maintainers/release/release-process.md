# Release process

How releases are cut and published. Driven by `.github/workflows/release.yml`.

## Triggers

- **Tag push** matching `v*` — the normal release path.
- **`workflow_dispatch`** with inputs `version`, `publish_jetson` (default true), and
  `validate_only` (default false) — for manual/validation runs.

Concurrency is grouped per ref with `cancel-in-progress: false`.

## Pipeline

1. **setup** — resolves the version and the image base
   (`ghcr.io/<repository>`), and computes the tag sets. Validation-only runs push the
   version tags but never `:latest`.
2. **build-amd64** — builds and pushes `linux/amd64` from
   `docker/gpu/Dockerfile.optimized`. Tags: `…-cu128:<ver>` and the bare `…:<ver>` alias
   (plus `:latest` variants on real releases).
3. **build-jetson** — builds and pushes `linux/arm64` from `docker/jetson/Dockerfile`
   (gated on `publish_jetson`). Tag: `…-jetson:<ver>` (+ `:latest`). Runs on an arm64
   runner.
4. **smoke-amd64** — pulls the just-pushed cu128 image and asserts the runtime contract on
   CPU: `/health` answers quickly (warming|healthy), `/ready` flips within ~300s, bearer
   auth returns 401 then 200, and `POST /v1/audio/speech` returns a real WAV.
5. **publish-chart** — `helm package charts/kokoro-server` with `--version`/`--app-version`
   set to the release version, then `helm push` to
   `oci://ghcr.io/forgeguard-ai/charts`.
6. **create-release** — composes the release notes (docker pull + helm install commands)
   and creates/updates the GitHub Release with the `gh` CLI.

## Image and chart coordinates

- amd64: `ghcr.io/forgeguard-ai/kokoro-server-cu128:<ver>` and the alias
  `ghcr.io/forgeguard-ai/kokoro-server:<ver>` (+ `:latest` on releases).
- Jetson: `ghcr.io/forgeguard-ai/kokoro-server-jetson:<ver>` (+ `:latest`).
- Helm chart: `oci://ghcr.io/forgeguard-ai/charts/kokoro-server`, version `<ver>`.

## Org Actions policy

The organization's Actions policy allows only **GitHub-authored and verified-creator**
actions. Two consequences:

- The release step uses the `gh` CLI rather than a Marketplace release action.
- New workflows must avoid arbitrary third-party actions. The documentation validation
  workflow (`.github/workflows/docs-validate.yml`) follows this rule: it uses only
  `actions/checkout` (pinned to a commit SHA) plus a checked-in Python validator
  (`scripts/docs/validate_docs.py`), with no third-party Marketplace actions.

## Versioning

The repository follows semantic versioning; `VERSION`, `pyproject.toml`, the chart
`version`/`appVersion`, and the web `package.json` are kept in lockstep (see
`scripts/update_version.py`). Update `CHANGELOG.md` for each release.

## Cutting a release

1. Bump the version across the tracked files and update `CHANGELOG.md`.
2. Merge to `main`.
3. Push a `v<version>` tag (or run the workflow with `validate_only: true` first to dry-run
   the build + smoke test without publishing `:latest` or a Release).
