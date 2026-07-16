#!/bin/bash
set -e

# Local build helper. CI publishes images via .github/workflows/release.yml;
# this is for local/manual builds. Bake was removed in favor of two plain images.
#
# Usage: docker/build.sh [amd64|jetson] [tag]

VARIANT=${1:-amd64}
TAG=${2:-local}
REPO=${IMAGE_REPO:-ghcr.io/forgeguard-ai/kokoro-server}

case "$VARIANT" in
  amd64)
    echo "Building amd64 CUDA (cu128) image -> ${REPO}-cu128:${TAG}"
    docker build -f docker/gpu/Dockerfile.optimized -t "${REPO}-cu128:${TAG}" .
    ;;
  jetson)
    echo "Building Jetson (arm64) image -> ${REPO}-jetson:${TAG}"
    docker build -f docker/jetson/Dockerfile -t "${REPO}-jetson:${TAG}" .
    ;;
  *)
    echo "Unknown variant: $VARIANT (expected 'amd64' or 'jetson')" >&2
    exit 1
    ;;
esac

echo "Build complete."
