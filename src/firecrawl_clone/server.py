"""FastAPI HTTP server for browser automation sessions."""

from __future__ import annotations

import json
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

from .session import SessionManager
from .browser import Browser
from .cookies import enable_cookie_blocker
from .adblock import enable_adblock

logger = logging.getLogger("firecrawl-clone")


async def _with_url(key: str, data: dict) -> dict:
    """Attach current URL to a response dict."""
    url = await SessionManager.get_url(key)
    data["url"] = url
    return data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    logger.info("firecrawl-clone server starting")
    # Load extensions before browser starts
    path = enable_cookie_blocker()
    if (path / "manifest.json").is_file():
        logger.info(f"cookie blocker extension loaded from {path}")
    abpath = enable_adblock()
    if (abpath / "manifest.json").is_file():
        logger.info(f"ad blocker extension loaded from {abpath}")
    yield
    await SessionManager.quit_all()
    logger.info("firecrawl-clone server stopped")


app = FastAPI(
    title="Firecrawl Clone",
    description="Local browser automation API",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Exception handler — print full tracebacks to console ──────

@app.exception_handler(Exception)
async def log_errors(request, exc):
    """Log full traceback for all unhandled exceptions."""
    logger.error(f"Unhandled exception on {request.method} {request.url}:\n{traceback.format_exc()}")
    return Response(
        status_code=500,
        content=json.dumps({"detail": str(exc)}),
        media_type="application/json",
    )


# ── session management ─────────────────────────────────────────

@app.post("/api/sessions")
async def create_session(name: str = Query(..., description="Session name")):
    """Create a new browser session (tab)."""
    session = await SessionManager.create(name)
    return {"ok": True, "session": session.name, "message": f"session '{name}' created"}


@app.delete("/api/sessions/{name}")
async def delete_session(name: str):
    """Close a browser session (tab)."""
    ok = await SessionManager.delete(name)
    if not ok:
        raise HTTPException(404, f"Session not found: {name}")
    return {"ok": True, "message": f"session '{name}' closed"}


@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions."""
    return {"sessions": SessionManager.list_sessions()}


@app.post("/api/sessions/{name}/add_tab")
async def add_tab(name: str, url: str = Query("")):
    """Add a new tab to a session. Returns tab index."""
    idx = await SessionManager.add_tab(name, url)
    return {"ok": True, "tab_index": idx, "message": f"added tab {idx} to session '{name}'"}


@app.get("/api/sessions/{name}/tabs")
async def list_tabs(name: str):
    """List all tabs in a session."""
    tabs = await SessionManager.list_tabs(name)
    return {"ok": True, "tabs": tabs}


@app.post("/api/sessions/{name}/switch_tab")
async def switch_tab(name: str, tab_index: int = Query(...)):
    """Switch the default tab for a session."""
    ok = SessionManager.switch_tab(name, tab_index)
    if not ok:
        raise HTTPException(404, f"Invalid tab index: {tab_index}")
    return {"ok": True, "message": f"switched to tab {tab_index}"}


@app.delete("/api/sessions/{name}/tabs/{tab_index}")
async def close_tab(name: str, tab_index: int):
    """Close a specific tab in a session."""
    ok = await SessionManager.close_tab(name, tab_index)
    if not ok:
        raise HTTPException(404, f"Invalid tab index: {tab_index}")
    return {"ok": True, "message": f"closed tab {tab_index} in session '{name}'"}


@app.post("/api/sessions/{name}/detect_tabs")
async def detect_tabs(name: str):
    """Detect and add newly opened browser tabs to the session."""
    new = await SessionManager.detect_new_tabs(name)
    return {"ok": True, "new_tabs": new, "message": f"found {len(new)} new tab(s)"}


@app.post("/api/quit")
async def quit_all():
    """Close all sessions and the browser."""
    await SessionManager.quit_all()
    return {"ok": True, "message": "all sessions closed, browser quit"}


# ── navigation ─────────────────────────────────────────────────

@app.post("/api/sessions/{name}/navigate")
async def navigate_session(name: str, url: str = Query(...)):
    """Navigate session's tab to a URL. Returns markdown, links, images."""
    try:
        result = await SessionManager.navigate(name, url)
        return await _with_url(name, {"ok": True, **result})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/back")
async def back_session(name: str):
    """Go back in session's tab history."""
    try:
        result = await SessionManager.go_back(name)
        return await _with_url(name, {"ok": True, **result})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/markdown")
async def markdown_session(name: str):
    """Get current page markdown without navigating."""
    try:
        result = await SessionManager.get_markdown(name)
        return await _with_url(name, result)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── interaction ────────────────────────────────────────────────

@app.post("/api/sessions/{name}/click")
async def click_session(name: str, selector: str = Query(""), by_text: str = Query("")):
    """Click an element by CSS selector or visible text."""
    if not selector and not by_text:
        raise HTTPException(400, "must provide selector or by_text")
    try:
        result = await SessionManager.click(name, selector, by_text)
        return await _with_url(name, result)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/type")
async def type_session(name: str, selector: str = Query(...), text: str = Query(...)):
    """Type text into an element by CSS selector."""
    try:
        result = await SessionManager.type_text(name, selector, text)
        return await _with_url(name, result)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/wait")
async def wait_session(name: str, selector: str = Query(""), timeout: int = Query(10), url_change: bool = Query(False)):
    """Wait for an element by CSS selector, or wait for URL to change."""
    try:
        result = await SessionManager.wait_for(name, selector, timeout, url_change)
        return await _with_url(name, result)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/loading")
async def loading_session(name: str):
    """Get current page loading state. Returns whether page/iframes are still loading."""
    try:
        result = await SessionManager.get_loading_state(name)
        return await _with_url(name, result)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/elements")
async def elements_session(name: str):
    """Get interactive elements (inputs, buttons, selects, textareas) on current page."""
    try:
        elements = await SessionManager.get_elements(name)
        return await _with_url(name, {"ok": True, "elements": elements})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/evaluate")
async def evaluate_session(name: str, script: str = Query(...)):
    """Evaluate JavaScript in the session's tab."""
    try:
        result = await SessionManager.evaluate(name, script)
        return await _with_url(name, {"ok": True, "result": result})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/query")
async def query_session(name: str, selector: str = Query(...)):
    """Query DOM for elements matching a CSS selector."""
    try:
        results = await SessionManager.query(name, selector)
        return await _with_url(name, {"ok": True, "results": results})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/text")
async def text_session(name: str, selector: str = Query(...)):
    """Get visible text from an element."""
    try:
        text = await SessionManager.get_text(name, selector)
        return await _with_url(name, {"ok": True, "text": text})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/url")
async def url_session(name: str):
    """Get the current URL of the session."""
    try:
        url = await SessionManager.get_url(name)
        return {"url": url}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── content ────────────────────────────────────────────────────

@app.get("/api/sessions/{name}/screenshot")
async def screenshot_session(name: str):
    """Take a screenshot. Returns PNG binary."""
    try:
        png_data = await SessionManager.take_screenshot(name)
        return Response(content=png_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/links")
async def links_session(name: str):
    """Get all links on the current page."""
    try:
        links = await SessionManager.get_links(name)
        return await _with_url(name, {"ok": True, "links": links})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/save_image")
async def save_image_session(name: str, uuid: str = Query(...)):
    """Download an image by its UUID (from navigate response). Returns image binary."""
    try:
        result = await SessionManager.save_image(name, uuid)
        if result is None:
            raise HTTPException(404, f"Image not found: {uuid}")
        data, content_type = result
        return Response(content=data, media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Action logging ─────────────────────────────────────────────

@app.post("/api/sessions/{name}/action_log/on")
async def action_log_on(name: str, log_response_mimes: str | None = Query(None)):
    """Enable action logging for a session.

    Args:
        name: Session name
        log_response_mimes: Comma-separated extra MIME type prefixes to log
                            (e.g. "image/png,video/mp4"). By default only text/json/xml.
    """
    try:
        result = await SessionManager.action_log_on(name, log_response_mimes=log_response_mimes)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "unknown"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/action_log/off")
async def action_log_off(name: str):
    """Disable action logging for a session. Returns summary."""
    try:
        result = await SessionManager.action_log_off(name)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "unknown"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/action_log/export")
async def action_log_export(
    name: str,
    include_bodies: bool = Query(True),
    filter_actions: str | None = Query(None),
    filter_urls: str | None = Query(None),
):
    """Export action log data as JSON.

    Args:
        name: Session name
        include_bodies: Include request/response bodies (default: True)
        filter_actions: Comma-separated action names to include
        filter_urls: Comma-separated URL regex patterns to include
    """
    try:
        result = await SessionManager.action_log_export(
            name,
            include_bodies=include_bodies,
            filter_actions=filter_actions,
            filter_urls=filter_urls,
        )
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "unknown"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/action_log/clear")
async def action_log_clear(name: str):
    """Clear action log data."""
    try:
        result = await SessionManager.action_log_clear(name)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "unknown"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


def run_server():
    """Run the FastAPI server with uvicorn. Pass --host and --port via CLI."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Firecrawl Clone API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3001, help="Port to bind to")
    args = parser.parse_args()

    logger.info(f"starting firecrawl-clone API on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
