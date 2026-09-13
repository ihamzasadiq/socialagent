"""Turn ingested source context + a template into per-platform drafts.

The real work happens in one OpenRouter chat call per platform (via
``imaging.core.complete_json``) that returns structured JSON: headline,
subhead, the post body, hashtags, alt text and an image prompt. The
``FIXTURE_DRAFTS`` fallback is only used when no OPENROUTER_API_KEY is
configured, so the UI stays demoable offline.

LinkedIn is the only platform the UI shows today; ``ACTIVE_PLATFORMS`` is the
single switch that turns Instagram generation on once publishing exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from config import load_env
from imaging.core import DESIGN_SYSTEM, CoreError, complete_json, extract_design
from templates.fixtures import FIXTURE_DRAFTS

ALL_PLATFORMS = ["linkedin", "instagram"]
ACTIVE_PLATFORMS = ["linkedin"]

MAX_CONTEXT_CHARS = 24_000

TEMPLATE_GUIDES = {
    "funding": (
        "Template: a funding announcement. Open with the news, name the round and lead "
        "investor if present in the sources, explain what the money is for, thank the people "
        "who made it possible, and close with a concrete next step or hiring note."
    ),
    "acquisition": (
        "Template: an acquisition / joining announcement. Lead with the news, be direct about "
        "what changes and what stays the same for customers and the team, and end with a warm, "
        "specific thank-you."
    ),
    "launch": (
        "Template: a product launch. Open with the problem, describe what shipped and who it is "
        "for, name one concrete capability, and close with availability and a single call to action."
    ),
    "custom": (
        "Template: follow the user's custom structure exactly. If no custom structure is "
        "provided, use a clean hook, two supporting paragraphs and one call to action."
    ),
}

PLATFORM_GUIDES = {
    "linkedin": (
        "Platform: LinkedIn. Long-form professional post. First line is the hook (it is all "
        "that shows before 'see more'). Short paragraphs separated by blank lines, plain text "
        "only — no markdown syntax. No emoji spam (at most one, usually none). 0-5 relevant "
        "hashtags."
    ),
    "instagram": (
        "Platform: Instagram. Punchy caption: hook, short lines, one clear call to action, "
        "up to 8 relevant hashtags, sparing emoji."
    ),
}

SYSTEM_PROMPT = """You are an expert social media copywriter. Write exactly one post per \
request, grounded ONLY in the provided source material — never invent facts, numbers, names \
or quotes that are not in it. If no source material is provided, write from the template and \
the user's steering alone, and keep it free of concrete claims (no specific figures, names or \
dates you were not given).

