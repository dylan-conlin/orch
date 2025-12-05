# Investigation: Why Agents Skip Completion Protocol

**Question:** Why do agents complete their work (commits, tests pass) but skip the completion protocol (no Phase: Complete comment, no /exit)?

**Started:** 2025-12-04
**Updated:** 2025-12-04
**Status:** Complete
**Confidence:** High

## Problem Statement

Agents finish their actual work (commits, tests pass) but don't follow completion protocol:
- Never mark Phase: Complete via `bd comment`
- Sit idle at prompt instead of calling /exit
- (WORKSPACE.md is no longer required - beads is source of truth)

Example: `feat-simplify-coll-run-04dec`:
- Committed work (607a142)
- Tests passed
- No Phase: Complete comment
- Still at prompt (12% context left)

## Findings

### Finding 1: Completion Instructions ARE Present in Skill

**Evidence:** The feature-impl skill has explicit completion instructions in multiple locations:

1. Validation phase (lines 934-935, 951-952, 971-972):
   ```
   4. Report completion: `bd comment <beads-id> "Phase: Complete - [brief summary]"`
   5. Call /exit to close agent session
   ```

2. Final Completion Criteria section (lines 1398, 1402):
   ```markdown
   - [ ] Final status reported: `bd comment <beads-id> "Phase: Complete - [summary of deliverables]"`
   **Final step:** After all criteria met, call /exit to close agent session.
   ```

3. Progress Tracking section (line 1362):
   ```bash
   bd comment <issue-id> "Phase: Complete - All tests passing..."
   ```

**Source:** `/Users/dylanconlin/.claude/skills/worker/feature-impl/SKILL.md`

**Significance:** Instructions exist but agents aren't following them - the issue isn't missing documentation.

### Finding 2: SPAWN_CONTEXT Has Completion Instructions but Buried Deep

**Evidence:** Looking at spawn_prompt.py (lines 460-470):
```python
status_updates = """STATUS UPDATES (CRITICAL):
Report phase transitions via `bd comment <beads-id>`:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session
```

However:
1. These appear AFTER the task description, context, deliverables
2. The full SKILL.md content (1,400+ lines) is embedded before verification requirements
3. Agents hit context limits after doing the actual work, before reaching completion steps

**Source:** `spawn_prompt.py:460-470`, SPAWN_CONTEXT structure

**Significance:** Critical completion instructions are buried beneath ~2000 lines of skill content and context.

### Finding 3: Completion Enforcement Requires `bd comment` "Phase: Complete"

**Evidence:** From `complete.py` (lines 977-1018):
```python
class BeadsPhaseNotCompleteError(Exception):
    """Raised when trying to close a beads issue without Phase: Complete comment."""

def close_beads_issue(beads_id: str, verify_phase: bool = True) -> bool:
    if verify_phase:
        current_phase = beads.get_phase_from_comments(beads_id)
        if not current_phase or current_phase.lower() != "complete":
            raise BeadsPhaseNotCompleteError(beads_id, current_phase)
```

**Source:** `src/orch/complete.py:965-1007`

**Significance:** The system DOES enforce completion - but only when orchestrator runs `orch complete`. Agents aren't incentivized during their session to report Phase: Complete.

### Finding 4: FIRST 3 ACTIONS Block Focuses on Start, Not End

**Evidence:** The critical instruction block (spawn_prompt.py:376-384) focuses entirely on session START:
```python
critical_instruction = """
🚨 CRITICAL - FIRST 3 ACTIONS:
You MUST do these within your first 3 tool calls:
1. Report via `bd comment <beads-id> "Phase: Planning - [brief description]"`
2. Read relevant codebase context for your task
3. Begin planning
...
```

There is NO equivalent "FINAL 3 ACTIONS" or "BEFORE /exit" block.

**Source:** `spawn_prompt.py:376-384`

**Significance:** Start-of-session instructions get special prominent treatment; end-of-session completion doesn't.

### Finding 5: Context Exhaustion Timeline

**Evidence:** The problem report shows:
- Agent had 12% context remaining when found idle
- Work was complete (commits made, tests passing)
- Agent didn't proceed to completion protocol

Typical session flow:
1. Agent reads SPAWN_CONTEXT (~2000 lines for feature-impl)
2. Agent does planning and investigation
3. Agent implements (reading files, writing code, running tests)
4. Agent commits work (80-90% of session complete)
5. Agent should report Phase: Complete and /exit ← **HERE'S THE GAP**

**Source:** Issue description showing 12% context at idle state

**Significance:** Agents finish work but don't have completion steps in "active memory" since they were read 80-90% of session ago.

## Synthesis

**Root Cause Analysis:**

