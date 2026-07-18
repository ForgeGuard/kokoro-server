# Streaming audio writer

A maintainer note on `StreamingAudioWriter`
(`api/src/services/streaming_audio_writer.py`), which encodes synthesized audio frames
into the wire format. This describes the current implementation.

## Encoder

Encoding is done with **PyAV** (`av`), not soundfile or pydub. `__init__` accepts a
format and, for every non-PCM format, opens an in-memory PyAV container over a `BytesIO`
and adds a single audio stream using this codec map:

| Format | Container | Codec | Bit rate |
|---|---|---|---|
| `wav` | `wav` | `pcm_s16le` | n/a |
| `flac` | `flac` | `flac` | n/a |
| `mp3` | `mp3` | `mp3` | 128 kbps |
| `opus` | `opus` | `libopus` | 128 kbps |
| `aac` | `adts` | `aac` | 128 kbps |
| `pcm` | *(none)* | raw | n/a |

Any other format raises `ValueError("Unsupported format: ...")`. Note that although the
writer can encode `aac`, it is excluded from the supported set at the request-schema
level, so the public API does not produce it.

> The module still imports `soundfile` and `pydub`, but they are not used by the current
> PyAV-based implementation — a safe cleanup opportunity.

Format-specific details:

- **MP3** sets the container option `write_xing: "0"` to disable the Xing VBR header,
  which fixed iOS timeline-reading issues.
- **AAC** is muxed into an `adts` container.
- **PCM** has no container at all.

## Writing chunks

`write_chunk(audio_data, finalize=False)` returns the bytes produced for that call:

- **PCM** returns `audio_data.tobytes()` directly — raw signed 16-bit little-endian, no
  header.
- **Everything else** builds an `s16` `AudioFrame` (mono/stereo per `channels`), assigns
  monotonically increasing `pts`, encodes it through the stream, muxes the packets, then
  reads and **truncates** the shared output buffer so each call returns only the newly
  produced bytes.
- Empty or `None` input returns `b""`.

## Finalizing

On `finalize=True` (non-PCM): the stream encoder is flushed (`stream.encode(None)`), the
container is closed (which writes the trailer — for Ogg/Opus the final page is only
written on close), and the buffered bytes are returned.

**WAV is a special case.** Closing the container performs a seek-and-patch on the RIFF
size fields, but because the streaming buffer is truncated after every chunk, that patch
lands roughly 78 bytes of size-field junk in the truncated buffer. Decoded as samples
that is an audible click at the end of the clip, so WAV finalize returns `b""` (see issue
#463). The practical consequence for clients is that streamed WAV size fields are not
authoritative — documented for users in
[Troubleshooting: audio formats](../../site/troubleshooting/audio-formats.md).

## Lifecycle

`close()` closes the container and buffer. Routers always call `writer.close()` in a
`finally` block, so a failed request cannot leak the encoder. The shared
[`map_speech_exception`](../../site/reference/openai-api.md) error mapper also closes the
writer before translating an exception to an HTTP error.
