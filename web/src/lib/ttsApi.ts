import { api } from './apiClient'

/** Supported output formats — single source of truth for the AudioFormat type. */
export const AUDIO_FORMATS = ['mp3', 'wav', 'opus', 'flac', 'aac', 'pcm'] as const
export type AudioFormat = (typeof AUDIO_FORMATS)[number]

export interface SpeechRequest {
  model: string
  input: string
  voice: string
  response_format: AudioFormat
  speed: number
  stream: boolean
}

interface VoicesResponse {
  voices: Array<string | { id: string; name?: string }>
}

/** Fetch the available voice names. Handles both the object and legacy shapes. */
export async function fetchVoices(): Promise<string[]> {
  const data = await api.getJson<VoicesResponse>('/v1/audio/voices')
  const list = data.voices ?? []
  return list
    .map((v) => (typeof v === 'string' ? v : v.id))
    .filter((v): v is string => Boolean(v && v.trim()))
}

/** Generate speech (non-streaming) and return the audio Blob. */
export async function generateSpeech(req: {
  input: string
  voice: string
  format: AudioFormat
  speed: number
}): Promise<Blob> {
  const body: SpeechRequest = {
    model: 'kokoro',
    input: req.input,
    voice: req.voice,
    response_format: req.format,
    speed: req.speed,
    stream: false,
  }
  return api.postForBlob('/v1/audio/speech', body)
}
