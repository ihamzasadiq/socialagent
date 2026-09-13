# backend/ingestion — Dev A

Turns a source URL into something `templates.generate_posts` can reference.

- `fetch.py`
  - `parse_source(raw_url) -> ParsedSource` — pure, offline, mirrors the
    frontend's client-side title derivation exactly. Raises `ValueError` on
    genuinely unparseable input.
  - `fetch_source(raw_url, timeout=2.5) -> ParsedSource` — real `httpx` GET +
    `<title>` scrape, falling back to `parse_source()` on any network error
    or timeout. This is what `orchestrator/routes.py` calls for every source
    in a `/api/generate` request.

## TODO — where to take this next

- Real content extraction: page body text, meta description, OpenGraph tags —
  not just `<title>`. `generate_posts` should get real context to work with,
  not just a slug-derived title.
- Handle PDFs and other non-HTML content types.
- Handle paywalled/JS-rendered pages (would need something heavier than a
  plain `httpx.get`, e.g. a headless browser — probably out of scope for the
  hackathon, but worth flagging).
