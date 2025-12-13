**TLDR:** Question: Why did "session not found" error occur during OpenCode spawn? Answer: The error was a known race condition in the old spawn flow where we created sessions via API before the TUI was ready to receive them. Commit 870c076 fixed this by reordering operations to start TUI first, then create sessions via API. High confidence (90%) - verified through code archaeology and understanding of the OpenCode TUI/API synchronization model.

---

# Investigation: Session Not Found Error in OpenCode Spawn

**Question:** What caused the "session not found" error during OpenCode spawn, and has it been addressed?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent (orch-cli-x20)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: The OpenCode Spawn Flow Changed Significantly

**Evidence:** Commit `870c076` ("fix(spawn): use workers session name for opencode backend") rewrote `spawn_with_opencode()` from a pure API-based approach to a tmux+API hybrid approach.

Old flow (before 870c076):
1. Discover or use provided server URL
2. Create session via API immediately (`backend.spawn_session()`)
3. Return session_id directly (no tmux window)

New flow (after 870c076):
1. Create tmux window for OpenCode TUI
2. Start `opencode attach <server> --dir <path>` in window
3. Wait for TUI to be ready (`_wait_for_opencode_ready()`)
4. THEN create session via API
5. Wait 0.5s for session to be visible to TUI

**Source:** 
- `src/orch/spawn.py:757-976` (current)
- `git diff 870c076^..870c076 -- src/orch/spawn.py`

**Significance:** The old flow had a fundamental race condition - the session was created via API before the TUI existed to display/use it. The new flow correctly sequences operations.

---

### Finding 2: "Session Not Found" Error Origins in OpenCode

**Evidence:** The "session not found" error can occur in two places in OpenCode:

1. **TUI Route Handler** (`packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:156`):
   - When `sync.session.sync(route.sessionID)` fails
   - Shows toast error and navigates back to home
   
2. **ACP Session Manager** (`packages/opencode/src/acp/session.ts:77-78`):
   - When `this.sessions.get(sessionId)` returns undefined
   - Throws `RequestError.invalidParams`

**Source:**
- OpenCode repo: `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:147-160`
- OpenCode repo: `packages/opencode/src/acp/session.ts:74-80`

**Significance:** Both error sources indicate the session ID doesn't exist in the server's session store. This happens when:
- Trying to navigate to a session before it's created
- Trying to use a session that was created on a different server instance
- Race condition between session creation and session lookup

---

### Finding 3: Current Flow Has Deliberate Race Condition Mitigation

**Evidence:** The current code at `src/orch/spawn.py:914-929` shows explicit handling:

```python
# For attach mode: now that TUI is ready, create session and send prompt via API
# This ensures the TUI is connected to the server before we try to create a session
if existing_server and session_id is None:
    # Create session via API (this sends the prompt immediately)
    session = backend.spawn_session(...)
    session_id = session.id
    
    # Wait briefly for session to be visible
    # The TUI should pick up the new session automatically
    time.sleep(0.5)
```

The comment explicitly acknowledges the timing issue and the 0.5s wait is intended to allow the TUI to pick up the new session.

**Source:** `src/orch/spawn.py:914-929`

**Significance:** The fix is in place, but the 0.5s wait is a heuristic. If the error recurs, we may need:
- Longer wait time
- Active polling to verify session is visible in TUI
- Better synchronization between API session creation and TUI session list refresh

---

## Synthesis

**Key Insights:**

1. **Operation Ordering Was the Root Cause** - The original `spawn_with_opencode()` created sessions via API before any TUI existed to consume them. This meant the session was orphaned until/unless a TUI attached and discovered it.

2. **The Fix Uses TUI-First, API-Second Pattern** - By starting the TUI first and waiting for it to be ready, then creating the session via API, the TUI can receive the SSE events about the new session and display it.

3. **The 0.5s Sleep is a Fragile Fix** - While the current approach works, the hard-coded 0.5s wait is not ideal. A more robust solution would poll to verify the session is visible or use OpenCode's SSE events to confirm synchronization.

