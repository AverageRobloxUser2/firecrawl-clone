"""Browser singleton using nodriver. Supports multiple tabs via sessions."""

from __future__ import annotations

from pathlib import Path

import nodriver as nd

from .errors import BrowserError


class Browser:
    """Singleton nodriver browser. Supports multiple tabs."""

    _instance: nd.Browser | None = None
    _extensions: list[str] = []

    @classmethod
    def add_extension(cls, path: str | Path) -> None:
        """Add an extension to load on next browser start.
        
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
    async def start(cls) -> nd.Browser:
        """Start the browser if not already running. Return the browser instance."""
        if cls._instance is None:
            args = [
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ]
            for ext in cls._extensions:
                args.append(f"--load-extension={ext}")

            try:
                cls._instance = await nd.start(
                    headless=False,
                    browser_args=args,
                )
            except Exception as e:
                raise BrowserError(f"Failed to start browser: {e}") from e
        return cls._instance

    @classmethod
    async def new_tab(cls, url: str = "data:text/html,<html><body></body></html>") -> nd.Tab:
        """Create a new tab in the browser. Starts browser if needed."""
        browser = await cls.start()
        return await browser.get(url)

    @classmethod
    def get_browser(cls) -> nd.Browser | None:
        """Get the browser instance without starting it."""
        return cls._instance

    @classmethod
    def quit(cls) -> None:
        """Close the browser. Synchronous — nodriver stop() is sync."""
        if cls._instance is not None:
            try:
                cls._instance.stop()
            except Exception:
                pass
            cls._instance = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._instance is not None
