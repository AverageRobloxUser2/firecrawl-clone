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


def _annotate_interactive(html: str) -> str:
    """Annotate interactive elements (buttons, inputs, selects) with their selectors in the HTML.
    
    Inserts a data attribute on interactive elements so markdown conversion can include them.
    Returns modified HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    for el in soup.find_all(['button', 'input', 'select', 'textarea']):
        # Build a useful selector
        tag = el.name
        el_id = el.get('id', '')
        name = el.get('name', '')
        el_type = el.get('type', '')
        
        if el_id:
            selector = f"#{el_id}"
        elif name:
            selector = f"{tag}[name=\"{name}\"]"
        else:
            selector = f"{tag}"
        
        # Skip hidden inputs
        if el_type and el_type.lower() == 'hidden':
            continue
        
        # Get visible text
        if tag == 'button':
            text = (el.get_text(strip=True) or '').strip()
            label = f"[{tag}: {selector}] {text}"
        elif tag == 'input':
            if el_type and el_type.lower() in ('submit', 'button'):
                text = el.get('value', '') or el.get('alt', '')
                label = f"[{tag} {el_type}: {selector}] {text}"
            elif el_type and el_type.lower() in ('checkbox', 'radio'):
                label = f"[{tag} {el_type}: {selector}]"
            else:
                placeholder = el.get('placeholder', '')
                label = f"[{tag} {el_type}: {selector}] {placeholder}"
        elif tag == 'select':
            label = f"[{tag}: {selector}]"
        elif tag == 'textarea':
            placeholder = el.get('placeholder', '')
            label = f"[{tag}: {selector}] {placeholder}"
        else:
            continue
        
        # Insert label before the element
        from bs4 import NavigableString
        wrapper = soup.new_tag('span')
        wrapper.string = label
        el.replace_with(wrapper)
    
    return str(soup)


def html_to_markdown(html: str, base_url: str = "", clean: bool = True) -> tuple[str, dict[str, str]]:
    """Convert HTML to markdown, replacing image URLs with UUIDs.
    
    Returns (markdown, image_map) where image_map is {uuid: original_url}.
    The markdown will have ![alt](__IMG_{uuid}__) references.
    Interactive elements (buttons, inputs) are annotated inline.
    """
    try:
        if clean:
            html = clean_html(html)

        # extract image URLs and replace with UUIDs
        html, image_map = _replace_image_urls(html, base_url)

        # annotate interactive elements before markdown conversion
        html = _annotate_interactive(html)

        markdown = md(html, heading_style="ATX")
        return markdown, image_map
    except Exception as e:
        raise ScrapingError(f"Failed to convert to markdown: {e}") from e
