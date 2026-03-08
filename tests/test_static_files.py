from __future__ import annotations

from fastapi.testclient import TestClient


def test_static_placeholder_is_served():
    from app.main import app

    client = TestClient(app)
    r = client.get("/static/placeholders/recommendation.svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")

