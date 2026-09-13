"""Dev B owns this module: image generation for post previews.

STUB — returns a placeholder image URL, no real image-gen API call is made
yet. Nothing calls this from orchestrator/routes.py today (the current
Post contract in /shared/types.ts has no image field) — it's here so the
shape exists before the wire contract grows to include one.
"""

from __future__ import annotations


def generate_image(post_id: str, platform: str) -> str:
    """TODO(Dev B): call a real image-gen API keyed off the post's text and
    platform, instead of returning a placehold.co URL."""
    del post_id  # unused until the real integration lands
    return f"https://placehold.co/400x400/131313/d9a95c?text={platform}"
