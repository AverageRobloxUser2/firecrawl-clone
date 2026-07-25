"""Page operations — navigate, click, type, screenshot, etc."""

from __future__ import annotations

from dataclasses import dataclass

import json
import nodriver as nd

from .browser import Browser
from .clean import html_to_markdown
from .errors import NavigationError, SelectorError, ScrapingError
from .images import find_page_images
from .protocol import Link


@dataclass
class PageResult:
    """Result of a page operation that returns content."""
    markdown: str
    links: list[Link]
    images: list[str]
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


async def _get_page_content(tab) -> PageResult:
    """Extract markdown, links, and images from the current page."""
    await tab  # wait for page to settle

    title = await tab.evaluate("document.title") or ""
    html = await tab.get_content()
    markdown = html_to_markdown(html, clean=True)

    links = await _extract_links(tab)
    images = await find_page_images(tab)

    return PageResult(markdown=markdown, links=links, images=images, title=title)


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
    from .images import _ensure_dir

    tab = await Browser.get_tab()
    path = _ensure_dir() / f"screenshot-{tab.url.replace('://', '_').replace('/', '_')[:50]}.png"

    try:
        await tab.save_screenshot(str(path))
        return str(path)
    except Exception as e:
        raise ScrapingError(f"Screenshot failed: {e}") from e


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
