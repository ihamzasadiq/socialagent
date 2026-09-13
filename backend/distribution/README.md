# backend/distribution — Dev B

Everything about actually getting a post onto a platform.

- `publish.py` — `publish_post(post_id, platform) -> PublishResult`. STUB:
  always fakes success, no real platform API call.
- `images.py` — `generate_image(post_id, platform) -> str`. STUB: returns a
  `placehold.co` URL. Not called from `orchestrator/` yet — the wire
  contract (`/shared/types.ts`) has no image field on `Post` today.
- `oauth.py` — empty, TODO-only. Nothing calls it yet since `publish_post`
  doesn't need real credentials until it stops being a stub.

## TODO — where to take this next

1. `oauth.py`: per-platform authorization-code flow (Twitter/X, LinkedIn,
   Discord all differ) and a place to keep the resulting tokens (env vars
   are fine for a hackathon).
2. `publish.py`: once auth exists, route `publish_post` by `platform` to the
   real API for each, and let real failures (expired auth, rate limits,
   platform outage) raise instead of always returning success — that also
   means `orchestrator/routes.py`'s `/api/approve` handler will need a real
   error path, not just the happy path it has today.
3. `images.py`: swap the placeholder URL for a real image-gen call. If a
   `Post` needs an `imageUrl` field once this is real, add it to
   `/shared/types.ts` and `orchestrator/schemas.py` together (see
   `/shared/README.md`).
