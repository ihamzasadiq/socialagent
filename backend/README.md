# backend

One FastAPI process that ingests sources, generates drafts and images, and
publishes to LinkedIn. No database: all state lives in the in-memory session
in `orchestrator/session.py`.

| Package | What it owns |
| --- | --- |
| `ingestion/` | `fetch_source(url, deep=False)` — trafilatura text extraction, metadata, image scraping, optional OpenRouter vision pass |
| `templates/` | `generate_posts(...)` / `regenerate_post(...)` — OpenRouter copy generation from source context |
| `imaging/` | OpenRouter image generation (`core.py`) + PIL composition (`composer.py`), moved here from the old standalone images app |
| `distribution/` | LinkedIn OAuth + publishing (`linkedin.py`), provider interface (`base.py`) |
| `orchestrator/` | HTTP API (`routes.py`), wire schemas (`schemas.py`), the single session (`session.py`) |
| `tests/` | pytest suite; all provider HTTP is mocked with respx |

## Run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # -dev adds pytest + respx
cp .env.example .env                   # then fill in keys
python -m uvicorn orchestrator.main:app --reload --port 8000
```

Use `python -m uvicorn` (not the bare `uvicorn` script): the app imports
sibling packages like `ingestion.fetch`, which requires the current directory
on `sys.path`. Interactive API docs are at `http://localhost:8000/docs`.

Generated images are written to `backend/media/<session-id>/` and served at
`/media`; the directory is gitignored and removed when the session is cleared.
