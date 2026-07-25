"""Browser singleton using nodriver. Supports multiple tabs via sessions."""

from __future__ import annotations

import os
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
    async def _is_alive(cls) -> bool:
        """Check if the browser is alive by sending a CDP command."""
        if cls._instance is None:
            return False
        try:
            # update_targets() sends Target.getTargets CDP command.
            # succeeds if ws is alive, raises if dead.
            await cls._instance.update_targets()
            return True
        except Exception:
            return False

    @classmethod
    async def start(cls) -> nd.Browser:
        """Start the browser if not already running. Return the browser instance."""
        if not await cls._is_alive():
            cls._instance = None  # clear dead reference
            args = [
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ]
            for ext in cls._extensions:
                args.append(f"--load-extension={ext}")

            try:
                headless = os.environ.get("FIRECRAWL_HEADLESS", "false").lower() in ("1", "true", "yes")
                cls._instance = await nd.start(
                    headless=headless,
                    browser_args=args,
                )
            except Exception as e:
                raise BrowserError(f"Failed to start browser: {e}") from e
        return cls._instance

    @classmethod
    async def new_tab(cls, url: str = "data:text/html,<html><body></body></html>") -> nd.Tab:
        """Create a new tab in the browser. Starts browser if needed.
        
        Uses new_tab=True to create a fresh tab each time. Cookie/storage
        is shared across tabs in the same browser — for true session isolation
        (separate cookies), separate browser profiles would be needed."""
        browser = await cls.start()
        return await browser.get(url, new_tab=True)

    @classmethod
    async def list_tabs(cls) -> list[nd.Tab]:
        """List all open tabs in the browser."""
        browser = await cls.start()
        await browser.update_targets()
        return list(browser.tabs)

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
