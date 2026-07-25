# Firecrawl Clone (nodriver)

## Goal

Local browser automation tool for AI agents. Scrape pages, click things, save images, return clean markdown. No API server needed — runs as a pi extension or standalone Python script.

## Architecture

- **Browser**: `nodriver` (anti-detection Chromium driver)
- **HTML → Markdown**: `beautifulsoup4` + `markdownify`
- **Image handling**: Download to `/tmp/pi-browser-images/`, UUID filenames, browser fetch (carries cookies)
- **Integration**: Pi extension (TypeScript) ↔ Python script (stdin/stdout JSON)

## TODO

### Phase 1: Core Python Service ✅

- [x] Install deps: `nodriver`, `beautifulsoup4`, `markdownify`, `lxml`
- [x] Write `browser.py` — browser singleton with `add_extension()` for extensions
- [x] Write `page.py` — navigate, click, type, wait, screenshot, get_links, back, save_image
- [x] Write `clean.py` — strip scripts/styles/nav/footer → markdownify
- [x] Write `images.py` — find `<img>` tags, download via browser (cookies), return paths

### Phase 2: Command Protocol ✅

- [x] Define JSON protocol in `protocol.py` (Command, SuccessResponse, ErrorResponse)
- [x] Write `__main__.py` — read JSON from stdin, dispatch, write JSON to stdout
- [x] Tests: 14 passing (6 unit + 8 integration)
- [x] stdin/stdout pipeline: `echo '{"cmd":"navigate","url":"..."}' | python -m firecrawl_clone`

### Image UUIDs ✅

- [x] Images in markdown use UUIDs instead of full URLs
- [x] Response includes `images: {uuid: path}` mapping
- [x] `save_image(url)` downloads via browser fetch (carries cookies/auth)

### Extensions ✅

- [x] `Browser.add_extension("/path/to/extension")` — generic extension loader

### Remaining

- [ ] Ad blocking: download uBlock Origin, call `Browser.add_extension()` before start
- [ ] Pi extension (separate project — TypeScript ↔ Python over stdin/stdout)
- [ ] MCP server wrapper (separate project `firecrawl-clone-mcp`)

## Local Sources

- nodriver: `/tmp/nodriver/`
- Firecrawl: `/tmp/firecrawl/`
