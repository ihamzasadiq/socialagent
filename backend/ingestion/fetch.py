"""Dev A owns this module: URL fetching + content extraction.

parse_source() is a pure, offline fallback — it mirrors the frontend's
client-side parseSource() (frontend/src/App.tsx) exactly, so a source card
never looks different depending on whether the network fetch below
succeeded.

fetch_source() is a genuine (if minimal) network call: GET the URL and pull
its <title> tag. It always returns a ParsedSource — on any network error,
timeout, or missing <title>, it falls back to parse_source()'s slug-derived
title rather than raising, so one bad link never breaks /api/generate for
the whole batch.

TODO(Dev A): this only looks at <title>. Real content extraction — page
body text, meta description, OpenGraph tags — belongs here next, and
templates.generate_posts should start taking that content as context
instead of just the title.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class ParsedSource:
    """Field-for-field match with the `Source` shape in /shared/types.ts —
    orchestrator/routes.py converts this straight into schemas.Source."""

    id: str
    url: str
    host: str
    title: str
    path: str


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def parse_source(raw_url: str) -> ParsedSource:
    """Pure, offline: derive a title from the URL's last path segment.
    Mirrors frontend/src/App.tsx's parseSource() 1:1.

    Raises ValueError for input that isn't even a parseable host+scheme —
    callers (routes.py) turn that into a 400.
    """
    url = raw_url if "://" in raw_url else f"https://{raw_url}"
    parsed = urlparse(url)
    if not parsed.hostname or "." not in parsed.hostname:
        raise ValueError(f"Not a valid URL: {raw_url!r}")

    host = parsed.hostname
    bare_host = host[4:] if host.startswith("www.") else host
    segments = [s for s in parsed.path.split("/") if s]
    slug = segments[-1] if segments else None

    if slug:
        words = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)  # strip a trailing file extension
        words = re.sub(r"[-_]+", " ", words)
        title = words.title()
    else:
        title = bare_host

    if len(title) > 46:
        title = title[:46] + "…"

    path = bare_host + (parsed.path if parsed.path not in ("", "/") else "")

    return ParsedSource(id=_new_id(), url=url, host=host, title=title, path=path)


def fetch_source(raw_url: str, timeout: float = 2.5) -> ParsedSource:
    """Best-effort real fetch. Falls back to parse_source() on any failure —
    network error, timeout, non-2xx, missing/empty <title> — so a slow,
    dead, or blocking URL degrades gracefully instead of failing the whole
    /api/generate request.
    """
    fallback = parse_source(raw_url)  # may raise ValueError — let it propagate

    try:
        response = httpx.get(
            fallback.url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "socialagent-ingestion/0.1"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return fallback

    match = _TITLE_RE.search(response.text)
    if not match:
        return fallback

    title = re.sub(r"\s+", " ", match.group(1)).strip()
    if not title:
        return fallback
    if len(title) > 60:
        title = title[:60] + "…"

    return ParsedSource(id=fallback.id, url=fallback.url, host=fallback.host, title=title, path=fallback.path)
