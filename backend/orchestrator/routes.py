"""HTTP API tying ingestion -> templates -> imaging -> distribution together.

All state lives in the single in-memory session (see session.py): adding a
source ingests it immediately, generation reads the stored source context,
and /api/approve publishes only after the user has seen and approved the
draft. There is no database anywhere in this flow.
"""

from __future__ import annotations

import base64
import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from config import settings
from distribution.base import ProviderError, ProviderNotConfigured, ProviderNotSupported
from distribution.linkedin import LinkedInProvider
from distribution.publish import publish_post
from imaging.core import CoreError
from imaging.composer import ComposeError
from imaging.service import generate_post_image
from ingestion.fetch import fetch_source
from orchestrator import schemas
from orchestrator.session import (
    GenerationParams,
    LinkedInConnection,
    PostRecord,
    ReferenceImage,
    SourceRecord,
    new_id,
    session,
    utcnow_iso,
    utcnow_naive,
)
from templates.generate import GeneratedPost, GenerationError, generate_posts, regenerate_post

router = APIRouter(prefix="/api")
callback_router = APIRouter()

REFERENCE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_REFERENCE_BYTES = 12 * 1024 * 1024


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------


def _linkedin_status() -> schemas.LinkedInStatus:
    connection = session.get_linkedin()
    if connection is None:
        return schemas.LinkedInStatus(connected=False, status="disconnected")

    status = "connected"
    if connection.expires_at is not None:
        now = utcnow_naive()
        if connection.expires_at <= now:
            status = "expired"
        elif connection.expires_at <= now + timedelta(hours=24):
            status = "expiring"
    return schemas.LinkedInStatus(
        connected=status in ("connected", "expiring"),
        status=status,
        display_name=connection.display_name,
        expires_at=connection.expires_at.isoformat() if connection.expires_at else None,
    )


@router.get("/session", response_model=schemas.SessionResponse)
def get_session() -> schemas.SessionResponse:
    reference = session.get_reference()
    return schemas.SessionResponse(
        sources=[schemas.source_out(source) for source in session.list_sources()],
        posts=[schemas.post_out(post) for post in session.list_posts()],
        linkedin=_linkedin_status(),
        reference_image=reference.url if reference else None,
        watermark=session.get_watermark(),
    )


@router.post("/session/clear", response_model=schemas.ClearSessionResponse)
def clear_session() -> schemas.ClearSessionResponse:
    session.reset()
    return schemas.ClearSessionResponse(ok=True)


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


@router.post("/sources", response_model=schemas.AddSourceResponse)
def add_source(req: schemas.AddSourceRequest) -> schemas.AddSourceResponse:
    try:
        fetched = fetch_source(req.url, deep=req.deep)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = SourceRecord(
        id=fetched.id,
        url=fetched.url,
        host=fetched.host,
        title=fetched.title,
        path=fetched.path,
        status=fetched.status,
        error=fetched.error,
        context=fetched.context,
        deep=fetched.deep,
    )
    session.add_source(record)
    return schemas.AddSourceResponse(source=schemas.source_out(record))


@router.delete("/sources/{source_id}", response_model=schemas.OkResponse)
def remove_source(source_id: str) -> schemas.OkResponse:
    if not session.remove_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return schemas.OkResponse(ok=True)


# --------------------------------------------------------------------------
# reference image
# --------------------------------------------------------------------------


@router.post("/reference", response_model=schemas.ReferenceResponse)
def set_reference(req: schemas.ReferenceRequest) -> schemas.ReferenceResponse:
    header, _, encoded = req.data_url.partition(",")
    if not header.startswith("data:image/") or not encoded.strip():
        raise HTTPException(status_code=400, detail="dataUrl must be a base64 image data URL")

    media_type = header[len("data:") :].split(";")[0].strip().lower()
    extension = REFERENCE_TYPES.get(media_type)
    if extension is None:
        raise HTTPException(
            status_code=400, detail=f"Unsupported reference image type: {media_type}"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="dataUrl is not valid base64") from exc
    if len(raw) > MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=400, detail="Reference image is larger than 12 MB")

    directory = session.ensure_media_dir()
    path = directory / f"reference{extension}"
    path.write_bytes(raw)
    reference = ReferenceImage(
        path=str(path),
        url=f"/media/{session.id}/reference{extension}",
        data_url=req.data_url,
    )
    session.set_reference(reference)
    return schemas.ReferenceResponse(reference_image=reference.url)


