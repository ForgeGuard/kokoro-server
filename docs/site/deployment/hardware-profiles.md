---
title: Hardware profiles
description: Supported GPUs, the Jetson image, and CPU fallback.
order: 40
status: stable
---

# Hardware profiles

The server is published as two images. Match the image to your hardware.

## NVIDIA x86_64 (CUDA cu128)

`ghcr.io/forgeguard-ai/kokoro-server:latest` (alias `kokoro-server-cu128`).

- **Supported.** Built on CUDA 12.8 with cuDNN. The cu128 PyTorch wheels carry kernels
  for compute capabilities sm_86 through sm_120 — that is NVIDIA **RTX 3000 (Ampere)
  through RTX 5000 (Blackwell)** in a single image, plus datacenter GPUs in that range.
- Runs as a container with `--gpus all`. Also runs on CPU with `USE_GPU=false`.

## NVIDIA Jetson Orin (arm64, JetPack 6)

`ghcr.io/forgeguard-ai/kokoro-server-jetson:latest`.

- **Supported** on Jetson Orin (compute capability sm_87) running **JetPack 6 / L4T
  r36** (CUDA 12.6, cuDNN 9.3). Confirm your L4T version with
  `cat /etc/nv_tegra_release`.
- Launch with the NVIDIA runtime:

  ```bash
  docker run -d --name kokoro --runtime nvidia -p 8880:8880 \
    ghcr.io/forgeguard-ai/kokoro-server-jetson:latest
  ```

- The Jetson image pins its CUDA math libraries to the JetPack 6 toolkit to avoid a
  cuBLAS version conflict; use the Jetson image (not the cu128 image) on these devices.

## CPU

- **Supported, reduced throughput.** The cu128 image runs on CPU with `USE_GPU=false`.
  Expect substantially slower synthesis than on a GPU. Useful for CI, development, and
  low-volume use.

## AMD (ROCm) and Intel

- **Planned, not currently supported.** Tracked on the roadmap; do not treat these as
  available today.

## Compatibility at a glance

| Target | Status | Notes |
|---|---|---|
| NVIDIA RTX 3000 → 5000 (x86_64, CUDA cu128) | Supported | Single cu128 image (sm_86–sm_120). |
| NVIDIA datacenter GPUs in that range | Supported | Same cu128 image. |
| NVIDIA Jetson Orin (arm64) | Supported | JetPack 6 / L4T r36; use the Jetson image. |
| CPU (x86_64) | Supported | `USE_GPU=false`; reduced throughput. |
| Apple Silicon (MPS) | Experimental | Auto-detected for local runs; not a published container target. |
| AMD (ROCm), Intel | Planned | Not currently supported. |

See [Compatibility](../reference/compatibility.md) for API and version details.
