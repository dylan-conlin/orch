---
date: "2025-12-02"
status: "Complete"
---

# Test browser-use MCP After Config Changes

**TLDR:** Adding `executable_path` to browseruse config fixed the CDP connection issues. All browser-use MCP operations now work correctly with Playwright Chromium.

## Question

Does adding `executable_path` to `~/.config/browseruse/config.json` (pointing to Playwright Chromium) fix the CDP client initialization errors and session state inconsistencies we've been seeing?

## What I tried

1. Called `browser_navigate` to https://example.com
2. Called `browser_get_state` immediately after
3. Called `browser_navigate` to http://localhost:3000/users/sign_in
4. Called `browser_get_state` on the localhost page
5. Checked `ps aux | grep chrom` to verify which browser was launched

## What I observed

1. **Navigation to example.com:** Succeeded immediately, no timeout or CDP errors
2. **browser_get_state after example.com:** Returned proper state with URL, title, tabs, and interactive elements
3. **Navigation to localhost:3000:** Succeeded, loaded "Sign In - Price Watch" page
4. **browser_get_state on localhost:** Returned form elements (inputs, links) correctly
5. **Browser process:** Running from `/Users/dylanconlin/Library/Caches/ms-playwright/chromium-1161/chrome-mac/Chromium.app/` - confirms Playwright Chromium is being used (NOT regular Chrome)

## Test performed

**Test:**
- `mcp__browser-use__browser_navigate(url="https://example.com")`
- `mcp__browser-use__browser_get_state()`
- `mcp__browser-use__browser_navigate(url="http://localhost:3000/users/sign_in")`
- `mcp__browser-use__browser_get_state()`
- `ps aux | grep chrom` to verify browser binary

**Result:**
- All 4 MCP operations succeeded without errors
- No CDP client initialization errors
- No BrowserStartEvent timeout
- No session state inconsistency
- Browser process confirmed as Playwright Chromium (chromium-1161)

## Conclusion

The config change **fixed the issue**. Adding `executable_path` to `~/.config/browseruse/config.json` pointing to Playwright's bundled Chromium resolved all the CDP connection problems. The browser-use MCP is now working correctly:

- Navigation works (both external URLs and localhost)
- State retrieval works (interactive elements properly detected)
- Using Playwright Chromium instead of system Chrome

---

## Notes

**What was changed:**
- Added `executable_path` to `~/.config/browseruse/config.json` pointing to:
  `/Users/dylanconlin/Library/Caches/ms-playwright/chromium-1161/chrome-mac/Chromium.app/Contents/MacOS/Chromium`

**Why this fixed it:**
The browser-use MCP was likely having issues with system Chrome's CDP implementation or version incompatibilities. Playwright's bundled Chromium is specifically tested and configured for automation via CDP.

**Prior issues (now resolved):**
- CDP client not initialized
- BrowserStartEvent timeout
- Session state inconsistency

---

## Session Persistence Testing

After fixing CDP, tested cookie/session persistence:

1. **Logged into** `https://price-watch-web.onrender.com` via browser-use
2. **Closed all browser sessions** with `browser_close_all`
3. **Reopened and navigated** to the same URL
4. **Result:** Automatically logged in - session cookie was persisted

**Key insight:** Browser-use already supports session persistence via `user_data_dir`. Cookies are stored in:
`~/.config/browseruse/profiles/default/Default/Cookies`

---

## Final Recommended Config

`~/.config/browseruse/config.json`:

```json
{
  "browser_profile": {
    "...uuid...": {
      "id": "...uuid...",
      "default": true,
      "created_at": "...",
      "headless": false,
      "user_data_dir": "/Users/dylanconlin/.config/browseruse/profiles/default",
      "allowed_domains": null,
      "downloads_path": null,
      "executable_path": "/Users/dylanconlin/Library/Caches/ms-playwright/chromium-1161/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
      "window_size": {"width": 1440, "height": 900},
      "enable_default_extensions": true,
      "wait_between_actions": 0.15
    }
  }
}
```

| Setting | Purpose |
|---------|---------|
| `executable_path` | Use Playwright Chromium (fixes CDP errors) |
| `user_data_dir` | Persist cookies/sessions across browser restarts |
| `window_size` | Consistent viewport for reliable element positioning |
| `enable_default_extensions` | uBlock Origin, cookie auto-dismiss, ClearURLs |
| `wait_between_actions` | Slightly slower actions for stability |

---

## Root Cause Analysis

**Problem:** Browser-use was using system Google Chrome instead of Playwright Chromium.

**Why this broke CDP:**
- System Chrome has extra security features and background processes
- These interfere with the Chrome DevTools Protocol (CDP) remote debugging connection
- Playwright's Chromium is stripped down specifically for automation

**GitHub reference:** Issue #3641 - multiple users reported same fix (use Chromium, not Chrome)

---

## Other Available Config Options

For future reference, browser-use supports many additional options:

- `disable_security` - Disable CORS/SSL (dev only)
- `allowed_domains` / `prohibited_domains` - Domain whitelisting/blacklisting
- `highlight_elements` - Visual highlighting of interactive elements
- `record_video_dir` - Save session recordings
- `proxy` - Proxy settings
- `demo_mode` - Show agent logs panel in browser
- `minimum_wait_page_load_time` - Page load wait time
- `wait_for_network_idle_page_load_time` - Network idle timeout

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] Session persistence verified
- [x] Final config documented
- [x] File complete

**Self-Review Status:** PASSED
