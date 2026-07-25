"""Browser singleton using nodriver."""

from __future__ import annotations

import nodriver as nd

from .errors import BrowserError


class Browser:
    """Singleton nodriver browser. Start once, share across commands."""

    _instance: nd.Browser | None = None
    _current_tab: nd.Tab | None = None

    @classmethod
    async def start(cls) -> nd.Tab:
        """Start the browser if not already running. Return the active tab."""
        if cls._instance is None:
            try:
                cls._instance = await nd.start(
                    headless=False,
                    browser_args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                    ],
                )
            except Exception as e:
                raise BrowserError(f"Failed to start browser: {e}") from e

        # always create a fresh tab — the default new tab has endless
        # background activity that blocks `await tab` from settling
        try:
            _ = cls._current_tab.url
        except Exception:
            cls._current_tab = None
        if cls._current_tab is None:
            cls._current_tab = await cls._instance.get("data:text/html,<html><body></body></html>")
        return cls._current_tab

    @classmethod
    async def get_tab(cls) -> nd.Tab:
        """Get the current tab, starting browser if needed."""
        if cls._instance is None:
            return await cls.start()
        if cls._current_tab is None:
            return await cls.start()
        # check if tab is still usable — nodriver 0.50.3 has no is_closed
        try:
            _ = cls._current_tab.url
            return cls._current_tab
        except Exception:
            return await cls.start()

    @classmethod
    def quit(cls) -> None:
        """Close the browser. Synchronous — nodriver stop() is sync."""
        if cls._instance is not None:
            try:
                cls._instance.stop()
            except Exception:
                pass  # already closed
            cls._instance = None
            cls._current_tab = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._instance is not None
