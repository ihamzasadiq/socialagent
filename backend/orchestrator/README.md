# backend/orchestrator

Ties ingestion -> templates -> imaging -> distribution together and exposes
them over HTTP.

- `main.py` — FastAPI app, CORS fallback, `/health`, `/media` static mount
- `routes.py` — the API (below) plus the LinkedIn OAuth callback
- `schemas.py` — Pydantic mirror of `/shared/types.ts` (camelCase on the wire)
- `session.py` — the single in-memory `session` object plus `new_id`/`utcnow`
  helpers. **No database.** `session.reset()` (exposed as
  `POST /api/session/clear`) empties sources/posts/LinkedIn and deletes the
  session's media directory.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness |
| GET | `/api/session` | rehydrate the UI: sources, posts, LinkedIn status |
| POST | `/api/session/clear` | wipe everything (incl. LinkedIn connection) |
| POST | `/api/sources` | add + ingest a URL (`{url, deep?}`) |
| DELETE | `/api/sources/{id}` | remove a source |
| POST | `/api/reference` | store a style-reference image (`{dataUrl}`) |
| DELETE | `/api/reference` | remove the style reference |
| POST | `/api/generate` | generate drafts from session sources (uses the reference when set) |
| POST | `/api/regenerate` | new variant for one post |
| POST | `/api/image` | generate + compose a post image (`{postId, ratio?, style?, imagePrompt?, webSearch?}`) |
| POST | `/api/approve` | publish to LinkedIn (409 + `connectUrl` when not connected) |
| GET | `/api/oauth/linkedin/connect` | redirect to LinkedIn consent |
| GET | `/api/oauth/linkedin/status` | connection status |
| POST | `/api/oauth/linkedin/disconnect` | revoke + forget |
| GET | `/oauth/callback/linkedin` | OAuth redirect target (tunnel-facing, no `/api`) |

## Run

From `backend/` specifically — sibling packages (`ingestion.fetch`,
`templates.generate`, ...) need `backend/` on `sys.path`, and the bare
`uvicorn` script doesn't reliably do that:

```bash
cd backend
python -m uvicorn orchestrator.main:app --reload --port 8000
```

Interactive API docs are at `http://localhost:8000/docs`.

## Why no database

This is a one-user demo: sources, drafts, generated media and the LinkedIn
token all belong to a single session, and "Clear session" is a feature rather
than a cleanup chore. Keeping state in process memory means no migrations, no
ORM and no token encryption — restarting the backend starts fresh.