@router.delete("/reference", response_model=schemas.ReferenceResponse)
def clear_reference() -> schemas.ReferenceResponse:
    session.set_reference(None)
    return schemas.ReferenceResponse(reference_image=None)


# --------------------------------------------------------------------------
# watermark
# --------------------------------------------------------------------------


@router.post("/watermark", response_model=schemas.WatermarkResponse)
def set_watermark(req: schemas.WatermarkRequest) -> schemas.WatermarkResponse:
    value = req.watermark
    if value is not None:
        value = " ".join(value.split())[:40]
    session.set_watermark(value)
    return schemas.WatermarkResponse(watermark=session.get_watermark())


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------


def _source_contexts() -> list[str]:
    return [
        source.context or f"# {source.title}\nSource: {source.url}"
        for source in session.list_sources()
    ]


def _generated_to_record(draft: GeneratedPost) -> PostRecord:
    return PostRecord(
        id=new_id(),
        platform=draft.platform,
        text=draft.text,
        headline=draft.headline,
        subhead=draft.subhead,
        hashtags=list(draft.hashtags),
        alt_text=draft.alt_text,
        image_prompt=draft.image_prompt,
        design=draft.design,
    )


def _reference_data_url() -> str | None:
    reference = session.get_reference()
    return reference.data_url if reference else None


