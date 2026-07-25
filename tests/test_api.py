"""API integration tests — require external http server on port 18931.

Start test server:
    cd tests/fixtures && python3 -m http.server 18931

Run the firecrawl-api server:
    .venv/bin/firecrawl-api --port 3001

Then run tests:
    pytest tests/test_api.py -v
"""

from __future__ import annotations

import pytest
import httpx

BASE = "http://localhost:3001"
TEST_SITE = "http://localhost:18931"


@pytest.fixture(scope="module")
def client():
    """HTTP client for the API server."""
    return httpx.Client(base_url=BASE, timeout=30)


@pytest.fixture(scope="module", autouse=True)
def session_lifecycle(client):
    """Create session before tests, clean up after."""
    client.post("/api/sessions", params={"name": "test"})
    yield
    client.post("/api/quit")


class TestAPI:
    def test_navigate(self, client):
        r = client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "Firecrawl Clone Test Page" in data["markdown"]
        assert data["title"] == "Firecrawl Test Page"
        assert isinstance(data["images"], dict)
        assert isinstance(data["links"], list)

    def test_click(self, client):
        client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        r = client.post("/api/sessions/test/click", params={"selector": "#test-button"})
        assert r.status_code == 200
        assert "hidden" in r.json().get("markdown", "").lower()

    def test_type(self, client):
        client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        r = client.post("/api/sessions/test/type", params={"selector": "#test-input", "text": "hello"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_screenshot(self, client):
        client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        r = client.get("/api/sessions/test/screenshot")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 1000

    def test_links(self, client):
        client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        r = client.get("/api/sessions/test/links")
        assert r.status_code == 200
        assert any("example.com" in l["url"] for l in r.json()["links"])

    def test_save_image(self, client):
        r = client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        data = r.json()
        img_uuid = next(iter(data["images"]))
        r = client.get("/api/sessions/test/save_image", params={"uuid": img_uuid})
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_back(self, client):
        client.post("/api/sessions/test/navigate", params={"url": f"{TEST_SITE}/test_page.html"})
        client.post("/api/sessions/test/navigate", params={"url": "http://example.com"})
        r = client.post("/api/sessions/test/back")
        assert r.status_code == 200
        assert "Firecrawl Clone Test Page" in r.json()["markdown"]

    def test_list_sessions(self, client):
        r = client.get("/api/sessions")
        assert r.status_code == 200
        assert "test" in r.json()["sessions"]
