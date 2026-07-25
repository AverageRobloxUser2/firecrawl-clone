"""FastAPI HTTP server for browser automation sessions."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

from .session import SessionManager
from .browser import Browser

logger = logging.getLogger("firecrawl-clone")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    logger.info("firecrawl-clone server starting")
    yield
    await SessionManager.quit_all()
    logger.info("firecrawl-clone server stopped")


app = FastAPI(
    title="Firecrawl Clone",
    description="Local browser automation API",
    version="0.1.0",
    lifespan=lifespan,
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
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/back")
async def back_session(name: str):
    """Go back in session's tab history."""
    try:
        result = await SessionManager.go_back(name)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── interaction ────────────────────────────────────────────────

@app.post("/api/sessions/{name}/click")
async def click_session(name: str, selector: str = Query(...)):
    """Click an element by CSS selector."""
    try:
        result = await SessionManager.click(name, selector)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/type")
async def type_session(name: str, selector: str = Query(...), text: str = Query(...)):
    """Type text into an element by CSS selector."""
    try:
        result = await SessionManager.type_text(name, selector, text)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/wait")
async def wait_session(name: str, selector: str = Query(...), timeout: int = Query(10)):
    """Wait for an element by CSS selector."""
    try:
        result = await SessionManager.wait_for(name, selector, timeout)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sessions/{name}/elements")
async def elements_session(name: str):
    """Get interactive elements (inputs, buttons, selects, textareas) on current page."""
    try:
        elements = await SessionManager.get_elements(name)
        return {"ok": True, "elements": elements}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/evaluate")
async def evaluate_session(name: str, script: str = Query(...)):
    """Evaluate JavaScript in the session's tab."""
    try:
        result = await SessionManager.evaluate(name, script)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/query")
async def query_session(name: str, selector: str = Query(...)):
    """Query DOM for elements matching a CSS selector."""
    try:
        results = await SessionManager.query(name, selector)
        return {"ok": True, "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sessions/{name}/evaluate")
async def evaluate_session(name: str, script: str = Query(...)):
    """Evaluate JavaScript in the session's tab."""
    try:
        session = SessionManager.get(name)
        if not session:
            raise HTTPException(404, f"Session not found: {name}")
        result = await session.tab.evaluate(script)
        return {"ok": True, "result": result}
    except HTTPException:
        raise
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
        return {"ok": True, "links": links}
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
