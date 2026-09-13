# backend/templates — Dev A

Turns a template + sources into per-platform draft text.

- `fixtures.py` — `FIXTURE_DRAFTS[template_id][platform_id]`, mock copy ported
  verbatim from the original frontend prototype. Two variants per pair.
- `generate.py`
  - `generate_posts(template_id, source_titles, custom_template=None, prompt=None) -> list[GeneratedDraft]`
    — one draft per platform, currently a fixture lookup.
  - `regenerate_variant(template_id, platform, current_variant_index, custom_template=None) -> (text, new_index)`
    — cycles to the next mock variant.
  - When `template_id == "custom"` and `custom_template` is non-empty, both
    functions embed the literal custom template text in the output instead
    of using fixtures — this is the one thing already wired for real.

## TODO — where to take this next

- Replace the fixture lookup in `generate_posts`/`_variants_for` with real
  per-platform LLM calls. `source_titles` and `prompt` are already threaded
  through the function signature for exactly this — you shouldn't need to
  touch `orchestrator/routes.py` to wire a real call in.
- Once `ingestion.fetch_source` returns real page content (not just a
  title), use that as generation context instead of just titles.
- Per-platform prompts/system messages (Twitter needs brevity, LinkedIn
  wants a narrative arc, Discord wants a casual community voice) — the
  fixture copy already demonstrates the tone difference to aim for.
