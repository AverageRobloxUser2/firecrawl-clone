"""Entry point — read JSON commands from stdin, write JSON responses to stdout."""

from __future__ import annotations

import asyncio
import sys

from .browser import Browser
from .errors import FirecrawlError
from .page import navigate, click, type_text, wait_for, screenshot, save_image, get_links, go_back
from .protocol import Command, ErrorResponse, SuccessResponse


# ── handlers ───────────────────────────────────────────────────

async def _handle_navigate(cmd: Command) -> SuccessResponse:
    result = await navigate(cmd.params["url"])
    return SuccessResponse(
        markdown=result.markdown,
        links=result.links,
        images=result.images,
        message=f"navigated to {cmd.params['url']}",
    )


async def _handle_click(cmd: Command) -> SuccessResponse:
    result = await click(cmd.params["selector"])
    return SuccessResponse(
        markdown=result.markdown,
        links=result.links,
        images=result.images,
        message=f"clicked {cmd.params['selector']}",
    )


async def _handle_type(cmd: Command) -> SuccessResponse:
    ok = await type_text(cmd.params["text"], cmd.params["selector"])
    return SuccessResponse(message=f"typed into {cmd.params['selector']}" if ok else "type failed")


async def _handle_wait(cmd: Command) -> SuccessResponse:
    ok = await wait_for(cmd.params["selector"], cmd.params.get("timeout", 30))
    return SuccessResponse(
        message=f"element {cmd.params['selector']} found" if ok else f"timed out waiting for {cmd.params['selector']}",
    )


async def _handle_screenshot(cmd: Command) -> SuccessResponse:
    path = await screenshot()
    return SuccessResponse(path=path, message=f"screenshot saved to {path}")


async def _handle_save_image(cmd: Command) -> SuccessResponse:
    path = await save_image(cmd.params["url"])
    return SuccessResponse(path=path, message=f"saved image to {path}")


async def _handle_get_links(cmd: Command) -> SuccessResponse:
    links = await get_links()
    return SuccessResponse(links=links)


async def _handle_back(cmd: Command) -> SuccessResponse:
    result = await go_back()
    return SuccessResponse(
        markdown=result.markdown,
        links=result.links,
        images=result.images,
        message="navigated back",
    )


async def _handle_quit(cmd: Command) -> SuccessResponse:
    Browser.quit()
    return SuccessResponse(message="browser closed")


# command dispatch table (after all handlers are defined)
HANDLERS = {
    "navigate": _handle_navigate,
    "click": _handle_click,
    "type": _handle_type,
    "wait": _handle_wait,
    "screenshot": _handle_screenshot,
    "save_image": _handle_save_image,
    "get_links": _handle_get_links,
    "back": _handle_back,
    "quit": _handle_quit,
}


# ── main loop ──────────────────────────────────────────────────

async def _process_line(line: str) -> str:
    """Parse one JSON command, dispatch, return JSON response."""
    line = line.strip()
    if not line:
        return ""

    cmd = Command.from_json(line)

    handler = HANDLERS.get(cmd.cmd)
    if handler is None:
        return ErrorResponse.from_message(f"Unknown command: {cmd.cmd}", "unknown_command").to_json()

    try:
        result = await handler(cmd)
        return result.to_json()
    except FirecrawlError as e:
        return ErrorResponse.from_exception(e).to_json()
    except Exception as e:
        return ErrorResponse.from_message(f"Unexpected error: {e}", "unexpected_error").to_json()


async def run_async() -> None:
    """Read lines from stdin, process as JSON commands, write responses to stdout."""
    for line in sys.stdin:
        response = await _process_line(line)
        if response:
            print(response, flush=True)

    # cleanup on stdin close
    Browser.quit()


def main() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
