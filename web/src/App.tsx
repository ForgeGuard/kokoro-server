import { useCallback, useEffect, useMemo, useState } from 'react'
import { AppShell } from './components/AppShell'
import { SettingsDialog } from './components/SettingsDialog'
import { AudioPlayer } from './components/tts/AudioPlayer'
import {
  serializeVoices,
  VoicePicker,
  type VoiceSelection,
} from './components/tts/VoicePicker'
import { api, ApiError } from './lib/apiClient'
import {
  fetchServerStatus,
  isWarmingError,
  type ServerStatus,
} from './lib/health'
import {
  AUDIO_FORMATS,
  fetchVoices,
  generateSpeech,
  type AudioFormat,
} from './lib/ttsApi'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Field,
  KeyIcon,
  Select,
  Slider,
  Spinner,
  TextArea,
  WaveIcon,
  useToast,
} from './ui'

// Display labels for the formats defined in lib/ttsApi.ts (single source).
const FORMAT_LABELS: Record<AudioFormat, string> = {
  mp3: 'MP3',
  wav: 'WAV',
  opus: 'Opus',
  flac: 'FLAC',
  aac: 'AAC',
  pcm: 'PCM',
}

const FORMATS = AUDIO_FORMATS.map((value) => ({
  value,
  label: FORMAT_LABELS[value],
}))

const SAMPLE_TEXT =
  'The quick brown fox jumps over the lazy dog. Kokoro turns this text into natural speech.'

