# Jetson (aarch64) image for Kokoro TTS.
#
# Unlike the faster-whisper Jetson image (which compiles CTranslate2 from source),
# Kokoro only needs PyTorch. On aarch64 the `gpu` extra resolves a JetPack-native
# torch build from the jetson-ai-lab wheel index, matched to this base image's
# CUDA 12.6 / cuDNN 9.3 stack (see pyproject.toml for why cu129 and pytorch.org
# builds don't work here). That build is compiled with Orin (sm_87) kernel
# support and links against the CUDA/cuDNN already provided by the l4t-jetpack
# base image below — it does NOT bundle its own CUDA runtime the way the
# generic pytorch.org aarch64 wheels do.
#
# IMPORTANT: L4T_JETPACK_TAG must be compatible with the host's JetPack/L4T release.
# Check the host with:  cat /etc/nv_tegra_release
# NVIDIA container images are compatible across minor revisions of the same major
# L4T line (an r36.4.0 container is expected to run on any R36.x host) but not
# across major lines (R35 vs R36). Adjust the default below if it stops matching.
ARG L4T_JETPACK_TAG=r36.4.0

# Stage 0: Build the web console (Vite/React) into static assets.
FROM node:22-slim AS webbuild
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build          # emits /web/dist

# Stage 1: Runtime on the L4T JetPack base.
FROM nvcr.io/nvidia/l4t-jetpack:${L4T_JETPACK_TAG}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        python3.10 python3.10-venv python3-dev \
        espeak-ng espeak-ng-data libsndfile1 ffmpeg git curl \
        libopenblas0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/ && \
    mv /root/.local/bin/uvx /usr/local/bin/ && \
    mkdir -p /usr/share/espeak-ng-data && \
    ln -s /usr/lib/*/espeak-ng-data/* /usr/share/espeak-ng-data/ 2>/dev/null || true && \
    useradd -m -u 1001 appuser

WORKDIR /app

ENV UV_HTTP_TIMEOUT=120 UV_HTTP_RETRIES=3

# Resolve dependencies with the GPU extra (aarch64 -> jetson-ai-lab jp6/cu126 torch).
COPY pyproject.toml ./pyproject.toml
RUN uv venv --python 3.10 && \
    uv sync --extra gpu --no-cache --no-install-project && \
    # nvidia-cudss-cu12 transitively pulls nvidia-cublas-cu12 (a CUDA 12.9
    # cuBLAS). PyTorch preloads that pip cuBLAS from site-packages ahead of the
    # base image's system cuBLAS 12.6, and the 12.9 build fails on this JetPack
    # 6 CUDA 12.6 driver with "CUBLAS_STATUS_ALLOC_FAILED when calling
    # cublasCreate(handle)". Remove it so torch falls back to the system
    # cuBLAS 12.6 (cuDSS itself resolves cuBLAS from the system libs fine).
    uv pip uninstall --python /app/.venv/bin/python nvidia-cublas-cu12

# Download the model (present at runtime too for entrypoint re-downloads).
COPY --chown=appuser:appuser docker/scripts/download_model.py ./download_model.py
ARG DOWNLOAD_MODEL=true
RUN if [ "$DOWNLOAD_MODEL" = "true" ]; then \
        /app/.venv/bin/python download_model.py --output api/src/models/v1_0; \
    fi

# Japanese support (UniDic dictionary). Set --build-arg INCLUDE_JAPANESE=false to skip.
ARG INCLUDE_JAPANESE=true
RUN if [ "$INCLUDE_JAPANESE" = "true" ]; then \
        /app/.venv/bin/python -m unidic download; \
    fi

# Application code + built web console.
COPY --chown=appuser:appuser api ./api
COPY --from=webbuild --chown=appuser:appuser /web/dist ./web
COPY --chown=appuser:appuser VERSION ./VERSION
COPY --chown=appuser:appuser docker/scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh && chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/api \
    UV_LINK_MODE=copy \
    USE_GPU=true \
    PHONEMIZER_ESPEAK_PATH=/usr/bin \
    PHONEMIZER_ESPEAK_DATA=/usr/share/espeak-ng-data \
    ESPEAK_DATA_PATH=/usr/share/espeak-ng-data \
    DEVICE="gpu" \
    LD_LIBRARY_PATH="/app/.venv/lib/python3.10/site-packages/nvidia/cu12/lib:${LD_LIBRARY_PATH}"

CMD ["./entrypoint.sh"]
