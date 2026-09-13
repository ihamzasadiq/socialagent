# backend/templates

Turns source context + a template into per-platform drafts.

- `generate_posts(template_id, source_contexts, custom_template=None, prompt=None, platforms=None, reference_data_url=None)`
  — one OpenRouter call per platform. Each call returns structured JSON:
  `headline`, `subhead`, `post`, `hashtags`, `alt_text`, `image_prompt`.
  When `reference_data_url` is set the call becomes multimodal (vision model),
  `DESIGN_SYSTEM` is appended with instructions to copy the same style as the
  image referenced, and the parsed `design` tokens ride along on each draft
  for the image step.
- `regenerate_post(original, source_contexts, template_id, ...)` — same call
  with a "write a different variant" instruction at a higher temperature.
- `PLATFORM_GUIDES` holds the per-platform system guidance; `TEMPLATE_GUIDES`
  holds the Funding / Acquisition / Launch / Custom shapes.
- `ACTIVE_PLATFORMS` is the single switch for which platforms get generated.
  It is `["linkedin"]` today — add `"instagram"` (already in
  `PLATFORM_GUIDES`) once Instagram publishing exists.
- `fixtures.py` keeps the original prototype copy. It is only used when no
  `OPENROUTER_API_KEY` is configured, so the UI stays demoable offline.

The LLM transport itself lives in `imaging/core.py` (`complete_json`), which
holds the OpenRouter request/retry/JSON-parsing logic.
