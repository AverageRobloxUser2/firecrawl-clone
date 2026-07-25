"""Ad blocking support — download uBlock Origin and register with Browser.

Usage:
    from firecrawl_clone.adblock import enable_adblock
    enable_adblock()  # downloads uBlock, calls Browser.add_extension()
    tab = await Browser.start()
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from .browser import Browser

_CACHE_DIR = pathlib.Path.home() / ".cache" / "firecrawl-clone"
_UBLOCK_DIR = _CACHE_DIR / "ublock-origin"


def _download_ublock() -> pathlib.Path:
    """Download and extract uBlock Origin. Returns extension directory."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # uBlock Origin Chrome extension from GitHub releases
    url = "https://github.com/gorhill/uBlock/releases/download/1.61.0/ublock_origin-1.61.0.chromium.zip"
    zip_path = _CACHE_DIR / "ublock.zip"

    try:
        subprocess.run(
            ["curl", "-fsSL", "-o", str(zip_path), url],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"warning: failed to download uBlock Origin: {e}", file=sys.stderr)
        print("installing manually: unzip uBlock Chrome ext to ~/.cache/firecrawl-clone/ublock-origin/", file=sys.stderr)
        return _UBLOCK_DIR

    import zipfile
    try:
        if _UBLOCK_DIR.exists():
            # clean old
            import shutil
            shutil.rmtree(_UBLOCK_DIR)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(_CACHE_DIR)
        zip_path.unlink()
    except Exception as e:
        print(f"warning: failed to extract uBlock Origin: {e}", file=sys.stderr)
        return _UBLOCK_DIR

    return _UBLOCK_DIR


def enable_adblock() -> pathlib.Path:
    """Download uBlock Origin and register it with the browser.
    
    Must be called BEFORE Browser.start().
    Returns the path to the extension directory.
    """
    if not _UBLOCK_DIR.exists():
        _download_ublock()

    if _UBLOCK_DIR.exists():
        Browser.add_extension(str(_UBLOCK_DIR))
        return _UBLOCK_DIR
    else:
        print("warning: uBlock Origin not available, ad blocking disabled", file=sys.stderr)
        return _UBLOCK_DIR
