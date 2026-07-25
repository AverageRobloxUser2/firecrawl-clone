"""Integration tests — run against external http server.

Start server before testing:
    cd tests/fixtures && python3 -m http.server 18931

Then run:
    pytest tests/test_browser.py -v
"""

from __future__ import annotations

import pathlib

import pytest

from firecrawl_clone.browser import Browser
from firecrawl_clone.page import navigate, click, type_text, screenshot, get_links, go_back

BASE = "http://localhost:18931"


@pytest.fixture(autouse=True)
def browser_cleanup():
    """Ensure browser is cleaned up after each test."""
    yield
    Browser.quit()


class TestBrowserNavigation:
    async def test_navigate_to_page(self):
        result = await navigate(f"{BASE}/test_page.html")
        assert result.markdown
        assert "Firecrawl Clone Test Page" in result.markdown
        assert result.title == "Firecrawl Test Page"

    async def test_navigate_markdown_clean(self):
        """Markdown should not contain scripts, styles, nav, footer."""
        result = await navigate(f"{BASE}/test_page.html")
        assert "<script" not in result.markdown
        assert "<style" not in result.markdown
        assert "should be stripped" not in result.markdown

    async def test_navigate_links(self):
        result = await navigate(f"{BASE}/test_page.html")
        ext_links = [l for l in result.links if "example.com" in l.url]
        assert len(ext_links) >= 1
        assert ext_links[0].text == "link to example.com"

    async def test_get_links(self):
        await navigate(f"{BASE}/test_page.html")
        links = await get_links()
        assert any("example.com" in l.url for l in links)

    async def test_click_button(self):
        await navigate(f"{BASE}/test_page.html")
        result = await click("#test-button")
        assert "This message was hidden!" in result.markdown

    async def test_type_into_input(self):
        await navigate(f"{BASE}/test_page.html")
        ok = await type_text("hello world", "#test-input")
        assert ok is True

    async def test_screenshot(self):
        await navigate(f"{BASE}/test_page.html")
        path = await screenshot()
        assert pathlib.Path(path).exists()
        assert pathlib.Path(path).suffix == ".png"

    async def test_back_navigation(self):
        await navigate(f"{BASE}/test_page.html")
        await navigate("http://example.com")
        result = await go_back()
        assert "Firecrawl Clone Test Page" in result.markdown
