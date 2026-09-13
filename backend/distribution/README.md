# backend/distribution

OAuth and publishing. Ported from the standalone oauth service, minus the
database, scheduler, token encryption and the X/Instagram providers — the
session is the only token store, and only LinkedIn is wired.

- `base.py` — provider plumbing: `Provider` ABC (`auth_url`, `exchange_code`,
  `fetch_identity`, `publish`), `TokenBundle`, `Identity`, and the
  `request`/`request_json` helpers with LinkedIn-friendly error summaries.
- `linkedin.py` — the real provider:
  - authorization-code flow against `linkedin.com/oauth/v2` with the
    `openid profile w_member_social` scopes;
  - `fetch_identity` via `/v2/userinfo`;
  - `publish(text, image_path)` posts to `/rest/posts` and, when an image is
    given, initializes the Images API upload and PUTs the **local JPEG bytes**
    straight from `backend/media/` — no public media URL needed.
- `publish.py` — `provider_for(platform)` / `publish_post(...)`. The one place
  to register a new platform; Instagram should slot in here.

OAuth state is single-use with a 10-minute TTL, stored in
`orchestrator/session.py` alongside the encrypted-at-rest-free tokens — this
is a one-user hackathon session, not a credential vault.
