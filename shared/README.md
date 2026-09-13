# /shared

One file, `types.ts` — the canonical wire contract between `/frontend` and `/backend`.

## Why this exists

The frontend is TypeScript and the backend is Python, so they can't literally
import the same file. `types.ts` is still "the" contract: the frontend
imports it directly (via the `@shared/*` path alias configured in
`frontend/vite.config.ts` and `frontend/tsconfig.json`), and the backend's
`backend/orchestrator/schemas.py` hand-mirrors it field-for-field using a
`CamelModel` Pydantic base so the JSON on the wire matches these field names
exactly, even though the Python code itself stays idiomatic snake_case.

**Rule: if you add, rename, or remove a field in `types.ts`, update the
matching model in `backend/orchestrator/schemas.py` in the same change.**
The field-mapping table lives as a docstring at the top of that file — check
it any time the two might drift.

## What's in here vs. what isn't

`types.ts` only holds the *wire* shapes — what actually crosses the network.
Frontend-only view-state (e.g. a post's `variantIndex` while regenerating,
or a `loading` flag on a card) is **not** here; it's layered on top locally
in `frontend/src/App.tsx`. Keeping those out of `Post` means the backend
never has to know about UI concerns it doesn't own.
