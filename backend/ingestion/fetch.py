"""Turn a source URL into agent-ready context.

Ported from the original standalone ``context.py``: fetch the page, extract
its text with trafilatura, collect candidate images, and (optionally, when
``deep=True``) ask an OpenRouter vision model to describe those images.

The result is a ``FetchedSource`` whose ``context`` string can be injected
straight into the generation prompt. Fetches never raise for network errors —
they degrade to ``status="error"`` with a slug-derived title so one bad link
doesn't break a whole generation run. Only genuinely unparseable URLs raise
``ValueError`` (routes turn that into a 400).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from config import load_env

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_VLM_MODEL = "google/gemini-2.5-flash"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
CRAWLER_USER_AGENT = (
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
)
MAX_IMAGES = 6
MAX_TEXT_CHARS = 12_000
MIN_TEXT_CHARS = 200
FETCH_TIMEOUT = 25.0
VLM_TIMEOUT = 120.0
JUNK_IMAGE_MARKERS = ("sprite", "spacer", "pixel", "1x1", "blank.gif", "tracking")

VLM_SYSTEM_PROMPT = """You are a context extraction engine for an AI agent. You receive \
the text and images of a web page. Produce a factual, self-contained description that gives \
another AI everything it needs to know about this page without seeing it.

Use markdown sections and cover:
- What the page is: page type, who or what it is about, the main message.
- Key facts: names, numbers, dates, prices, quotes, calls to action.
- Topics, themes, and tone.
- Images: for every image provided, describe the scene, objects, brands, and visual style. \
Transcribe visible text that carries meaning (signs, slides, captions, charts) verbatim, but \
skip decorative clutter, stock icon grids, and symbol soup. Keep each image under 200 words.

Rules: use only the provided page text and images, never outside knowledge; never guess \
identities or invent facts; if the content is insufficient, say so; no preamble."""


@dataclass
class FetchedSource:
    id: str
    url: str
    host: str
    title: str
    path: str
    context: str
    deep: bool
    status: str  # ready | error
    error: str | None = None


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


def parse_source(raw_url: str) -> FetchedSource:
    """Pure, offline: derive host/path and a slug-derived title.

    Mirrors the frontend's client-side parseSource() so a source card never
    looks different depending on whether the network fetch succeeded.
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
        words = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)
        words = re.sub(r"[-_]+", " ", words)
        title = words.title()
    else:
        title = bare_host

    if len(title) > 46:
        title = title[:46] + "…"

    path = bare_host + (parsed.path if parsed.path not in ("", "/") else "")
    return FetchedSource(
        id=_new_id(), url=url, host=host, title=title, path=path, context="", deep=False, status="ready"
    )


def _norm_image_url(src: str, base_url: str) -> str | None:
    src = src.strip().split(" ")[0]
    if src.startswith("data:"):
        return None
    absolute = urljoin(base_url, src)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    if (parsed.path or "").lower().endswith(".svg"):
        return None
    return absolute


def _image_key(url: str) -> str:
    name = urlparse(url).path.rsplit("/", 1)[-1].lower()
    return re.sub(r"^\d+px-", "", name)


def _looks_tiny(img: Any) -> bool:
    for attr in ("width", "height"):
        value = img.get(attr)
        if value is None:
            continue
        try:
            if int(str(value).strip().rstrip("px")) <= 64:
                return True
        except ValueError:
            continue
    return False


