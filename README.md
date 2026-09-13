# Social Agent

Ingests source URLs, generates on-brand posts from templates, and distributes
them across platforms after approval. Dark, NotebookLM-styled UI; TypeScript
frontend, Python/FastAPI backend.

```
/frontend           React + Tailwind UI (TypeScript)
/backend
  /ingestion          URL fetching + content extraction        — Dev A
  /templates          template filling, post generation        — Dev A
  /distribution        OAuth, platform posting, image generation — Dev B
  /orchestrator        ties the above together, exposes the HTTP API
/shared               the wire contract (Source/Post/PostBundle types)
```

Each backend folder owns its own lane so two people can work in parallel
without touching each other's files — `orchestrator` is the one place both
meet. See the `README.md` in each folder for what's already there and what's
still a `TODO`.

## Quickstart (two terminals)

**Backend** — from `backend/` specifically, not the repo root (see
`backend/README.md` for why this matters):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn orchestrator.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api to :8000
```

Open `http://localhost:5173`. Add a source URL, pick a template, hit
Generate — that's a real `POST /api/generate` call, not mock data. API docs
(auto-generated from the Pydantic schemas) are at `http://localhost:8000/docs`.

## The contract

`/shared/types.ts` is the canonical shape of everything that crosses the
network (`Source`, `Post`, `PostBundle`, and the request/response types for
each endpoint). The frontend imports it directly; the Python backend
hand-mirrors it in `backend/orchestrator/schemas.py`. If you change one,
change the other in the same commit — see `/shared/README.md`.

## What's real vs. what's a stub today

Everything in this repo runs — there are no empty folders — but the
content each module produces is still a stand-in:

- **ingestion** does a real (best-effort, short-timeout) fetch of each URL
  and scrapes its `<title>`, falling back to a slug-derived title on any
  failure.
- **templates** returns fixture copy ported from the original UI prototype,
  except when you use the Custom template, which already embeds whatever
  you paste into the textarea.
- **distribution** always fakes a successful "publish" and returns a
  placeholder image URL — no real platform API calls or OAuth yet.

Each module's `README.md` has the specific `TODO`s for turning its stub into
the real thing.
