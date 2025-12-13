**TLDR:** Question: Does `orch send` work with OpenCode backend agents? Answer: No - OpenCode agents spawned in standalone TUI mode don't register with the HTTP API server, so `session_id` is always None, causing `orch send` to fail with "has no session_id". High confidence (95%) - tested directly with spawned agent.

---

# Investigation: Test orch send functionality with OpenCode backend

**Question:** Does `orch send` work correctly for agents spawned with the OpenCode backend?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Agent oc-inv-test-orch-send-12dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: OpenCode agents spawned without session_id

**Evidence:** Checked the agent registry for active OpenCode agents:
```
Agent: oc-inv-test-orch-send-12dec
  backend: opencode
  session_id: N/A
  window: workers-orch-cli:2

Agent: oc-inv-quick-test-agent-say-12dec
  backend: opencode
  session_id: N/A
  window: workers-orch-cli:4
```

All OpenCode agents have `session_id: N/A`.

**Source:** `~/.orch/agent-registry.json`, `src/orch/spawn.py:860`

**Significance:** The spawn code explicitly sets `session_id = None` with comment "Will be created by opencode on first submit" - but the session_id is never captured/updated.

---

### Finding 2: orch send fails for OpenCode agents

**Evidence:** Attempted to send a message to a spawned OpenCode agent:
```bash
$ orch send oc-inv-quick-test-agent-say-12dec "Hello! This is a test message from orch send."
❌ Agent 'oc-inv-quick-test-agent-say-12dec' is an OpenCode agent but has no session_id. Cannot send message.
Aborted!
```

**Source:** `src/orch/send.py:39-44`

**Significance:** The `_send_message_opencode()` function raises a RuntimeError if session_id is None, making `orch send` completely non-functional for OpenCode agents.

---

### Finding 3: OpenCode TUI runs standalone, not attached to server

**Evidence:** 
1. Spawn command creates standalone TUI: `opencode {project} --model {model} --prompt {prompt}`
2. Sessions from spawned agents don't appear in HTTP API server:
   ```
   # HTTP API shows 29 sessions, none in /Users/dylanconlin/Documents/personal/orch-cli
   # All sessions are in /Users/dylanconlin/orch-knowledge or meta-orchestration
   ```
3. OpenCode has separate modes:
   - `opencode [project]` - Standalone TUI (what spawn uses)
   - `opencode serve` - Headless server with HTTP API
   - `opencode attach <url>` - Attach TUI to existing server

**Source:** `opencode --help`, HTTP API queries to `http://127.0.0.1:4096/session`

**Significance:** The HTTP API approach in `send.py` fundamentally won't work because standalone TUI instances don't register with any server. The session_id concept is only valid when using attach mode.

---

## Synthesis

**Key Insights:**

1. **Architecture mismatch** - The `send.py` code assumes OpenCode agents have session_ids because it was designed for attached server mode, but `spawn.py` creates standalone TUI instances that don't register sessions.

2. **Two viable paths forward:**
   - **Option A:** Use tmux send-keys fallback for OpenCode (same as Claude Code) - simple, works now
   - **Option B:** Switch spawn to use attach mode - requires server management, more complex

3. **Claude Code uses tmux successfully** - The `_send_message_tmux()` function in send.py works well for Claude Code agents. OpenCode TUI also accepts input via tmux send-keys.

**Answer to Investigation Question:**

`orch send` does NOT work with OpenCode backend agents in the current implementation. The failure is due to an architecture mismatch: spawn creates standalone TUI instances without session_ids, while send expects session_ids from an HTTP API server. The fix is straightforward: fall back to tmux send-keys for OpenCode agents that lack session_id.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct testing confirmed the exact failure path. The code is clear about the requirement (session_id) and why it's not being met (standalone TUI doesn't register).

**What's certain:**

- ✅ OpenCode agents spawn with session_id = None
- ✅ orch send fails with "has no session_id" error
- ✅ Standalone OpenCode TUI doesn't register with HTTP API server
- ✅ tmux send-keys works for sending input to TUI-based agents

**What's uncertain:**

