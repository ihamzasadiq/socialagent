"""FastAPI entrypoint.

Run from the backend/ directory (this matters — see README.md for why):

    python -m uvicorn orchestrator.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.routes import router

app = FastAPI(title="Social Agent orchestrator", version="0.1.0")

# frontend/vite.config.ts proxies /api and /health straight to us in dev,
# which sidesteps CORS entirely in normal use. This middleware is a
# defensive fallback for anyone hitting the backend directly, or a future
# deploy where frontend/backend don't share an origin via a proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
