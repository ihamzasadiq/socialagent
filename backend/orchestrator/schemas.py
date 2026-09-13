"""Pydantic mirror of /shared/types.ts — the Python half of the wire
contract. Field names below are idiomatic snake_case; every model inherits
CamelModel, which serializes/deserializes camelCase JSON on the wire, so
the two sides match byte-for-byte without either language compromising its
own naming convention.

RULE: any field added, renamed, or removed in /shared/types.ts must be
mirrored here in the same change. Field-mapping table:

| /shared/types.ts field         | wire JSON key | this file's field       |
|---------------------------------|---------------|---------------------------|
| Source.id/url/host/title/path  | same          | id/url/host/title/path    |
| Post.id/platform/text/status   | same          | id/platform/text/status   |
| PostBundle.templateId          | templateId    | template_id               |
| PostBundle.createdAt           | createdAt     | created_at                |
| GenerateRequest.customTemplate | customTemplate| custom_template           |
| RegenerateRequest.postId       | postId        | post_id                   |
| RegenerateRequest.variantIndex | variantIndex  | variant_index             |
| ApproveRequest.postId          | postId        | post_id                   |
| ApproveResponse.postedAt       | postedAt      | posted_at                 |
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

PlatformId = Literal["twitter", "linkedin", "discord"]
TemplateId = Literal["funding", "acquisition", "launch", "custom"]
PostStatus = Literal["preview", "posted"]


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


class Post(CamelModel):
    id: str
    platform: PlatformId
    text: str
    status: PostStatus


class PostBundle(CamelModel):
    id: str
    template_id: TemplateId
    posts: list[Post]
    created_at: str  # ISO 8601


class SourceRef(CamelModel):
    """The client only ever sends a URL to generate from — not a full Source."""

    url: str


class GenerateRequest(CamelModel):
    sources: list[SourceRef]
    template_id: TemplateId
    custom_template: str | None = None
    prompt: str | None = None


class GenerateResponse(CamelModel):
    bundle: PostBundle


class RegenerateRequest(CamelModel):
    post_id: str
    platform: PlatformId
    template_id: TemplateId
    custom_template: str | None = None
    variant_index: int  # client's CURRENT index — input only, not stored server-side


class RegenerateResponse(CamelModel):
    post: Post
    variant_index: int  # the new index; client persists it locally


class ApproveRequest(CamelModel):
    post_id: str
    platform: PlatformId
    # The backend is stateless and never stored this post's text, so the
    # client sends it along so the response can echo the real thing back.
    text: str


class ApproveResponse(CamelModel):
    post: Post
    posted_at: str  # ISO 8601
