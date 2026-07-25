# Firecrawl Clone (nodriver)

## Goal

Local browser automation tool for AI agents. Scrape pages, click things, save images, return clean markdown.

## Architecture

- **Browser**: `nodriver` (anti-detection Chromium driver)
- **HTML → Markdown**: `beautifulsoup4` + `markdownify`
- **Images**: UUID references in markdown, browser fetch (carries cookies)
- **API**: Session-based HTTP API + stdin/stdout JSON protocol

## ✅ Done

### HTTP API Server
- FastAPI server on `:3001` (configurable via `--port`)
- Sessions = browser tabs (multiple concurrent)
- `firecrawl-api` CLI entry point

### API Endpoints
- `POST /api/sessions?name=...` — create session
- `DELETE /api/sessions/{name}` — close session
- `GET /api/sessions` — list sessions
- `POST /api/quit` — close all + browser
- `POST /api/sessions/{name}/navigate?url=...` — markdown + links + images
- `POST /api/sessions/{name}/click?selector=...` — click + return page
- `POST /api/sessions/{name}/type?selector=...&text=...` — type text
- `POST /api/sessions/{name}/wait?selector=...&timeout=...` — wait for element
- `GET /api/sessions/{name}/screenshot` — PNG binary
- `GET /api/sessions/{name}/links` — page links
- `GET /api/sessions/{name}/save_image?uuid=...` — image binary by UUID
- `POST /api/sessions/{name}/back` — go back

### Features
- Image UUIDs in markdown + `images: {uuid: path}` mapping
- `save_image?uuid=...` returns image by UUID from navigate response
- `Browser.add_extension("/path")` — generic extension loader
- `enable_adblock()` — download uBlock Origin + register with browser
- stdin/stdout JSON protocol (`echo '{"cmd":"navigate"}' | python -m firecrawl_clone`)

### Tests
- 6 unit tests (HTML cleaning)
- 8 API integration tests (require server + test site running)

## Remaining

- [ ] MCP server wrapper (separate project)
- [ ] Pi extension (separate project, after MCP)

## Local Sources

- nodriver: `/tmp/nodriver/`
- Firecrawl: `/tmp/firecrawl/`
