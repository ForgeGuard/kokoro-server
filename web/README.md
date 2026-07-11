# ForgeGuard Kokoro Server — Web Console

A Vite + React 18 + TypeScript + Tailwind CSS v3 console for ForgeGuard
Kokoro Server. Built to static assets and served by FastAPI at `/web/`.

## Develop

```bash
npm install
npm run dev      # local dev server
npm run build    # emits dist/ (index.html + hashed assets)
npm run preview  # preview the production build
```

The Docker image runs `npm ci && npm run build` and copies `web/dist` into the
image's web directory. Vite is configured with `base: './'` so relative asset
URLs work behind a reverse-proxy prefix (`UVICORN_ROOT_PATH`).

## Shared design system — keep in sync

The following are **byte-for-byte identical** to the faster-whisper console at
`faster-whisper-server/webui/`:

- `src/ui/**` — design tokens + primitives (Button, Card, Select, TextArea,
  Slider, Dialog, Toast, Spinner, IconButton, Badge, Field, Input, icons,
  ThemeProvider/ThemeToggle).
- `src/lib/apiClient.ts` — API key handling (localStorage `apiKey`), Bearer
  auth injection, root-path bootstrap from `GET /web/config`, and 401 handling.
- `src/index.css` and `tailwind.config.ts` — shared theme tokens.

When changing any shared file here, copy it to the other repo (and vice versa):

```bash
cp -r src/ui ../../faster-whisper-server/webui/src/
cp src/lib/apiClient.ts ../../faster-whisper-server/webui/src/lib/
cp src/index.css tailwind.config.ts ../../faster-whisper-server/webui/
```

App-specific code lives in `src/App.tsx`, `src/components/tts/**`,
`src/lib/ttsApi.ts`, and `src/lib/health.ts` (warmup polling that drives the
"model warming" banner). These are NOT part of the shared design system and
may diverge freely from the whisper console.
