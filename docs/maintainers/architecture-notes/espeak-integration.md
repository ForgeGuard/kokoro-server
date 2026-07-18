# espeak-ng integration

A maintainer note on how grapheme-to-phoneme (G2P) is wired, why the Dockerfiles set the
espeak environment variables they do, and the historical issue this resolved. This
reflects the current implementation; it is not an open incident.

## How G2P is wired today

The phonemizer stack is provided transitively through `misaki`:

```
kokoro -> misaki -> phonemizer-fork + espeakng-loader
```

Relevant pinned dependencies (`pyproject.toml`): `kokoro==0.9.4`,
`misaki[en,ja,ko,zh]==0.9.4`, `phonemizer-fork>=3.3.2`, and `espeakng-loader==0.2.4`.
There is **no direct `phonemizer==3.3.0` dependency** — that older pin was removed, since
it conflicted with the fork that `misaki` now uses.

The runtime images install the system `espeak-ng` and `espeak-ng-data` packages and point
the phonemizer at them explicitly. Both `Dockerfile.optimized` (amd64/cu128) and the
Jetson `Dockerfile` set:

```dockerfile
ENV PHONEMIZER_ESPEAK_PATH=/usr/bin \
    PHONEMIZER_ESPEAK_DATA=/usr/share/espeak-ng-data \
    ESPEAK_DATA_PATH=/usr/share/espeak-ng-data
```

`ESPEAK_DATA_PATH` is what `espeakng-loader` reads; pinning it to the distro's
`espeak-ng-data` avoids the loader looking inside its own package directory (which is
what produced the historical `phontab: No such file or directory` error).

## Pipeline management

Language pipelines are created and cached by the Kokoro backend rather than constructed
ad hoc. Code that needs a pipeline calls `backend._get_pipeline(lang_code)`
(`api/src/inference/kokoro_v1.py`), which lazily builds and caches a `KPipeline` per
language code. Constructing `KPipeline(...)` directly is avoided — doing so previously
caused an "object is in an invalid state" error from device/pipeline mismatch. Language
codes are resolved by `_resolve_lang_code` (explicit `lang_code` → default voice code →
first letter of the voice name).

## Verifying in an image

```bash
echo "$ESPEAK_DATA_PATH"          # /usr/share/espeak-ng-data
echo "$PHONEMIZER_ESPEAK_DATA"    # /usr/share/espeak-ng-data
ls /usr/share/espeak-ng-data      # phontab and friends present
```

A quick functional check is to call `POST /dev/phonemize` and confirm phonemes come back
for `en-us` (`{"text":"Hello world!","language":"a"}`).

## If this regresses

- Keep G2P dependencies transitive through `misaki`; do not re-add a direct `phonemizer`
  pin.
- Keep the three espeak `ENV` lines in both Dockerfiles in sync when changing base images.
- Go through `backend._get_pipeline(...)` for pipeline creation.
