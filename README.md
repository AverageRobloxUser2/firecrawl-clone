# Firecrawl Clone

Local browser automation for AI agents. Navigate, click, type, screenshot, extract clean markdown — all through a session-based HTTP API or CLI.

Built on [nodriver](https://github.com/ultrafunkamaster/nodriver) (anti-detection Chromium driver speaking CDP directly).

## Quick Start

```bash
# start the API server (desktop)
source .venv/bin/activate
uvicorn firecrawl_clone.server:app --host 0.0.0.0 --port 42069

# headless (bypasses basic checks but Cloudflare-protected sites may block)
FIRECRAWL_HEADLESS=true uvicorn firecrawl_clone.server:app --host 0.0.0.0 --port 42069

# headless + Xvfb (bypasses Cloudflare — install xorg-server-xvfb first)
Xvfb :99 -screen 0 1920x1080x24 &>/dev/null &
DISPLAY=:99 uvicorn firecrawl_clone.server:app --host 0.0.0.0 --port 42069

# in another terminal
firecrawl session create bot
firecrawl navigate -s bot "https://example.com"
firecrawl click -s bot --text "Sign In"
firecrawl type -s bot "#email" "you@example.com"
firecrawl screenshot -s bot
firecrawl session close bot
```

## Architecture

- **Browser**: nodriver (anti-detection, CDP-direct, no selenium wire protocol)
- **HTML → Markdown**: BeautifulSoup4 + markdownify (strips scripts, styles, nav, footer, svg)
- **Images**: UUID placeholders in markdown, downloaded via browser fetch (carries cookies/auth)
- **API**: FastAPI HTTP server + CLI client
- **CLI**: `firecrawl` command with session management, navigation, interaction, HAR capture

## Features

- **Multi-tab sessions** — each session holds multiple tabs, shared cookies/storage
- **Popup detection** — auto-detects newly opened browser tabs after clicks (auth flows, `target="_blank"`)
- **Interactive element annotation** — markdown annotates buttons/inputs with selectors: `[button: #submit] Login`
- **Image download** — images fetched through the browser (respects auth/cookies), saved to disk, referenced by path in markdown
- **Cookie blocker** — loads cookie-blocking extension on startup
- **Console output** — captures `console.log`, `console.error`, `console.warn`, `console.info`, `console.debug` from page JS, filterable by type
- **Action logging** — logs browser actions + network requests with request/response bodies and full JS initiator stack traces for debugging automations
- **Click by text** — `click --text "Sign In"` finds buttons by visible text content
- **Wait for navigation** — `wait --url-change` waits for page URL to change after a click

## CLI Reference

```
firecrawl session create <name>            # create session
firecrawl session close <name>             # close session
firecrawl session list                     # list sessions
firecrawl session add-tab <name> [url]     # add tab to session
firecrawl session list-tabs <name>         # list tabs
firecrawl session switch <name> <tab>      # switch default tab
firecrawl session close-tab <name> <tab>   # close a tab
firecrawl session detect-tabs <name>       # detect new popup tabs

firecrawl navigate -s <session> <url>      # navigate, print markdown
firecrawl click -s <session> <selector>    # click by CSS selector
firecrawl click -s <session> --text <txt>  # click by visible text
firecrawl type -s <session> <sel> <text>   # type into element
firecrawl wait -s <session> <sel>          # wait for element
firecrawl wait -s <session> --url-change   # wait for navigation

firecrawl screenshot -s <session>          # screenshot (saves to /tmp/)
firecrawl links -s <session>               # list page links
firecrawl elements -s <session>            # list interactive elements
firecrawl query -s <session> <selector>    # query DOM by CSS selector
firecrawl text -s <session> <selector>     # get element text
firecrawl url -s <session>                 # get current URL
firecrawl loading -s <session>             # page load state
firecrawl evaluate -s <session> <js>       # evaluate JavaScript
firecrawl back -s <session>                # go back in history

firecrawl console -s <session>              # get console output (log/error/warn/etc)
firecrawl action-log on/off -s <session>  # enable/disable action logging
firecrawl action-log export -s <session>   # export trace (actions + network + initiator stacks)
firecrawl action-log clear -s <session>    # clear log

firecrawl quit                             # close all sessions + browser
```

### Session:Tab Syntax

Use `session:tab` syntax to target specific tabs:

```bash
firecrawl navigate -s bot:1 "https://example.com"   # tab 1
firecrawl navigate -s bot:2 "https://other.com"     # tab 2
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FIRECRAWL_API` | `http://localhost:42069` | API server URL for CLI |
| `FIRECRAWL_HEADLESS` | `false` | Run browser headless (`true`/`1`/`yes`) |

## API Endpoints

Full HTTP API served by `firecrawl-api --port <port>`:

```
POST /api/sessions?name=...                      # create session
DELETE /api/sessions/{name}                      # close session
GET  /api/sessions                               # list sessions
POST /api/sessions/{name}/add_tab?url=...        # add tab
GET  /api/sessions/{name}/tabs                   # list tabs
POST /api/sessions/{name}/switch_tab?tab_index=  # switch tab
DELETE /api/sessions/{name}/tabs/{tab_index}     # close tab
POST /api/sessions/{name}/detect_tabs            # detect new tabs
POST /api/quit                                   # quit all

POST /api/sessions/{name}/navigate?url=...       # navigate (returns markdown, links, images)
POST /api/sessions/{name}/back                   # go back
POST /api/sessions/{name}/click?selector=...     # click element
POST /api/sessions/{name}/type?selector=&text=   # type text
POST /api/sessions/{name}/wait?selector=&timeout= # wait for element
GET  /api/sessions/{name}/loading                # page load state
GET  /api/sessions/{name}/elements               # interactive elements
POST /api/sessions/{name}/evaluate?script=       # evaluate JS
POST /api/sessions/{name}/query?selector=        # query DOM
POST /api/sessions/{name}/text?selector=         # get element text
GET  /api/sessions/{name}/url                    # current URL

GET  /api/sessions/{name}/screenshot             # PNG binary
GET  /api/sessions/{name}/links                  # page links
GET  /api/sessions/{name}/save_image?uuid=       # image binary by UUID
GET  /api/sessions/{name}/console?type=&count=   # console output (filter: type, count, clear)

GET  /api/sessions/{name}/console?type=&count=   # console output (filter: type, count, clear)
POST /api/sessions/{name}/action_log/on          # enable action logging
POST /api/sessions/{name}/action_log/off         # disable action logging
GET  /api/sessions/{name}/action_log/export      # export trace (JSON)
POST /api/sessions/{name}/action_log/clear       # clear log
```

## Dev

```bash
python -m pytest
python -m pytest --ignore=tests/test_api.py   # unit tests only
```

API integration tests require the server and a test site running.

## Planned

- MCP server wrapper (separate project)
- Pi extension (separate project, after MCP)
