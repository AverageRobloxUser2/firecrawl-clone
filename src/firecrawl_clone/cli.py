#!/usr/bin/env python3
"""CLI tool for firecrawl-clone browser automation.

Usage:
    firecrawl session create mybot
    firecrawl navigate -s mybot:1 "https://example.com"
    firecrawl click -s mybot:1 "#login"
    firecrawl type -s mybot:1 "#pass" "secret"
    firecrawl screenshot -s mybot:1 -o page.png
    firecrawl links -s mybot:1
    firecrawl save-image -s mybot:1 <uuid> -o photo.png
    firecrawl console -s mybot:1
    firecrawl action-log on -s mybot:1
    firecrawl action-log export -s mybot:1 -o trace.json
    firecrawl session close mybot
    firecrawl session list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

DEFAULT_API = os.environ.get("FIRECRAWL_API", "http://localhost:42069")


def _client(base: str) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=60)


def cmd_session_create(args):
    """Create a named session."""
    r = _client(args.api).post("/api/sessions", params={"name": args.name})
    if r.status_code == 200:
        print(f"session '{args.name}' created")
    else:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)


def cmd_session_close(args):
    """Close a session."""
    r = _client(args.api).delete(f"/api/sessions/{args.name}")
    if r.status_code == 200:
        print(f"session '{args.name}' closed")
    else:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)


def cmd_session_list(args):
    """List active sessions."""
    r = _client(args.api).get("/api/sessions")
    data = r.json()
    sessions = data.get("sessions", [])
    if not sessions:
        print("no active sessions")
        return
    for s in sessions:
        print(s)


def cmd_session_list_tabs(args):
    """List tabs in a session."""
    r = _client(args.api).get(f"/api/sessions/{args.name}/tabs")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    for t in r.json().get("tabs", []):
        default = " *" if t.get("is_default") else ""
        print(f"  tab {t['index']}{default}  {t['title']}")
        print(f"         {t['url']}")


def cmd_session_add_tab(args):
    """Add a new tab to a session."""
    r = _client(args.api).post(f"/api/sessions/{args.name}/add_tab", params={"url": args.url or ""})
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print(f"added tab {data['tab_index']}")


def cmd_session_switch(args):
    """Switch default tab in a session."""
    r = _client(args.api).post(f"/api/sessions/{args.name}/switch_tab", params={"tab_index": args.tab})
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"switched to tab {args.tab}")


def cmd_session_close_tab(args):
    """Close a tab in a session."""
    r = _client(args.api).delete(f"/api/sessions/{args.name}/tabs/{args.tab}")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"closed tab {args.tab}")


def cmd_session_detect_tabs(args):
    """Detect newly opened browser tabs."""
    r = _client(args.api).post(f"/api/sessions/{args.name}/detect_tabs")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    if data.get("new_tabs"):
        print(f"found {len(data['new_tabs'])} new tab(s): {data['new_tabs']}")
    else:
        print("no new tabs")


def cmd_navigate(args):
    """Navigate to URL, print markdown."""
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/navigate",
        params={"url": args.url},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print(f"url: {data.get('url', '')}")
    if args.links:
        for link in data.get("links", []):
            print(f"[{link['text']}]({link['url']})")
    elif args.images:
        for uuid, path in data.get("images", {}).items():
            print(f"{uuid} -> {path}")
    else:
        print(data.get("markdown", ""))


def cmd_click(args):
    """Click an element, print new markdown."""
    params = {}
    if args.text:
        params["by_text"] = args.text
    elif args.selector:
        params["selector"] = args.selector
    else:
        print("error: must provide selector or --text", file=sys.stderr)
        sys.exit(1)
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/click",
        params=params,
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    # Auto-detect new tabs after click
    session_name = args.session.rsplit(":", 1)[0]  # strip tab index if present
    detect = _client(args.api).post(f"/api/sessions/{session_name}/detect_tabs")
    if detect.status_code == 200:
        new = detect.json().get("new_tabs", [])
        if new:
            print(f"(new tab(s) opened: {new})", file=sys.stderr)
    print(f"url: {data.get('url', '')}")
    if "error" in data:
        avail = data.get("available")
        if avail:
            print(f"click failed: {data['error']}", file=sys.stderr)
            print("available buttons:", file=sys.stderr)
            for b in avail:
                print(f"  - {b}", file=sys.stderr)
        else:
            print(f"click failed: {data['error']}", file=sys.stderr)
        sys.exit(1)
    print(data.get("markdown", ""))


def cmd_type(args):
    """Type text into an element."""
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/type",
        params={"selector": args.selector, "text": args.text},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print(f"url: {data.get('url', '')}")
    if data.get("ok"):
        print("ok")
    else:
        print(f"type failed: {data.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def cmd_wait(args):
    """Wait for an element or URL change."""
    params = {"timeout": args.timeout}
    if args.url_change:
        params["url_change"] = "true"
        params["selector"] = ""  # dummy, not used
    else:
        params["selector"] = args.selector
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/wait",
        params=params,
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    if args.url_change:
        if data.get("found"):
            print(f"url changed: {data.get('old_url', '')} -> {data.get('new_url', '')}")
        else:
            print(f"timeout: url still {data.get('url', '')}", file=sys.stderr)
            sys.exit(1)
    else:
        if data.get("found"):
            print("found")
        else:
            print("not found", file=sys.stderr)
            sys.exit(1)


def cmd_screenshot(args):
    """Take a screenshot. Saves to /tmp/<session>-<uuid>.png if no output specified."""
    import uuid as _uuid
    r = _client(args.api).get(f"/api/sessions/{args.session}/screenshot")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    if args.output:
        path = Path(args.output)
    else:
        path = Path(f"/tmp/{args.session}-{_uuid.uuid4().hex[:8]}.png")
    path.write_bytes(r.content)
    print(f"screenshot saved to {path}")


def cmd_links(args):
    """Print all links on the page."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/links")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    for link in r.json().get("links", []):
        print(f"[{link['text']}]({link['url']})")