**Answer to Investigation Question:**

The "session not found" error occurred because the old OpenCode spawn flow created sessions via API before any TUI was running to receive them. When the TUI later tried to sync/display the session, it couldn't find it in its local state.

Commit `870c076` (Dec 12, 2025) fixed this by restructuring the flow to:
1. Start TUI first (`opencode attach`)
2. Wait for TUI to be ready
3. Then create session via API
4. Wait 0.5s for session visibility

The fix is confirmed to be in place in the current codebase. If the error recurs, the 0.5s wait may need to be increased or replaced with active polling.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

The code archaeology clearly shows the before/after states, and the fix's intent is explicitly documented in comments. The OpenCode error handling code confirms where "session not found" originates.

**What's certain:**

- ✅ Commit 870c076 completely rewrote the OpenCode spawn flow
- ✅ The old flow had a race condition (API session creation before TUI)
- ✅ The new flow creates TUI first, then creates session via API
- ✅ There's a 0.5s wait to allow session visibility

**What's uncertain:**

- ⚠️ Whether the 0.5s wait is always sufficient
- ⚠️ Whether the TUI automatically refreshes its session list on SSE events
- ⚠️ Whether there are edge cases where the session could still be "not found"

**What would increase confidence to Very High (95%+):**

- Reproduce the original error and verify the fix prevents it
- Understand OpenCode's SSE event handling for new sessions
- Test with network latency to ensure 0.5s is sufficient

---

## Implementation Recommendations

**Purpose:** The fix is already implemented. These recommendations are for potential robustness improvements.

### Current State ⭐

**The fix is already in place** - Commit 870c076 addressed the root cause. No immediate action needed unless the error recurs.

**Why this is sufficient:**
- The operation ordering is now correct (TUI before API session)
- The 0.5s wait provides margin for session synchronization
- Agent recovered successfully (per issue description)

### Potential Future Improvements

**Option A: Active Session Verification**
- After creating session, poll the TUI/API to verify it's visible
- More robust than fixed sleep, but adds complexity
- **When to implement:** If 0.5s proves insufficient

**Option B: Longer Fixed Wait**
- Increase from 0.5s to 1.0s or 2.0s
- Simple but wasteful of time
- **When to implement:** Quick fix if sporadic failures occur

**Option C: SSE-Based Confirmation**
- Subscribe to OpenCode events, wait for session.created event
- Most robust but requires understanding OpenCode's event flow
- **When to implement:** If reliability is critical

---

## References

**Files Examined:**
- `src/orch/spawn.py:757-976` - OpenCode spawn implementation
- `src/orch/backends/opencode.py` - OpenCode backend client
- OpenCode: `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx` - TUI session handling
- OpenCode: `packages/opencode/src/acp/session.ts` - ACP session manager

**Commands Run:**
```bash
# Check recent spawn.py changes
git log --oneline -20 -- src/orch/spawn.py

# View the fix commit
git show 870c076 --stat

# Check what changed in the fix
git diff 870c076^..870c076 -- src/orch/spawn.py

# Search for "session not found" in codebase
grep -r "session.*not.*found" src/

# Check opencode attach help
opencode attach --help

# Search for error source in OpenCode
grep -r "session.not.found" ~/Documents/personal/opencode
```

**Related Artifacts:**
- **Commit:** 870c076 - "fix(spawn): use workers session name for opencode backend"
- **Beads Issue:** orch-cli-x20 - Original bug report

---

## Investigation History

**2025-12-12 19:39:** Investigation started
- Initial question: What caused "session not found" during OpenCode spawn?
- Context: Error observed during spawn, agent recovered but root cause unknown

**2025-12-12 19:45:** Found relevant commit 870c076
- Discovered major rewrite of spawn_with_opencode() function
- Identified the operation ordering change as the likely fix

**2025-12-12 19:50:** Traced "session not found" error in OpenCode source
- Found two locations where this error can occur
- Confirmed both relate to session ID not being in server's session store

**2025-12-12 19:55:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Root cause was race condition in old flow, fix is already in place via commit 870c076
