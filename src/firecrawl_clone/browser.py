"""Browser singleton using nodriver."""

from __future__ import annotations

from pathlib import Path

import nodriver as nd

from .errors import BrowserError


class Browser:
    """Singleton nodriver browser. Start once, share across commands."""

    _instance: nd.Browser | None = None
    _current_tab: nd.Tab | None = None
    _extensions: list[str] = []

    @classmethod
    def add_extension(cls, path: str | Path) -> None:
        """Add an extension to load on next browser start.
        
        Path should point to an unpacked Chrome extension directory
        (one with a manifest.json).
        
        Must be called BEFORE start(). Has no effect after browser is running.
        
        Example:
            Browser.add_extension("/path/to/ublock-origin")
            tab = await Browser.start()
        """
        if cls._instance is not None:
            print(f"warning: Browser.add_extension() called after browser started, ignoring: {path}")
            return
        cls._extensions.append(str(path))

    @classmethod
    async def start(cls) -> nd.Tab:
        """Start the browser if not already running. Return the active tab."""
        if cls._instance is None:
            args = [
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ]
            # add extensions via --load-extension
            for ext in cls._extensions:
                args.append(f"--load-extension={ext}")

            try:
                cls._instance = await nd.start(
                    headless=False,
                    browser_args=args,
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
                pass
            cls._instance = None
            cls._current_tab = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._instance is not None
