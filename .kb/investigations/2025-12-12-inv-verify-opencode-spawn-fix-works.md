**TLDR:** Question: Does the OpenCode spawn timing fix (commit 870c076) work correctly? Answer: Yes - the fix changed `spawn_with_opencode()` to use `get_workers_session_name(config.project)` instead of `config.project` directly, which correctly produces `workers-orch-cli` instead of `orch-cli`. Very High confidence (98%) - verified via code inspection and real spawn test that succeeded without "session not found" errors.

---

# Investigation: Verify OpenCode Spawn Fix Works

**Question:** Does the session creation timing fix in commit 870c076 resolve the "session not found" errors during OpenCode spawn?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (98%)

---

## Findings

### Finding 1: The Bug Was Using Wrong Session Name

**Evidence:** The commit 870c076 commit message explicitly states:
```
spawn_with_opencode() was using config.project directly (e.g., 'orch-cli')
instead of get_workers_session_name(config.project) (e.g., 'workers-orch-cli'),
causing tmux 'can't find session' errors when opencode was the default backend.
```

**Source:** `git show 870c076` - commit message

**Significance:** This confirms the root cause was incorrect session name resolution. When spawning into tmux, the code was looking for session `orch-cli` instead of `workers-orch-cli`.

---

### Finding 2: Fix Correctly Uses get_workers_session_name()

**Evidence:** Current code at line 815:
```python
session_name = get_workers_session_name(config.project)  # e.g., "workers-orch-cli"
```

This matches the pattern used in `spawn_in_tmux()` at line 525:
```python
session_name = get_workers_session_name(config.project)
```

**Source:** `src/orch/spawn.py:815` and `src/orch/spawn.py:525`

**Significance:** Both spawn paths (OpenCode and Claude/Codex) now use the same session name resolution, ensuring consistency.

---

### Finding 3: Real Spawn Test Succeeds Without Errors

**Evidence:** Executed spawn test:
```bash
$ orch spawn investigation "test spawn timing fix" -y
📍 Auto-detected project: orch-cli
🚀 spawning: 🔬investigation → orch-cli "test spawn timing fix"

✅ Spawned (OpenCode): oc-inv-test-spawn-timing-fix-12dec
   Window: workers-orch-cli:7
   Session: ses_4eadcfba1ffeTXbGGlyBwHR42S
   Workspace: oc-inv-test-spawn-timing-fix-12dec
```

Registry confirms correct backend and window:
```
oc-inv-test-spawn-timing-fix-12dec: backend=opencode, window=workers-orch-cli:7
```

**Source:** Direct command execution

**Significance:** End-to-end verification that OpenCode spawns work correctly with the fix. No "session not found" error occurred.

---

### Finding 4: Existing Active Agents All Using Correct Session

**Evidence:** All active agents in `workers-orch-cli` session:
```
oc-audit-orch-cli-orch-12dec: backend=opencode, window=workers-orch-cli:2
oc-debug-session-not-found-12dec: backend=opencode, window=workers-orch-cli:3
oc-inv-verify-opencode-spawn-12dec: backend=opencode, window=workers-orch-cli:5
oc-inv-test-spawn-verify-12dec: backend=opencode, window=workers-orch-cli:6
oc-inv-test-spawn-timing-fix-12dec: backend=opencode, window=workers-orch-cli:7
```

**Source:** `~/.orch/agent-registry.json`

**Significance:** All agents spawned after the fix are correctly using `workers-orch-cli` session.

---

## Test Performed

**Test:** Spawned a new investigation agent with OpenCode backend (default) and verified:
1. No "session not found" error during spawn
2. Agent created in correct tmux window (`workers-orch-cli:7`)
3. Registry shows correct backend (`opencode`) and window

**Result:** 
- Spawn completed successfully in ~3 seconds
- Window target correctly resolved to `workers-orch-cli:7`
- OpenCode session created: `ses_4eadcfba1ffeTXbGGlyBwHR42S`
- Agent registered with correct metadata
- Test agent cleaned up via `orch abandon`

---

## Synthesis

**Key Insights:**

