import { useEffect, useRef, useState } from 'react'
import {
  fetchSystemInfo,
  type GpuInfo,
  type SystemInfo,
} from '../lib/system'

/**
 * Compact, theme-matched GPU + activity monitor. Polls the open `/system`
 * endpoint every ~3s and renders GPU utilization / VRAM / temperature / power
 * plus in-flight ("running") and queued request counts. Mirrors the GpuMonitor
 * in the sibling ForgeGuard consoles, adapted to this app's design tokens.
 *
 * Renders nothing until the first successful poll, so a CPU-only or offline
 * server simply shows no monitor rather than an error.
 */

function gb(n: number): string {
  return `${(n / 1e9).toFixed(1)} GB`
}

// Green under moderate load, amber as it fills, red when saturated — a quick
// read on how hard the GPU is working without parsing the numbers.
function loadColor(pct: number): string {
  if (pct >= 90) return 'bg-danger'
  if (pct >= 70) return 'bg-warning'
  return 'bg-success'
}

function Meter({
  label,
  value,
  pct,
}: {
  label: string
  value: string
  pct: number
}) {
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div className="min-w-[7rem] flex-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-faint">{label}</span>
        <span className="font-medium tabular-nums text-fg">{value}</span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full rounded-full transition-all ${loadColor(clamped)}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}

function GpuMeters({ gpu }: { gpu: GpuInfo }) {
  const memPct = (gpu.memory_used_bytes / gpu.memory_total_bytes) * 100
  return (
    <>
      {gpu.utilization_pct != null && (
        <Meter
          label="GPU"
          value={`${gpu.utilization_pct}%`}
          pct={gpu.utilization_pct}
        />
      )}
      <Meter
        label="VRAM"
        value={`${gb(gpu.memory_used_bytes)} / ${gb(gpu.memory_total_bytes)}`}
        pct={memPct}
      />
      {gpu.temperature_c != null && (
        <div className="text-xs text-faint">
          temp{' '}
          <span className="font-medium tabular-nums text-fg">
            {gpu.temperature_c}°C
          </span>
        </div>
      )}
      {gpu.power_w != null && (
        <div className="text-xs text-faint">
          power{' '}
          <span className="font-medium tabular-nums text-fg">
            {gpu.power_w}
            {gpu.power_limit_w != null ? ` / ${gpu.power_limit_w}` : ''} W
          </span>
        </div>
      )}
    </>
  )
}

function ActivityPill({ active, waiting }: { active: number; waiting: number }) {
  const busy = active > 0 || waiting > 0
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          busy ? 'animate-pulse bg-accent' : 'bg-faint/50'
        }`}
      />
      <span className="text-muted">
        {active} running{waiting > 0 ? ` · ${waiting} queued` : ''}
      </span>
    </div>
  )
}

export function GpuMonitor() {
  const [system, setSystem] = useState<SystemInfo | null>(null)
  // Keep a ref so the interval callback never closes over a stale setter.
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    let timer: number | undefined
    const poll = async () => {
      const info = await fetchSystemInfo()
      if (!aliveRef.current) return
      setSystem(info)
      timer = window.setTimeout(poll, 3000)
    }
    void poll()
    return () => {
      aliveRef.current = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [])

  // Nothing to show until the first successful poll.
  if (!system) return null

  const gpu = system.gpu
  const activity = system.activity ?? { active: 0, waiting: 0 }
  const model = system.model ?? {}

  return (
    <div className="rounded-xl border border-border bg-surface/60 px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-faint">
            Monitor
          </span>
          {gpu && (
            <span
              className="max-w-[10rem] truncate text-xs text-muted"
              title={gpu.name}
            >
              {gpu.name}
            </span>
          )}
        </div>
        {gpu ? (
          <GpuMeters gpu={gpu} />
        ) : (
          <span className="text-xs text-faint">CPU backend (no GPU)</span>
        )}
        <ActivityPill active={activity.active} waiting={activity.waiting} />
        {model.voicepack_count != null && model.voicepack_count > 0 && (
          <span className="text-xs text-faint">
            {model.voicepack_count} voices
            {model.device ? ` · ${model.device}` : ''}
          </span>
        )}
      </div>
    </div>
  )
}
