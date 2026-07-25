"""Unit tests for HTML cleaning (no browser needed)."""

import pytest

from firecrawl_clone.clean import html_to_markdown, clean_html


class TestCleanHTML:
    def test_strips_scripts(self):
        html = '<body><script>evil()</script><p>safe</p></body>'
        result = clean_html(html)
        assert "evil" not in result
        assert "safe" in result

    def test_strips_styles(self):
        html = '<style>body{color:red}</style><p>content</p>'
        result = clean_html(html)
        assert "color:red" not in result
        assert "content" in result

    def test_strips_nav(self):
        html = '<nav><a href="/">Nav</a></nav><main><p>content</p></main>'
        result = clean_html(html)
        assert "Nav" not in result
        assert "content" in result

    def test_strips_footer(self):
        html = '<main><p>content</p></main><footer>foot</footer>'
        result = clean_html(html)
        assert "foot" not in result
        assert "content" in result

    def test_html_to_markdown(self):
        html = '<h1>Title</h1><p>Para with <strong>bold</strong>.</p>'
        md, img_map = html_to_markdown(html)
        assert "# Title" in md
        assert "**bold**" in md
        assert img_map == {}  # no images

    def test_html_to_markdown_images(self):
        html = '<body><img src="https://example.com/photo.jpg" alt="photo"></body>'
        md, img_map = html_to_markdown(html, base_url="https://example.com")
        assert len(img_map) == 1
        uuid_key = list(img_map.keys())[0]
        assert img_map[uuid_key] == "https://example.com/photo.jpg"
        assert f"__IMG_{uuid_key}__" in md
