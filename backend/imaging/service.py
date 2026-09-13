"""Post-image pipeline: OpenRouter image generation + PIL composition.

Two modes:

- **compose** (default): generate a background, then layer the headline/subhead
  on top with PIL and the brand defaults.
- **reference**: when the user has uploaded a style reference, ask the image
  model to copy the same style as the referenced image and render the whole
  post in one pass (typography, palette and layout included).

Both modes optionally search the web (Tavily) for a real scene photo about
the post and pass it as a scene guide for the background.

Ported from the standalone images app's app.py + core.py.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from config import settings
from imaging import composer, core
from orchestrator.session import PostRecord, session


def _next_index(directory: Path, prefix: str) -> int:
    numbers = []
    for path in directory.glob(f"{prefix}-*"):
        match = re.search(r"-(\d+)$", path.stem)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def _fallback_headline(post: PostRecord) -> str:
    words = (post.text or "").strip().split()
    if not words:
        return "New post"
    headline = " ".join(words[:6]).strip(" .,:;!-")
    return headline or "New post"


def _topic(post: PostRecord) -> str:
    if post.headline:
        return post.headline
    return " ".join((post.text or "").split()[:12]).strip() or "social media post"


def _media_url(path: Path) -> str:
    return f"/media/{path.relative_to(settings.media_dir).as_posix()}"


def _web_scene(directory: Path, post: PostRecord, query: str) -> tuple[str, dict]:
    """Tavily image search + download; first downloadable candidate wins.

    Mirrors the standalone app's ``_web_scene``: the downloaded photo is kept
    on disk for the UI and passed to the image model as a scene guide.
    """
    found = core.search_topic_images(query)
    if not found["images"]:
        raise core.CoreError(f'web search found no images for "{query}"')

    last_error = "no downloadable image"
    for candidate in found["images"][:3]:
        try:
            fetched = core.fetch_image_as_data_url(candidate["url"])
        except (core.CoreError, OSError) as error:
            last_error = str(error)
            continue
        ext = core.EXT_BY_MEDIA_TYPE.get(fetched["media_type"], ".jpg")
        index = _next_index(directory, f"{post.id}-web")
        local = directory / f"{post.id}-web-{index}{ext}"
        local.write_bytes(base64.b64decode(fetched["data_url"].split(",", 1)[1]))
        info = {
            "query": found["query"],
            "url": candidate["url"],
            "description": candidate["description"],
            "local": _media_url(local),
        }
        return fetched["data_url"], info
    raise core.CoreError(f"could not download a web image: {last_error}")


def generate_post_image(
    post: PostRecord,
    *,
    ratio: str = "4:5",
    style: str | None = None,
    image_prompt: str | None = None,
    web_search: bool = False,
) -> dict:
    """Generate (+ optionally compose) an image for ``post``.

    Returns ``{"url", "path", "mode", ..., "web_image"}``.
    """
    directory = session.ensure_media_dir()
    brand = core.load_brand()
    reference = session.get_reference()
    # Session watermark wins; None falls back to brand.json, "" disables it.
    watermark = session.get_watermark()
    handle = brand.get("handle") if watermark is None else watermark

    web_data_url: str | None = None
    web_info: dict | None = None
    if web_search:
        query = (image_prompt or post.headline or _topic(post)).strip()
        web_data_url, web_info = _web_scene(directory, post, query)

    if reference is not None and post.design:
        # Reference mode: the image model renders the finished post, copying
        # the style of the referenced image (text baked in).
        index = _next_index(directory, f"{post.id}-ref")
        output = directory / f"{post.id}-ref-{index}.png"
        copy = {
            "image_prompt": image_prompt or post.image_prompt,
            "headline": post.headline,
            "subhead": post.subhead,
        }
        prompt = core.build_reference_prompt(
            _topic(post),
            "bold",
            ratio,
            copy,
            post.design,
            handle,
            scene_ref=bool(web_data_url),
        )
        image = core.generate_image(
            prompt,
            output,
            model=brand.get("reference_model") or None,
            aspect_ratio=ratio,
            reference=reference.data_url,
            references=[web_data_url] if web_data_url else None,
        )
        composer.normalize_output(image["path"])
        path = Path(image["path"])
        return {
            "url": _media_url(path),
            "path": str(path),
            "mode": "reference",
            "model": image.get("model"),
            "cost_usd": image.get("cost_usd"),
            "ratio": ratio,
            "web_image": web_info,
        }

    # Compose mode: background from the model, text layered on top with PIL.
    prompt = (image_prompt or post.image_prompt or "").strip()
    if not prompt:
        prompt = (
            f"Editorial social media background image about: {_topic(post)}. "
            "Modern, bold, cinematic lighting, strong composition, generous clean negative "
            "space reserved for a headline. No text, words, letters, watermarks or logos."
        )
    if web_data_url:
        prompt = core.with_scene_reference(prompt)

    index = _next_index(directory, f"{post.id}-bg")
    background = core.generate_image(
        prompt,
        directory / f"{post.id}-bg-{index}.png",
        aspect_ratio=ratio,
        references=[web_data_url] if web_data_url else None,
    )
    composer.normalize_output(background["path"])

    output = directory / f"{post.id}-post-{index}.png"
    summary = composer.compose(
        background["path"],
        post.headline or _fallback_headline(post),
        subhead=post.subhead or None,
        handle=handle,
        ratio=ratio,
        style=style or brand.get("default_style") or "modern",
        output=output,
        jpeg=True,
    )
    composed = Path(summary.get("jpeg") or summary["output"])
    composer.normalize_output(composed)

    return {
        "url": _media_url(composed),
        "path": str(composed),
        "background": background["path"],
        "mode": "compose",
        "model": background.get("model"),
        "cost_usd": background.get("cost_usd"),
        "ratio": ratio,
        "web_image": web_info,
    }
