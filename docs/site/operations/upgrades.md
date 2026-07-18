---
title: Upgrades
description: Image tags, versioning, and upgrading containers and the Helm chart.
order: 40
status: stable
---

# Upgrades

## Tags and versioning

Images and the chart follow semantic versioning. Two tag styles are published:

- **`latest`** tracks the newest stable release and may change without notice.
- **Version tags** (for example `1.1.0`) are immutable pointers to a specific release.

For persistent or production deployments, **pin a version tag** rather than `latest`, so
a redeploy cannot silently move to a new version.

## Upgrading a container / Compose

Pull the new tag and recreate:

```bash
docker pull ghcr.io/forgeguard-ai/kokoro-server:1.1.0
docker compose -f docker/gpu/docker-compose.prod.yml up -d
```

Because model weights are baked into the image, an upgrade is just a new image — there is
no separate migration step. Generated audio under a mounted `OUTPUT_DIR` is unaffected.

## Upgrading the Helm release

```bash
helm upgrade kokoro \
  oci://ghcr.io/forgeguard-ai/charts/kokoro-server --version 1.1.0
```

Review the [CHANGELOG](https://github.com/forgeguard-ai/kokoro-server/blob/main/CHANGELOG.md)
for changed values or defaults before upgrading.

### Migrating from the `kokoro-fastapi` chart

The chart was **renamed from `kokoro-fastapi` to `kokoro-server` in 1.1.0**, and its
selector labels changed. Helm cannot upgrade across the immutable selector change in
place. Migrate by installing fresh:

```bash
helm uninstall kokoro-fastapi   # remove the old release
helm install kokoro oci://ghcr.io/forgeguard-ai/charts/kokoro-server --version 1.1.0
```

There is no persistent server state to preserve across this change (audio output is
ephemeral unless you mounted your own volume).

## Verifying an upgrade

```bash
curl -s http://localhost:8880/system | grep -o '"version":"[^"]*"'
curl --fail http://localhost:8880/ready
```

Confirm the reported version matches the tag you deployed and that `/ready` returns `200`
after warmup. See [Health and readiness](./health-and-readiness.md).