@router.post("/generate", response_model=schemas.GenerateResponse)
def generate(req: schemas.GenerateRequest) -> schemas.GenerateResponse:
    # Sources are optional: without them the prompt is built from the template
    # and the user's steering text alone (see templates/generate.py).
    try:
        drafts = generate_posts(
            template_id=req.template_id,
            source_contexts=_source_contexts(),
            custom_template=req.custom_template,
            prompt=req.prompt,
            reference_data_url=_reference_data_url(),
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    posts = [_generated_to_record(draft) for draft in drafts]
    session.set_posts(posts)
    session.set_generation_params(
        GenerationParams(
            template_id=req.template_id,
            custom_template=req.custom_template,
            prompt=req.prompt,
        )
    )

    bundle = schemas.PostBundle(
        id=new_id(),
        template_id=req.template_id,
        posts=[schemas.post_out(post) for post in posts],
        created_at=utcnow_iso(),
    )
    return schemas.GenerateResponse(bundle=bundle)


@router.post("/regenerate", response_model=schemas.RegenerateResponse)
def regenerate(req: schemas.RegenerateRequest) -> schemas.RegenerateResponse:
    post = session.get_post(req.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    params = session.get_generation_params() or GenerationParams(template_id="launch")
    original = GeneratedPost(
        platform=post.platform,
        text=post.text,
        headline=post.headline,
        subhead=post.subhead,
        hashtags=list(post.hashtags),
        alt_text=post.alt_text,
        image_prompt=post.image_prompt,
    )
    try:
        draft = regenerate_post(
            original=original,
            source_contexts=_source_contexts(),
            template_id=params.template_id,
            custom_template=params.custom_template,
            prompt=params.prompt,
            reference_data_url=_reference_data_url(),
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=f"Regeneration failed: {exc}") from exc

    post.text = draft.text
    post.headline = draft.headline
    post.subhead = draft.subhead
    post.hashtags = list(draft.hashtags)
    post.alt_text = draft.alt_text
    post.image_prompt = draft.image_prompt
    post.design = draft.design
    post.variant_index += 1
    post.image_url = None
    post.image_status = "none"
    post.image_error = None
    session.replace_post(post)
    return schemas.RegenerateResponse(post=schemas.post_out(post))


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------


@router.post("/image", response_model=schemas.ImageResponse)
def create_image(req: schemas.ImageRequest) -> schemas.ImageResponse:
    post = session.get_post(req.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    post.image_status = "generating"
    post.image_error = None
    session.replace_post(post)

    try:
        result = generate_post_image(
            post,
            ratio=req.ratio,
            style=req.style,
            image_prompt=req.image_prompt,
            web_search=req.web_search,
        )
    except (CoreError, ComposeError, ValueError, OSError) as exc:
        post.image_status = "error"
        post.image_error = str(exc)
        session.replace_post(post)
        raise HTTPException(status_code=502, detail=f"Image generation failed: {exc}") from exc

    post.image_url = result["url"]
    post.image_status = "ready"
    post.image_error = None
    session.replace_post(post)
    web_image = result.get("web_image")
    return schemas.ImageResponse(
        post=schemas.post_out(post),
        web_image=schemas.WebImageInfo(**web_image) if web_image else None,
    )


def _local_image_path(image_url: str | None) -> str | None:
    if not image_url or not image_url.startswith("/media/"):
        return None
    path = settings.media_dir / image_url[len("/media/") :]
    return str(path) if path.is_file() else None


# --------------------------------------------------------------------------
# approve / publish
# --------------------------------------------------------------------------


@router.post("/approve", response_model=schemas.ApproveResponse)
async def approve(req: schemas.ApproveRequest) -> schemas.ApproveResponse:
    post = session.get_post(req.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "posted":
        return schemas.ApproveResponse(post=schemas.post_out(post), posted_at=utcnow_iso())

    connection = session.get_linkedin()
    if connection is None or connection.access_token == "":
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Connect LinkedIn before publishing.",
                "connectUrl": "/api/oauth/linkedin/connect",
            },
        )

    try:
        provider_post_id = await publish_post(
            post.platform,
            connection,
            post.text,
            _local_image_path(post.image_url),
        )
    except ProviderNotSupported as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Publish failed: {exc}") from exc

    post.status = "posted"
    session.replace_post(post)
    return schemas.ApproveResponse(
        post=schemas.post_out(post),
        posted_at=utcnow_iso(),
        provider_post_id=provider_post_id,
    )


# --------------------------------------------------------------------------
# LinkedIn OAuth
# --------------------------------------------------------------------------


@router.get("/oauth/linkedin/connect")
def linkedin_connect() -> RedirectResponse:
    provider = LinkedInProvider(settings)
    try:
        state = secrets.token_urlsafe(32)
        url = provider.auth_url(state)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    session.add_oauth_state(state, provider="linkedin")
    return RedirectResponse(url, status_code=307)


@router.get("/oauth/linkedin/status", response_model=schemas.LinkedInStatus)
def linkedin_status() -> schemas.LinkedInStatus:
    return _linkedin_status()


@router.post("/oauth/linkedin/disconnect", response_model=schemas.OkResponse)
async def linkedin_disconnect() -> schemas.OkResponse:
    connection = session.get_linkedin()
    if connection is not None:
        try:
            await LinkedInProvider(settings).revoke(connection.access_token)
        except ProviderError:
            pass
        session.set_linkedin(None)
    return schemas.OkResponse(ok=True)


@callback_router.get("/oauth/callback/linkedin")
async def linkedin_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            settings.success_url(error=error_description or error), status_code=307
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not session.take_oauth_state(state, provider="linkedin"):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    provider = LinkedInProvider(settings)
    try:
        bundle = await provider.exchange_code(code)
        identity = await provider.fetch_identity(bundle.access_token)
    except ProviderError as exc:
        return RedirectResponse(settings.success_url(error=str(exc)), status_code=307)

    session.set_linkedin(
        LinkedInConnection(
            access_token=bundle.access_token,
            refresh_token=bundle.refresh_token,
            expires_at=bundle.expires_at,
            scopes=bundle.scopes,
            external_id=identity.external_id,
            display_name=identity.display_name,
        )
    )
    return RedirectResponse(settings.success_url(provider="linkedin"), status_code=307)
