"""Strip junk from HTML and convert to clean markdown."""

from __future__ import annotations

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
    "form",
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

    # remove known noise tags
    for tag in soup.find_all():
        if _is_noise(tag):
            tag.decompose()

    return str(soup)


def html_to_markdown(html: str, clean: bool = True) -> str:
    """Convert HTML to markdown. Optionally clean first."""
    try:
        if clean:
            html = clean_html(html)
        return md(html, heading_style="ATX")
    except Exception as e:
        raise ScrapingError(f"Failed to convert to markdown: {e}") from e