1. **Root cause was simple session name mismatch** - The code was using `config.project` (e.g., `orch-cli`) instead of `get_workers_session_name(config.project)` (e.g., `workers-orch-cli`). This caused tmux to fail with "can't find session" because `orch-cli` is not a valid session name.

2. **Fix aligns both spawn paths** - Both `spawn_in_tmux()` (for claude/codex) and `spawn_with_opencode()` now use the same `get_workers_session_name()` function, ensuring consistent behavior across backends.

3. **The fix also improved the architecture** - The commit restructured `spawn_with_opencode()` to follow the same tmux-window-per-agent pattern as other backends, rather than trying to use a pure HTTP API approach. This means each OpenCode agent gets its own TUI instance in a dedicated tmux window.

**Answer to Investigation Question:**

Yes, the fix works correctly. The session name resolution bug has been fixed, and OpenCode spawns now succeed without "session not found" errors. The test spawn demonstrated that:
- Session name correctly resolves to `workers-orch-cli`
- tmux window creation succeeds
- OpenCode TUI starts correctly
- Agent registration works properly

---

## Confidence Assessment

**Current Confidence:** Very High (98%)

**Why this level?**

Multiple verification methods confirm the fix:
- Code inspection shows correct fix applied
- Real spawn test succeeded
- Registry shows correct metadata
- No errors observed

**What's certain:**

- ✅ `get_workers_session_name()` is now used in `spawn_with_opencode()` (code inspection)
- ✅ Spawn test succeeded without "session not found" error (runtime test)
- ✅ Agent created in correct tmux session `workers-orch-cli` (registry inspection)
- ✅ OpenCode session ID assigned correctly (spawn output)

**What's uncertain:**

- ⚠️ Haven't tested edge cases (server down, concurrent spawns)
- ⚠️ Only tested single spawn - production volume untested

**What would increase confidence to 100%:**

- Run multiple spawns in rapid succession
- Test with OpenCode server restarting mid-spawn
- Verify agent lifecycle (spawn → work → complete)

---

## Implementation Recommendations

N/A - This was a verification investigation. The fix (commit 870c076) is already implemented and working correctly.

**The bug was:** `spawn_with_opencode()` used `config.project` as the tmux session name
**The fix was:** Changed to use `get_workers_session_name(config.project)`
**Status:** Fix verified working

---

## References

**Files Examined:**
- `src/orch/spawn.py:815` - Fixed line using `get_workers_session_name()`
- `src/orch/spawn.py:525` - Reference line in `spawn_in_tmux()` for comparison
- `~/.orch/agent-registry.json` - Agent registration verification

**Commands Run:**
```bash
# View fix commit
git show 870c076 --stat

# Verify fix is in code
grep -n "get_workers_session_name" src/orch/spawn.py

# Check existing sessions
tmux list-sessions

# Verify OpenCode is default backend
cat ~/.orch/config.yaml | grep backend

# Test spawn
orch spawn investigation "test spawn timing fix" -y

# Check registry
cat ~/.orch/agent-registry.json | python3 -c "import sys, json; ..."

# Cleanup
orch abandon oc-inv-test-spawn-timing-fix-12dec -y
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-12-inv-test-opencode-default.md` - Prior investigation confirming OpenCode works as default
- **Investigation:** `.kb/investigations/2025-12-12-inv-verify-opencode-default-test.md` - Prior investigation verifying default backend behavior

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: Verify OpenCode spawn timing fix works
- Context: Commit 870c076 fixed "session not found" error during OpenCode spawn

**2025-12-12:** Code inspection complete
- Found fix at line 815 using `get_workers_session_name()`
- Verified matches pattern in `spawn_in_tmux()` at line 525

**2025-12-12:** Spawn test performed
- Spawned `oc-inv-test-spawn-timing-fix-12dec` successfully
- No "session not found" error
- Window correctly created in `workers-orch-cli:7`

**2025-12-12:** Investigation completed
- Final confidence: Very High (98%)
- Status: Complete
- Key outcome: Fix verified working - session name resolution bug is resolved