def extract_images(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    images: list[str] = []
    seen: set[str] = set()

    def add(raw: str | None) -> None:
        if not raw:
            return
        lowered = raw.lower()
        if any(marker in lowered for marker in JUNK_IMAGE_MARKERS):
            return
        url = _norm_image_url(raw, base_url)
        key = _image_key(url) if url else ""
        if url and url not in images and key not in seen:
            seen.add(key)
            images.append(url)

    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:url"},
        {"name": "twitter:image"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag:
            add(tag.get("content"))

    for img in soup.find_all("img"):
        if _looks_tiny(img):
            continue
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src:
            srcset = img.get("srcset") or img.get("data-srcset")
            if srcset:
                src = srcset.split(",")[0].strip().split(" ")[0]
        add(src)

    return images[:MAX_IMAGES]


def extract_text(html: str, url: str) -> str:
    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_links=True,
        include_formatting=True,
    )
    if not text:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ", strip=True).split())
    return (text or "").strip()


def extract_metadata(html: str, url: str) -> dict[str, Any]:
    metadata = trafilatura.extract_metadata(html, default_url=url)
    if metadata is None:
        return {}
    return {
        "title": metadata.title,
        "author": metadata.author,
        "published": metadata.date,
        "site": metadata.sitename,
        "description": metadata.description,
    }


def _vision_context(
    url: str, title: str | None, text: str, images: list[str]
) -> tuple[str | None, str | None]:
    if not images and len(text.strip()) < MIN_TEXT_CHARS:
        return None, "page has too little extractable content; skipped model analysis"

    load_env()
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None, "OPENROUTER_API_KEY is not set; skipped the vision step"

    if images:
        model = os.environ.get("OPENROUTER_VLM_MODEL", "").strip() or DEFAULT_VLM_MODEL
    else:
        model = (
            os.environ.get("OPENROUTER_MODEL", "").strip()
            or os.environ.get("OPENROUTER_VLM_MODEL", "").strip()
            or DEFAULT_VLM_MODEL
        )

    user_text = (
        f"URL: {url}\nTitle: {title or '(none)'}\n\n"
        f"Page text:\n{text or '(no extractable text)'}"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for image_url in images:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": VLM_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = httpx.post(
            OPENROUTER_CHAT_URL, headers=headers, json=payload, timeout=VLM_TIMEOUT
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        return None, f"vision request failed with HTTP {exc.response.status_code}: {detail}"
    except Exception as exc:
        return None, f"vision request failed: {exc}"

    data = response.json()
    message = (data.get("choices") or [{}])[0].get("message") or {}
    result = (message.get("content") or "").strip()
    if not result:
        return None, "vision model returned an empty response"
    return result, None


def _render_context(
    url: str,
    metadata: dict[str, Any],
    text: str,
    vision: str | None,
    errors: list[str],
) -> str:
    lines = [f"# {metadata.get('title') or url}", f"Source: {url}"]
    for label, key in (
        ("Site", "site"),
        ("Author", "author"),
        ("Published", "published"),
    ):
        if metadata.get(key):
            lines.append(f"{label}: {metadata[key]}")
    lines.append(f"## Page content\n\n{text or '(no extractable text)'}")
    if vision:
        lines.append(f"## Visual context\n\n{vision}")
    if errors:
        lines.append("## Notes\n\n" + "\n".join(f"- {error}" for error in errors))
    return "\n\n".join(lines)


def _fetch(url: str, user_agent: str) -> tuple[str, str]:
    headers = {"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(follow_redirects=True, timeout=FETCH_TIMEOUT, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return str(response.url), response.text


def _extract(html: str, url: str) -> tuple[dict[str, Any], str, list[str]]:
    metadata = extract_metadata(html, url)
    text = extract_text(html, url)
    if len(text.strip()) < MIN_TEXT_CHARS and metadata.get("description"):
        description = metadata["description"].strip()
        text = f"{text.strip()}\n\n{description}".strip()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[text truncated]"
    return metadata, text, extract_images(html, url)


def fetch_source(raw_url: str, deep: bool = False) -> FetchedSource:
    """Fetch a URL and build its context. ``deep=True`` adds a vision pass."""
    fallback = parse_source(raw_url)  # raises ValueError for garbage input

    try:
        final_url, html = _fetch(fallback.url, USER_AGENT)
    except httpx.HTTPStatusError as exc:
        fallback.status = "error"
        fallback.error = f"fetch failed with HTTP {exc.response.status_code}"
        return fallback
    except Exception as exc:
        fallback.status = "error"
        fallback.error = f"fetch failed: {exc}"
        return fallback

    metadata, text, images = _extract(html, final_url)

    if not images and len(text.strip()) < MIN_TEXT_CHARS:
        try:
            crawler_url, crawler_html = _fetch(fallback.url, CRAWLER_USER_AGENT)
        except Exception:
            pass
        else:
            crawler_metadata, crawler_text, crawler_images = _extract(crawler_html, crawler_url)
            if crawler_images or len(crawler_text.strip()) > len(text.strip()):
                final_url, metadata, text, images = (
                    crawler_url,
                    crawler_metadata,
                    crawler_text,
                    crawler_images,
                )

    errors: list[str] = []
    vision: str | None = None
    if deep:
        vision, error = _vision_context(final_url, metadata.get("title"), text, images)
        if error:
            errors.append(error)

    host = urlparse(final_url).hostname or fallback.host
    title = (metadata.get("title") or fallback.title).strip()
    if len(title) > 60:
        title = title[:60] + "…"

    return FetchedSource(
        id=fallback.id,
        url=final_url,
        host=host,
        title=title,
        path=fallback.path,
        context=_render_context(final_url, metadata, text, vision, errors),
        deep=deep and vision is not None,
        status="ready",
        error=None,
    )
