"""Pydantic mirror of /shared/types.ts — the Python half of the wire
contract. Field names below are idiomatic snake_case; every model inherits
CamelModel, which serializes/deserializes camelCase JSON on the wire, so
the two sides match byte-for-byte without either language compromising its
own naming convention.

RULE: any field added, renamed, or removed in /shared/types.ts must be
mirrored here in the same change.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

PlatformId = Literal["linkedin", "instagram"]
TemplateId = Literal["funding", "acquisition", "launch", "custom"]
PostStatus = Literal["preview", "posted"]
SourceStatus = Literal["loading", "ready", "error"]
ImageStatus = Literal["none", "generating", "ready", "error"]
ImageRatio = Literal["1:1", "4:5", "16:9"]
ImageStyle = Literal["modern", "editorial", "minimal"]


class CamelModel(BaseModel):
    """Base for every wire model: Python fields stay snake_case, JSON in/out
    is camelCase — must match /shared/types.ts field names exactly."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Source(CamelModel):
    id: str
    url: str
    host: str
    title: str
    path: str
    status: SourceStatus = "ready"
    error: str | None = None
    deep: bool = False


class Post(CamelModel):
    id: str
    platform: PlatformId
    text: str
    status: PostStatus = "preview"
    headline: str = ""
    subhead: str = ""
    hashtags: list[str] = []
    alt_text: str = ""
    image_prompt: str = ""
    image_url: str | None = None
    image_status: ImageStatus = "none"
    image_error: str | None = None
    variant_index: int = 0


class PostBundle(CamelModel):
    id: str
    template_id: TemplateId
    posts: list[Post]
    created_at: str  # ISO 8601


class AddSourceRequest(CamelModel):
    url: str
    deep: bool = False


class AddSourceResponse(CamelModel):
    source: Source


class OkResponse(CamelModel):
    ok: bool = True


class GenerateRequest(CamelModel):
    template_id: TemplateId
    custom_template: str | None = None
    prompt: str | None = None


class GenerateResponse(CamelModel):
    bundle: PostBundle


class RegenerateRequest(CamelModel):
    post_id: str


class RegenerateResponse(CamelModel):
    post: Post


class WebImageInfo(CamelModel):
    query: str
    url: str | None = None
    description: str | None = None
    local: str | None = None


class ImageRequest(CamelModel):
    post_id: str
    ratio: ImageRatio = "4:5"
    style: ImageStyle | None = None
    image_prompt: str | None = None
    # Search the web (Tavily) for a real scene photo to guide the background.
    web_search: bool = False


class ImageResponse(CamelModel):
    post: Post
    web_image: WebImageInfo | None = None


class ReferenceRequest(CamelModel):
    data_url: str


class ReferenceResponse(CamelModel):
    reference_image: str | None = None


class WatermarkRequest(CamelModel):
    """Empty/null clears the watermark; None falls back to brand.json."""

    watermark: str | None = None


class WatermarkResponse(CamelModel):
    watermark: str | None = None


class ApproveRequest(CamelModel):
    post_id: str


class ApproveResponse(CamelModel):
    post: Post
    posted_at: str  # ISO 8601
    provider_post_id: str | None = None


class LinkedInStatus(CamelModel):
    connected: bool
    status: Literal["connected", "expiring", "expired", "needs_reauth", "disconnected"]
    display_name: str | None = None
    expires_at: str | None = None


class SessionResponse(CamelModel):
    sources: list[Source]
    posts: list[Post]
    linkedin: LinkedInStatus
    reference_image: str | None = None
    watermark: str | None = None


class ClearSessionResponse(CamelModel):
    ok: bool = True


def source_out(record) -> Source:
    return Source(
        id=record.id,
        url=record.url,
        host=record.host,
        title=record.title,
        path=record.path,
        status=record.status,
        error=record.error,
        deep=record.deep,
    )


def post_out(record) -> Post:
    return Post(
        id=record.id,
        platform=record.platform,
        text=record.text,
        status=record.status,
        headline=record.headline,
        subhead=record.subhead,
        hashtags=list(record.hashtags or []),
        alt_text=record.alt_text,
        image_prompt=record.image_prompt,
        image_url=record.image_url,
        image_status=record.image_status,
        image_error=record.image_error,
        variant_index=record.variant_index,
    )
