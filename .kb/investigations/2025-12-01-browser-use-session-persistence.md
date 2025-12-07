# Investigation: Browser Use Session Persistence

**Date:** 2025-12-01
**Type:** Simple Investigation
**Status:** Complete
**Time:** ~30 minutes

---

## Question

Does the browser-use MCP server support cookie/session persistence, and if not, could it?

## TLDR

Browser Use's core library has **full session persistence support** via `StorageStateWatchdog`, but the MCP server doesn't expose these capabilities. This is a gap that could be fixed with 2-3 new MCP tools.

---

## Findings

### Core Library: Full Support Exists

**File:** `browser_use/browser/watchdogs/storage_state_watchdog.py`

The `StorageStateWatchdog` class provides comprehensive session persistence:

```python
class StorageStateWatchdog(BaseWatchdog):
    """Monitors and persists browser storage state including cookies and localStorage."""

    auto_save_interval: float = Field(default=30.0)  # Auto-save every 30 seconds
    save_on_change: bool = Field(default=True)  # Save immediately when cookies change
```

**Capabilities:**
- **Auto-save**: Periodically saves cookies to `storage_state.json`
- **Change detection**: Monitors for cookie changes via CDP
- **Atomic writes**: Uses temp file + rename pattern for safety
- **Merge logic**: Intelligently merges with existing state file
- **Full state**: Handles cookies, localStorage, and sessionStorage

**Key methods:**
- `_save_storage_state(path)` - Saves current browser state
- `_load_storage_state(path)` - Restores state on browser start
- `_merge_storage_states(existing, new)` - Merges cookie sets by (name, domain, path) key
- `add_cookies(cookies)` - Programmatic cookie injection

### BrowserProfile Configuration

**File:** `browser_use/browser/profile.py`

```python
class BrowserProfile(BaseModel):
    storage_state: str | Path | dict[str, Any] | None = None
    user_data_dir: str | Path | None = None
```

- `storage_state`: Path to JSON file for cookie/storage persistence
- `user_data_dir`: Chrome user data directory (includes cache, extensions, etc.)

### MCP Server: Limited Exposure

**File:** `browser_use/mcp/server.py`

The MCP server configures `user_data_dir` but doesn't expose storage management:

```python
browser_profile = BrowserProfile(
    user_data_dir='~/.config/browseruse/profiles/default',
    # storage_state is NOT configured
)
```

**Available MCP tools:**
- `browser_navigate`, `browser_click`, `browser_type`
- `browser_get_state`, `browser_extract_content`
- `browser_scroll`, `browser_go_back`
- `browser_list_tabs`, `browser_switch_tab`, `browser_close_tab`
- `browser_list_sessions`, `browser_close_session`, `browser_close_all`
- `retry_with_browser_use_agent`

**Missing tools:**
- No `browser_save_state` / `browser_load_state`
- No `browser_get_cookies` / `browser_set_cookies`
- No storage state path configuration

---

## Gap Analysis

| Capability | Core Library | MCP Server |
|------------|--------------|------------|
| Auto-save cookies | ✅ StorageStateWatchdog | ❌ Not enabled |
| Manual save/load | ✅ Events + methods | ❌ No tools |
| Cookie injection | ✅ `add_cookies()` | ❌ No tool |
| Storage state file | ✅ Configurable path | ❌ Not exposed |
| User data dir | ✅ Configurable | ✅ Hardcoded default |

---

## PR Opportunity

Add session persistence tools to MCP server:

```python
@mcp.tool()
async def browser_save_state(path: str = None) -> dict:
    """Save current browser cookies and storage to file."""
    # Dispatch SaveStorageStateEvent or call watchdog directly

@mcp.tool()
async def browser_load_state(path: str = None) -> dict:
    """Load browser cookies and storage from file."""
    # Dispatch LoadStorageStateEvent

@mcp.tool()
async def browser_get_cookies() -> list[dict]:
    """Get all current browser cookies."""
    # Use watchdog.get_current_cookies()

@mcp.tool()
async def browser_set_cookies(cookies: list[dict]) -> dict:
    """Add cookies to the browser."""
    # Use watchdog.add_cookies()
```

**Effort estimate:** 50-100 lines of code, straightforward since infrastructure exists.

---

## Comparison to Prior Research

From `2025-12-01-ai-browser-automation-tools-2025.md`:

> "Playwright MCP limitation: Each session starts clean (no cookies, cache, logged-in states)"

Browser Use's architecture is *already designed* to solve this - the MCP just doesn't expose it yet. This makes Browser Use potentially superior for workflows requiring authentication persistence (e.g., staying logged into services across sessions).

---

## Recommendation

⭐ **RECOMMENDED:** Open PR to add storage state tools to browser-use MCP

**Why:**
- Infrastructure already exists (StorageStateWatchdog is battle-tested)
- Low effort (2-4 new tool functions)
- High value (enables persistent auth workflows)
- Differentiator vs Playwright MCP

**Alternative:** Fork and add locally
- **Pros:** Immediate use, no upstream dependency
- **Cons:** Maintenance burden, loses upstream updates

---

## GitHub Context

**Repo stats:** 73k stars, 8.7k forks, 155 open issues, actively maintained (commits daily)

### Relevant Issues

**#3523 - "Bug: State store isn't loading any cookies"** (Open)
- User reports `storage_state` not loading cookies properly
- Using Playwright-exported `auth.json` format
- Confirms there may be bugs in the StorageStateWatchdog implementation

**#3118 - "Novnc and cookies examples"** (Open PR)
- Adds `examples/browser/cookies_json.py` showing manual CDP cookie persistence
- Uses `browser_session._cdp_set_cookies()` and `_cdp_get_cookies()` directly
- Workaround for missing high-level API

### MCP-Related Issues

- **#3099** - MCP `retry_with_browser_use_agent` ignores configured LLM
- **#3447** - CLI addon install issues
- **#2748** - MCP stdio broken by INFO logs
- No existing issues/PRs for MCP cookie tools

### PR Opportunity Assessment

**Pros:**
- No existing work on MCP cookie tools (greenfield)
- Active maintainers (daily commits)
- High-value feature (common request pattern in issues)
- Infrastructure exists (just needs exposure)

**Cons:**
- No CONTRIBUTING.md (unclear contribution process)
- Existing bug #3523 suggests StorageStateWatchdog may need fixes first
- MCP has multiple open bugs (may want to stabilize first)

**Recommendation:** Watch #3523 for resolution before adding MCP tools on top of potentially buggy foundation.

---

## Files Referenced

- `/Users/dylanconlin/Documents/personal/browser-use/browser_use/browser/watchdogs/storage_state_watchdog.py`
- `/Users/dylanconlin/Documents/personal/browser-use/browser_use/browser/profile.py`
- `/Users/dylanconlin/Documents/personal/browser-use/browser_use/mcp/server.py`
- `/Users/dylanconlin/Documents/personal/orch-cli/.orch/investigations/simple/2025-12-01-ai-browser-automation-tools-2025.md`
- GitHub: https://github.com/browser-use/browser-use
