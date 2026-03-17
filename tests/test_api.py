import pytest
from fastapi.testclient import TestClient
from viralpulse.api import app


client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_platforms():
    resp = client.get("/api/v1/platforms")
    assert resp.status_code == 200
    platforms = resp.json()["platforms"]
    names = {p["name"] for p in platforms}
    assert "reddit" in names
    assert "tiktok" in names
    assert len(names) == 4


def test_posts_requires_topic():
    resp = client.get("/api/v1/posts")
    assert resp.status_code == 422


def test_topics_empty_without_db():
    resp = client.get("/api/v1/topics")
    assert resp.status_code == 200


def test_posts_empty_without_db():
    resp = client.get("/api/v1/posts?topic=test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["posts"] == []
