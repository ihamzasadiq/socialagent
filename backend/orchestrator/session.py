"""The one in-memory session this app runs on.

There is deliberately no database. Everything the UI can see — sources and
their extracted context, generated posts, image paths, and the LinkedIn
connection — lives on this module's single ``session`` object, guarded by a
lock because FastAPI runs sync endpoints in a thread pool.

``POST /api/session/clear`` resets it: new id, empty lists, no LinkedIn
connection, and the session's media directory is deleted from disk.
"""

from __future__ import annotations

import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    return utcnow().replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow_iso() -> str:
    return utcnow().isoformat()


@dataclass
class SourceRecord:
    id: str
    url: str
    host: str
    title: str
    path: str
    status: str = "ready"  # loading | ready | error
    error: str | None = None
    context: str = ""  # rendered markdown handed to the generator
    deep: bool = False


@dataclass
class PostRecord:
    id: str
    platform: str
    text: str
    status: str = "preview"
    headline: str = ""
    subhead: str = ""
    hashtags: list[str] = field(default_factory=list)
    alt_text: str = ""
    image_prompt: str = ""
    image_url: str | None = None
    image_status: str = "none"  # none | generating | ready | error
    image_error: str | None = None
    variant_index: int = 0
    # Design tokens extracted from the style reference at generation time.
    design: dict | None = None


@dataclass
class GenerationParams:
    template_id: str
    custom_template: str | None = None
    prompt: str | None = None


@dataclass
class LinkedInConnection:
    access_token: str
    external_id: str
    display_name: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: str | None = None


@dataclass
class ReferenceImage:
    """A user-uploaded style reference: on disk for the UI, data URL for models."""

    path: str
    url: str
    data_url: str


@dataclass
class OAuthStateRecord:
    provider: str
    created_at: datetime = field(default_factory=utcnow_naive)


OAUTH_STATE_TTL = timedelta(minutes=10)


class Session:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reset_locked()

    # -- lifecycle ---------------------------------------------------------

    def _reset_locked(self) -> None:
        self.id = new_id()
        self.created_at = utcnow()
        self.sources: list[SourceRecord] = []
        self.posts: list[PostRecord] = []
        self.linkedin: LinkedInConnection | None = None
        self.oauth_states: dict[str, OAuthStateRecord] = {}
        self.generation: GenerationParams | None = None
        self.reference: ReferenceImage | None = None
        # Watermark drawn on generated images. None = use brand.json's handle,
        # "" = explicitly no watermark.
        self.watermark: str | None = None

    def reset(self) -> None:
        """Wipe the session and its generated media."""
        with self._lock:
            media = self.media_dir
            self._reset_locked()
            shutil.rmtree(media, ignore_errors=True)

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def media_dir(self) -> Path:
        return settings.media_dir / self.id

    def ensure_media_dir(self) -> Path:
        directory = self.media_dir
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # -- sources -----------------------------------------------------------

    def list_sources(self) -> list[SourceRecord]:
        with self._lock:
            return list(self.sources)

    def get_source(self, source_id: str) -> SourceRecord | None:
        with self._lock:
            return next((s for s in self.sources if s.id == source_id), None)

    def add_source(self, source: SourceRecord) -> SourceRecord:
        with self._lock:
            self.sources.append(source)
            return source

    def remove_source(self, source_id: str) -> bool:
        with self._lock:
            before = len(self.sources)
            self.sources = [s for s in self.sources if s.id != source_id]
            return len(self.sources) != before

    # -- posts -------------------------------------------------------------

    def list_posts(self) -> list[PostRecord]:
        with self._lock:
            return list(self.posts)

    def get_post(self, post_id: str) -> PostRecord | None:
        with self._lock:
            return next((p for p in self.posts if p.id == post_id), None)

    def set_posts(self, posts: list[PostRecord]) -> None:
        with self._lock:
            self.posts = posts

    def replace_post(self, post: PostRecord) -> None:
        with self._lock:
            for index, existing in enumerate(self.posts):
                if existing.id == post.id:
                    self.posts[index] = post
                    return
            self.posts.append(post)

    # -- LinkedIn connection ----------------------------------------------

    def get_linkedin(self) -> LinkedInConnection | None:
        with self._lock:
            return self.linkedin

    def set_linkedin(self, connection: LinkedInConnection | None) -> None:
        with self._lock:
            self.linkedin = connection

    # -- watermark ---------------------------------------------------------

    def get_watermark(self) -> str | None:
        with self._lock:
            return self.watermark

    def set_watermark(self, value: str | None) -> None:
        with self._lock:
            self.watermark = value

    # -- reference image ---------------------------------------------------

    def get_reference(self) -> ReferenceImage | None:
        with self._lock:
            return self.reference

    def set_reference(self, reference: ReferenceImage | None) -> None:
        with self._lock:
            previous = self.reference
            self.reference = reference
        if previous is not None and previous.path and previous.path != (reference.path if reference else None):
            Path(previous.path).unlink(missing_ok=True)

    # -- OAuth state -------------------------------------------------------

    def add_oauth_state(self, state: str, provider: str) -> None:
        with self._lock:
            self.oauth_states[state] = OAuthStateRecord(provider=provider)
            self._prune_oauth_states_locked()

    def take_oauth_state(self, state: str, provider: str) -> bool:
        """Validate and consume a state value. Returns False when unknown or stale."""
        with self._lock:
            record = self.oauth_states.pop(state, None)
            if record is None or record.provider != provider:
                return False
            return utcnow_naive() - record.created_at <= OAUTH_STATE_TTL

    def _prune_oauth_states_locked(self) -> None:
        cutoff = utcnow_naive() - OAUTH_STATE_TTL
        self.oauth_states = {
            key: record for key, record in self.oauth_states.items() if record.created_at > cutoff
        }

    # -- generation params -------------------------------------------------

    def set_generation_params(self, params: GenerationParams) -> None:
        with self._lock:
            self.generation = params

    def get_generation_params(self) -> GenerationParams | None:
        with self._lock:
            return self.generation


session = Session()
