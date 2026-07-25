#!/usr/bin/env python3
"""CLI tool for firecrawl-clone browser automation.

Usage:
    firecrawl session create mybot
    firecrawl navigate -s mybot "https://example.com"
    firecrawl click -s mybot "#login"
    firecrawl type -s mybot "#pass" "secret"
    firecrawl screenshot -s mybot -o page.png
    firecrawl links -s mybot
    firecrawl save-image -s mybot <uuid> -o photo.png
    firecrawl session close mybot
    firecrawl session list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_API = "http://localhost:3001"


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
    r = _client(args.api).post(
        f"/api/sessions/{args.session}/click",
        params={"selector": args.selector},
    )
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print(f"url: {data.get('url', '')}")
    if "error" in data:
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
    """Take a screenshot."""
    r = _client(args.api).get(f"/api/sessions/{args.session}/screenshot")
    if r.status_code != 200:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)
    if args.output:
        Path(args.output).write_bytes(r.content)
        print(f"screenshot saved to {args.output}")
    else:
        print(r.content, file=sys.stdout.buffer)


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


def cmd_quit(args):
    """Quit all sessions and browser."""
    r = _client(args.api).post("/api/quit")
    if r.status_code == 200:
        print("browser closed")
    else:
        print(f"error: {r.text}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="firecrawl-clone CLI — browser automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  firecrawl session create bot
  firecrawl navigate -s bot "https://example.com"
  firecrawl click -s bot "#search"
  firecrawl type -s bot "#q" "hello world"
  firecrawl click -s bot "button[type=submit]"
  firecrawl screenshot -s bot -o page.png
  firecrawl links -s bot
  firecrawl elements -s bot
  firecrawl query -s bot "input[type=email]"
  firecrawl evaluate -s bot "document.title"
  firecrawl save-image -s bot <uuid> -o img.png
  firecrawl session close bot
""",
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
    p.add_argument("selector")
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

    # back
    p = sub.add_parser("back", help="Go back")
    p.add_argument("-s", "--session", required=True)
    p.set_defaults(func=cmd_back)

    # quit
    p = sub.add_parser("quit", help="Close browser")
    p.set_defaults(func=cmd_quit)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "session" and not hasattr(args, "subcmd"):
        print("usage: firecrawl session {create,close,list}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "session":
        # session subcommands don't have --api at args level
        args.api = args.api if hasattr(args, "api") else DEFAULT_API

    args.func(args)


if __name__ == "__main__":
    main()
