from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ingestion.fetch import FetchedSource
from orchestrator import routes
from orchestrator.main import app
from orchestrator.session import session

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_session():
    session.reset()
    yield
    session.reset()


def _fake_source(url: str, deep: bool = False) -> FetchedSource:
    return FetchedSource(
        id="src-1",
        url=url,
        host="example.com",
        title="Example Page",
        path="example.com/post",
        context="# Example Page\nSource: https://example.com/post\n\nWe shipped something new.",
        deep=deep,
        status="ready",
    )


def test_session_clear_and_health():
    assert client.get("/health").json() == {"status": "ok"}

    body = client.get("/api/session").json()
    assert body == {
        "sources": [],
        "posts": [],
        "linkedin": {
            "connected": False,
            "status": "disconnected",
            "displayName": None,
            "expiresAt": None,
        },
        "referenceImage": None,
        "watermark": None,
    }

    assert client.post("/api/session/clear").json() == {"ok": True}


def test_add_source_rejects_invalid_url():
    response = client.post("/api/sources", json={"url": "not a url"})
    assert response.status_code == 400


def test_add_and_remove_source(monkeypatch):
    monkeypatch.setattr(routes, "fetch_source", _fake_source)

    response = client.post("/api/sources", json={"url": "https://example.com/post"})
    assert response.status_code == 200
    source = response.json()["source"]
    assert source["title"] == "Example Page"
    assert source["status"] == "ready"

    assert len(client.get("/api/session").json()["sources"]) == 1
    assert client.delete(f"/api/sources/{source['id']}").json() == {"ok": True}
    assert client.get("/api/session").json()["sources"] == []


def test_generate_regenerate_and_approve_gate(monkeypatch):
    monkeypatch.setattr(routes, "fetch_source", _fake_source)

    # Sources are optional: generation works from the template + steering alone.
    solo = client.post("/api/generate", json={"templateId": "launch", "prompt": "be bold"})
    assert solo.status_code == 200
    assert len(solo.json()["bundle"]["posts"]) == 1

    client.post("/api/sources", json={"url": "https://example.com/post"})
    response = client.post("/api/generate", json={"templateId": "launch", "prompt": "be bold"})
    assert response.status_code == 200

    bundle = response.json()["bundle"]
    assert bundle["templateId"] == "launch"
    assert len(bundle["posts"]) == 1
    post = bundle["posts"][0]
    assert post["platform"] == "linkedin"
    assert post["text"]
    assert post["status"] == "preview"
    assert post["variantIndex"] == 0

    regenerated = client.post("/api/regenerate", json={"postId": post["id"]}).json()["post"]
    assert regenerated["variantIndex"] == 1

    blocked = client.post("/api/approve", json={"postId": post["id"]})
    assert blocked.status_code == 409
    assert blocked.json()["connectUrl"] == "/api/oauth/linkedin/connect"


def test_regenerate_unknown_post_is_404():
    assert client.post("/api/regenerate", json={"postId": "nope"}).status_code == 404
    assert client.post("/api/image", json={"postId": "nope"}).status_code == 404


PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_reference_roundtrip():
    assert client.get("/api/session").json()["referenceImage"] is None

    response = client.post("/api/reference", json={"dataUrl": PNG_1PX})
    assert response.status_code == 200
    url = response.json()["referenceImage"]
    assert url.startswith("/media/") and url.endswith(".png")
    assert client.get("/api/session").json()["referenceImage"] == url

    assert client.post("/api/reference", json={"dataUrl": "data:text/plain;base64,aGk="}).status_code == 400
    assert client.post("/api/reference", json={"dataUrl": "not-a-data-url"}).status_code == 400

    cleared = client.delete("/api/reference")
    assert cleared.status_code == 200
    assert cleared.json()["referenceImage"] is None
    assert client.get("/api/session").json()["referenceImage"] is None


def test_watermark_roundtrip():
    assert client.get("/api/session").json()["watermark"] is None

    saved = client.post("/api/watermark", json={"watermark": "  @acme  "})
    assert saved.status_code == 200
    assert saved.json()["watermark"] == "@acme"
    assert client.get("/api/session").json()["watermark"] == "@acme"

    disabled = client.post("/api/watermark", json={"watermark": ""})
    assert disabled.json()["watermark"] == ""
    assert client.get("/api/session").json()["watermark"] == ""

    fallback = client.post("/api/watermark", json={"watermark": None})
    assert fallback.json()["watermark"] is None
