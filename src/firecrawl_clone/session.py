"""Session manager — maps session names to browser tabs."""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any

import time
from typing import Any

from .browser import Browser
from .clean import html_to_markdown
from .errors import BrowserError
from .action_log import ActionLog


@dataclass
class TabEntry:
    """A single tab in a session."""
    tab: Any  # nodriver Tab
    image_registry: dict[str, str] = field(default_factory=dict)
    action_log: ActionLog = field(default_factory=ActionLog)


@dataclass
class Session:
    """A browser session — multiple tabs with its state."""
    name: str
    tabs: list[TabEntry] = field(default_factory=list)

    def add_tab(self, tab) -> int:
        """Add a tab, return its index (1-based)."""
        idx = len(self.tabs)
        self.tabs.append(TabEntry(tab=tab))
        return idx + 1  # 1-based

    def get_tab(self, index: int) -> TabEntry:
        """Get tab by 0-based index. Always requires explicit index."""
        if index < 0 or index >= len(self.tabs):
            raise BrowserError(f"Tab {index + 1} not found, session has {len(self.tabs)} tab(s)")
        return self.tabs[index]


class SessionManager:
    """Manages browser sessions (multi-tab)."""

    _sessions: dict[str, Session] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def create(cls, name: str) -> Session:
        async with cls._lock:
            if name in cls._sessions:
                return cls._sessions[name]
            tab = await Browser.new_tab()
            session = Session(name=name)
            session.add_tab(tab)  # creates tab 0, returns index 1
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
                for te in session.tabs:
                    try:
                        await te.tab.close()
                    except Exception:
                        pass
                # If this was the last session, clear the browser reference.
                # nodriver kills the browser process when the last tab closes,
                # so _instance would be stale. Browser.start() will auto-restart next time.
                if not cls._sessions:
                    Browser.quit()
                return True
            return False

    @classmethod
    async def add_tab(cls, name: str, url: str = "") -> int:
        """Add a new tab to a session. Returns 1-based tab index."""
        async with cls._lock:
            session = cls._sessions.get(name)
            if not session:
                raise BrowserError(f"Session not found: {name}")
            if url:
                tab = await Browser.new_tab(url)
            else:
                tab = await Browser.new_tab()
            idx = session.add_tab(tab)
            return idx

    @classmethod
    async def detect_new_tabs(cls, name: str) -> list[int]:
        """Detect tabs opened outside this session and add them. Returns list of new tab indices."""
        session = cls._sessions.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        all_tabs = await Browser.list_tabs()
        # Use tab target URLs as identifiers since Tabs aren't hashable
        known_urls = set()
        for te in session.tabs:
            try:
                known_urls.add(te.tab.url or "")
            except Exception:
                pass
        new_indices = []
        for tab in all_tabs:
            try:
                tab_url = tab.url or ""
            except Exception:
                tab_url = ""
            if tab_url not in known_urls:
                idx = session.add_tab(tab)
                new_indices.append(idx)
                known_urls.add(tab_url)
        return new_indices

    @classmethod
    async def close_tab(cls, name: str, tab_index: int) -> bool:
        """Close a specific tab. tab_index is 1-based. Returns True on success."""
        async with cls._lock:
            session = cls._sessions.get(name)
            if not session:
                return False
            idx = tab_index - 1
            if idx < 0 or idx >= len(session.tabs):
                return False
            try:
                await session.tabs[idx].tab.close()
            except Exception:
                pass
            session.tabs.pop(idx)
            if not session.tabs:
                # Last tab closed, create a new one
                new_tab = await Browser.new_tab()
                session.add_tab(new_tab)
            return True

    @classmethod
    def switch_tab(cls, name: str, tab_index: int) -> bool:
        """Deprecated — tab is always specified explicitly. Kept for compat."""
        return True  # no-op

    @classmethod
    async def list_tabs(cls, name: str) -> list[dict[str, Any]]:
        """List all tabs in a session with index, title, url."""
        session = cls._sessions.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        result = []
        for i, te in enumerate(session.tabs):
            try:
                url = te.tab.url or ""
                title = await te.tab.evaluate("document.title") or ""
            except Exception:
                url = "<closed>"
                title = "<closed>"
            result.append({
                "index": i + 1,
                "title": title,
                "url": url,
            })
        return result

    @classmethod
    def list_sessions(cls) -> list[str]:
        return list(cls._sessions.keys())

    @staticmethod
    def parse_session_key(key: str) -> tuple[str, int]:
        """Parse 'session:tab' syntax. Returns (name, 0-based tab index).

        'test:1' -> ('test', 0)  # tab 1 = index 0
        'test:2' -> ('test', 1)  # tab 2 = index 1
        'test' -> raises error (must specify tab)
        """
        if ":" in key:
            parts = key.rsplit(":", 1)
            name = parts[0]
            tab_idx = int(parts[1]) - 1  # convert to 0-based
            return name, tab_idx
        raise BrowserError(f"No tab specified in '{key}'. Use format 'session:tab' (e.g. 'test:1')")

    @classmethod
    def get_tab(cls, key: str) -> tuple[Session, TabEntry]:
        """Get a specific tab from a session key. Returns (session, tab_entry)."""
        name, tab_idx = cls.parse_session_key(key)
        session = cls._sessions.get(name)
        if not session:
            raise BrowserError(f"Session not found: {name}")
        tab_entry = session.get_tab(tab_idx)
        return session, tab_entry

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
    async def _page_content(cls, session: Session, tab_entry: TabEntry = None) -> dict[str, Any]:
        if tab_entry is None:
            tab_entry = session.tab
        tab = tab_entry.tab
        await tab.sleep(0.5)

        title = await tab.evaluate("document.title") or ""
        page_url = tab.url or ""
        html = await tab.get_content()

        markdown, image_urls = html_to_markdown(html, base_url=page_url, clean=True)

        if image_urls:
            downloaded = await cls._download_images(tab, image_urls)
            tab_entry.image_registry.update(downloaded)
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
    async def navigate(cls, key: str, url: str) -> dict[str, Any]:
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "navigate", {"url": url})
        try:
            await tab_entry.tab.get(url)
            await tab_entry.tab.sleep(1)
        except Exception as e:
            raise BrowserError(f"Failed to navigate to {url}: {e}") from e
        return await cls._page_content(session, tab_entry)

    @classmethod
    async def go_back(cls, key: str) -> dict[str, Any]:
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "go_back", {})
        try:
            await tab_entry.tab.back()
            await tab_entry.tab.sleep(1)
        except Exception as e:
            raise BrowserError(f"Failed to go back: {e}") from e
        return await cls._page_content(session, tab_entry)

    @classmethod
    async def get_markdown(cls, key: str) -> dict[str, Any]:
        """Get current page markdown without navigating."""
        session, tab_entry = cls.get_tab(key)
        return await cls._page_content(session, tab_entry)

    @classmethod
    async def click(cls, key: str, selector: str, by_text: str = "") -> dict[str, Any]:
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "click", {"selector": selector, "by_text": by_text})
        tab = tab_entry.tab

        # Resolve target element
        el = None
        if by_text:
            # Click by visible text content
            safe_text = by_text.replace("'", "\\'")
            found = await tab.evaluate(f"""
                (function() {{
                    var targets = Array.from(document.querySelectorAll('button, a, input[type=submit], [role=button]'));
                    for (var i = 0; i < targets.length; i++) {{
                        var t = targets[i].textContent.trim();
                        if (t === '{safe_text}' || t.includes('{safe_text}')) {{
                            return true;
                        }}
                    }}
                    return false;
                }})()
            """)
            if not found:
                # Get available button texts as plain strings via innerText hack
                raw = await tab.evaluate(f"""
                    (function() {{
                        var targets = Array.from(document.querySelectorAll('button, a, input[type=submit], [role=button]'));
                        return JSON.stringify(targets.map(function(e) {{ return e.textContent.trim(); }}).slice(0, 20));
                    }})()
                """)
                import json
                matches = json.loads(raw or "[]")
                return {
                    "ok": False,
                    "error": f'No button found with text "{by_text}"',
                    "available": matches,
                }
            # Click the button via JS
            await tab.evaluate(f"""
                (function() {{
                    var targets = Array.from(document.querySelectorAll('button, a, input[type=submit], [role=button]'));
                    for (var i = 0; i < targets.length; i++) {{
                        var t = targets[i].textContent.trim();
                        if (t === '{safe_text}' || t.includes('{safe_text}')) {{
                            targets[i].click();
                            break;
                        }}
                    }}
                }})()
            """)
            return await cls._page_content(session, tab_entry)
        else:
            # Click by CSS selector
            try:
                el = await tab.select(selector)
            except Exception:
                # Selector syntax error
                return {"ok": False, "error": f"Invalid selector: {selector}"}
            if el is None:
                # Count similar elements for helpful error
                count = await tab.evaluate(f"""
                    (function() {{
                        try {{ return document.querySelectorAll('{selector.replace(chr(39), chr(92)+chr(39))}').length; }}
                        catch(e) {{ return -1; }}
                    }})()
                """)
                if count == 0:
                    return {"ok": False, "error": f"No element matched: {selector}"}
                elif count > 1:
                    return {"ok": False, "error": f"{count} elements matched '{selector}' — selector not unique. use --text instead"}
                else:
                    return {"ok": False, "error": f"Element '{selector}' found but not clickable (hidden or invalid)"}
            await el.click()
        return await cls._page_content(session, tab_entry)

    @classmethod
    async def type_text(cls, key: str, selector: str, text: str) -> dict[str, Any]:
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "type", {"selector": selector, "text": text})
        tab = tab_entry.tab
        try:
            el = await tab.select(selector)
            if el is None:
                return {"ok": False, "error": f"No element matched: {selector}"}
            await el.clear_input()
            await el.send_keys(text)
            # Dispatch input events for JS framework reactivity
            safe_sel = selector.replace("'", "\\'")
            await tab.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{safe_sel}');
                    if (el) {{
                        ['focus','input','keyup','change'].forEach(function(e) {{
                            el.dispatchEvent(new Event(e, {{bubbles:true}}));
                        }});
                    }}
                }})()"""
            )
            return {"ok": True, "message": f"typed into {selector}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def wait_for(cls, key: str, selector: str, timeout: int = 10, url_change: bool = False) -> dict[str, Any]:
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "wait", {"selector": selector, "timeout": timeout, "url_change": url_change})
        tab = tab_entry.tab
        if url_change:
            current_url = await tab.evaluate("window.location.href")
            elapsed = 0
            while elapsed < timeout:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                new_url = await tab.evaluate("window.location.href")
                if new_url != current_url:
                    return {"ok": True, "found": True, "old_url": current_url, "new_url": new_url}
            return {"ok": True, "found": False, "url": current_url, "message": "url did not change"}
        try:
            el = await tab.select(selector, timeout=timeout)
            return {"ok": True, "found": el is not None, "selector": selector}
        except Exception:
            return {"ok": True, "found": False, "selector": selector}

    @classmethod
    async def get_loading_state(cls, key: str) -> dict[str, Any]:
        """Get current page loading state."""
        session, tab_entry = cls.get_tab(key)
        tab = tab_entry.tab

        ready_state = await tab.evaluate("document.readyState")
        frames_pending = await tab.evaluate("""
            (function() {
                var count = 0;
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try {
                        if (frames[i].contentDocument && frames[i].contentDocument.readyState !== 'complete') {
                            count++;
                        }
                    } catch(e) {
                        count++;
                    }
                }
                return count;
            })()
        """)

        return {
            "ok": True,
            "ready_state": ready_state,
            "frames_pending": frames_pending,
            "is_loading": ready_state != "complete" or (frames_pending or 0) > 0,
        }

    @classmethod
    async def take_screenshot(cls, key: str) -> bytes:
        session, tab_entry = cls.get_tab(key)
        from .images import _ensure_dir
        path = _ensure_dir() / f"screenshot-{session.name}-{uuid.uuid4().hex[:8]}.png"
        await tab_entry.tab.save_screenshot(str(path))
        return path.read_bytes()

    @classmethod
    async def get_text(cls, key: str, selector: str) -> str:
        """Get visible text from an element matching a CSS selector."""
        session, tab_entry = cls.get_tab(key)
        text = await tab_entry.tab.evaluate(f"(document.querySelector('{selector.replace(chr(39), chr(92)+chr(39))}'))?.innerText?.trim() || ''")
        return text or ""

    @classmethod
    async def get_url(cls, key: str) -> str:
        """Get the current URL of the session via JS (tab.url can be stale)."""
        session, tab_entry = cls.get_tab(key)
        return await tab_entry.tab.evaluate("window.location.href")

    @classmethod
    async def get_links(cls, key: str) -> list[dict[str, str]]:
        session, tab_entry = cls.get_tab(key)
        return await cls._extract_links(tab_entry.tab)

    @classmethod
    async def get_elements(cls, key: str) -> list[dict[str, Any]]:
        """Extract interactive elements (inputs, buttons, selects, textareas) from current page."""
        session, tab_entry = cls.get_tab(key)
        raw = await tab_entry.tab.evaluate("""
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
    async def evaluate(cls, key: str, script: str) -> Any:
        """Evaluate JavaScript in the session's tab."""
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "evaluate", {"script": script})
        return await tab_entry.tab.evaluate(script)

    @classmethod
    async def query(cls, key: str, selector: str) -> list[dict[str, Any]]:
        """Query the DOM for elements matching a CSS selector."""
        session, tab_entry = cls.get_tab(key)
        cls._log_action(tab_entry, "query", {"selector": selector})
        # Escape selector for JS string literal
        safe = selector.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        js = f"var sel='{safe}';JSON.stringify(Array.from(document.querySelectorAll(sel)).map(function(el){{return{{tag:el.tagName.toLowerCase(),text:(el.innerText||el.textContent||'').trim().substring(0,200),html:el.innerHTML?el.innerHTML.substring(0,500):null,attributes:Object.fromEntries(Array.from(el.attributes).map(function(a){{return[a.name,a.value]}})),href:el.href||null,src:el.src||null,value:el.value||null}}}}))" 
        raw = await tab_entry.tab.evaluate(js)
        return json.loads(raw or "[]")

    @classmethod
    async def save_image(cls, key: str, img_uuid: str) -> tuple[bytes, str] | None:
        session, tab_entry = cls.get_tab(key)
        path = tab_entry.image_registry.get(img_uuid)
        if not path:
            return None
        data = pathlib.Path(path).read_bytes()
        ext = pathlib.Path(path).suffix.lower()
        ct = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
        return data, ct.get(ext, "application/octet-stream")

    # ── Action logging ─────────────────────────────────────────

    @staticmethod
    def _log_action(tab_entry: TabEntry, action: str, params: dict[str, Any] | None = None) -> str:
        """Log an action to the tab's action log. Returns action id."""
        return tab_entry.action_log.log_action(action, params)

    @classmethod
    async def action_log_on(cls, key: str, log_response_mimes: str | None = None) -> dict[str, Any]:
        """Turn on action logging for a session/tab."""
        session, tab_entry = cls.get_tab(key)
        extra_mimes = frozenset(log_response_mimes.split(",")) if log_response_mimes else None
        try:
            # Navigate to about:blank first to clear chrome:// context
            await tab_entry.tab.get('about:blank')
            tab_entry.action_log = ActionLog(log_response_mimes=extra_mimes)
            await tab_entry.action_log.start(tab_entry.tab)
            return {"ok": True, "message": f"action logging enabled for {key}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def action_log_off(cls, key: str) -> dict[str, Any]:
        """Turn off action logging for a session/tab."""
        session, tab_entry = cls.get_tab(key)
        try:
            await tab_entry.action_log.stop(tab_entry.tab)
            return {"ok": True, "message": f"action logging disabled for {key}",
                    "summary": tab_entry.action_log.export()["summary"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def action_log_export(
        cls,
        key: str,
        include_bodies: bool = True,
        filter_actions: str | None = None,
        filter_urls: str | None = None,
    ) -> dict[str, Any]:
        """Export action log data for a session/tab."""
        session, tab_entry = cls.get_tab(key)
        filter_actions_list = filter_actions.split(",") if filter_actions else None
        filter_urls_list = filter_urls.split(",") if filter_urls else None
        data = tab_entry.action_log.export(
            include_bodies=include_bodies,
            filter_actions=filter_actions_list,
            filter_urls=filter_urls_list,
        )
        return {"ok": True, **data}

    @classmethod
    async def action_log_clear(cls, key: str) -> dict[str, Any]:
        """Clear action log data for a session/tab."""
        session, tab_entry = cls.get_tab(key)
        tab_entry.action_log.clear()
        return {"ok": True, "message": f"action log cleared for {key}"}

    @classmethod
    async def quit_all(cls) -> None:
        async with cls._lock:
            for name in list(cls._sessions.keys()):
                for te in cls._sessions[name].tabs:
                    try:
                        await te.action_log.stop(te.tab)
                    except Exception:
                        pass
                    try:
                        await te.tab.close()
                    except Exception:
                        pass
            cls._sessions.clear()
            Browser.quit()
