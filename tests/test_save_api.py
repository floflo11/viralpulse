from fastapi.testclient import TestClient
from viralpulse.api import app

client = TestClient(app)


def test_saved_requires_auth():
    resp = client.get("/api/v1/saved")
    assert resp.status_code == 401


def test_save_requires_auth():
    resp = client.post("/api/v1/save", json={"url": "https://x.com/test"})
    assert resp.status_code == 401


def test_delete_requires_auth():
    resp = client.delete("/api/v1/saved/fake-id")
    assert resp.status_code == 401


def test_save_returns_platform():
    from viralpulse.platform_detect import detect_platform
    assert detect_platform("https://x.com/test/status/123") == "twitter"
    assert detect_platform("https://reddit.com/r/test") == "reddit"
