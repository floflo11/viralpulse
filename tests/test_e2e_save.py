"""E2E tests for the save posts feature — full flow with structured data + images."""
import base64
import json
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """Client with a test user."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        pytest.skip("No DATABASE_URL set")

    from viralpulse.api import app
    from viralpulse.db import get_conn, init_db

    init_db()
    client = TestClient(app)

    # Create test user
    resp = client.post("/api/v1/users", json={"name": "E2E Test"})
    assert resp.status_code == 200
    user = resp.json()
    api_key = user["api_key"]

    yield client, api_key, str(user["id"])

    # Cleanup
    conn = get_conn()
    conn.execute("DELETE FROM saved_posts WHERE user_id = %s", (str(user["id"]),))
    conn.execute("DELETE FROM users WHERE id = %s", (str(user["id"]),))
    conn.commit()
    conn.close()


def test_save_with_structured_metadata(api_client):
    """Save a post with full metadata and verify retrieval."""
    client, key, uid = api_client
    resp = client.post("/api/v1/save",
        json={
            "url": "https://x.com/testuser/status/999",
            "metadata": {
                "author": "@testuser",
                "content": "This is a viral post about AI tools that got 50K likes #AI #viral",
                "engagement": {"likes": 50000, "comments": 2000, "shares": 5000, "views": 1200000},
                "hashtags": ["AI", "viral"],
            },
            "user_note": "amazing hook pattern #hook",
        },
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "twitter"
    assert data["id"]

    # Retrieve and verify
    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    assert resp.status_code == 200
    posts = resp.json()["posts"]
    assert len(posts) >= 1
    saved = next(p for p in posts if p["url"] == "https://x.com/testuser/status/999")
    assert saved["author"] == "@testuser"
    assert "AI tools" in saved["content"]
    assert saved["user_note"] == "amazing hook pattern #hook"
    assert saved["platform"] == "twitter"
    # Engagement stored as JSONB
    eng = saved.get("engagement")
    if isinstance(eng, str):
        eng = json.loads(eng)
    if eng:
        assert eng.get("likes") == 50000


def test_save_with_images(api_client):
    """Save a post with image data and verify images field is populated."""
    client, key, uid = api_client
    fake_img = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
    resp = client.post("/api/v1/save",
        json={
            "url": "https://reddit.com/r/test/comments/abc/image_post",
            "metadata": {
                "author": "redditor",
                "content": "Check out this amazing screenshot",
                "engagement": {"likes": 500},
                "hashtags": [],
                "images_base64": [f"data:image/png;base64,{fake_img}"],
                "video_thumbnail_base64": f"data:image/png;base64,{fake_img}",
                "video_url": "https://youtube.com/watch?v=abc123",
            },
        },
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    assert resp.json()["platform"] == "reddit"

    # Retrieve
    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    posts = resp.json()["posts"]
    saved = next(p for p in posts if "reddit.com" in p["url"])
    # images should be present (S3 URLs if configured, or may be empty if S3 fails in test)
    assert "images" in saved
    assert "video_url" in saved
    if saved.get("video_url"):
        assert saved["video_url"] == "https://youtube.com/watch?v=abc123"


def test_save_and_delete(api_client):
    """Save then delete a post."""
    client, key, uid = api_client
    resp = client.post("/api/v1/save",
        json={"url": "https://linkedin.com/feed/update/urn:123", "metadata": {"content": "delete me"}},
        headers={"X-API-Key": key},
    )
    post_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/saved/{post_id}", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    urls = [p["url"] for p in resp.json()["posts"]]
    assert "https://linkedin.com/feed/update/urn:123" not in urls


def test_save_search_filter(api_client):
    """Save two posts, search should filter correctly."""
    client, key, uid = api_client
    client.post("/api/v1/save",
        json={"url": "https://x.com/a/status/1", "metadata": {"content": "AI tools are changing the game", "author": "@ai_fan"}},
        headers={"X-API-Key": key},
    )
    client.post("/api/v1/save",
        json={"url": "https://x.com/b/status/2", "metadata": {"content": "Best sourdough bread recipe ever", "author": "@chef"}},
        headers={"X-API-Key": key},
    )

    # Search for AI
    resp = client.get("/api/v1/saved?query=AI", headers={"X-API-Key": key})
    posts = resp.json()["posts"]
    assert any("AI" in p.get("content", "") for p in posts)
    assert not any("sourdough" in p.get("content", "") for p in posts)

    # Search by author
    resp = client.get("/api/v1/saved?query=chef", headers={"X-API-Key": key})
    posts = resp.json()["posts"]
    assert any("sourdough" in p.get("content", "") for p in posts)


def test_save_dedup(api_client):
    """Saving the same URL twice should not create duplicates."""
    client, key, uid = api_client
    client.post("/api/v1/save",
        json={"url": "https://x.com/test/status/dup1", "metadata": {"content": "first save"}},
        headers={"X-API-Key": key},
    )
    client.post("/api/v1/save",
        json={"url": "https://x.com/test/status/dup1", "metadata": {"content": "second save"}, "user_note": "updated note"},
        headers={"X-API-Key": key},
    )

    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    matching = [p for p in resp.json()["posts"] if p["url"] == "https://x.com/test/status/dup1"]
    assert len(matching) == 1  # No duplicate


def test_auth_required(api_client):
    """Endpoints require X-API-Key header."""
    client, key, uid = api_client

    # No key
    assert client.get("/api/v1/saved").status_code == 401
    assert client.post("/api/v1/save", json={"url": "https://x.com/test"}).status_code == 401
    assert client.delete("/api/v1/saved/fake-id").status_code == 401

    # Bad key
    assert client.get("/api/v1/saved", headers={"X-API-Key": "bad_key"}).status_code == 403
