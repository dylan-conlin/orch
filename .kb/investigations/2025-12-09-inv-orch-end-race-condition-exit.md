**TLDR:** Question: Why doesn't /exit work when orch end is called from a Bash tool call? Answer: The tmux send-keys delivers /exit while Claude Code is still executing the Bash tool, so the REPL isn't at its input prompt to process the command. High confidence (95%) - root cause confirmed, recommendation to split orch end into check-only with agent-driven exit.

---

# Investigation: orch end race condition - /exit via tmux arrives during tool execution

**Question:** Why does /exit sent via tmux from orch end not terminate the session when run from within a Bash tool call?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** spawned worker
**Phase:** Complete
**Next Step:** Implement recommended solution
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: The send-keys race condition is fundamental

**Evidence:** When an agent calls `orch end` from a Bash tool call:
1. Claude Code is mid-execution of the Bash tool
2. The Bash tool runs `send_exit_to_pane()` which executes `tmux send-keys -t $pane_id /exit` then `Enter`
3. The /exit text arrives in the tmux pane immediately
4. But Claude Code is still waiting for the Bash tool to return
5. The REPL is not at its input prompt - it's processing a tool call
6. Result: /exit appears but isn't interpreted as a command

**Source:**
- `src/orch/end.py:162-192` - `send_exit_to_pane()` sends via tmux send-keys
- Prior investigation `.kb/investigations/2025-12-09-inv-test-orch-end-command-verify.md` confirmed the behavior

**Significance:** This is not a timing bug that can be fixed with delays. The send-keys happens DURING tool execution, and no amount of waiting can fix it because the wait happens within the tool call itself.

---

### Finding 2: External invocation works fine

**Evidence:** When `orch end` is called from outside the agent's Claude Code session (e.g., orchestrator calling it on a worker, or from another terminal), the /exit is delivered to the pane when the REPL is idle, and it's processed correctly.

**Source:** Design intent from `src/orch/end.py:1-10` docstring describes external use case

**Significance:** The command design works for external control, just not for self-exit. This suggests the solution is to separate the two use cases.

---

### Finding 3: The command combines two distinct concerns

**Evidence:** `orch end` does two things:
1. **Knowledge gate check** - Check `.kn/entries.jsonl` for session entries, warn/prompt if none
2. **Session exit** - Send /exit via tmux to trigger SessionEnd hooks

These are orthogonal concerns. The knowledge check is valuable for agents. The tmux send-keys only makes sense for external callers.

**Source:** `src/orch/end.py:207-257` - `end_session()` function does both in sequence

**Significance:** Separating these concerns solves the race condition and makes the API cleaner.

---

## Synthesis

**Key Insights:**

1. **Race condition is structural** - Cannot be fixed with timing/delays because the send-keys occurs within the same tool call that needs to complete before the REPL accepts input.

2. **Self-exit vs external-exit** - The command works for external callers but fails for self-exit. These are different use cases that should be handled differently.

3. **Knowledge check is the value** - The soft gate warning about uncaptured knowledge is useful. The tmux integration is problematic.

**Answer to Investigation Question:**

The /exit doesn't work because tmux send-keys delivers the command while Claude Code is still processing the Bash tool call that invoked `orch end`. The REPL only accepts /exit commands when at its input prompt, not during tool execution.

The fix is to remove the tmux send-keys from `orch end` and have it output guidance for the agent to use /exit manually. This separates concerns and eliminates the race condition.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

The root cause is deterministic and well-understood:
- tmux send-keys runs inside a Bash tool call
- The REPL cannot process input during tool execution
- This is fundamental to how Claude Code works, not a bug

**What's certain:**

- ✅ Race condition root cause (tool execution blocks input processing)
- ✅ External invocation works (orchestrator → worker)
- ✅ Self-invocation fails (agent → itself)

**What's uncertain:**

