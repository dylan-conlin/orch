**TLDR:** Why does `orch tail` fail with "no session_id" for OpenCode agents? Root cause: OpenCode agents spawned in standalone TUI mode don't have session_ids (created dynamically by OpenCode, not captured). Fix: Add tmux fallback to tail.py, matching existing pattern in send.py. High confidence (90%) - root cause traced through code, fix pattern already validated.

---

# Investigation: orch tail fails for OpenCode agents - 'no session_id' error

**Question:** Why does `orch tail` fail with "no session_id" error for OpenCode agents, and how to fix it?

**Started:** 2025-12-13
**Updated:** 2025-12-13
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Resolution-Status:** Resolved
**Confidence:** High (90%)

---

## Findings

### Finding 1: OpenCode agents are spawned in standalone TUI mode without session_id

**Evidence:** In `src/orch/spawn.py:861`:
```python
session_id = None  # Will be created by opencode on first submit
```

The `spawn_with_opencode()` function sets `session_id = None` and never updates it. The comment acknowledges OpenCode will create a session ID dynamically, but orch-cli never captures it.

**Source:** `src/orch/spawn.py:757-968` - `spawn_with_opencode()` function

**Significance:** This is the root cause. OpenCode agents registered in the agent registry have `backend: "opencode"` but `session_id: null`, making API-based operations impossible.

---

### Finding 2: send.py has tmux fallback for missing session_id, tail.py doesn't

**Evidence:** In `src/orch/send.py:41-48`:
```python
# Fallback to tmux if no session_id (standalone TUI mode)
if not session_id:
    import logging
    logging.getLogger(__name__).info(
        f"OpenCode agent {agent['id']} has no session_id, using tmux fallback"
    )
    _send_message_tmux(agent, message)
    return
```

But `src/orch/tail.py:41-45` just raises an error:
```python
if not session_id:
    raise RuntimeError(
        f"Agent '{agent['id']}' is an OpenCode agent but has no session_id. "
        f"Cannot capture output."
    )
```

**Source:** 
- `src/orch/send.py:35-48` - has fallback
- `src/orch/tail.py:38-45` - no fallback

**Significance:** The fix pattern already exists - just apply it to tail.py.

---

### Finding 3: Agent registry shows mixed session_id presence

**Evidence:** From `~/.orch/agent-registry.json`:
- `ok-inv-test-opencode-bac-3053-12dec`: `backend: "opencode"`, NO `session_id`
- `ok-inv-test-opencode-bac-5224-12dec`: `backend: "opencode"`, `session_id: "ses_4eafbf22effeXc1Wa5Zz9s1Fls"`

The difference is likely due to:
1. Agents spawned with standalone TUI mode (no session_id)
2. Agents spawned with server attach mode (has session_id)

**Source:** `grep -i "opencode\|session_id" ~/.orch/agent-registry.json`

**Significance:** The tmux fallback is essential because standalone mode is the default and many agents won't have session_ids.

---

## Synthesis

**Key Insights:**

1. **Standalone vs Server mode** - OpenCode can run in two modes: standalone TUI (each instance creates its own session) or attached to a server (pre-existing session). Only server mode provides a session_id upfront.

2. **Pattern already exists** - The `send.py` module already handles this case with tmux fallback. Since OpenCode agents still run in tmux windows (spawned via `tmux new-window`), we can capture output via `tmux capture-pane`.

3. **Minimal fix required** - Just add the tmux fallback to `_tail_opencode()` in tail.py, matching the pattern in send.py.

**Answer to Investigation Question:**

`orch tail` fails for OpenCode agents without session_id because tail.py doesn't have the tmux fallback that send.py has. The fix is to add the same fallback pattern: when an OpenCode agent has no session_id, use `_tail_tmux()` instead of raising an error. This works because OpenCode agents still run in tmux windows.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Root cause traced through code, fix pattern validated in existing codebase (send.py), and error successfully reproduced.

**What's certain:**

- ✅ Root cause is missing session_id in standalone TUI mode
- ✅ Fix pattern exists in send.py and works
- ✅ OpenCode agents run in tmux windows regardless of mode

**What's uncertain:**

- ⚠️ Whether all OpenCode spawn paths set window/window_id correctly (assumed yes based on code review)

**What would increase confidence to Very High:**

- End-to-end test after implementing fix

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add tmux fallback to _tail_opencode()** - Match the pattern in send.py

**Why this approach:**
- Pattern already validated in send.py (lines 41-48)
- Minimal code change
- Doesn't require capturing session_id from OpenCode

**Trade-offs accepted:**
- tmux capture-pane shows TUI output, not structured messages
- Acceptable because it's better than failing entirely

**Implementation sequence:**
1. Add fallback in `_tail_opencode()` when session_id is None
2. Log the fallback for debugging
3. Run existing tests + manual verification

### Alternative Approaches Considered

**Option B: Capture session_id from OpenCode**
- **Pros:** Would enable API-based operations
- **Cons:** Complex - would need to parse OpenCode TUI output or poll server API
- **When to use instead:** When structured message history is essential

**Option C: Require server mode for OpenCode**
- **Pros:** Always have session_id
- **Cons:** Changes spawn architecture, may break existing workflows
- **When to use instead:** If API operations become critical

**Rationale for recommendation:** Option A is minimal, validated, and fixes the immediate issue.

---

### Implementation Details

**What to implement first:**
- Add tmux fallback in `_tail_opencode()` function

**Things to watch out for:**
- ⚠️ Ensure window/window_id keys are present for OpenCode agents
- ⚠️ Log the fallback so users understand they're seeing TUI output

**Success criteria:**
- ✅ `orch tail ok-inv-test-opencode-bac-3053-12dec` works (the agent without session_id)
- ✅ Existing tests pass
- ✅ OpenCode agents with session_id still use API (preferred path)

---

## References

**Files Examined:**
- `src/orch/tail.py:38-68` - _tail_opencode function
- `src/orch/send.py:35-48` - _send_message_opencode with fallback pattern
- `src/orch/spawn.py:757-968` - spawn_with_opencode function
- `src/orch/backends/opencode.py` - OpenCode client API

**Commands Run:**
```bash
# Reproduce error
orch tail ok-inv-test-opencode-bac-3053-12dec

# Verify working case
orch tail ok-inv-test-opencode-bac-5224-12dec

# Check registry structure
grep -i "opencode\|session_id" ~/.orch/agent-registry.json
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-02-implement-tail-command-support-opencode.md` - Original tail implementation

---

## Investigation History

**2025-12-13 02:45:** Investigation started
- Initial question: Why does orch tail fail with "no session_id" for OpenCode agents?
- Context: Beads issue orch-cli-zsp1 reports this failure

**2025-12-13 02:55:** Root cause identified
- Found session_id is never set in spawn_with_opencode()
- Found send.py has working tmux fallback pattern

**2025-12-13 03:00:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Missing tmux fallback in tail.py, fix pattern exists in send.py
