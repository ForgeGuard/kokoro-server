import { useCallback, useEffect, useRef, useState } from 'react'
import {
  DownloadIcon,
  IconButton,
  PauseIcon,
  PlayIcon,
  WaveIcon,
  cn,
} from '../../ui'

function formatTime(s: number): string {
  if (!isFinite(s) || s < 0) s = 0
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

/** Decode audio into a fixed number of normalized peak values for the waveform. */
async function computePeaks(blob: Blob, buckets = 128): Promise<number[] | null> {
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext
    if (!AudioCtx) return null
    const ctx = new AudioCtx()
    const arrayBuf = await blob.arrayBuffer()
    const audioBuf = await ctx.decodeAudioData(arrayBuf.slice(0))
    const data = audioBuf.getChannelData(0)
    const block = Math.floor(data.length / buckets) || 1
    const peaks: number[] = []
    let max = 0
    for (let i = 0; i < buckets; i++) {
      let sum = 0
      for (let j = 0; j < block; j++) {
        const v = data[i * block + j] || 0
        sum += v * v
      }
      const rms = Math.sqrt(sum / block)
      peaks.push(rms)
      if (rms > max) max = rms
    }
    void ctx.close()
    return peaks.map((p) => (max > 0 ? p / max : 0))
  } catch {
    return null
  }
}

export function AudioPlayer({
  blob,
  filename,
}: {
  blob: Blob
  filename: string
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [url, setUrl] = useState('')
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)
  const [peaks, setPeaks] = useState<number[] | null>(null)

  useEffect(() => {
    const objectUrl = URL.createObjectURL(blob)
    setUrl(objectUrl)
    setPeaks(null)
    setCurrent(0)
    setDuration(0)
    setPlaying(false)
    let alive = true
    computePeaks(blob).then((p) => {
      if (alive) setPeaks(p)
    })
    return () => {
      alive = false
      URL.revokeObjectURL(objectUrl)
    }
  }, [blob])

  const toggle = useCallback(() => {
    const el = audioRef.current
    if (!el) return
    if (el.paused) void el.play()
    else el.pause()
  }, [])

  const seekToFraction = useCallback(
    (frac: number) => {
      const el = audioRef.current
      if (!el || !isFinite(duration) || duration === 0) return
      el.currentTime = Math.min(duration, Math.max(0, frac * duration))
    },
    [duration],
  )

  const progress = duration > 0 ? current / duration : 0
  const activeBucket = Math.floor(progress * (peaks?.length ?? 0))

  return (
    <div className="rounded-2xl border border-border bg-surface-2/60 p-4">
      <audio
        ref={audioRef}
        src={url}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration
          setDuration(isFinite(d) ? d : 0)
        }}
      />
      <div className="flex items-center gap-4">
        <IconButton
          variant="accent"
          size="lg"
          aria-label={playing ? 'Pause' : 'Play'}
          onClick={toggle}
        >
          {playing ? <PauseIcon /> : <PlayIcon className="ml-0.5" />}
        </IconButton>

        <div className="min-w-0 flex-1">
          {/* Waveform / progress track — click or drag to seek */}
          <div
            role="slider"
            aria-label="Seek"
            aria-valuemin={0}
            aria-valuemax={Math.round(duration)}
            aria-valuenow={Math.round(current)}
            tabIndex={0}
            className="group relative flex h-14 cursor-pointer items-center gap-[2px] overflow-hidden"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect()
              seekToFraction((e.clientX - rect.left) / rect.width)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') seekToFraction((current + 5) / duration)
              if (e.key === 'ArrowLeft') seekToFraction((current - 5) / duration)
            }}
          >
            {peaks ? (
              peaks.map((p, i) => (
                <span
                  key={i}
                  className={cn(
                    'w-full flex-1 rounded-none transition-colors',
                    i <= activeBucket ? 'bg-accent' : 'bg-border-strong',
                  )}
                  style={{ height: `${Math.max(6, p * 100)}%` }}
                />
              ))
            ) : (
              // Fallback: simple progress bar when decoding is unavailable.
              <div className="relative h-2 w-full self-center overflow-hidden rounded-none bg-border-strong">
                <div
                  className="absolute inset-y-0 left-0 rounded-none bg-accent"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <span className="font-mono text-xs tabular-nums text-muted">
            {formatTime(current)} / {formatTime(duration)}
          </span>
          <a
            href={url}
            download={filename}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-border-strong hover:text-fg"
          >
            <DownloadIcon className="text-[1rem]" />
            Download
          </a>
        </div>
      </div>
      {!peaks && (
        <p className="mt-2 flex items-center gap-1.5 text-[0.7rem] text-faint">
          <WaveIcon className="text-[0.9rem]" />
          Waveform unavailable for this format — playback still works.
        </p>
      )}
    </div>
  )
}
