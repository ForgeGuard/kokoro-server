---
title: Audio formats
description: WAV duration quirks, PCM playback, and reading exact durations.
order: 20
status: stable
---

# Audio formats

## WAV duration reported as nonsense in some readers

Streamed WAV responses are produced by an incremental encoder. Because the total size is
not known until the stream ends, the RIFF size fields are not back-patched the way a
fully buffered file's would be, and a streamed WAV finalizes without rewriting them.

Most tools handle this fine (soundfile, pydub/ffmpeg, browsers, OS players). Python's
standard-library `wave` module does not, and may report a wrong duration or fail to read
the length.

To get an exact duration, use a robust reader:

```python
import soundfile as sf
print(sf.info("speech.wav").duration)
```

Or on the command line:

```bash
ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 speech.wav
```

If you specifically need a WAV with fully correct header sizes, request it non-streamed
(`"stream": false`), which returns a complete file, or transcode with `ffmpeg`.

## Playing raw PCM

`pcm` output is raw signed 16-bit little-endian, 24 kHz, mono, with no header. Players
need those parameters supplied explicitly:

```bash
ffplay -f s16le -ar 24000 -ch_layout mono speech.pcm
```

In code, wrap it in a WAV header or feed it to an audio device configured for
`paInt16 / 24000 Hz / mono`. See
[Streaming and audio formats](../concepts/streaming-and-audio-formats.md).

## Choosing a format

- **Streaming to a player incrementally** → `pcm` (simplest) or `mp3`.
- **A self-contained file** → `mp3`, `flac`, or non-streamed `wav`.
- **Smallest lossy size** → `opus`.
- **Lossless archival** → `flac`.

`aac` is accepted by the request schema but is not currently produced; use one of the
formats above.
