"""Live GPU + request-activity telemetry for the ``/system`` endpoint.

Memory always comes from torch; utilization/temperature/power are added via
NVML (``nvidia-ml-py`` / ``pynvml``) when installed. Every metric is
best-effort: a missing dependency or a driver that omits one field degrades
gracefully rather than failing the whole endpoint, so this stays safe to call
on CPU-only or mock deployments.
"""

from __future__ import annotations

from typing import Any, Optional


def gpu_info() -> Optional[dict[str, Any]]:
    """Live GPU telemetry, or None when torch/CUDA isn't present (CPU/mock).

    Memory always comes from torch; utilization/temperature/power are added via
    NVML when ``nvidia-ml-py`` is installed (each metric is best-effort so a
    driver that omits one doesn't drop the rest).
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info(0)
    except Exception:  # torch missing, driver error, etc. — GPU info is optional
        return None

    info: dict[str, Any] = {
        "name": torch.cuda.get_device_name(0),
        "memory_used_bytes": int(total - free),
        "memory_total_bytes": int(total),
    }
    _add_nvml_metrics(info)
    return info


def _add_nvml_metrics(info: dict[str, Any]) -> None:
    """Best-effort utilization/temperature/power via NVML (optional dependency)."""
    try:
        import pynvml
    except ImportError:
        return
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            info["utilization_pct"] = int(util.gpu)
            info["memory_utilization_pct"] = int(util.memory)
        except Exception:
            pass
        try:
            info["temperature_c"] = int(
                pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            )
        except Exception:
            pass
        try:
            info["power_w"] = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
        except Exception:
            pass
        try:
            info["power_limit_w"] = round(
                pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000, 1
            )
        except Exception:
            pass
    except Exception:  # NVML unavailable (no driver in this ns) — memory-only is fine
        return
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def activity_info() -> dict[str, int]:
    """Live request activity: in-flight generations and queue depth.

    ``active`` is the number of generations currently using the backend
    (tracked by ``ModelManager``). Kokoro serves without a bounded waiting
    queue, so ``waiting`` is always 0 today; the field is kept for parity with
    the other ForgeGuard servers and so the web monitor renders identically.
    """
    active = 0
    try:
        from ..inference.model_manager import ModelManager

        instance = ModelManager._instance
        if instance is not None:
            active = max(0, int(instance.inflight))
    except Exception:  # never let telemetry break the status endpoint
        active = 0
    return {"active": active, "waiting": 0}
