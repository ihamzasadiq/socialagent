"""LinkedIn provider: OAuth authorization code + publishing.

Ported from the standalone oauth service, trimmed to what this app needs:

- No database — the caller passes tokens in from the in-memory session.
- No refresh-token dance; LinkedIn access tokens last ~60 days, far longer
  than a hackathon session.
- Images are uploaded straight from local bytes (the generated post image),
  so the media never needs a public URL. Only the OAuth callback does.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlencode

from config import Settings
from distribution.base import (
    Identity,
    MediaNotSupported,
    Provider,
    ProviderError,
    ProviderNotConfigured,
    TokenBundle,
    expires_at_from,
    request,
    request_json,
)

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}


class LinkedInProvider(Provider):
    name = "linkedin"

    auth_endpoint = "https://www.linkedin.com/oauth/v2/authorization"
    token_endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
    userinfo_endpoint = "https://api.linkedin.com/v2/userinfo"
    posts_endpoint = "https://api.linkedin.com/rest/posts"
    images_endpoint = "https://api.linkedin.com/rest/images"
    scopes = "openid profile w_member_social"
    api_version = "202601"

    def __init__(self, settings: Settings):
        self.settings = settings

    def credentials(self) -> tuple[str, str]:
        if not self.settings.linkedin_client_id or not self.settings.linkedin_client_secret:
            raise ProviderNotConfigured("LinkedIn client credentials are not configured")
        return self.settings.linkedin_client_id, self.settings.linkedin_client_secret

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Linkedin-Version": self.api_version,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def auth_url(self, state: str) -> str:
        client_id, _ = self.credentials()
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": self.settings.redirect_uri(self.name),
                "state": state,
                "scope": self.scopes,
            },
            quote_via=quote,
        )
        return f"{self.auth_endpoint}?{query}"

    async def exchange_code(self, code: str) -> TokenBundle:
        client_id, client_secret = self.credentials()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": self.settings.redirect_uri(self.name),
        }
        data = await request_json("POST", self.token_endpoint, data=payload)
        return TokenBundle(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at_from(data),
            scopes=data.get("scope"),
        )

    async def fetch_identity(self, access_token: str) -> Identity:
        data = await request_json(
            "GET",
            self.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        name = data.get("name") or " ".join(
            part for part in (data.get("given_name"), data.get("family_name")) if part
        )
        return Identity(external_id=str(data["sub"]), display_name=name or None)

    async def publish(
        self,
        access_token: str,
        external_id: str,
        text: str,
        image_path: str | None = None,
    ) -> str:
        body: dict = {
            "author": f"urn:li:person:{external_id}",
            "commentary": text or "",
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_path:
            image_urn = await self._upload_image(access_token, external_id, image_path)
            body["content"] = {"media": {"id": image_urn}}

        headers = self._headers(access_token) | {"Content-Type": "application/json"}
        response = await request(
            "POST", self.posts_endpoint, headers=headers, json=body, expected=(201,)
        )
        post_id = response.headers.get("x-restli-id")
        if not post_id:
            raise ProviderError("LinkedIn did not return a post id")
        return post_id

    async def _upload_image(self, access_token: str, external_id: str, image_path: str) -> str:
        path = Path(image_path)
        if not path.is_file():
            raise MediaNotSupported(f"Image file not found: {image_path}")
        content_type = CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise MediaNotSupported(f"Unsupported image type: {path.suffix}")

        headers = self._headers(access_token) | {"Content-Type": "application/json"}
        init = await request_json(
            "POST",
            f"{self.images_endpoint}?action=initializeUpload",
            headers=headers,
            json={"initializeUploadRequest": {"owner": f"urn:li:person:{external_id}"}},
        )
        value = init.get("value") or {}
        upload_url = value.get("uploadUrl")
        image_urn = value.get("image")
        if not upload_url or not image_urn:
            raise ProviderError("LinkedIn image upload initialization failed", payload=init)

        upload = await request(
            "PUT",
            upload_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": content_type},
            content=path.read_bytes(),
            expected=(200, 201),
            timeout=120.0,
        )
        if upload.status_code not in (200, 201):
            raise ProviderError("LinkedIn image upload failed", status_code=upload.status_code)
        return image_urn
