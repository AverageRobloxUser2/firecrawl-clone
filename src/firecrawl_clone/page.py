"""Page operations — navigate, click, type, screenshot, etc."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass, field

import nodriver as nd

from .browser import Browser
from .clean import html_to_markdown
from .errors import NavigationError, SelectorError, ScrapingError
from .images import _ensure_dir
from .protocol import Link


@dataclass
class PageResult:
    """Result of a page operation that returns content."""
    markdown: str
    links: list[Link]
    images: dict[str, str] = field(default_factory=dict)  # uuid -> local path
    title: str = ""


async def _extract_links(tab) -> list[Link]:
    """Extract all links from the current page."""
    raw = await tab.evaluate("""
        JSON.stringify(Array.from(document.querySelectorAll('a[href]')).map(a => ({
            url: a.href,
            text: (a.innerText || a.textContent || '').trim()
        })))
    """)
    links_data = json.loads(raw or "[]")
    return [Link(url=item["url"], text=item["text"]) for item in links_data]


def _guess_ext(url: str) -> str:
    """Guess file extension from URL."""
    parts = url.rsplit(".", 1)
    if len(parts) == 2:
        ext = parts[1].split("?")[0].split("&")[0].lower()
        known = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}
        if ext in known:
            return f".{ext}"
    return ".png"


async def _download_images(image_map: dict[str, str], tab=None) -> dict[str, str]:
    """Download images from URL map. Returns {uuid: local_path}."""
    if tab is None:
        tab = await Browser.get_tab()
    downloaded: dict[str, str] = {}

    for img_uuid, url in image_map.items():
        try:
            ext = _guess_ext(url)
            path = _ensure_dir() / f"{img_uuid}{ext}"
            # escape URL for JS string
            safe_url = url.replace("\\", "\\\\").replace("'", "\\'")
            b64 = await tab.evaluate(
                f"(async () => {{ const r = await fetch('{safe_url}'); const buf = await r.arrayBuffer(); return btoa(String.fromCharCode(...new Uint8Array(buf))); }})()",
                await_promise=True,
            )
            data = base64.b64decode(b64)
            path.write_bytes(data)
            downloaded[img_uuid] = str(path)
        except Exception:
            continue  # skip failed images

    return downloaded


async def _resolve_markdown_images(markdown: str, image_map: dict[str, str]) -> str:
    """Replace __IMG_{uuid}__ placeholders with local paths in markdown."""
    for img_uuid, path in image_map.items():
        markdown = markdown.replace(f"__IMG_{img_uuid}__", path)
    return markdown


async def _get_page_content(tab) -> PageResult:
    """Extract markdown, links, and images from the current page."""
    await tab  # wait for page to settle

    title = await tab.evaluate("document.title") or ""
    page_url = tab.url or ""

    # Strip elements with display:none or visibility:hidden before markdown conversion
    html = await tab.evaluate("""
        (() => {
            function isVisible(el) {
                while (el && el !== document.body) {
                    const s = getComputedStyle(el);
                    if (s.display === 'none' || s.visibility === 'hidden') return false;
                    el = el.parentElement;
                }
                return true;
            }
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            const toRemove = [];
            let node = walker.currentNode;
            while (node) {
                if (!isVisible(node)) {
                    toRemove.push(node);
                }
                node = walker.nextNode();
            }
            toRemove.forEach(el => el.remove());
            return document.documentElement.outerHTML;
        })()
    """)
    html = html

    # convert HTML to markdown, get image UUIDs
    markdown, image_urls = html_to_markdown(html, base_url=page_url, clean=True)

    # download images via browser (carries cookies)
    if image_urls:
        downloaded = await _download_images(image_urls)
        markdown = await _resolve_markdown_images(markdown, downloaded)
    else:
        downloaded = {}

    links = await _extract_links(tab)

    return PageResult(markdown=markdown, links=links, images=downloaded, title=title)


async def navigate(url: str) -> PageResult:
    """Navigate to a URL and return markdown + links + images."""
    tab = await Browser.get_tab()

    try:
        await tab.get(url)
    except Exception as e:
        raise NavigationError(f"Failed to navigate to {url}: {e}") from e

    return await _get_page_content(tab)


async def click(selector: str) -> PageResult:
    """Click an element matching the CSS selector, return new page content."""
    tab = await Browser.get_tab()

    try:
        el = await tab.select(selector)
        if el is None:
            raise SelectorError(f"No element matched selector: {selector}")
        await el.click()
    except SelectorError:
        raise
    except Exception as e:
        raise SelectorError(f"Click failed on '{selector}': {e}") from e

    return await _get_page_content(tab)


async def type_text(text: str, selector: str) -> bool:
    """Type text into an element matching the CSS selector."""
    tab = await Browser.get_tab()

    try:
        el = await tab.select(selector)
        if el is None:
            raise SelectorError(f"No element matched selector: {selector}")
        await el.send_keys(text)
        return True
    except SelectorError:
        raise
    except Exception as e:
        raise SelectorError(f"Type failed on '{selector}': {e}") from e


async def wait_for(selector: str, timeout: int = 10) -> bool:
    """Wait for an element matching the CSS selector to appear."""
    tab = await Browser.get_tab()

    try:
        el = await tab.select(selector, timeout=timeout)
        return el is not None
    except Exception:
        return False


async def screenshot() -> str:
    """Take a screenshot of the current page. Return path to saved PNG."""
    tab = await Browser.get_tab()
    path = _ensure_dir() / f"screenshot-{uuid.uuid4().hex}.png"

    try:
        await tab.save_screenshot(str(path))
        return str(path)
    except Exception as e:
        raise ScrapingError(f"Screenshot failed: {e}") from e


async def save_image(url: str) -> str:
    """Download an image through the browser (uses cookies/session).
    
    Uses JS fetch() in browser context — carries all cookies, auth, etc.
    """
    tab = await Browser.get_tab()
    ext = _guess_ext(url)
    path = _ensure_dir() / f"img-{uuid.uuid4().hex}{ext}"

    try:
        safe_url = url.replace("\\", "\\\\").replace("'", "\\'")
        b64 = await tab.evaluate(
            f"(async () => {{ const r = await fetch('{safe_url}'); const buf = await r.arrayBuffer(); return btoa(String.fromCharCode(...new Uint8Array(buf))); }})()",
            await_promise=True,
        )
        data = base64.b64decode(b64)
        path.write_bytes(data)
        return str(path)
    except Exception as e:
        raise ScrapingError(f"Failed to save image {url}: {e}") from e


async def get_links() -> list[Link]:
    """Return all links on the current page."""
    tab = await Browser.get_tab()
    return await _extract_links(tab)


async def go_back() -> PageResult:
    """Navigate back in history."""
    tab = await Browser.get_tab()

    try:
        await tab.back()
    except Exception as e:
        raise NavigationError(f"Failed to go back: {e}") from e

    return await _get_page_content(tab)
