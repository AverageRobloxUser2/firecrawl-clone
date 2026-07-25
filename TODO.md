# Firecrawl Clone (nodriver)

## Goal

Local browser automation tool for AI agents. Scrape pages, click things, save images, return clean markdown. No API server needed — runs as a pi extension or standalone Python script.

## Architecture

- **Browser**: `nodriver` (anti-detection Chromium driver)
- **HTML → Markdown**: `beautifulsoup4` + `markdownify`
- **Image handling**: Download to `/tmp/pi-browser-images/`, return paths
- **Integration**: Pi extension (TypeScript) ↔ Python script (stdin/stdout JSON)

## TODO

### Phase 1: Core Python Service

- [ ] Install deps: `nodriver`, `beautifulsoup4`, `markdownify`, `aiohttp`, `lxml`
- [ ] Write `browser.py` — async browser singleton (start/close)
- [ ] Write `scrape.py` — navigate URL → return HTML + metadata
- [ ] Write `clean.py` — strip scripts/styles/nav/footer → markdownify
- [ ] Write `images.py` — find `<img>` tags, download, return paths
- [ ] Write `commands.py` — JSON command handler (stdin/stdout protocol)
  - `navigate(url)` → markdown + links
  - `click(selector)` → success/fail + new markdown
  - `type(text, selector)` → success/fail
  - `wait(selector, timeout)` → success/fail
  - `screenshot()` → path to saved PNG
  - `save_image(url)` → path to saved image
  - `get_links()` → list of {url, text}
  - `back()` → go back
  - `quit()` → close browser

### Phase 2: Command Protocol

- [ ] Define JSON protocol:
  ```json
  {"cmd": "navigate", "url": "https://example.com"}
  {"ok": true, "markdown": "...", "images": ["/tmp/...png"], "links": [...]}
  ```
- [ ] Write `main.py` — read JSON from stdin, execute, write JSON to stdout
- [ ] Test with: `echo '{"cmd":"navigate","url":"..."}' | python main.py`

## Local Sources

- nodriver: `/tmp/nodriver/`
- Firecrawl: `/tmp/firecrawl/`

## Notes

- No robots.txt checking
- Ad blocking: install uBlock Origin extension into nodriver profile
- Images saved to `/tmp/pi-browser-images/` with UUID filenames
- Markdown uses `markdownify` (standard HTML → MD conversion)
- Future: MCP server wrapper (separate project `firecrawl-clone-mcp`)
- Future: Pi extension (separate project)
