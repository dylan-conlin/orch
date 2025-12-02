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

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED
