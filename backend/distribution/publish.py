"""Dev B owns this module: actually posting to each platform.

STUB — always succeeds, no real platform API call is made yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class PublishResult:
    status: str  # always "posted" today
    posted_at: str  # ISO 8601


def publish_post(post_id: str, platform: str, text: str) -> PublishResult:
    """STUB: fakes a successful publish, no real platform API call.

    TODO(Dev B): route by `platform` to the real integration — Twitter API
    v2, LinkedIn API, Discord webhook — posting `text`, and let failures
    (auth expired, rate limited, platform down) propagate as exceptions so
    orchestrator/routes.py can turn them into a real error response instead
    of the fake-always-succeeds behavior here. Will need distribution/oauth.py
    filled in first for anything that requires user authorization.
    """
    del post_id, platform, text  # unused until the real integration lands
    return PublishResult(status="posted", posted_at=datetime.now(timezone.utc).isoformat())
