"""Download images from a page to /tmp/pi-browser-images/."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urljoin

import nodriver as nd
from bs4 import BeautifulSoup

from .errors import ImageError

IMAGE_DIR = Path("/tmp/pi-browser-images")


def _ensure_dir() -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_DIR


def _guess_ext(content_type: str = "", url: str = "") -> str:
    """Guess file extension from content-type or URL."""
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    if content_type in ext_map:
        return ext_map[content_type]
    # fallback: try URL extension
    if url:
        parts = url.rsplit(".", 1)
        if len(parts) == 2:
            ext = parts[1].split("?")[0].lower()
            if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"):
                return f".{ext}"
    return ".png"  # default


async def download_image(url: str, tab) -> str:
    """Download a single image by URL via browser. Return local file path."""
    try:
        ext = _guess_ext(url=url)
        filename = f"{uuid.uuid4()}{ext}"
        dest = _ensure_dir() / filename

        await tab.download_file(url, str(dest))
        return str(dest)
    except Exception as e:
        raise ImageError(f"Failed to download {url}: {e}") from e


async def find_page_images(tab: nd.Tab) -> list[str]:
    """Find all <img> tags on the current page, download them, return paths."""
    try:
        page_url = tab.url
        html = await tab.evaluate("document.documentElement.outerHTML")
        soup = BeautifulSoup(html, "lxml")

        images: list[str] = []
        for img_tag in soup.find_all("img"):
            src = img_tag.get("src") or img_tag.get("data-src")
            if not src:
                continue
            # resolve relative URLs
            abs_url = urljoin(page_url, src)
            try:
                path = await download_image(abs_url, tab)
                images.append(path)
            except ImageError:
                continue  # skip failed images, don't fail the whole scrape
        return images
    except Exception as e:
        raise ImageError(f"Failed to find images: {e}") from e
