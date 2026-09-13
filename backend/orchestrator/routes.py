"""Ties ingestion -> templates -> distribution together and exposes them as
HTTP endpoints for the frontend. Stateless per request (see state.py) — the
frontend keeps owning `posts`/`sources` in its own React state, populated
from whatever these endpoints return.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from distribution.publish import publish_post
from ingestion.fetch import fetch_source
from orchestrator import schemas
from orchestrator.state import new_id, utcnow_iso
from templates.generate import generate_posts, regenerate_variant

router = APIRouter(prefix="/api")


@router.post("/generate", response_model=schemas.GenerateResponse)
def generate(req: schemas.GenerateRequest) -> schemas.GenerateResponse:
    if not req.sources:
        raise HTTPException(status_code=400, detail="At least one source is required.")

    try:
        fetched = [fetch_source(s.url) for s in req.sources]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        drafts = generate_posts(
            template_id=req.template_id,
            source_titles=[s.title for s in fetched],
            custom_template=req.custom_template,
            prompt=req.prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    posts = [
        schemas.Post(id=new_id(), platform=draft.platform, text=draft.text, status="preview")
        for draft in drafts
    ]
    bundle = schemas.PostBundle(
        id=new_id(),
        template_id=req.template_id,
        posts=posts,
        created_at=utcnow_iso(),
    )
    return schemas.GenerateResponse(bundle=bundle)


@router.post("/regenerate", response_model=schemas.RegenerateResponse)
def regenerate(req: schemas.RegenerateRequest) -> schemas.RegenerateResponse:
    try:
        text, variant_index = regenerate_variant(
            template_id=req.template_id,
            platform=req.platform,
            current_variant_index=req.variant_index,
            custom_template=req.custom_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    post = schemas.Post(id=req.post_id, platform=req.platform, text=text, status="preview")
    return schemas.RegenerateResponse(post=post, variant_index=variant_index)


@router.post("/approve", response_model=schemas.ApproveResponse)
def approve(req: schemas.ApproveRequest) -> schemas.ApproveResponse:
    result = publish_post(post_id=req.post_id, platform=req.platform, text=req.text)
    post = schemas.Post(id=req.post_id, platform=req.platform, text=req.text, status=result.status)
    return schemas.ApproveResponse(post=post, posted_at=result.posted_at)