def cmd_save_image(args):
    """Save an image by UUID."""
    r = _client(args.api).get(
        f"/api/sessions/{args.session}/save_image",
        params={"uuid": args.uuid},
    )
    if r.status_code == 404:
        print(f"image not found: {args.uuid}", file=sys.stderr)
        sys.exit(1)
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    if args.output:
        Path(args.output).write_bytes(r.content)
        print(f"image saved to {args.output}")
    else:
        print(r.content, file=sys.stdout.buffer)


def cmd_text(args):
    """Get visible text from an element."""
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/text",
        params={"selector": args.selector},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(r.json().get("text", ""))


def cmd_url(args):
    """Print current URL."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/url")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(r.json().get("url", ""))


def cmd_loading(args):
    """Print current page loading state."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/loading")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print(f"ready_state: {data.get('ready_state', '')}")
    print(f"frames_pending: {data.get('frames_pending', 0)}")
    print(f"is_loading: {data.get('is_loading', '')}")


def cmd_elements(args):
    """List interactive elements on the page."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/elements")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    for el in r.json().get("elements", []):
        tag = el.get("tag", "")
        typ = el.get("type", "")
        name = el.get("name", "")
        placeholder = el.get("placeholder", "")
        value = el.get("value", "")
        sel = el.get("selector", "")
        label = f"<{tag}" 
        if typ:
            label += f" type={typ}"
        if name:
            label += f" name={name}"
        if placeholder:
            label += f" placeholder={placeholder}"
        label += ">"
        print(f"{label}  [{sel}]")
        if value:
            print(f"  value: {value}")


def cmd_evaluate(args):
    """Evaluate JavaScript on the current page."""
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/evaluate",
        params={"script": args.script},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    result = data.get("result")
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2))
    else:
        print(result)


def cmd_query(args):
    """Query DOM elements by CSS selector."""
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/query",
        params={"selector": args.selector},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    for el in r.json().get("results", []):
        tag = el.get("tag", "")
        text = el.get("text", "")
        attrs = el.get("attributes", {})
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items() if k not in ("class", "style"))
        print(f"<{tag} {attr_str.strip()}> {text[:100]}")


def cmd_back(args):
    """Go back, print markdown."""
    r = _client(args.api).post(f"/api/sessions/{args.session}/back")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(r.json().get("markdown", ""))


def cmd_markdown(args):
    """Print current page markdown without navigating."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/markdown")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(r.json().get("markdown", ""))


