#!/bin/bash
set -e

if [ "$DOWNLOAD_MODEL" = "true" ]; then
    python download_model.py --output api/src/models/v1_0
fi

# Preflight: the model weights are baked into the image at build time. If they
# are missing here (and we weren't asked to download them), something is
# shadowing them — most likely a volume mount over /app/api.
if [ "$DOWNLOAD_MODEL" != "true" ] && [ ! -f "/app/api/src/models/v1_0/kokoro-v1_0.pth" ]; then
    echo "ERROR: model weights not found at /app/api/src/models/v1_0/kokoro-v1_0.pth." >&2
    echo "The weights are baked into the image at build time, so if they are missing" >&2
    echo "a volume mount over /app/api is most likely shadowing them (e.g. a" >&2
    echo "'../../api:/app/api' bind mount in docker-compose)." >&2
    echo "Fix: remove the mount over /app/api, or set DOWNLOAD_MODEL=true to" >&2
    echo "download the weights at container start." >&2
    exit 1
fi

exec uv run --extra "${DEVICE:?DEVICE must be set to 'gpu' or 'cpu'}" --no-sync python -m uvicorn api.src.main:app --host 0.0.0.0 --port 8880 --log-level "${UVICORN_LOG_LEVEL:-info}"
