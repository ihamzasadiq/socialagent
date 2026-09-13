"""LinkedIn provider tests — every provider HTTP call is mocked with respx."""

from __future__ import annotations

import asyncio

import pytest
import respx
from httpx import Response

from config import settings
from distribution.linkedin import LinkedInProvider

PROVIDER = LinkedInProvider(settings)


def test_auth_url_includes_state_and_scopes():
    url = PROVIDER.auth_url("state-123")
    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?")
    assert "state=state-123" in url
    assert "w_member_social" in url
    assert "redirect_uri=https%3A%2F%2Ftest.example.com%2Foauth%2Fcallback%2Flinkedin" in url


def test_redirect_uri_override(monkeypatch):
    bridge = "https://bridge.example/functions/v1/linkedin-callback"
    monkeypatch.setattr(type(settings), "linkedin_redirect_uri", bridge)
    url = LinkedInProvider(settings).auth_url("state-xyz")
    assert "redirect_uri=https%3A%2F%2Fbridge.example%2Ffunctions%2Fv1%2Flinkedin-callback" in url


def test_exchange_code_and_identity():
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "li-token",
                    "expires_in": 5184000,
                    "scope": "openid profile w_member_social",
                },
            )
        )
        mock.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=Response(200, json={"sub": "abc123", "name": "Test User"})
        )
        bundle = asyncio.run(PROVIDER.exchange_code("code-1"))
        identity = asyncio.run(PROVIDER.fetch_identity(bundle.access_token))

    assert bundle.access_token == "li-token"
    assert bundle.expires_at is not None
    assert identity.external_id == "abc123"
    assert identity.display_name == "Test User"


def test_publish_text_only():
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://api.linkedin.com/rest/posts").mock(
            return_value=Response(201, headers={"x-restli-id": "urn:li:share:1"})
        )
        post_id = asyncio.run(PROVIDER.publish("token", "person-1", "hello"))

    assert post_id == "urn:li:share:1"
    import json

    body = json.loads(route.calls[0].request.content)
    assert body["author"] == "urn:li:person:person-1"
    assert body["commentary"] == "hello"
    assert "content" not in body


def test_publish_uploads_local_image(tmp_path):
    image = tmp_path / "post.jpg"
    image.write_bytes(b"\xff\xd8\xff fake jpeg bytes")

    with respx.mock(assert_all_called=True) as mock:
        init = mock.post("https://api.linkedin.com/rest/images?action=initializeUpload").mock(
            return_value=Response(
                200,
                json={"value": {"uploadUrl": "https://upload.example/put", "image": "urn:li:image:9"}},
            )
        )
        upload = mock.put("https://upload.example/put").mock(return_value=Response(201))
        posts = mock.post("https://api.linkedin.com/rest/posts").mock(
            return_value=Response(201, headers={"x-restli-id": "urn:li:share:2"})
        )
        post_id = asyncio.run(
            PROVIDER.publish("token", "person-1", "with image", str(image))
        )

    assert post_id == "urn:li:share:2"
    assert upload.calls[0].request.content == b"\xff\xd8\xff fake jpeg bytes"
    assert upload.calls[0].request.headers["content-type"] == "image/jpeg"
    assert init.called
    import json

    body = json.loads(posts.calls[0].request.content)
    assert body["content"] == {"media": {"id": "urn:li:image:9"}}


def test_publish_rejects_unknown_image_type(tmp_path):
    image = tmp_path / "post.bmp"
    image.write_bytes(b"bmp")

    from distribution.base import MediaNotSupported

    with pytest.raises(MediaNotSupported):
        asyncio.run(PROVIDER.publish("token", "person-1", "hi", str(image)))
