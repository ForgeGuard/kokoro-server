# Responsible use & synthetic-media disclosure

This server turns text into natural-sounding speech. That is genuinely useful
(accessibility, narration, localization, personal projects) and, like any
speech-synthesis tool, carries real potential for misuse (impersonation,
fraud, non-consensual "voice-alike" content, disinformation). This document
records how to use it responsibly and a roadmap of provenance safeguards to add
before a deployment is made public.

> This is engineering documentation, not legal advice. Laws vary by jurisdiction
> and change quickly; consult a qualified attorney for your situation.

## Why this matters (the landscape)

Kokoro ships a fixed set of *designed* voices — it does not clone a specific
real person from a sample, which meaningfully lowers the impersonation risk
compared with a voice-cloning system. It does not, however, eliminate it:
synthesized speech can still be used to deceive, and a "generic" voice can be
represented as a real person's.

- **Right of publicity / voice as a protected attribute.** Tennessee's
  [ELVIS Act](https://en.wikipedia.org/wiki/ELVIS_Act) (2024) makes a person's
  *voice* a protected personal right; several US states have overlapping
  right-of-publicity / digital-replica laws. Passing synthetic speech off as a
  real, identifiable person can be actionable even without cloning their voice.
- **Deceptive / impersonating use.** The FTC treats deceptive voice generation
  as an unfair/deceptive practice under §5 and its
  [impersonation rule](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2023/11/preventing-harms-ai-enabled-voice-cloning);
  synthetic voice in a robocall is illegal under the TCPA; fraud/identity-theft
  statutes and the 2025 TAKE IT DOWN Act reach the worst cases criminally.
- **Platform & disclosure norms.** A growing number of platforms and
  jurisdictions require that AI-generated media be **disclosed as such**.

The practical takeaway: **disclose synthetic speech as synthetic**, and never
represent it as a real, identifiable individual without their consent.

## What the software does today

- **Designed voices only.** No reference-audio upload / cloning path exists, so
  the server cannot mint a likeness of an arbitrary real person from a sample.
- **Operator controls.** Optional `API_KEY` gates the synthesis API; the web
  console and health endpoints stay open by design. Nothing reaches an external
  service by default (offline model, offline TLS cert generation).
- **No hidden retention.** The server does not persist request text as a matter
  of course; generated audio is written only where the operator points
  `OUTPUT_DIR`. See [security.md](security.md) for the data-handling detail.

## Ideas to harden further (roadmap / open to feedback)

Ordered roughly by leverage-to-effort. None is a silver bullet; layered, they
raise the cost of misuse and improve traceability.

1. **Watermark every generated clip.** Embed an imperceptible, robust audio
   watermark (e.g. Meta's AudioSeal, or a SynthID-style scheme) in all output,
   and ship the detector. Makes audio from this tool provably traceable and lets
   platforms/victims flag it. Highest-value single addition.
2. **Provenance metadata (C2PA content credentials).** Attach signed
   "AI-generated with this tool" provenance to exported audio so downstream
   systems can read it. Complements (not replaces) the watermark.
3. **Audible disclosure option.** A config to prepend/append a spoken "This
   voice is AI-generated" tag, on by default for a public demo deployment.
4. **Acceptable-Use Policy + abuse pipeline.** A short AUP, a takedown/abuse
   contact, and a documented response process.
5. **Identity + accountability for API use.** Per-key ownership and rate limits;
   log which key produced how much audio (never the transcript text by default).

If the repo goes public, a reasonable **minimum bar** would be: watermarking (1)
or C2PA provenance (2), plus an AUP/abuse process (4), plus a clear synthetic-
media disclosure in the UI and docs.

## References

- [ELVIS Act — overview](https://en.wikipedia.org/wiki/ELVIS_Act) ·
  [Holland & Knight analysis](https://www.hklaw.com/en/insights/publications/2024/04/first-of-its-kind-ai-law-addresses-deep-fakes-and-voice-clones)
- [FTC — Preventing the Harms of AI-enabled Voice Cloning](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2023/11/preventing-harms-ai-enabled-voice-cloning)
- [C2PA — Coalition for Content Provenance and Authenticity](https://c2pa.org/)
- [Meta AudioSeal](https://github.com/facebookresearch/audioseal)
- [Deepfake & AI Voice Laws by State](https://www.recordinglaw.com/us-laws/deepfake-laws/)
