"""Session manager — maps session names to browser tabs."""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from .browser import Browser
from .clean import html_to_markdown
from .errors import BrowserError


@dataclass
class Session:
    """A browser session — one tab with its state."""
    name: str
    tab: Any  # nodriver Tab
    image_registry: dict[str, str] = field(default_factory=dict)


class SessionManager:
    """Manages browser sessions (tabs)."""

    _sessions: dict[str, Session] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def create(cls, name: str) -> Session:
        async with cls._lock:
            if name in cls._sessions:
                return cls._sessions[name]
            tab = await Browser.new_tab()
            session = Session(name=name, tab=tab)
            cls._sessions[name] = session
            return session

    @classmethod
    def get(cls, name: str) -> Session | None:
        return cls._sessions.get(name)

    @classmethod
    async def delete(cls, name: str) -> bool:
        async with cls._lock:
            session = cls._sessions.pop(name, None)
            if session:
                try:
                    await session.tab.close()
                except Exception:
                    pass
                return True
            return False

    @classmethod
    def list_sessions(cls) -> list[str]:
        return list(cls._sessions.keys())

    # ── internal helpers ───────────────────────────────────────

    @staticmethod
    async def _extract_links(tab) -> list[dict[str, str]]:
        raw = await tab.evaluate("""
            JSON.stringify(Array.from(document.querySelectorAll('a[href]')).map(a => ({
                url: a.href,
                text: (a.innerText || a.textContent || '').trim()
            })))
        """)
        return json.loads(raw or "[]")

    @staticmethod
    def _guess_ext(url: str) -> str:
        parts = url.rsplit(".", 1)
        if len(parts) == 2:
            ext = parts[1].split("?")[0].split("&")[0].lower()
            if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"):
                return f".{ext}"
        return ".png"

    @classmethod
    async def _download_images(cls, tab, image_map: dict[str, str]) -> dict[str, str]:
        from .images import _ensure_dir
        downloaded: dict[str, str] = {}
        for img_uuid, url in image_map.items():
            try:
                ext = cls._guess_ext(url)
                path = _ensure_dir() / f"{img_uuid}{ext}"
                safe_url = url.replace("\\", "\\\\").replace("'", "\\'")
                b64 = await tab.evaluate(
                    f"(async () => {{ const r = await fetch('{safe_url}'); const buf = await r.arrayBuffer(); return btoa(String.fromCharCode(...new Uint8Array(buf))); }})()",
                    await_promise=True,
                )
                data = base64.b64decode(b64)
                path.write_bytes(data)
                downloaded[img_uuid] = str(path)
            except Exception:
                continue
        return downloaded

    @classmethod
    async def _page_content(cls, session: Session) -> dict[str, Any]:
        tab = session.tab
        await tab.sleep(0.5)

        title = await tab.evaluate("document.title") or ""
        page_url = tab.url or ""
        html = await tab.get_content()

        markdown, image_urls = html_to_markdown(html, base_url=page_url, clean=True)

        if image_urls:
            downloaded = await cls._download_images(tab, image_urls)
            session.image_registry.update(downloaded)
            for img_uuid, path in downloaded.items():
                markdown = markdown.replace(f"__IMG_{img_uuid}__", path)
        else:
            downloaded = {}

        links = await cls._extract_links(tab)

        return {
            "markdown": markdown,
            "images": downloaded,
            "links": links,
            "title": title,
        }

    # ── public API ─────────────────────────────────────────────

    @classmethod
    async def navigate(cls, name: str, url: str) -> dict[str, Any]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        try:
            await session.tab.get(url)
            await session.tab.sleep(1)
        except Exception as e:
            raise BrowserError(f"Failed to navigate to {url}: {e}") from e
        return await cls._page_content(session)

    @classmethod
    async def go_back(cls, name: str) -> dict[str, Any]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        try:
            await session.tab.back()
            await session.tab.sleep(1)
        except Exception as e:
            raise BrowserError(f"Failed to go back: {e}") from e
        return await cls._page_content(session)

    @classmethod
    async def click(cls, name: str, selector: str) -> dict[str, Any]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        try:
            el = await session.tab.select(selector)
            if el is None:
                return {"ok": False, "error": f"No element matched: {selector}"}
            await el.click()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return await cls._page_content(session)

    @classmethod
    async def type_text(cls, name: str, selector: str, text: str) -> dict[str, Any]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        try:
            el = await session.tab.select(selector)
            if el is None:
                return {"ok": False, "error": f"No element matched: {selector}"}
            await el.clear_input()
            await el.send_keys(text)
            return {"ok": True, "message": f"typed into {selector}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def wait_for(cls, name: str, selector: str, timeout: int = 10) -> dict[str, Any]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        try:
            el = await session.tab.select(selector, timeout=timeout)
            return {"ok": True, "found": el is not None, "selector": selector}
        except Exception:
            return {"ok": True, "found": False, "selector": selector}

    @classmethod
    async def take_screenshot(cls, name: str) -> bytes:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        from .images import _ensure_dir
        path = _ensure_dir() / f"screenshot-{session.name}-{uuid.uuid4().hex[:8]}.png"
        await session.tab.save_screenshot(str(path))
        return path.read_bytes()

    @classmethod
    async def get_links(cls, name: str) -> list[dict[str, str]]:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        return await cls._extract_links(session.tab)

    @classmethod
    async def get_elements(cls, name: str) -> list[dict[str, Any]]:
        """Extract interactive elements (inputs, buttons, selects, textareas) from current page."""
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        raw = await session.tab.evaluate("""
            JSON.stringify(Array.from(document.querySelectorAll('input, button, select, textarea, [role=button], [role=textbox], [role=checkbox], [role=radio]')).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || null,
                name: el.name || null,
                id: el.id || null,
                placeholder: el.placeholder || null,
                value: (el.tagName.toLowerCase() === 'button' || el.tagName.toLowerCase() === 'select') ? el.textContent?.trim() : (el.value || null),
                disabled: el.disabled,
                checked: el.checked || null,
                role: el.getAttribute('role') || null,
                selector: el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}[name="${el.name || ''}"]`
            })))
        """)
        return json.loads(raw or "[]")

    @classmethod
    async def evaluate(cls, name: str, script: str) -> Any:
        """Evaluate JavaScript in the session's tab."""
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        return await session.tab.evaluate(script)

    @classmethod
    async def query(cls, name: str, selector: str) -> list[dict[str, Any]]:
        """Query the DOM for elements matching a CSS selector."""
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        # Escape selector for JS string literal
        safe = selector.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        js = f"var sel='{safe}';JSON.stringify(Array.from(document.querySelectorAll(sel)).map(function(el){{return{{tag:el.tagName.toLowerCase(),text:(el.innerText||el.textContent||'').trim().substring(0,200),html:el.innerHTML?el.innerHTML.substring(0,500):null,attributes:Object.fromEntries(Array.from(el.attributes).map(function(a){{return[a.name,a.value]}})),href:el.href||null,src:el.src||null,value:el.value||null}}}}))" 
        raw = await session.tab.evaluate(js)
        return json.loads(raw or "[]")

    @classmethod
    async def save_image(cls, name: str, img_uuid: str) -> tuple[bytes, str] | None:
        session = cls.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        path = session.image_registry.get(img_uuid)
        if not path:
            return None
        data = pathlib.Path(path).read_bytes()
        ext = pathlib.Path(path).suffix.lower()
        ct = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
        return data, ct.get(ext, "application/octet-stream")

    @classmethod
    async def quit_all(cls) -> None:
        async with cls._lock:
            for name in list(cls._sessions.keys()):
                try:
                    await cls._sessions[name].tab.close()
                except Exception:
                    pass
            cls._sessions.clear()
            Browser.quit()
