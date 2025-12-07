**TLDR:** Question: Why does switch_workers_client switch the orchestrator instead of workers? Answer: The function picks the FIRST client on a `workers*` session, and if orchestrator is accidentally on a workers session, it gets picked because it appears first in `tmux list-clients`. High confidence (90%) - reproduced and verified the root cause.

---

# Investigation: switch_workers_client Switches Wrong Client

**Question:** Why does `switch_workers_client()` switch the orchestrator Ghostty window instead of the workers Ghostty window?

**Started:** 2025-12-07
**Updated:** 2025-12-07
**Owner:** debugging-agent
**Phase:** Complete
**Next Step:** Implement fix - exclude current client from selection
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Client list order - orchestrator appears first

**Evidence:** `tmux list-clients -F '#{client_tty} #{session_name}'` consistently returns:
```
/dev/ttys000 orchestrator
/dev/ttys043 workers-orch-cli
```
The orchestrator client (`/dev/ttys000`) always appears before the workers client (`/dev/ttys043`).

**Source:** Direct tmux command execution, tested multiple times.

**Significance:** The order of clients matters because the function uses `break` after finding the first match.

---

### Finding 2: Function picks FIRST workers* client, not the intended one

**Evidence:** The `switch_workers_client` function at `src/orch/tmuxinator.py:104-153` iterates through clients in order and picks the first one on a `workers*` session:
```python
for line in result.stdout.strip().split('\n'):
    ...
    if session.startswith('workers'):
        workers_client_tty = tty
        break  # <-- First match wins
```

**Source:** `src/orch/tmuxinator.py:132-140`

**Significance:** If orchestrator is accidentally attached to a workers session, it gets selected instead of the actual workers client.

---

### Finding 3: Bug reproduced - orchestrator on workers session causes wrong selection

**Evidence:** When orchestrator client is switched to a workers session (e.g., `workers` base session), the function incorrectly selects it:
```
=== State after orchestrator on workers ===
/dev/ttys000 -> workers
/dev/ttys043 -> workers-orch-cli

=== Function would select ===
-> Found workers client: /dev/ttys000 (on workers)
```
This causes the orchestrator window to switch instead of the workers window.

**Source:** Manual reproduction via bash testing

**Significance:** This is the exact bug scenario described. The orchestrator can end up on a workers session through:
1. User manually switching sessions
2. Race conditions during startup
3. tmux session inheritance

---

## Synthesis

**Key Insights:**

1. **Order-dependent selection is fragile** - Using `break` on first match assumes there's only one workers client, which isn't always true.

2. **Current client should be excluded** - When `orch spawn` runs from the orchestrator, it should never switch the orchestrator client itself. The calling client should be excluded from selection.

3. **No validation of client identity** - The function doesn't verify it's switching the "right" workers client, just any client on a workers session.

**Answer to Investigation Question:**

The bug occurs because `switch_workers_client()` selects the FIRST client attached to a `workers*` session. Since orchestrator (`/dev/ttys000`) appears first in `tmux list-clients`, if it's ever attached to a workers session (intentionally or accidentally), it gets selected and switched. The fix should exclude the current/calling client from the selection, ensuring only the actual workers Ghostty window gets switched.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Root cause was reproduced and verified through direct testing. The code path is clear and the bug mechanism is understood.

**What's certain:**

- ✅ The function selects the first `workers*` client in list order
- ✅ Orchestrator client appears first in `tmux list-clients`
- ✅ If orchestrator is on workers session, it gets incorrectly selected
- ✅ The `-c` flag in `switch-client` works correctly (not the issue)

**What's uncertain:**

- ⚠️ Exact scenarios that cause orchestrator to be on workers session in production
- ⚠️ Whether there are other edge cases (e.g., more than 2 clients)

**What would increase confidence to Very High:**

- Testing the fix in production with Dylan's setup
- Confirming the fix handles edge cases (no workers client, multiple workers clients)

---

## Implementation Recommendations

**Purpose:** Fix the client selection to exclude the calling client.

### Recommended Approach ⭐

**Exclude current client from selection** - Get the current client's TTY and skip it when looking for workers clients.

**Why this approach:**
- Directly addresses root cause (calling client gets selected)
- Simple implementation (add one check)
- No false positives (current client is never the intended target)

**Trade-offs accepted:**
- Requires knowing current client TTY (available via tmux display-message)
- Slightly more complex logic

**Implementation sequence:**
1. Get current client TTY at start of function
2. Skip current client in the selection loop
3. Return False if no OTHER workers client found

### Alternative Approaches Considered

**Option B: Use client activity timestamp to pick most recent workers client**
- **Pros:** Might pick the more "active" workers window
- **Cons:** Doesn't address the core issue - orchestrator could still be more recent
- **When to use instead:** If we need to handle multiple legitimate workers clients

**Option C: Look for a specific client pattern (e.g., exclude /dev/ttys000)**
- **Pros:** Simple
- **Cons:** Hardcoded, fragile, won't work if TTYs change
- **When to use instead:** Never

**Rationale for recommendation:** Option A directly solves the problem by ensuring the calling client (orchestrator) is never selected, regardless of which session it's attached to.

---

### Implementation Details

**What to implement first:**
- Modify `switch_workers_client()` to get and exclude current client TTY
- Test with both normal and bug scenarios

**Things to watch out for:**
- ⚠️ Getting current client TTY requires `tmux display-message -p '#{client_tty}'`
- ⚠️ Must handle case where current client isn't in tmux (shouldn't happen but be defensive)
- ⚠️ Should still return False if no workers client found (after exclusion)

**Success criteria:**
- ✅ Orchestrator window stays on orchestrator session during spawn
- ✅ Workers window correctly switches to target session
- ✅ Function returns False when no suitable workers client exists

---

## References

**Files Examined:**
- `src/orch/tmuxinator.py` - Main file with `switch_workers_client` function
- `src/orch/spawn.py` - Caller of the function, around line 615

**Commands Run:**
```bash
# List clients
tmux list-clients -F '#{client_tty} #{session_name}'

# Get current client
tmux display-message -p '#{client_tty}'

# Test switch-client with -c flag
tmux switch-client -c /dev/ttys000 -t workers
```

---

## Investigation History

**2025-12-07 17:30:** Investigation started
- Initial question: Why does switch_workers_client switch orchestrator instead of workers?
- Context: Bug report from per-project workers sessions feature

**2025-12-07 17:45:** Root cause identified
- Function picks first client on workers* session
- Orchestrator appears first in list
- If orchestrator on workers session, it gets selected

**2025-12-07 17:50:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Exclude current client from selection to fix the bug
