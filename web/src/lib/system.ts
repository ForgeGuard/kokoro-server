import { api } from './apiClient'

/**
 * Live system telemetry from the server's open `/system` endpoint (same
 * auth posture as `/health`: no key required). Powers the GPU + activity
 * monitor. Every field is best-effort — `gpu` is null on CPU-only hosts and
 * individual GPU metrics are optional depending on the driver/NVML.
 */

export interface GpuInfo {
  name: string
  memory_used_bytes: number
  memory_total_bytes: number
  utilization_pct?: number
  memory_utilization_pct?: number
  temperature_c?: number
  power_w?: number
  power_limit_w?: number
}

export interface ActivityInfo {
  active: number
  waiting: number
}

export interface ModelMeta {
  device?: string
  backend?: string
  voicepack_count?: number
}

export interface SystemInfo {
  version: string
  status: string
  gpu: GpuInfo | null
  activity: ActivityInfo
  model: ModelMeta
}

/** Fetch `/system`; returns null on any error so the monitor can hide quietly. */
export async function fetchSystemInfo(): Promise<SystemInfo | null> {
  try {
    const url = await api.apiUrl('/system')
    const res = await fetch(url, { headers: { Accept: 'application/json' } })
    if (!res.ok) return null
    return (await res.json()) as SystemInfo
  } catch {
    return null
  }
}
