# Security

Operator-facing notes on the server's security posture. The defaults are
conservative and fully offline; loosen them deliberately.

## Authentication

- `API_KEY` — optional bearer key for `/v1`, `/dev`, and `/debug`. **Empty
  disables auth** (open server), matching the original behavior.
- When set, protected endpoints require `Authorization: Bearer <API_KEY>`;
  comparison is constant-time and a bad/missing key returns `401` with
  `WWW-Authenticate: Bearer`.
- `/health`, `/ready`, `/system`, and the `/web` console **never require auth**:
  orchestrators probe `/health` before any key is known, Kubernetes probes
  cannot send bearer headers, and the web monitor polls `/system` (which exposes
  only version, model state, and GPU/activity telemetry — no secrets).

## Transport (built-in TLS)

- With `TLS_ENABLED=true` the server speaks HTTPS directly via uvicorn — no
  reverse proxy or extra container. If no certificate is supplied and
  `TLS_SELF_SIGNED=true` (default), a **self-signed** cert is generated on first
  run and persisted under `{OUTPUT_DIR}/tls` (key mode `0600`), so restarts
  reuse it.
- Cert generation is fully local and offline (the `cryptography` library); RSA
  2048, ~10-year validity, with SANs for `TLS_CN`, `localhost`, `127.0.0.1`,
  `::1`, and any `TLS_SAN` entries.
- Self-signed certs trigger a browser "not trusted" warning — expected for
  local/self-hosted testing. For anything public, point `TLS_CERT_FILE` /
  `TLS_KEY_FILE` at a CA-issued cert, or terminate TLS at an ingress/proxy.

## Data handling

- **Text is not persisted by default.** The server synthesizes and streams audio
  back; it does not write a transcript store. Application logs do not record the
  full input text at the default log level.
- **Generated audio** is written only under `OUTPUT_DIR` (and short-lived files
  under the temp dir, garbage-collected by age/size/count). Mount these on a
  volume you control; nothing is uploaded anywhere.
- **No external calls by default.** The model and voices are baked into the
  image; `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, and `DO_NOT_TRACK=1`
  are set so nothing phones home. TLS cert generation is local.

## Container hardening

- Images run as a **non-root user** (uid 1001). Only the data/output directory
  (`/data` in the local compose, via `OUTPUT_DIR`) needs to be writable.
- The Helm chart sets `runAsNonRoot`, a matching `runAsUser`/`fsGroup`, drops
  all Linux capabilities, and disallows privilege escalation.
  `readOnlyRootFilesystem` is compatible with a writable data volume and can be
  enabled per environment.
- Model weights are baked in and SHA-256-verified at build; the entrypoint
  fails fast if a volume mount shadows them.

## Responsible use

TTS is synthetic-media generation. See [responsible-use.md](responsible-use.md)
for synthetic-media disclosure guidance and the provenance/watermarking roadmap
(C2PA, audio watermarking) to consider before making a deployment public.