def cmd_quit(args):
    """Quit all sessions and browser."""
    r = _client(args.api).post("/api/quit")
    if r.status_code == 200:
        print("browser closed")
    else:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)


def cmd_restart(args):
    """Restart the server."""
    r = _client(args.api).post("/api/server/restart")
    if r.status_code == 200:
        print("server restarting...")
    else:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)


def cmd_action_log_on(args):
    """Enable action logging."""
    params = {}
    if args.log_mimes:
        params["log_response_mimes"] = args.log_mimes
    r = _client(args.api).post(f"/api/sessions/{args.session}/action_log/on", params=params)
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print("action logging enabled")


def cmd_action_log_off(args):
    """Disable action logging."""
    r = _client(args.api).post(f"/api/sessions/{args.session}/action_log/off")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    summary = data.get("summary", {})
    print(f"action logging disabled.")
    print(f"  actions: {summary.get('actions', 0)}")
    print(f"  network requests: {summary.get('network_completed', 0)}")
    print(f"  response bodies captured: {summary.get('response_bodies_captured', 0)}")
    print(f"  response bodies skipped: {summary.get('response_bodies_skipped', 0)}")


def cmd_action_log_export(args):
    """Export action log data."""
    params = {
        "include_bodies": "false" if getattr(args, 'no_bodies', False) else "true",
    }
    if args.filter_actions:
        params["filter_actions"] = args.filter_actions
    if args.filter_urls:
        params["filter_urls"] = args.filter_urls
    r = _client(args.api).get(f"/api/sessions/{args.session}/action_log/export", params=params)
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2))
        print(f"action log exported to {args.output}")
    else:
        print(json.dumps(data, indent=2))


def cmd_action_log_clear(args):
    """Clear action log data."""
    r = _client(args.api).post(f"/api/sessions/{args.session}/action_log/clear")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    print("action log cleared")


def cmd_console(args):
    """Get console output from a session/tab."""
    session_name = args.session.split(":")[0] if ":" in args.session else args.session
    r = _client(args.api).get(f"/api/sessions/{session_name}/console",
                              params={"type": args.type, "count": args.count, "clear": args.clear})
    r.raise_for_status()
    data = r.json()
    for msg in data.get("messages", []):
        if args.json:
            print(json.dumps(msg, indent=2))
        else:
            level = msg.get("type", "log").upper()
            print(f"[{level}] {msg.get('message', '')}")
            if args.trace:
                trace = msg.get("stack_trace")
                if trace:
                    for frame in trace.get("call_frames", []):
                        fn = frame.get("function_name", "")
                        url = frame.get("url", "")
                        line = frame.get("line_number", 0)
                        col = frame.get("column_number", 0)
                        print(f"    at {fn} ({url}:{line}:{col})" if fn else f"    at {url}:{line}:{col}")
    if not data.get("messages"):
        print("No console messages.")


