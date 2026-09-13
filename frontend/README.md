# Social Agent — frontend

Dark, NotebookLM-flavored UI for the source -> draft -> image -> approve
pipeline. TypeScript + React + Tailwind v4.

```bash
npm install
npm run dev         # http://localhost:5173 — proxies /api and /media to :8000
npm run typecheck   # tsc --noEmit
npm run build       # typecheck + vite build
```

The backend (`../backend`) must be running on `:8000` — see
`../backend/README.md`.

## What the UI does

- **Boot** — `GET /api/session` rehydrates sources, drafts and the LinkedIn
  status, and consumes `?connected=linkedin` / `?error=...` from the OAuth
  callback.
- **Sources (optional)** — adding a URL calls `POST /api/sources` (real fetch
  + text extraction; the "Analyze page images too" checkbox turns on the slow
  vision pass). Sources can fail individually without blocking anything, and
  Generate works with zero sources — the draft is then written from the
  template and the composer prompt alone.
- **Generate** — `POST /api/generate` produces a LinkedIn draft; Regenerate
  asks for a fresh variant of one card.
- **Images** — "Add image" calls `POST /api/image` with a ratio (4:5 / 1:1 /
  16:9); the composed JPEG appears on the card and is attached on publish.
  Two optional guides: a **Style ref** upload (top right, `POST /api/reference`)
  makes generation use the vision model and the image model copy that
  reference's design; the per-card **Web bg** checkbox runs a Tavily search
  for a real scene photo to guide the background.
- **Approve** — a confirmation dialog is the permission step. Publishing
  without a LinkedIn connection redirects to `/api/oauth/linkedin/connect`
  and returns via the callback.
- **Clear session** — wipes the in-memory session (and the LinkedIn
  connection) server-side.

## Layout

- `src/App.tsx` — the entire UI (sidebar, template tabs, feed, composer, activity log, dialogs)
- `src/api.ts` — the only file that talks to the backend; typed wrappers for every endpoint
- `src/index.css` — Tailwind v4 `@theme` tokens (canvas / raised / line / ink / accent / ok / error).
  Base rules **must** stay inside `@layer base` — unlayered CSS silently outranks
  Tailwind's utility layer regardless of specificity.
- `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx` — scaffolding

## Where the wire contract lives

`../shared/types.ts` — imported here via the `@shared/*` path alias. If the
backend's response shape changes, this is the file to check first; see
`../shared/README.md` for how the Python side stays in sync.