The completion protocol failure has **three contributing factors**:

1. **Temporal Distance:** Completion instructions (buried 2000+ lines into SPAWN_CONTEXT) are read at session start but needed at session end - by then they've scrolled out of agent's effective working memory.

2. **Asymmetric Prominence:** Session START has a `🚨 CRITICAL - FIRST 3 ACTIONS` block with enforcement warning. Session END has no equivalent prominent reminder.

3. **No In-Session Trigger:** Nothing in the agent's flow naturally triggers "now check completion protocol". After making final commit, agents just... stop.

**Why WORKSPACE.md Isn't the Answer:**
The system moved to beads-based tracking (beads is source of truth). WORKSPACE.md is no longer required. The real requirement is:
- `bd comment <beads-id> "Phase: Complete - [summary]"`
- `/exit` to close session

## Recommendations

### Option A: Add Prominent "SESSION COMPLETE PROTOCOL" Block (Recommended)

Add a highly visible completion block to SPAWN_CONTEXT that mirrors the "FIRST 3 ACTIONS" pattern:

```markdown
🚨 SESSION COMPLETE PROTOCOL (DO NOT SKIP):
Before typing anything else after your final commit:
1. `bd comment <beads-id> "Phase: Complete - [summary]"`
2. Call /exit

Work is NOT done until Phase: Complete is reported.
```

**Placement:** Put this IMMEDIATELY AFTER the `🚨 CRITICAL - FIRST 3 ACTIONS` block so it's read early and associated with the critical instructions.

### Option B: Add Completion Reminder to Validation Phase

Add explicit step in validation phase completion criteria:
```markdown
## Validation: tests

1. **Run test suite**
2. **Verify all tests pass**
3. **Commit all changes**
4. **Verify commit** - `git status` shows "nothing to commit"
5. **🚨 FINAL STEP - Report completion and exit:**
   ```bash
   bd comment <beads-id> "Phase: Complete - [summary]"
   /exit
   ```
   **Session is NOT complete until you run /exit**
```

### Option C: Context Recovery Prompt

Add a "completion reminder" that agents should re-read before finishing:
```markdown
**Before calling /exit:**
Re-read: "SESSION COMPLETE PROTOCOL" section in SPAWN_CONTEXT
```

### Option D: Automated Context Window Monitor (Complex)

Build a hook that detects when an agent makes a commit, waits for them to report Phase: Complete, and prompts them if they don't within N minutes.

## Implementation Recommendation

**Start with Option A + Option B combined:**

1. Add `🚨 SESSION COMPLETE PROTOCOL` block early in SPAWN_CONTEXT (near FIRST 3 ACTIONS)
2. Update feature-impl skill validation phases to emphasize completion step
3. Test with 3-5 spawned agents
4. Measure completion rate before/after

This addresses:
- Temporal distance (instructions early in prompt)
- Asymmetric prominence (matching format of critical start block)
- No in-session trigger (validation phase explicitly includes it)

## Confidence Assessment

**Current Confidence:** Medium

**What's certain:**
- Instructions exist but are buried
- Agents have context remaining but don't complete
- System enforces completion only when orchestrator runs `orch complete`

**What's uncertain:**
- Exact attention mechanism causing instructions to be "forgotten"
- Whether adding prominent block will fix issue or agents will still skip
- Whether this is Claude-model-specific or applies to all agent implementations

**To increase confidence:**
- A/B test with modified spawn prompts
- Track completion rate across 10+ agents
- Check if issue occurs with different skills (not just feature-impl)

## Implementation

**Changes made:**

1. **spawn_prompt.py** - Added `🚨 SESSION COMPLETE PROTOCOL` block immediately after `FIRST 3 ACTIONS` block:
   - Location: Lines 385-392
   - Content: Clear instructions to run `bd comment <beads-id> "Phase: Complete"` and `/exit`
   - Warning about consequences: "Work is NOT complete until Phase: Complete is reported"

2. **tests/test_spawn_prompt.py** - Added `TestSpawnPromptCompletionProtocol` test class:
   - `test_spawn_prompt_includes_session_complete_protocol_block` - Verifies block exists
   - `test_session_complete_protocol_appears_early_in_prompt` - Verifies appears before skill guidance
   - `test_completion_protocol_warns_about_consequences` - Verifies warning language

**Note:** Skill source files in orch-knowledge also need the prominent completion block added to validation.md. This is a separate change for that repo.

## Verification

- All spawn_prompt tests pass (8/8)
- SESSION COMPLETE PROTOCOL appears early in prompt (before SKILL GUIDANCE)
- Protocol includes consequences warning ("Work is NOT complete", "cannot close this issue")
