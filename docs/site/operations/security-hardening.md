---
title: Security hardening
description: Authentication, transport security, data handling, and container posture.
order: 30
status: stable
---

# Security hardening

Operator-facing notes on the server's security posture. The defaults are conservative
and fully offline, but they are **not "secure" in the abstract**: authentication is off
until you set `API_KEY`, and several endpoints are intentionally open. Harden
deliberately for your environment.

## Authentication

- `API_KEY` is an optional bearer key for `/v1`, `/dev`, and `/debug`. **Leaving it unset
  disables auth** (an open server), matching the original behavior.
- When set, protected endpoints require `Authorization: Bearer <API_KEY>`. The comparison
  is constant-time, and a missing or bad key returns `401` with `WWW-Authenticate: Bearer`.
- `/health`, `/ready`, `/system`, and the `/web` console **never require auth**:
  orchestrators probe `/health` before any key is known, Kubernetes probes cannot send
  bearer headers, and the console polls `/system` (which exposes only version, model
  state, and GPU/activity telemetry — no secrets).

For anything beyond local use, set `API_KEY`. Treat it as a secret: inject it from a
Kubernetes Secret (`kokoroTTS.apiKey.existingSecret`) or your platform's secret store,
not a plaintext manifest.

## Transport (built-in TLS)

- With `TLS_ENABLED=true` the server speaks HTTPS directly via uvicorn — no reverse proxy
  or extra container. If no certificate is supplied and `TLS_SELF_SIGNED=true` (default),
  a self-signed certificate is generated on first run and persisted under
  `{OUTPUT_DIR}/tls` (the private key is written with mode `0600`), so restarts reuse it.
- Certificate generation is fully local and offline (the `cryptography` library): RSA
  2048, SHA-256, ~10-year validity (3650 days), with SANs for `TLS_CN`, `localhost`,
  `127.0.0.1`, `::1`, and any `TLS_SAN` entries.

### Local self-signed vs. public deployments

- **Local / self-hosted testing** — a self-signed certificate is appropriate. Browsers
  will show a "not trusted" warning; that is expected.
- **Public or shared deployments** — a self-signed certificate is **not appropriate**.
  Point `TLS_CERT_FILE` / `TLS_KEY_FILE` at a CA-issued certificate, or terminate TLS at
  an ingress or reverse proxy (see [Kubernetes](../deployment/kubernetes.md#ingress-and-tls)).

## Data handling

- **Text is not persisted by default.** The server synthesizes and streams audio back; it
  does not keep a transcript store. At the default log level, application logs do not
  record full input text.
- **Generated audio** is written only under `OUTPUT_DIR` (and short-lived files under the
  temp directory, garbage-collected by age/size/count). Mount these on a volume you
  control; nothing is uploaded anywhere.
- **No external calls by default.** The model and voices are baked into the image, and
  `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, and `DO_NOT_TRACK=1` are set so
  nothing phones home. TLS certificate generation is local.

## Container hardening

- Images run as a **non-root user (uid 1001)**. Only the data/output directory (via
  `OUTPUT_DIR`, e.g. `/data` in the local Compose file) needs to be writable.
- The Helm chart sets `runAsNonRoot`, a matching `runAsUser`/`fsGroup` (1001), drops all
  Linux capabilities, and disallows privilege escalation. `readOnlyRootFilesystem` is
  compatible with a writable data volume and can be enabled per environment.
- Model weights are baked in and SHA-256-verified at build; the entrypoint fails fast if
  a volume mount shadows them.

## Reporting vulnerabilities

Do not report suspected vulnerabilities through a public issue. Follow the instructions
in the repository
[`SECURITY.md`](https://github.com/forgeguard-ai/kokoro-server/blob/main/SECURITY.md).

## Responsible use

Text-to-speech is synthetic-media generation. See
[Responsible use](../concepts/responsible-use.md) for synthetic-media disclosure guidance
and the provenance/watermarking roadmap to consider before making a deployment public.
