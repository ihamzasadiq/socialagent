"""Route an approved post to the right provider.

Only LinkedIn is wired up today. Instagram has a provider-shaped hole here:
implement ``Provider``, register it below, and ``/api/approve`` starts working
for it without any other change.
"""

from __future__ import annotations

from config import settings
from distribution.base import Provider, ProviderNotSupported
from distribution.linkedin import LinkedInProvider
from orchestrator.session import LinkedInConnection


def provider_for(platform: str) -> Provider:
    if platform == "linkedin":
        return LinkedInProvider(settings)
    raise ProviderNotSupported(f"{platform} publishing is not wired up yet")


async def publish_post(
    platform: str,
    connection: LinkedInConnection,
    text: str,
    image_path: str | None = None,
) -> str:
    provider = provider_for(platform)
    return await provider.publish(
        connection.access_token, connection.external_id, text, image_path
    )
