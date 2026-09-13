# backend/ingestion

Turns a source URL into the context block that `templates.generate_posts`
feeds to the model.

- `parse_source(raw_url) -> FetchedSource` — pure, offline URL validation
  plus a slug-derived title. Raises `ValueError` on genuinely unparseable
  input (routes turn that into a 400).
- `fetch_source(raw_url, deep=False) -> FetchedSource` — real work:
  - fetches with a browser User-Agent, retrying with a crawler User-Agent
    when the page yields almost no text and no images;
  - extracts markdown text with trafilatura (falling back to a BeautifulSoup
    text dump) and caps it at 12k chars;
  - collects up to 6 candidate images, skipping tracking pixels/spacers/SVGs;
  - when `deep=True`, asks an OpenRouter vision model to describe the page
    and its images (this is the slow step, up to ~2 minutes);
  - renders everything into a single markdown `context` string.
- Network failures never raise: the source comes back with `status="error"`
  and its slug-derived title, so one dead link can't break generation.

Configuration comes from `backend/.env` (`OPENROUTER_API_KEY`,
`OPENROUTER_VLM_MODEL` / `OPENROUTER_MODEL` overrides). Without an API key,
deep analysis is skipped with a note appended to the context.
