"""Dev A owns this module: turning sources + a template into per-platform
drafts. Today it's a fixture lookup (see fixtures.py); the TODOs below mark
exactly where a real LLM call replaces that.
"""

from __future__ import annotations

from dataclasses import dataclass

from templates.fixtures import FIXTURE_DRAFTS

PLATFORM_ORDER = ["twitter", "linkedin", "discord"]


@dataclass
class GeneratedDraft:
    platform: str
    text: str


def _variants_for(template_id: str, platform: str, custom_template: str | None) -> list[str]:
    if template_id == "custom" and custom_template and custom_template.strip():
        # Honors the customTemplate textarea from the frontend — this is the
        # first thing to actually consume it end to end. Two variants so
        # regenerate_variant() still has somewhere to cycle to.
        base = custom_template.strip()
        return [
            f"{base}\n\n— drafted for {platform}, variant 1.",
            f"{base}\n\n— drafted for {platform}, variant 2 (shorter framing).",
        ]

    if template_id not in FIXTURE_DRAFTS:
        raise ValueError(f"Unknown templateId: {template_id!r}")
    if platform not in FIXTURE_DRAFTS[template_id]:
        raise ValueError(f"Unknown platform: {platform!r}")
    return FIXTURE_DRAFTS[template_id][platform]


def generate_posts(
    template_id: str,
    source_titles: list[str],
    custom_template: str | None = None,
    prompt: str | None = None,
) -> list[GeneratedDraft]:
    """Returns one draft per platform in PLATFORM_ORDER.

    TODO(Dev A): replace the fixture lookup with real per-platform LLM
    calls, using `source_titles` (soon: full source content, see
    ../ingestion/README.md) plus `custom_template`/`prompt` as context.
    `prompt` and `source_titles` are intentionally already threaded through
    the signature so wiring in a real call doesn't require touching
    orchestrator/routes.py.
    """
    del source_titles, prompt  # not consumed yet — real generation uses these
    return [
        GeneratedDraft(platform=platform, text=_variants_for(template_id, platform, custom_template)[0])
        for platform in PLATFORM_ORDER
    ]


def regenerate_variant(
    template_id: str,
    platform: str,
    current_variant_index: int,
    custom_template: str | None = None,
) -> tuple[str, int]:
    """Cycles to the next of the (currently: 2) mock variants for this
    template/platform pair. Returns (new_text, new_variant_index)."""
    variants = _variants_for(template_id, platform, custom_template)
    new_index = (current_variant_index + 1) % len(variants)
    return variants[new_index], new_index
