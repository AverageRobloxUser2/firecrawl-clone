"""Cookie consent blocker — load 'I don't care about cookies' Chrome extension.

Usage:
    from firecrawl_clone.cookies import enable_cookie_blocker
    enable_cookie_blocker()  # calls Browser.add_extension()
    tab = await Browser.start()
"""

from __future__ import annotations

import pathlib
import shutil

from .browser import Browser

_CACHE_DIR = pathlib.Path.home() / ".cache" / "firecrawl-clone"
_COOKIE_BLOCKER_DIR = _CACHE_DIR / "cookie-blocker"


def _unpacked_exists() -> bool:
    """Check if the extension directory and manifest exist."""
    return (
        _COOKIE_BLOCKER_DIR.is_dir()
        and (_COOKIE_BLOCKER_DIR / "manifest.json").is_file()
    )


def enable_cookie_blocker() -> pathlib.Path:
    """Register the cookie consent blocker extension with the browser.

    Must be called BEFORE Browser.start().
    Looks for unpacked extension at ~/.cache/firecrawl-clone/cookie-blocker/.

    Returns the path to the extension directory.
    """
    if _unpacked_exists():
        Browser.add_extension(str(_COOKIE_BLOCKER_DIR))
        return _COOKIE_BLOCKER_DIR
    else:
        import sys
        print(
            f"warning: cookie blocker not found at {_COOKIE_BLOCKER_DIR}",
            file=sys.stderr,
        )
        print(
            "to install: unpack 'I don't care about cookies' CRX to that path",
            file=sys.stderr,
        )
        return _COOKIE_BLOCKER_DIR
