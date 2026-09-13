# Social Agent — frontend

Dark, NotebookLM-flavored UI for a source → template → post-draft pipeline.
TypeScript + React + Tailwind v4, everything in one component file per the
original design brief.

```bash
npm install
npm run dev         # http://localhost:5173 — proxies /api to :8000, see vite.config.ts
npm run typecheck   # tsc --noEmit
```

The backend (`../backend`) must be running on `:8000` for Generate/Regenerate/Approve
to work — see `../backend/README.md`. Everything else (adding/removing a source
card, switching templates, collapsing panels) is local state and works without it.

## Layout

- `src/App.tsx` — the entire UI (sidebar, template tabs, feed, composer, activity log)
- `src/api.ts` — the only file that talks to the backend; typed wrappers around
  `POST /api/generate`, `/api/regenerate`, `/api/approve`
- `src/index.css` — Tailwind v4 `@theme` tokens (canvas / raised / line / ink / accent / error).
  Base rules **must** stay inside `@layer base` — unlayered CSS silently outranks
  Tailwind's utility layer regardless of specificity (this broke every button's text
  color once already; see git history if curious).
- `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx` — scaffolding

## Where the wire contract lives

`../shared/types.ts` — imported here via the `@shared/*` path alias. If the backend's
response shape changes, this is the file to check first; see `../shared/README.md`
for how the Python side stays in sync with it.

## States

Empty (no sources) → ready → loading (skeletons + live log) → preview → posted per
card, plus an error state (with Retry) if a `/api/*` call fails. Both side panels
collapse; the activity log is monospace and scroll-pinned to the newest line.