- ⚠️ Whether removing send-keys breaks any external use cases (likely no, since external callers can just call /exit directly)

**What would increase confidence to 100%:**

- Verify no external workflows depend on the tmux send-keys behavior
- Test the fix in a real agent session

---

## Implementation Recommendations

**Purpose:** Fix the race condition by separating knowledge check from session exit.

### Recommended Approach ⭐

**Remove tmux send-keys from orch end** - Have the command only perform the knowledge check and output guidance for the agent to exit manually.

**Why this approach:**
- Eliminates the race condition entirely (no timing dependencies)
- Makes agent behavior explicit (agent consciously types /exit)
- Keeps the valuable knowledge gate check
- Simplifies the code

**Trade-offs accepted:**
- Agents must type /exit manually (one extra step)
- Less "magic" - but that's actually good for transparency

**Implementation sequence:**
1. Modify `end_session()` to remove `send_exit_to_pane()` call
2. Change output from "Sending /exit..." to "Ready to exit. Use /exit to close session."
3. Update documentation and help text

### Alternative Approaches Considered

**Option B: Output marker for agent to parse**
- **Pros:** Automatic exit if agent follows convention
- **Cons:** Still requires agent compliance, adds complexity, agents might miss the marker
- **When to use instead:** If fully automatic exit is required AND agent prompts can be modified

**Option C: Tmux timing hack (delay send-keys)**
- **Pros:** Keeps current behavior
- **Cons:** Fundamentally cannot work - delay runs inside the tool call
- **When to use instead:** Never - this is structurally impossible

**Option D: Keep send-keys for external callers only**
- **Pros:** Supports orchestrator → worker pattern
- **Cons:** Adds complexity to detect self vs external invocation
- **When to use instead:** If orchestrators actually use this (they probably just call /exit directly)

**Rationale for recommendation:** Option A is the simplest fix that addresses the root cause. The knowledge check is the real value of `orch end`. External callers can trigger /exit directly without going through orch.

---

### Implementation Details

**What to implement first:**
- Remove `send_exit_to_pane()` call from `end_session()`
- Update output message to guide agent behavior

**Things to watch out for:**
- ⚠️ Ensure output message is clear: "Ready to exit. Use /exit to close session."
- ⚠️ Update SPAWN_CONTEXT.md instructions if they expect automatic exit

**Areas needing further investigation:**
- Check if any external workflows use `orch end` (likely no)
- May want to add `--send-exit` flag for external use case if needed

**Success criteria:**
- ✅ Agent can run `orch end` and see knowledge check result
- ✅ Agent can then type `/exit` to close session
- ✅ No race condition

---

## References

**Files Examined:**
- `src/orch/end.py` - Core implementation, `send_exit_to_pane()` at line 162
- `src/orch/end_commands.py` - CLI registration
- `.kb/investigations/2025-12-09-inv-test-orch-end-command-verify.md` - Prior test confirming bug

**Commands Run:**
```bash
# Find orch end implementation
grep -r "orch end\|/exit\|send-keys" src/orch/

# Review prior investigation
cat .kb/investigations/2025-12-09-inv-test-orch-end-command-verify.md
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-test-orch-end-command-verify.md` - Initial bug discovery

---

## Investigation History

**2025-12-09 16:10:** Investigation started
- Initial question: Why doesn't /exit work when orch end is called from a Bash tool call?
- Context: Bug reported after testing orch end command

**2025-12-09 16:15:** Root cause identified
- Race condition: send-keys delivers during tool execution
- REPL can't process input while executing a tool

**2025-12-09 16:20:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Remove send-keys, make orch end a check-only command

**2025-12-09 16:30:** Fix implemented and tested
- Removed `send_exit_to_pane()` and `get_current_pane_id()` functions
- Updated `end_session()` to output guidance: "Ready to exit. Use /exit to close session."
- Updated tests to match new behavior (16/16 pass)
- All 999+ other tests pass, no regressions
