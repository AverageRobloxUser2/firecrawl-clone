# Firecrawl Clone (nodriver)

## Goal

Local browser automation tool for AI agents. Scrape pages, click things, save images, return clean markdown.

## Architecture

- **Browser**: `nodriver` (anti-detection Chromium driver)
- **HTML → Markdown**: `beautifulsoup4` + `markdownify`
- **Images**: UUID references in markdown, browser fetch (carries cookies)
- **API**: FastAPI HTTP server + CLI client
- **Headless**: `FIRECRAWL_HEADLESS=true` env var

## ✅ Done

### HTTP API Server
- FastAPI server on `:42069` (configurable via `--port`)
- Sessions = browser with multiple tabs (shared cookies/storage)
- `firecrawl-api` CLI entry point

### API Endpoints
- `POST /api/sessions?name=...` — create session
- `DELETE /api/sessions/{name}` — close session
- `GET /api/sessions` — list sessions
- `POST /api/sessions/{name}/add_tab?url=...` — add tab
- `GET /api/sessions/{name}/tabs` — list tabs
- `POST /api/sessions/{name}/switch_tab?tab_index=` — switch tab
- `DELETE /api/sessions/{name}/tabs/{tab_index}` — close tab
- `POST /api/sessions/{name}/detect_tabs` — detect new popup tabs
- `POST /api/quit` — close all + browser
- `POST /api/sessions/{name}/navigate?url=...` — markdown + links + images
- `POST /api/sessions/{name}/click?selector=...` — click + return page
- `POST /api/sessions/{name}/type?selector=...&text=...` — type text
- `POST /api/sessions/{name}/wait?selector=...&timeout=...` — wait for element
- `POST /api/sessions/{name}/wait?url_change=true` — wait for navigation
- `GET /api/sessions/{name}/screenshot` — PNG binary
- `GET /api/sessions/{name}/links` — page links
- `GET /api/sessions/{name}/save_image?uuid=...` — image binary by UUID
- `POST /api/sessions/{name}/back` — go back
- `GET /api/sessions/{name}/elements` — interactive elements
- `POST /api/sessions/{name}/evaluate?script=` — evaluate JS
- `POST /api/sessions/{name}/query?selector=` — query DOM
- `POST /api/sessions/{name}/text?selector=` — get element text
- `GET /api/sessions/{name}/url` — current URL
- `GET /api/sessions/{name}/loading` — page load state

### Action Logging
- `POST /api/sessions/{name}/action_log/on` — enable logging
- `POST /api/sessions/{name}/action_log/off` — disable logging
- `GET /api/sessions/{name}/action_log/export` — export trace (JSON)
- `POST /api/sessions/{name}/action_log/clear` — clear log
- logs browser actions + network requests + full JS initiator stack traces
- filter by URLs or action types on export

### Features
- multi-tab sessions with `session:tab` syntax (e.g. `bot:1`, `bot:2`)
- popup detection — auto-detects newly opened browser tabs after clicks
- interactive element annotation — `[button: #submit] Login`, `[input text: #email]`
- image UUIDs in markdown + `images: {uuid: path}` mapping
- click by text — `click --text "Sign In"`
- wait for navigation — `wait --url-change`
- cookie blocker — "I don't care about cookies" extension
- headless mode — `FIRECRAWL_HEADLESS=true`
- `Browser.add_extension("/path")` — generic extension loader
- `enable_adblock()` — download uBlock Origin + register with browser

### CLI
- `firecrawl` command with all endpoints covered
- session management, navigation, interaction, screenshots, action logging

### Tests
- 6 unit tests (HTML cleaning)
- 8 API integration tests (require server + test site running)

## Remaining

- [ ] MCP server wrapper (separate project)
- [ ] Pi extension (separate project, after MCP)
