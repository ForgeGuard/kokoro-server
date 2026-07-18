---
title: Responsible use
description: Synthetic-media disclosure guidance, operator responsibilities, and provenance roadmap.
order: 30
status: stable
---

# Responsible use and synthetic-media disclosure

This server turns text into natural-sounding speech. That is genuinely useful
(accessibility, narration, localization, personal projects) and, like any
speech-synthesis tool, carries real potential for misuse (impersonation, fraud,
non-consensual "voice-alike" content, disinformation). This page records how to use
it responsibly and a roadmap of provenance safeguards to consider before a deployment
is made public.

> This is engineering documentation, not legal advice. Laws governing synthetic media,
> the right of publicity, impersonation, and disclosure vary by jurisdiction and change
> quickly. Consult a qualified attorney for your situation before deploying publicly.

## Why this matters

Kokoro ships a fixed set of *designed* voices — it does not clone a specific real
person from a sample, which meaningfully lowers impersonation risk compared with a
voice-cloning system. It does not eliminate it: synthesized speech can still be used to
deceive, and a generic voice can be misrepresented as a real, identifiable person.

Across many jurisdictions, a few themes recur and are a reasonable baseline regardless
of where you operate:

- **A person's voice can be a protected attribute.** Passing synthetic speech off as a
  real, identifiable individual can create legal exposure even without cloning that
  person's voice.
- **Deceptive or impersonating use is broadly regulated.** Consumer-protection,
  anti-fraud, telecommunications, and identity-theft rules can all apply to synthetic
  voice used to deceive.
- **Disclosure norms are tightening.** A growing number of platforms and regulators
  expect AI-generated media to be disclosed as such.

The practical takeaway: **disclose synthetic speech as synthetic**, and never represent
it as a real, identifiable individual without their consent.

## What the software does today

- **Designed voices only.** There is no reference-audio upload or cloning path, so the
  server cannot mint a likeness of an arbitrary real person from a sample.
- **Operator controls.** An optional `API_KEY` gates the synthesis API; the web console
  and health endpoints stay open by design. Nothing reaches an external service by
  default — the model and voices are offline, and TLS certificate generation is local.
- **No hidden retention.** The server does not persist request text as a matter of
  course; generated audio is written only where the operator points `OUTPUT_DIR`. See
  [Security hardening](../operations/security-hardening.md) for data-handling detail.

## Operator responsibilities

If you expose this server beyond personal use, take ownership of:

- **Consent** — do not synthesize a real, identifiable person's voice or persona
  without their permission.
- **Disclosure** — label AI-generated audio as synthetic wherever it is published.
- **Access control** — set `API_KEY`, and place the server behind properly terminated
  TLS or an authenticated gateway.
- **Traceability** — keep enough operational logging to attribute abuse to an API key,
  without logging transcript text by default.

## Provenance roadmap

Ordered roughly by leverage-to-effort. None is a silver bullet; layered, they raise the
cost of misuse and improve traceability.

1. **Watermark every generated clip.** Embed an imperceptible, robust audio watermark in
   all output and ship the detector. The highest-value single addition.
2. **Provenance metadata (C2PA content credentials).** Attach signed
   "AI-generated with this tool" provenance to exported audio. Complements a watermark.
3. **Audible disclosure option.** A config to prepend or append a spoken
   "This voice is AI-generated" tag, on by default for public demo deployments.
4. **Acceptable-use policy and abuse pipeline.** A short AUP, an abuse/takedown contact,
   and a documented response process.
5. **Identity and accountability for API use.** Per-key ownership and rate limits; log
   which key produced how much audio (never the transcript text by default).

If a deployment goes public, a reasonable minimum bar is: watermarking (1) or C2PA
provenance (2), plus an AUP/abuse process (4), plus a clear synthetic-media disclosure
in the UI and docs.

## References

- [FTC — Preventing the Harms of AI-enabled Voice Cloning](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2023/11/preventing-harms-ai-enabled-voice-cloning)
- [C2PA — Coalition for Content Provenance and Authenticity](https://c2pa.org/)
- [Meta AudioSeal — audio watermarking](https://github.com/facebookresearch/audioseal)
