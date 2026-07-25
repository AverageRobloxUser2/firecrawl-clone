"""Strip junk from HTML and convert to clean markdown."""

from __future__ import annotations

import uuid
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

from .errors import ScrapingError

# tags to strip entirely (content + tag)
_STRIP_TAGS: set[str] = {
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "footer",
    "header",
    "aside",
    "svg",
}

# common nav/footer class hints — best effort
_NAV_CLASSES: set[str] = {
    "nav",
    "navigation",
    "menu",
    "sidebar",
    "footer",
    "breadcrumb",
    "cookie",
    "popup",
    "modal",
    "ad",
    "advertisement",
    "banner",
}


def _is_noise(element: Tag) -> bool:
    """Heuristic: is this element likely noise (nav, ads, etc.)?"""
    if element.name in _STRIP_TAGS:
        return True
    if element.attrs is None:
        return False
    classes = element.get("class", [])
    if isinstance(classes, list):
        class_str = " ".join(classes).lower()
        for hint in _NAV_CLASSES:
            if hint in class_str:
                return True
    return False


def clean_html(html: str) -> str:
    """Strip scripts/styles/nav/footer from HTML. Return clean HTML string."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        raise ScrapingError(f"Failed to parse HTML: {e}") from e

    for tag in soup.find_all():
        if _is_noise(tag):
            tag.decompose()

    return str(soup)


def _replace_image_urls(html: str, base_url: str) -> tuple[str, dict[str, str]]:
    """Replace <img> src URLs with UUID placeholders.
    
    Returns (modified_html, {uuid: original_url, ...}).
    """
    soup = BeautifulSoup(html, "lxml")
    image_map: dict[str, str] = {}

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        abs_url = urljoin(base_url, src)
        img_uuid = uuid.uuid4().hex[:16]
        alt = img.get("alt", "")
        # replace src with local UUID reference
        img["src"] = f"__IMG_{img_uuid}__"
        image_map[img_uuid] = abs_url

    return str(soup), image_map


def html_to_markdown(html: str, base_url: str = "", clean: bool = True) -> tuple[str, dict[str, str]]:
    """Convert HTML to markdown, replacing image URLs with UUIDs.
    
    Returns (markdown, image_map) where image_map is {uuid: original_url}.
    The markdown will have ![alt](__IMG_{uuid}__) references.
    """
    try:
        if clean:
            html = clean_html(html)

        # extract image URLs and replace with UUIDs
        html, image_map = _replace_image_urls(html, base_url)

        markdown = md(html, heading_style="ATX")
        return markdown, image_map
    except Exception as e:
        raise ScrapingError(f"Failed to convert to markdown: {e}") from e
