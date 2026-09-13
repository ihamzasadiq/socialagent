"""FastAPI entrypoint.

Run from the backend/ directory (this matters — sibling packages are on the
path only from there):

    python -m uvicorn orchestrator.main:app --reload --port 8000

One process, one in-memory session, no database. Generated images are served
from /media so the frontend (and LinkedIn) can preview them.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, settings
from distribution.base import ProviderNotConfigured
from orchestrator.routes import callback_router, router

app = FastAPI(title="Social Agent orchestrator", version="0.2.0")

# frontend/vite.config.ts proxies /api, /media and /oauth to us in dev, which
# sidesteps CORS entirely in normal use. This middleware is a defensive
# fallback for anyone hitting the backend directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(callback_router)

settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.exception_handler(ProviderNotConfigured)
async def provider_not_configured_handler(
    request: Request, exc: ProviderNotConfigured
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Production mode: when a frontend build exists, serve it from the same
# process so one host serves the UI, the API and /media. Added last so the
# API routes above always win. `npm run build` creates this directory.
FRONTEND_DIST = Path(BASE_DIR).parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
