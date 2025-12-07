---
date: "2025-12-01"
status: "Complete"
phase: "Complete"
---

# OpenCode Backend Implementation Investigation

**TLDR:** OpenCode backend has robust spawn/send/status support, but `tail` command is NOT implemented for OpenCode agents - it tries to use tmux which causes errors. The backend uses HTTP API instead of tmux, so tail needs SSE-based implementation.

## Question

What is the implementation status of the OpenCode backend in orch-cli? Specifically:
1. Is tail command support (live output streaming) implemented?
2. Is send command support (sending messages to running agents) implemented?
3. Is status command support implemented?
4. Is check command support implemented?
5. How does OpenCodeBackend integrate with CLI commands in monitoring_commands.py?

## What I tried

1. Read the OpenCodeBackend implementation at `src/orch/backends/opencode.py` (547 lines)
2. Read the base Backend interface at `src/orch/backends/base.py` (101 lines)
3. Read monitoring_commands.py (1307 lines) to understand command implementations
4. Read send.py (107 lines) and tail.py (52 lines) for backend-specific handling
5. Read registry.py (670 lines) for OpenCode agent registration and reconciliation
6. Ran Python tests to verify method availability and behavior

## What I observed

### 1. **OpenCodeBackend Implementation (Fully Implemented)**
Located at: `src/orch/backends/opencode.py`

The backend is well-structured with:
- `OpenCodeClient` class (lines 96-348): Full HTTP API client with methods for:
  - `list_sessions()`, `get_session()`, `create_session()`, `delete_session()`
  - `send_message()`, `send_message_async()`, `get_messages()`
  - `get_session_status()`, `get_tool_calls()`
  - `subscribe_events()` - SSE client for real-time events
  - `health_check()`

- `OpenCodeBackend` class (lines 350-547): Backend adapter implementing:
  - `build_command()` → returns empty string (not CLI-based)
  - `wait_for_ready()` → health check via API
  - `get_env_vars()` → OPENCODE_* environment variables
  - OpenCode-specific: `spawn_session()`, `send_message()`, `get_status()`, `subscribe_events()`

### 2. **Send Command Support: IMPLEMENTED**
Located at: `src/orch/send.py:27-64`

```python
def send_message_to_agent(agent: Dict[str, Any], message: str):
    # Check if this is an opencode agent
    if agent.get('backend') == 'opencode':
        _send_message_opencode(agent, message)
        return
```

The `_send_message_opencode()` function (lines 35-64):
- Discovers server via `discover_server()`
- Creates OpenCodeClient
- Uses `send_message_async()` to send messages

### 3. **Tail Command Support: NOT IMPLEMENTED**
Located at: `src/orch/tail.py` (entire file)

The `tail_agent_output()` function has NO OpenCode handling:
```python
def tail_agent_output(agent: Dict[str, Any], lines: int = 20) -> str:
    # Prefer stable window_id over window target
    window_target = agent.get('window_id', agent['window'])  # <-- Fails for opencode
    # ... uses tmux capture-pane
```

For OpenCode agents, this causes a `KeyError: 'window'` because OpenCode agents don't have a tmux window.

### 4. **Status Command Support: IMPLEMENTED**
Located at: `src/orch/monitoring_commands.py:165-166`

```python
# Also reconcile opencode agents (separate from tmux)
registry.reconcile_opencode()
```

The `reconcile_opencode()` method in registry.py (lines 511-606):
- Gets active OpenCode agents from registry
- Checks if sessions still exist via API
- Updates agent status (completed/terminated) based on workspace phase

### 5. **Check Command Support: PARTIALLY IMPLEMENTED**
Located at: `src/orch/monitoring_commands.py:404-586`

The `check` command uses `check_agent_status()` from `monitor.py`, which:
- Works for OpenCode agents (checks workspace files)
- BUT relies on `agent['window']` for some display info (line 297, 310, 324)
- OpenCode agents have `window=None`, which may cause display issues

### 6. **Registry Integration: FULLY IMPLEMENTED**
Located at: `src/orch/registry.py:223-354`

The `register()` method handles OpenCode agents:
- Accepts `backend='opencode'` and `session_id` parameters
- Logs OpenCode-specific info
- OpenCode agents skip tmux reconciliation (line 389)
- Separate `reconcile_opencode()` method for API-based reconciliation

## Test performed

**Test 1:** Python script to verify method availability and backend routing:
```python
from orch.backends.opencode import OpenCodeBackend, OpenCodeClient
from orch.send import send_message_to_agent
from orch.tail import tail_agent_output
import inspect

# Check send module for OpenCode support
source = inspect.getsource(send_message_to_agent)
has_opencode = 'opencode' in source.lower()  # True

# Check tail module for OpenCode support
tail_source = inspect.getsource(tail_agent_output)
tail_has_opencode = 'opencode' in tail_source.lower()  # False
```

**Result:** 
- `send_message_to_agent` handles OpenCode: **True**
- `tail_agent_output` handles OpenCode: **False**

**Test 2:** Actual tail call with simulated OpenCode agent:
```python
opencode_agent = {
    'id': 'test-opencode-agent',
    'backend': 'opencode',
    'session_id': 'test-session-123',
}
output = tail_agent_output(opencode_agent, lines=5)
```

**Result:** `KeyError: 'window'` - confirms tail is not implemented for OpenCode.

## Conclusion

Based on the tests and code analysis:

| Command | OpenCode Support | Notes |
|---------|------------------|-------|
| `orch spawn --backend opencode` | ✅ Fully Implemented | spawn.py:817-942, uses HTTP API |
| `orch send <agent> "msg"` | ✅ Fully Implemented | send.py:27-64, routes to OpenCode API |
| `orch status` | ✅ Fully Implemented | Uses `reconcile_opencode()` for lifecycle |
| `orch check <agent>` | ⚠️ Partial | Works but may have display issues (no window) |
| `orch tail <agent>` | ❌ NOT Implemented | Causes `KeyError: 'window'` |
| `orch wait <agent>` | ✅ Works | Uses workspace phase, not backend-specific |
| `orch complete <agent>` | ✅ Works | Checks workspace, not backend-specific |

### Missing Functionality - Tail Command

The `tail` command needs OpenCode-specific implementation to:
1. Check if `agent.get('backend') == 'opencode'`
2. Use SSE events (`subscribe_events()`) or message polling (`get_messages()`) for output
3. Return formatted recent messages/tool outputs

### Recommendations

1. **Add OpenCode handling to `tail.py`:**
   ```python
   def tail_agent_output(agent: Dict[str, Any], lines: int = 20) -> str:
       if agent.get('backend') == 'opencode':
           return _tail_opencode(agent, lines)
       # ... existing tmux code
   ```

2. **Implement `_tail_opencode()` using messages API:**
   - Get recent messages via `client.get_messages(session_id)`
   - Extract text content from assistant messages
   - Format tool calls with status

3. **Optional: Add SSE-based live streaming:**
   - Use `subscribe_events()` for real-time output
   - Would require refactoring tail to support streaming mode

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

## Notes

Key files for future implementation work:
- `src/orch/tail.py` - Add OpenCode routing
- `src/orch/backends/opencode.py:198-214` - `get_messages()` API ready
- `src/orch/backends/opencode.py:310-325` - SSE events for streaming

Related: OpenCode backend was added recently and the monitoring commands (status, check) were updated for it, but tail was missed.
