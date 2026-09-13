# backend/orchestrator

Ties `ingestion` → `templates` → `distribution` together and exposes them as
HTTP endpoints for the frontend. This is the one module both Dev A and Dev B
will touch — everyone else's work is isolated to their own folder.

- `main.py` — FastAPI app, CORS, mounts the router, `GET /health`
- `routes.py` — `POST /api/generate`, `POST /api/regenerate`, `POST /api/approve`
- `schemas.py` — Pydantic mirror of `/shared/types.ts` (camelCase on the wire —
  see the field-mapping table at the top of that file)
- `state.py` — `new_id()`/`utcnow_iso()` only. **Not** a persistence layer —
  see below.

## Run it

From the `backend/` directory specifically (not repo root, not this folder):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn orchestrator.main:app --reload --port 8000
```

`routes.py` imports sibling packages (`from ingestion.fetch import ...`, etc.),
so `backend/` needs to be on `sys.path`. The bare `uvicorn` console script
doesn't reliably put the current directory there — `python -m uvicorn` does.
Running from the wrong directory gets you `ModuleNotFoundError: No module
named 'ingestion'`.

Interactive API docs (auto-generated from `schemas.py`) at
`http://localhost:8000/docs` once it's running.

## Why stateless

No database, no in-memory store keyed by post id. `postId` is only ever
echoed back in a response so the frontend can match it to the right card —
the backend never needs to look anything up. The frontend keeps owning
`posts`/`sources` in its own React state, same as before this backend
existed, just populated from real responses now. For a hackathon stub this
is the right tradeoff: nothing here needs a persistence layer to work.