Respond with a single JSON object and nothing else. Keys:
- headline: max 6 words, punchy, no trailing period (used on the post image).
- subhead: max 10 words, adds information, never repeats the headline.
- post: the full post text as plain text with \\n line breaks, ready to publish.
- hashtags: array of 0-8 short tags without the # symbol.
- alt_text: under 125 characters describing the intended image, no hashtags.
- image_prompt: an English art-direction prompt for a text-to-image model (subject, setting, \
style, lighting, color mood, composition); reserve clean negative space for a headline; \
never include text, words, letters, watermarks or logos.
"""


class GenerationError(Exception):
    """Raised when the model cannot produce a usable draft."""


@dataclass
class GeneratedPost:
    platform: str
    text: str
    headline: str = ""
    subhead: str = ""
    hashtags: list[str] = field(default_factory=list)
    alt_text: str = ""
    image_prompt: str = ""
    model: str | None = None
    # Design tokens extracted from the reference image (layout/style/palette),
    # reused later to render the post image in the reference's style.
    design: dict | None = None


def _clean_hashtags(raw) -> list[str]:
    import re

    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw)
    tags: list[str] = []
    for tag in raw or []:
        cleaned = re.sub(r"[\s#]+", "", str(tag))
        if cleaned:
            tags.append(cleaned)
    return tags[:8]


def _source_block(source_contexts: list[str]) -> str:
    joined = "\n\n---\n\n".join(text.strip() for text in source_contexts if text and text.strip())
    if not joined:
        return "(no source material was extracted)"
    if len(joined) > MAX_CONTEXT_CHARS:
        joined = joined[:MAX_CONTEXT_CHARS] + "\n\n[source material truncated]"
    return joined


def _user_prompt(
    *,
    template_id: str,
    platform: str,
    source_contexts: list[str],
    custom_template: str | None,
    prompt: str | None,
    variation: bool,
    reference: bool = False,
) -> str:
    parts = [
        f"Write one {platform} post.",
        PLATFORM_GUIDES[platform],
        TEMPLATE_GUIDES[template_id],
    ]
    if reference:
        parts.append(
            "A reference image is attached: copy the same style as the image referenced for the "
            "post image, but write completely fresh copy for the source material."
        )
    if template_id == "custom" and custom_template and custom_template.strip():
        parts.append(
            "The user provided this custom template/structure — follow it exactly:\n\n"
            + custom_template.strip()
        )
    if prompt and prompt.strip():
        parts.append(f"Additional steering from the user: {prompt.strip()}")
    if variation:
        parts.append(
            "Write a distinctly different variant from the obvious take: change the hook, the "
            "structure and the phrasing while keeping the same facts."
        )
    parts.append(f"Source material:\n\n{_source_block(source_contexts)}")
    return "\n\n".join(parts)


def _draft_from_json(platform: str, parsed: dict, *, reference: bool = False) -> GeneratedPost:
    text = str(parsed.get("post") or parsed.get("caption") or "").strip()
    if not text:
        raise GenerationError("model returned an empty post")
    return GeneratedPost(
        platform=platform,
        text=text,
        headline=str(parsed.get("headline") or "").strip(),
        subhead=str(parsed.get("subhead") or "").strip(),
        hashtags=_clean_hashtags(parsed.get("hashtags")),
        alt_text=str(parsed.get("alt_text") or "").strip(),
        image_prompt=str(parsed.get("image_prompt") or "").strip(),
        model=parsed.get("_model"),
        design=extract_design(parsed) if reference else None,
    )


def _fixture_draft(platform: str, template_id: str, custom_template: str | None) -> GeneratedPost:
    if template_id == "custom" and custom_template and custom_template.strip():
        return GeneratedPost(
            platform=platform,
            text=f"{custom_template.strip()}\n\n— offline draft, no OPENROUTER_API_KEY set.",
        )
    variants = FIXTURE_DRAFTS.get(template_id, {}).get(platform) or []
    if not variants:
        raise GenerationError(f"No offline draft for {template_id!r}/{platform!r}")
    return GeneratedPost(platform=platform, text=variants[0])


def generate_posts(
    template_id: str,
    source_contexts: list[str],
    custom_template: str | None = None,
    prompt: str | None = None,
    platforms: list[str] | None = None,
    reference_data_url: str | None = None,
) -> list[GeneratedPost]:
    if template_id not in TEMPLATE_GUIDES:
        raise ValueError(f"Unknown templateId: {template_id!r}")
    platforms = platforms or ACTIVE_PLATFORMS
    for platform in platforms:
        if platform not in PLATFORM_GUIDES:
            raise ValueError(f"Unknown platform: {platform!r}")

    load_env()
    online = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    has_reference = bool(reference_data_url)
    system = SYSTEM_PROMPT + ("\n" + DESIGN_SYSTEM if has_reference else "")
    drafts: list[GeneratedPost] = []
    for platform in platforms:
        if not online:
            drafts.append(_fixture_draft(platform, template_id, custom_template))
            continue
        try:
            parsed = complete_json(
                system,
                _user_prompt(
                    template_id=template_id,
                    platform=platform,
                    source_contexts=source_contexts,
                    custom_template=custom_template,
                    prompt=prompt,
                    variation=False,
                    reference=has_reference,
                ),
                image_url=reference_data_url,
            )
        except CoreError as exc:
            raise GenerationError(str(exc)) from exc
        drafts.append(_draft_from_json(platform, parsed, reference=has_reference))
    return drafts


def regenerate_post(
    original: GeneratedPost,
    source_contexts: list[str],
    template_id: str,
    custom_template: str | None = None,
    prompt: str | None = None,
    reference_data_url: str | None = None,
) -> GeneratedPost:
    load_env()
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        variants = FIXTURE_DRAFTS.get(template_id, {}).get(original.platform) or []
        if len(variants) > 1:
            draft = _fixture_draft(original.platform, template_id, custom_template)
            draft.text = variants[1]
            return draft
        return original
    has_reference = bool(reference_data_url)
    system = SYSTEM_PROMPT + ("\n" + DESIGN_SYSTEM if has_reference else "")
    try:
        parsed = complete_json(
            system,
            _user_prompt(
                template_id=template_id,
                platform=original.platform,
                source_contexts=source_contexts,
                custom_template=custom_template,
                prompt=prompt,
                variation=True,
                reference=has_reference,
            ),
            temperature=0.95,
            image_url=reference_data_url,
        )
    except CoreError as exc:
        raise GenerationError(str(exc)) from exc
    return _draft_from_json(original.platform, parsed, reference=has_reference)
