
## 2025-07-24 Bugs Found During manodienynas-client Development

### Bug: action-log.json doesn't capture request/response bodies
- **Location**: Network request logging in action-log capture
- **Issue**: `request_body` and `response_body` fields are always empty strings `""` in the JSON output, even for POST requests with body data. Only metadata (URL, method, status code, headers) is captured.
- **Impact**: Cannot reconstruct exact API payloads from action logs alone. Must probe endpoints independently.
- **Evidence**: All 4 POST requests in action-log.json (login, lostandfound, day_view) have empty `requestBody` and `responseBody`.

### Bug: Browser.quit() wipes all cookies on session deletion
- **Location**: `Browser.quit()` in browser.py, called by `SessionManager.delete()` when last session closes
- **Issue**: `quit()` kills the Chrome process entirely, destroying all browser state (cookies, localStorage, session storage). Extension state (cookie blocker) persists only as a Python class variable, not on disk.
- **Impact**: Session cookies cannot survive session kill + restart. Auth state is lost.
- **Evidence**: `Browser._extensions` is a class variable that survives restart, but `self.process` is killed by `quit()` meaning Chrome restarts fresh with no cookies.