def main():
    parser = argparse.ArgumentParser(
        description="firecrawl-clone CLI — browser automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Session management
  firecrawl session create bot
  firecrawl session list
  firecrawl session close bot
  firecrawl session add-tab bot "https://example.com"
  firecrawl session list-tabs bot
  firecrawl session close-tab bot 1
  firecrawl session switch bot 1
  firecrawl session detect-tabs bot

  # Navigation
  firecrawl navigate -s bot:1 "https://example.com"
  firecrawl back -s bot:1
  firecrawl url -s bot:1
  firecrawl loading -s bot:1

  # Interaction
  firecrawl click -s bot:1 "#search"
  firecrawl click -s bot:1 --text "Sign In"
  firecrawl type -s bot:1 "#q" "hello world"
  firecrawl wait -s bot:1 "#results"              # wait for element
  firecrawl wait -s bot:1 --url-change             # wait for navigation
  firecrawl evaluate -s bot:1 "document.title"

  # Content extraction
  firecrawl markdown -s bot:1
  firecrawl screenshot -s bot:1                    # saves to /tmp/<session>-<uuid>.png
  firecrawl screenshot -s bot:1 -o page.png        # custom path
  firecrawl links -s bot:1
  firecrawl elements -s bot:1
  firecrawl query -s bot:1 "input[type=email]"
  firecrawl text -s bot:1 "#content"
  firecrawl save-image -s bot:1 <uuid> -o img.png

  # Action logging (debugging)
  firecrawl action-log on -s bot:1
  firecrawl navigate -s bot:1 "https://app.example.com"
  firecrawl action-log export -s bot:1 -o trace.json
  firecrawl action-log clear -s bot:1
  firecrawl action-log off -s bot:1

  # Console
  firecrawl console -s bot:1
  firecrawl console -s bot:1 --type error

  # Server
  firecrawl quit              # close all sessions + browser
  firecrawl restart           # hot-restart server
"""
    )
    parser.add_argument("--api", default=DEFAULT_API, help="API server URL")

    sub = parser.add_subparsers(dest="cmd")

    # session
    sess = sub.add_parser("session", help="Manage sessions")
    sess_sub = sess.add_subparsers(dest="subcmd")

    p = sess_sub.add_parser("create", help="Create a session")
    p.add_argument("name")
    p.set_defaults(func=cmd_session_create)

    p = sess_sub.add_parser("close", help="Close a session")
    p.add_argument("name")
    p.set_defaults(func=cmd_session_close)

    p = sess_sub.add_parser("list", help="List sessions")
    p.set_defaults(func=cmd_session_list)

    p = sess_sub.add_parser("list-tabs", help="List tabs in a session")
    p.add_argument("name")
    p.set_defaults(func=cmd_session_list_tabs)

    p = sess_sub.add_parser("add-tab", help="Add new tab to session")
    p.add_argument("name")
    p.add_argument("url", nargs="?", default="", help="URL to navigate to")
    p.set_defaults(func=cmd_session_add_tab)

    p = sess_sub.add_parser("close-tab", help="Close a tab")
    p.add_argument("name")
    p.add_argument("tab", type=int, help="Tab index (1-based)")
    p.set_defaults(func=cmd_session_close_tab)

    p = sess_sub.add_parser("switch", help="Switch default tab")
    p.add_argument("name")
    p.add_argument("tab", type=int, help="Tab index (1-based)")
    p.set_defaults(func=cmd_session_switch)

    p = sess_sub.add_parser("detect-tabs", help="Detect newly opened browser tabs")
    p.add_argument("name")
    p.set_defaults(func=cmd_session_detect_tabs)

    # navigate
    p = sub.add_parser("navigate", help="Navigate to URL")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("url")
    p.add_argument("--links", action="store_true", help="Print links instead of markdown")
    p.add_argument("--images", action="store_true", help="Print image UUIDs instead")
    p.set_defaults(func=cmd_navigate)

    # click
    p = sub.add_parser("click", help="Click element")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("selector", nargs="?", default="", help="CSS selector")
    p.add_argument("-t", "--text", help="Click by visible text instead of selector")
    p.set_defaults(func=cmd_click)

    # type
    p = sub.add_parser("type", help="Type text")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("selector")
    p.add_argument("text")
    p.set_defaults(func=cmd_type)

    # wait
    p = sub.add_parser("wait", help="Wait for element or URL change")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("selector", nargs="?", default="", help="CSS selector (omit with --url-change)")
    p.add_argument("-t", "--timeout", type=int, default=10)
    p.add_argument("--url-change", action="store_true", help="Wait for URL to change instead")
    p.set_defaults(func=cmd_wait)

    # screenshot
    p = sub.add_parser("screenshot", help="Take screenshot")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("-o", "--output", help="Save to file")
    p.set_defaults(func=cmd_screenshot)

    # links
    p = sub.add_parser("links", help="List page links")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_links)

    # save-image
    p = sub.add_parser("save-image", help="Save image by UUID")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("uuid")
    p.add_argument("-o", "--output", help="Save to file")
    p.set_defaults(func=cmd_save_image)

    # elements
    p = sub.add_parser("elements", help="List interactive elements")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_elements)

    # evaluate
    p = sub.add_parser("evaluate", help="Evaluate JavaScript")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("script")
    p.set_defaults(func=cmd_evaluate)

    # query
    p = sub.add_parser("query", help="Query DOM by CSS selector")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("selector")
    p.set_defaults(func=cmd_query)

    # text
    p = sub.add_parser("text", help="Get visible text from element")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("selector")
    p.set_defaults(func=cmd_text)

    # url
    p = sub.add_parser("url", help="Print current URL")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_url)

    # loading
    p = sub.add_parser("loading", help="Get page loading state")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_loading)

    # back
    p = sub.add_parser("back", help="Go back")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_back)

    # markdown (print current page)
    p = sub.add_parser("markdown", help="Print current page markdown")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_markdown)

    # quit
    p = sub.add_parser("quit", help="Close browser")
    p.set_defaults(func=cmd_quit)

    # restart
    p = sub.add_parser("restart", help="Restart the server")
    p.set_defaults(func=cmd_restart)

    # console
    p = sub.add_parser("console", help="Get console output (log/error/warn)")
    p.add_argument("-s", "--session", required=True, help="Session:tab (e.g. bot:1)")
    p.add_argument("--type", choices=["log", "error", "warning", "info", "debug", "exception"], default=None)
    p.add_argument("--count", type=int, default=100, help="Max messages to return")
    p.add_argument("--clear", action="store_true", default=False, help="Clear messages after reading")
    p.add_argument("--json", action="store_true", default=False, help="Output raw JSON for each message")
    p.add_argument("--trace", action="store_true", default=False, help="Show stack traces")
    p.set_defaults(func=cmd_console)

    # action-log
    p = sub.add_parser("action-log", help="Log browser actions + network requests")
    p.add_argument("action", choices=["on", "off"])
    p.add_argument("-s", "--session", required=True)
    p.add_argument("--log-mimes", help="Extra MIME types to capture responses for (comma-separated)")
    p.set_defaults(func=lambda args: cmd_action_log_on(args) if args.action == "on" else cmd_action_log_off(args))

    # action-log-export
    p = sub.add_parser("action-log-export", help="Export action log")
    p.add_argument("-s", "--session", required=True)
    p.add_argument("-o", "--output", help="Save to file")
    p.add_argument("--no-bodies", action="store_true", help="Exclude bodies from output")
    p.add_argument("--filter-actions", help="Only include these action names (comma-separated)")
    p.add_argument("--filter-urls", help="Only include these URL patterns (comma-separated regex)")
    p.set_defaults(func=cmd_action_log_export)

    # action-log-clear
    p = sub.add_parser("action-log-clear", help="Clear action log data")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_action_log_clear)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "session" and not hasattr(args, "subcmd"):
        print("usage: firecrawl session {create,close,list,list-tabs,add-tab,close-tab,switch,detect-tabs}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "session":
        # session subcommands don't have --api at args level
        if not hasattr(args, "api"):
            args.api = DEFAULT_API

    args.func(args)


if __name__ == "__main__":
    main()