export default function App() {
  const toast = useToast()
  const [ready, setReady] = useState(false)
  const [serverStatus, setServerStatus] = useState<ServerStatus | 'connecting'>(
    'connecting',
  )
  const [version, setVersion] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  // True once the server has answered 401: auth is enabled and we lack a
  // valid key. Drives the inline "Enter API key" affordance.
  const [authRequired, setAuthRequired] = useState(false)

  const [voices, setVoices] = useState<string[]>([])
  const [selectedVoices, setSelectedVoices] = useState<VoiceSelection[]>([])
  const [text, setText] = useState(SAMPLE_TEXT)
  const [format, setFormat] = useState<AudioFormat>('mp3')
  const [speed, setSpeed] = useState(1)

  const [generating, setGenerating] = useState(false)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)

  const voiceString = useMemo(
    () => serializeVoices(selectedVoices),
    [selectedVoices],
  )
  const voiceLabel = useMemo(
    () => selectedVoices.map((s) => s.id).join(' + '),
    [selectedVoices],
  )

  // Reopen settings automatically on auth failure.
  useEffect(() => {
    return api.onUnauthorized(() => {
      setAuthRequired(true)
      setSettingsOpen(true)
      toast.error('Authentication required', 'Enter a valid API key to continue.')
    })
  }, [toast])

  const loadVoices = useCallback(async () => {
    try {
      const list = await fetchVoices()
      setAuthRequired(false) // an authenticated (or open) request succeeded
      setVoices(list)
      setSelectedVoices((cur) =>
        cur.length ? cur : list.length ? [{ id: list[0], weight: 1 }] : [],
      )
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      toast.error(
        'Could not load voices',
        err instanceof Error ? err.message : String(err),
      )
    }
  }, [toast])

  useEffect(() => {
    let alive = true
    api.init().then(() => {
      if (!alive) return
      setVersion(api.getVersion())
      setReady(true)
      void loadVoices()
    })
    return () => {
      alive = false
    }
  }, [loadVoices])

  // Track model warmup: poll /health until it reports healthy. Re-armed by
  // setting serverStatus back to 'warming' (e.g. on a model_warming 503).
  // 'failed' is NOT terminal: the container typically restarts, so keep
  // polling and flip back to healthy once the server recovers.
  useEffect(() => {
    if (serverStatus === 'healthy') return
    let alive = true
    let timer: number | undefined
    const poll = async () => {
      const { status, error } = await fetchServerStatus()
      if (!alive) return
      if (status === 'healthy') {
        if (serverStatus === 'warming' || serverStatus === 'failed') {
          toast.success('Model ready', 'Warmup complete.')
        }
        setServerStatus('healthy')
        return
      }
      if (status === 'failed' && serverStatus !== 'failed') {
        toast.error('Model failed to load', error ?? 'Check the server logs.')
      }
      setServerStatus(status) // 'warming' | 'unreachable' | 'failed'
      timer = window.setTimeout(poll, 3000)
    }
    void poll()
    return () => {
      alive = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [serverStatus, toast])

  const warming = serverStatus === 'warming' || serverStatus === 'connecting'
  const canGenerate =
    ready &&
    !generating &&
    serverStatus === 'healthy' &&
    text.trim().length > 0 &&
    selectedVoices.length > 0

  const onGenerate = async () => {
    if (!canGenerate) return
    setGenerating(true)
    try {
      const blob = await generateSpeech({
        input: text.trim(),
        voice: voiceString,
        format,
        speed,
      })
      setAudioBlob(blob)
      toast.success('Speech generated', `${voiceLabel} · ${format.toUpperCase()}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      if (err instanceof ApiError && err.status === 503 && isWarmingError(err.detail)) {
        // Model still warming — resume polling; the banner shows progress.
        setServerStatus('warming')
        toast.info('Model warming up', 'Hang tight — generation unlocks when it finishes.')
        return
      }
      toast.error(
        'Generation failed',
        err instanceof Error ? err.message : String(err),
      )
    } finally {
      setGenerating(false)
    }
  }

  const downloadName = useMemo(() => {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    const v = selectedVoices.map((s) => s.id).join('+') || 'speech'
    return `${v}_${stamp}.${format}`
  }, [selectedVoices, format])

  return (
    <AppShell
      title="ForgeGuard Kokoro Server"
      tagline="OpenAI-compatible text-to-speech console"
      mark={<WaveIcon />}
      version={version}
      onOpenSettings={() => setSettingsOpen(true)}
    >
      {warming && ready && (
        <div
          role="status"
          className="mb-6 flex animate-fade-in items-center gap-3 rounded-xl border border-border bg-accent-soft px-4 py-3 text-sm text-fg"
        >
          <Spinner />
          <div>
            <span className="font-medium">The speech model is warming up.</span>{' '}
            <span className="text-muted">
              This can take a little while on a cold start — generation unlocks
              automatically when it&apos;s ready.
            </span>
          </div>
        </div>
      )}
      {serverStatus === 'failed' && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-fg"
        >
          <span className="font-medium">The speech model failed to load.</span>{' '}
          <span className="text-muted">
            Check the server logs — the container usually restarts on its own.
          </span>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        {/* Main column */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader
              title="Input text"
              description="Enter the text you want to synthesize."
              action={
                <span className="text-xs tabular-nums text-faint">
                  {text.length} chars
                </span>
              }
            />
            <CardBody>
              <TextArea
                aria-label="Text to synthesize"
                rows={9}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type or paste text to convert to speech…"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  size="lg"
                  onClick={onGenerate}
                  disabled={!canGenerate}
                  loading={generating}
                >
                  {generating ? 'Generating…' : 'Generate speech'}
                </Button>
                {authRequired && (
                  <Button
                    size="lg"
                    variant="secondary"
                    onClick={() => setSettingsOpen(true)}
                  >
                    <KeyIcon />
                    Enter API key
                  </Button>
                )}
                {!ready && (
                  <span className="flex items-center gap-2 text-sm text-muted">
                    <Spinner /> Connecting…
                  </span>
                )}
                {text.trim().length === 0 && (
                  <span className="text-sm text-faint">Enter some text</span>
                )}
                {text.trim().length > 0 && selectedVoices.length === 0 && (
                  <span className="text-sm text-faint">Select a voice</span>
                )}
              </div>
            </CardBody>
          </Card>

          {audioBlob && (
            <Card>
              <CardHeader
                title="Output"
                description="Play, scrub, or download the generated audio."
              />
              <CardBody>
                <AudioPlayer blob={audioBlob} filename={downloadName} />
              </CardBody>
            </Card>
          )}
        </div>

        {/* Controls sidebar */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader title="Voices" />
            <CardBody>
              <VoicePicker
                voices={voices}
                selected={selectedVoices}
                onChange={setSelectedVoices}
                disabled={!ready}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Output options" />
            <CardBody className="space-y-5">
              <Field label="Format">
                {(id) => (
                  <Select
                    id={id}
                    value={format}
                    onChange={(e) =>
                      setFormat(e.target.value as AudioFormat)
                    }
                    options={FORMATS}
                  />
                )}
              </Field>
              <Field
                label="Speed"
                hint={`${speed.toFixed(2)}×`}
              >
                {(id) => (
                  <Slider
                    id={id}
                    min={0.25}
                    max={4}
                    step={0.05}
                    value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  />
                )}
              </Field>
              <div className="flex justify-between text-[0.7rem] text-faint">
                <span>0.25×</span>
                <button
                  type="button"
                  className="text-muted hover:text-accent"
                  onClick={() => setSpeed(1)}
                >
                  reset
                </button>
                <span>4×</span>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      <SettingsDialog
        open={settingsOpen}
        onClose={() => {
          setSettingsOpen(false)
          // Retry with the (possibly new) key so the console recovers
          // without a manual refresh.
          if (authRequired) void loadVoices()
        }}
      />
    </AppShell>
  )
}
