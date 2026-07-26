"""Action logging — browser actions + network requests with initiator traces.

Captures all browser actions (navigate, click, type, evaluate, etc.) and
network requests with full context:
- Request body: ALWAYS captured
- Response body: selective by MIME type (text/json/html only by default)
- Initiator: full JS stack trace backtrace via CDP Debugger domain
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import nodriver.cdp.network as cdp_network
import nodriver.cdp.debugger as cdp_debugger
import nodriver.cdp.runtime as cdp_runtime


# ── MIME type filtering ────────────────────────────────────────

# Default MIME prefixes for response body capture.
# We log text, json, xml, binary data — skip media files.
DEFAULT_LOG_RESPONSE_MIME_PREFIXES = frozenset({
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/x-www-form-urlencoded",
    "application/javascript",
    "application/x-javascript",
    "application/octet-stream",  # binary data — useful
    "application/x-bin",
    "application/wasm",
    "application/msgpack",
    "application/proto",
    "message/",
    "multipart/",
    "application/ld+json",
    "application/manifest+json",
    "application/graphql-response+json",
    "application/x-protobuf",
})

# MIME prefixes to skip (media files that are useless in traces)
SKIP_RESPONSE_MIME_PREFIXES = frozenset({
    "image/",  # jpg, png, gif, webp, bmp, svg — all graphics
    "video/",
    "audio/",
    "font/",
    "application/vnd.",  # proprietary (ms office, adobe, etc.)
})


def _should_log_response(mime_type: str, extra_prefixes: frozenset[str] = frozenset()) -> bool:
    """Decide whether to log a response body based on MIME type.

    Logic:
    1. If mime matches any DEFAULT_LOG prefix → log (exact types like svg+xml win over skip)
    2. If mime matches any extra_prefix → log (user override)
    3. If mime matches any SKIP prefix → skip
    4. Default: skip unknown types
    """
    mime_lower = mime_type.lower().split(";")[0].strip()

    # Check default log list first (svg+xml etc. should win)
    for prefix in DEFAULT_LOG_RESPONSE_MIME_PREFIXES:
        if mime_lower.startswith(prefix):
            return True

    # Check explicit extra prefixes (user override)
    for prefix in extra_prefixes:
        if mime_lower.startswith(prefix):
            return True

    # Check skip list
    for prefix in SKIP_RESPONSE_MIME_PREFIXES:
        if mime_lower.startswith(prefix):
            return False

    # Unknown type → skip
    return False


# ── Data models ────────────────────────────────────────────────

@dataclass
class InitiatorInfo:
    """Who caused this network request, with JS stack backtrace."""
    type: str = ""  # parser, script, preload, preflight, other
    url: str = ""
    line_number: int = -1
    column_number: int = -1
    stack_frames: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "url": self.url,
            **({"line": self.line_number} if self.line_number >= 0 else {}),
            **({"col": self.column_number} if self.column_number >= 0 else {}),
            "stack": self.stack_frames,
        }


@dataclass
class NetworkEntry:
    """A single captured network request/response with initiator trace."""
    request_id: str
    timestamp: float  # epoch seconds
    url: str = ""
    method: str = ""
    # Request
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: str = ""
    # Response
    status: int = 0
    reason_phrase: str = ""
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: str = ""
    mime_type: str = ""
    # Timing
    wall_time: float = 0
    finish_time: float = 0
    # Initiator
    initiator: InitiatorInfo = field(default_factory=InitiatorInfo)
    # Flags
    _response_body_skipped: bool = False  # was response body intentionally not captured?
    failed: bool = False
    error_text: str = ""

    def to_dict(self, include_bodies: bool = True) -> dict[str, Any]:
        d = {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "url": self.url,
            "method": self.method,
            "request_headers": self.request_headers,
            "request_body": self.request_body if include_bodies else "<redacted>",
            "status": self.status,
            "reason_phrase": self.reason_phrase,
            "response_headers": self.response_headers,
            "mime_type": self.mime_type,
            "initiator": self.initiator.to_dict(),
            "wall_time": self.wall_time,
            "finish_time": self.finish_time,
        }
        if self.failed:
            d["failed"] = True
            d["error_text"] = self.error_text

        if self._response_body_skipped:
            d["response_body"] = f"<skipped: {self.mime_type}>"
        elif include_bodies:
            d["response_body"] = self.response_body
        else:
            d["response_body"] = "<redacted>"

        return d


@dataclass
class ActionEntry:
    """A logged browser action (navigate, click, type, etc.)."""
    action: str
    timestamp: float
    params: dict[str, Any] = field(default_factory=dict)
    id: str = ""  # short unique id


# ── ActionLog class ────────────────────────────────────────────

class ActionLog:
    """Logs browser actions and network requests with full initiator traces.

    Uses CDP Network + Debugger domains to capture:
    - All browser actions (navigate, click, type, evaluate, screenshot, etc.)
    - All network requests with request body (always)
    - Response bodies (selective by MIME type, configurable)
    - Request initiator with full JS stack backtrace
    """

    def __init__(
        self,
        log_response_mimes: frozenset[str] | None = None,
    ):
        """Create an ActionLog.

        Args:
            log_response_mimes: Extra MIME type prefixes to log response bodies for.
                                By default, only text/json/xml/svg are logged.
                                Pass {"image/png"} to also capture PNG responses, etc.
                                Pass {"*"} to log ALL response bodies.
        """
        self._active = False
        self._tab = None
        self._entries: dict[str, NetworkEntry] = {}  # request_id -> entry
        self._completed: list[NetworkEntry] = []
        self._actions: list[ActionEntry] = []
        self._extra_mimes: frozenset[str] = log_response_mimes or frozenset()
        self._log_all_bodies = "*" in self._extra_mimes

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def pending_count(self) -> int:
        return len(self._entries)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def action_count(self) -> int:
        return len(self._actions)

    # ── Action logging ─────────────────────────────────────────

    def log_action(self, action: str, params: dict[str, Any] | None = None) -> str:
        """Log a browser action. Returns the action id."""
        import uuid
        entry = ActionEntry(
            action=action,
            timestamp=time.time(),
            params=params or {},
            id=uuid.uuid4().hex[:8],
        )
        self._actions.append(entry)
        return entry.id

    # ── Initiator parsing ──────────────────────────────────────

    @staticmethod
    def _parse_initiator(initiator) -> InitiatorInfo:
        """Parse a CDP Initiator object into InitiatorInfo with stack frames."""
        info = InitiatorInfo()
        if initiator is None:
            return info

        info.type = getattr(initiator, "type_", "other")
        info.url = initiator.url or ""
        info.line_number = getattr(initiator, "line_number", None) or -1
        info.column_number = getattr(initiator, "column_number", None) or -1

        # Parse JS stack trace
        stack = getattr(initiator, "stack", None)
        if stack is not None:
            frames = getattr(stack, "call_frames", []) or []
            for frame in frames:
                info.stack_frames.append({
                    "function": frame.function_name or "<anonymous>",
                    "url": frame.url or "",
                    "line": frame.line_number,
                    "column": frame.column_number,
                })
            # Handle async parent stacks
            parent = getattr(stack, "parent", None)
            if parent is not None:
                info.stack_frames.append({"--- async ---": parent.description or ""})
                parent_frames = getattr(parent, "call_frames", []) or []
                for frame in parent_frames:
                    info.stack_frames.append({
                        "function": frame.function_name or "<anonymous>",
                        "url": frame.url or "",
                        "line": frame.line_number,
                        "column": frame.column_number,
                    })

        return info

    # ── CDP event handlers ─────────────────────────────────────

    async def _on_request(self, event: cdp_network.RequestWillBeSent) -> None:
        """Handle Network.requestWillBeSent event."""
        req_id = str(event.request_id)
        request = event.request
        wall_time = event.wall_time

        initiator_info = self._parse_initiator(getattr(event, "initiator", None))

        entry = NetworkEntry(
            request_id=req_id,
            timestamp=time.time(),
            method=request.method,
            url=request.url,
            request_headers=dict(request.headers) if request.headers else {},
            wall_time=wall_time,
            initiator=initiator_info,
        )
        self._entries[req_id] = entry

        # Capture request body immediately if present
        if request.post_data or getattr(request, "has_post_data", False):
            await self._fetch_request_body(req_id)

    def _on_request_extra_info(self, event: cdp_network.RequestWillBeSentExtraInfo) -> None:
        """Handle Network.requestWillBeSentExtraInfo — patch in actual wire headers."""
        req_id = str(event.request_id)
        entry = self._entries.get(req_id)
        if entry is None:
            return
        # Only replace if we got actual headers (not empty from initiator-only)
        if event.headers:
            entry.request_headers = dict(event.headers)

    async def _on_response(self, event: cdp_network.ResponseReceived, tab=None) -> None:
        """Handle Network.responseReceived event — capture headers + body."""
        use_tab = tab or self._tab
        req_id = event.request_id
        response = event.response

        entry = self._entries.get(str(req_id))
        if entry is None:
            return

        entry.status = response.status
        entry.reason_phrase = response.status_text or ""
        entry.response_headers = dict(response.headers) if response.headers else {}
        entry.mime_type = response.mime_type or ""

        # Patch in refined request headers from response (headers actually sent over wire)
        # This is a fallback if RequestWillBeSentExtraInfo didn't fire or fired before _on_request
        refined_headers = getattr(response, "request_headers", None)
        if refined_headers and dict(refined_headers):
            entry.request_headers = dict(refined_headers)

        # Fetch response body immediately
        if entry.url and not entry.url.startswith(("data:", "blob:", "chrome://")):
            should_log = self._log_all_bodies or _should_log_response(entry.mime_type, self._extra_mimes)
            if should_log:
                try:
                    body, base64_encoded = await use_tab.send(cdp_network.get_response_body(req_id))
                    if base64_encoded and body:
                        body = base64.b64decode(body).decode("utf-8", errors="replace")
                    if body:
                        entry.response_body = body
                except Exception:
                    pass
            else:
                entry._response_body_skipped = True

    def _on_loading_finished(self, event: cdp_network.LoadingFinished, tab=None) -> None:
        """Handle Network.loadingFinished event."""
        req_id = str(event.request_id)
        entry = self._entries.pop(req_id, None)
        if entry is None:
            return

        entry.finish_time = event.timestamp
        self._completed.append(entry)

    def _on_loading_failed(self, event: cdp_network.LoadingFailed) -> None:
        """Handle Network.loadingFailed event."""
        req_id = str(event.request_id)
        entry = self._entries.pop(req_id, None)
        if entry is None:
            return

        entry.finish_time = event.timestamp
        entry.failed = True
        entry.error_text = event.error_text or "failed"
        self._completed.append(entry)

    # ── Body fetching ──────────────────────────────────────────

    async def _fetch_request_body(self, req_id: str) -> None:
        """Fetch request body for a request."""
        if not self._tab:
            return
        try:
            body, base64_encoded = await self._tab.send(
                cdp_network.get_request_post_data(cdp_network.RequestId(req_id))
            )
            entry = self._entries.get(req_id)
            if entry and body:
                if base64_encoded:
                    body = base64.b64decode(body).decode("utf-8", errors="replace")
                entry.request_body = body
        except Exception:
            pass

    # ── Lifecycle ──────────────────────────────────────────────

    async def start(self, tab) -> None:
        """Start capturing on the given nodriver tab.

        Enables Network + Debugger domains for full initiator stack traces.
        """
        if self._active:
            return
        self._active = True
        self._tab = tab

        # Enable Network domain with body caching
        await tab.send(cdp_network.enable(
            max_total_buffer_size=100_000_000,
            max_resource_buffer_size=1_000_000,
            enable_durable_messages=True,
        ))
        await tab.send(cdp_network.set_cache_disabled(cache_disabled=True))

        # Register event handlers after enable
        tab.add_handler(cdp_network.RequestWillBeSent, self._on_request)
        tab.add_handler(cdp_network.RequestWillBeSentExtraInfo, self._on_request_extra_info)
        tab.add_handler(cdp_network.ResponseReceived, self._on_response)
        tab.add_handler(cdp_network.LoadingFinished, self._on_loading_finished)
        tab.add_handler(cdp_network.LoadingFailed, self._on_loading_failed)

        # Enable debug stack attachment for deeper traces
        await tab.send(cdp_network.set_attach_debug_stack(enabled=True))

        # Enable Debugger domain for JS stack traces on script initiators
        try:
            await tab.send(cdp_debugger.enable())
            # Enable async call stacks (depth 50) for full async backtraces
            await tab.send(cdp_debugger.set_async_call_stack_depth(max_depth=50))
        except Exception:
            # Debugger might already be enabled by something else
            pass

    async def stop(self, tab) -> None:
        """Stop capturing on the given nodriver tab."""
        if not self._active:
            return
        self._active = False

        try:
            await tab.send(cdp_network.set_cache_disabled(cache_disabled=False))
        except Exception:
            pass

        # Try to disable Debugger (might fail if something else enabled it)
        try:
            await tab.send(cdp_debugger.disable())
        except Exception:
            pass

    def clear(self) -> None:
        """Clear all captured data."""
        self._entries.clear()
        self._completed.clear()
        self._actions.clear()

    # ── Export ─────────────────────────────────────────────────

    def export(
        self,
        include_bodies: bool = True,
        filter_actions: list[str] | None = None,
        filter_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Export all captured data as a JSON-serializable dict.

        Args:
            include_bodies: Include request/response bodies in output.
            filter_actions: Only include actions matching these names.
            filter_urls: Only include network entries matching these URL patterns.
        """
        # Filter actions
        actions = [asdict(a) for a in self._actions]
        if filter_actions:
            actions = [a for a in actions if a["action"] in filter_actions]

        # Filter network entries
        url_patterns = [re.compile(p) for p in (filter_urls or [])]

        network = []
        for entry in self._completed:
            if url_patterns and not any(p.search(entry.url) for p in url_patterns):
                continue
            network.append(entry.to_dict(include_bodies=include_bodies))

        # Add pending entries
        for entry in self._entries.values():
            if url_patterns and not any(p.search(entry.url) for p in url_patterns):
                continue
            d = entry.to_dict(include_bodies=include_bodies)
            d["_pending"] = True
            network.append(d)

        return {
            "actions": actions,
            "network": network,
            "summary": {
                "actions": len(actions),
                "network_completed": len(self._completed),
                "network_pending": len(self._entries),
                "response_bodies_captured": sum(
                    1 for e in self._completed if e.response_body
                ),
                "response_bodies_skipped": sum(
                    1 for e in self._completed if e._response_body_skipped
                ),
            },
        }

    def export_json(self, include_bodies: bool = True, **kwargs) -> str:
        """Export as JSON string."""
        return json.dumps(
            self.export(include_bodies=include_bodies, **kwargs),
            indent=2,
        )
