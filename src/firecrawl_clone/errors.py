"""Exception hierarchy for firecrawl-clone."""


class FirecrawlError(Exception):
    """Base exception. All project errors inherit from this."""

    code: str = "unknown_error"
    message: str = "An unknown error occurred"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class BrowserError(FirecrawlError):
    """Browser lifecycle failures (start, quit, profile)."""

    code = "browser_error"
    message = "Browser operation failed"


class NavigationError(FirecrawlError):
    """Page navigation failures (timeout, bad URL, etc.)."""

    code = "navigation_error"
    message = "Navigation failed"


class SelectorError(FirecrawlError):
    """CSS/XPath selector didn't match any element."""

    code = "selector_error"
    message = "Selector matched no element"


class ScrapingError(FirecrawlError):
    """Content extraction failures (parse errors, etc.)."""

    code = "scraping_error"
    message = "Content scraping failed"


class ImageError(FirecrawlError):
    """Image download/save failures."""

    code = "image_error"
    message = "Image operation failed"