- ⚠️ Whether attach mode would be better long-term (more structured messaging)
- ⚠️ How session_id discovery would work if we wanted to implement it

**What would increase confidence to 100%:**

- Testing the tmux fallback fix to confirm it works
- Verifying attach mode behavior if that path is chosen

---

## Implementation Recommendations

**Purpose:** Fix `orch send` for OpenCode agents.

### Recommended Approach ⭐

**Tmux Fallback for OpenCode** - Modify `_send_message_opencode()` to fall back to tmux send-keys when session_id is None.

**Why this approach:**
- Minimal change - add a few lines of code
- Consistent with Claude Code behavior
- Works immediately with existing spawn architecture
- No server management complexity

**Trade-offs accepted:**
- Less structured than API messaging
- Can't use advanced OpenCode API features
- Message delivery isn't confirmed (fire and forget)

**Implementation sequence:**
1. In `_send_message_opencode()`, check for session_id
2. If None, fall back to `_send_message_tmux()` using agent's window info
3. Add logging to indicate fallback was used

### Alternative Approaches Considered

**Option B: Switch to Attach Mode**
- **Pros:** Proper session management, structured API, richer monitoring
- **Cons:** Requires server orchestration, more complex spawn flow
- **When to use instead:** If we need persistent sessions or richer API features

**Option C: Discover Session ID Post-Spawn**
- **Pros:** Keeps API-based approach
- **Cons:** Complex discovery logic, timing issues, may not work with standalone
- **When to use instead:** Never - standalone TUI doesn't expose sessions to API

**Rationale for recommendation:** Option A provides immediate fix with minimal risk. The tmux approach is battle-tested with Claude Code and OpenCode TUI accepts keyboard input the same way.

---

### Implementation Details

**What to implement first:**
```python
# In src/orch/send.py, modify _send_message_opencode():

def _send_message_opencode(agent: Dict[str, Any], message: str):
    """Send message to an OpenCode agent via HTTP API or tmux fallback."""
    session_id = agent.get('session_id')
    
    # Fallback to tmux if no session_id (standalone TUI mode)
    if not session_id:
        import logging
        logging.getLogger(__name__).info(
            f"OpenCode agent {agent['id']} has no session_id, using tmux fallback"
        )
        _send_message_tmux(agent, message)
        return
    
    # ... rest of existing HTTP API code
```

**Things to watch out for:**
- ⚠️ Ensure agent has `window` or `window_id` for tmux fallback
- ⚠️ Test that tmux send-keys works with OpenCode TUI input handling
- ⚠️ Consider adding explicit indicator in orch send output

**Success criteria:**
- ✅ `orch send <opencode-agent> "message"` succeeds
- ✅ Message appears in agent's input buffer
- ✅ Works for both agents with and without session_id

---

## References

**Files Examined:**
- `src/orch/send.py` - Send message implementation
- `src/orch/spawn.py:850-945` - OpenCode spawn flow
- `src/orch/backends/opencode.py` - OpenCode client and backend
- `~/.orch/agent-registry.json` - Agent registry data

**Commands Run:**
```bash
# Check OpenCode server sessions
curl -s http://127.0.0.1:4096/session

# Test orch send
orch send oc-inv-quick-test-agent-say-12dec "Hello! Test message"

# Check agent registry
cat ~/.orch/agent-registry.json | python3 -c "..." 

# Check OpenCode help
opencode --help
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-test-orch-end-command-verify.md` - Similar command testing

---

## Investigation History

**2025-12-12 16:43:** Investigation started
- Initial question: Does orch send work with OpenCode backend?
- Context: Testing orch send functionality with OpenCode agents

**2025-12-12 16:55:** Found session_id is always None for OpenCode agents

**2025-12-12 17:05:** Discovered architecture mismatch - standalone TUI vs server mode

**2025-12-12 17:15:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: orch send fails for OpenCode agents due to missing session_id; recommend tmux fallback

---

## Self-Review

- [x] Real test performed (ran orch send, observed error)
- [x] Conclusion from evidence (direct test failure + code analysis)
- [x] Question answered (orch send does NOT work with OpenCode backend currently)
- [x] File complete

**Self-Review Status:** PASSED
