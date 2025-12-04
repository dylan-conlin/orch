# Post-Mortem: Worker Double-Tracking (Workspace + Beads)

**Status:** Complete
**Date:** 2025-12-04
**Type:** Design Investigation
**Related Issue:** orch-cli-30j

## Design Question

Why are workers using BOTH workspaces AND beads for lifecycle tracking, when beads was intended to be the source of truth?

## Problem Framing

### Success Criteria
- Identify root cause of double-tracking pattern
- Determine if this is a spawn prompt issue, skill issue, or knowledge gap
- Provide actionable recommendations to prevent this

### Constraints
- Workers follow spawn context instructions literally
- Beads integration was added incrementally (may have legacy patterns)
- Some investigations still need artifact files (distinct from lifecycle tracking)

### Scope
- IN: Analyzing spawn prompt instructions, transcript patterns
- OUT: Implementing fixes (recommendations only)

---

## Exploration

### Evidence from Transcripts

**Worker 1 (pw-i0n) - Config Cleanup:**
- Created WORKSPACE.md with Phase field tracking (lines 38-50)
- Used `bd comment pw-i0n "Phase: Planning - ..."` (line 54)
- Used `bd comment pw-i0n "Phase: Complete - ..."` (line 669)
- **Result:** Double-tracking confirmed - both systems used

**Worker 2 (pw-cnf) - Thickness Variants:**
- Created WORKSPACE.md with Phase field tracking (lines 38-54)
- Used `bd comment pw-cnf "Phase: Planning - ..."` (line 58)
- Used `bd comment pw-cnf "BLOCKED: ..."` (line 815)
- **Result:** Double-tracking confirmed - both systems used

**Orchestrator:**
- Correctly used beads commands (bd ready, bd show, bd close, bd dep add)
- Spawned from beads issues (orch spawn --issue)
- Monitored via orch status/check/tail
- **Result:** Orchestrator pattern is correct

### Root Cause Analysis

**Primary Cause: spawn_prompt.py has conflicting instructions**

Location: `src/orch/spawn_prompt.py`

1. **Lines 296-343 (fallback_template)** explicitly tells workers:
   ```
   Update Phase: field in WORKSPACE.md at transitions
   Orchestrator monitors via 'orch status' (reads workspace Phase field)
   ```

2. **Lines 422-437 (requires_workspace handling)** tells workers to:
   - Verify workspace exists
   - Update workspace with TLDR, Session Scope, Progress Tracking
   - Update workspace Phase field

3. **Lines 463-474 (STATUS UPDATES section)** says:
   ```
   Update Phase: field in your coordination artifact (WORKSPACE.md) at transitions
   Orchestrator monitors via 'orch status' (reads coordination artifact Phase field)
   ```

4. **Lines 494-525 (BEADS PROGRESS TRACKING)** adds beads tracking BUT says:
   ```
   Note: Workspace still tracks detailed work state. Beads comments are the primary progress log for orchestrator visibility.
   ```

**The instruction explicitly tells workers to use BOTH systems!**

### Existing Issue

Issue `orch-cli-30j` already identifies this exact problem:
> "spawn_prompt.py still includes WORKSPACE.md creation instructions when requires_workspace=true, even though beads is now source of truth for progress tracking."

The issue was discovered but not yet fixed.

---

## Synthesis

### Recommendation

⭐ **RECOMMENDED:** Complete orch-cli-30j to remove legacy workspace instructions

**Why:**
- Root cause is clearly in spawn_prompt.py
- Issue already exists and describes the exact fix needed
- Workers are following instructions - instructions are wrong

**Trade-off:**
- Some skills (architect, investigation) may still want artifact files
- These are DISTINCT from lifecycle tracking workspaces
- Investigation files should stay (they're deliverables, not coordination)

### What to Change in spawn_prompt.py

1. **Remove workspace creation instructions** when beads_id is present
2. **Remove "Workspace still tracks detailed work state"** language
3. **Remove Phase field tracking instructions** for WORKSPACE.md
4. **Keep investigation file tracking** (different from workspace lifecycle)

### What to Keep

- `bd comment` for progress tracking (this is correct)
- Investigation files for investigations (deliverables, not coordination)
- Workspace files ONLY for skills that explicitly need them (architect with design artifacts)

### What to Remove

- WORKSPACE.md creation for feature-impl tasks
- Double-tracking language in BEADS PROGRESS section
- Phase field instructions for WORKSPACE.md

### When This Would Change

- If beads integration is rolled back (unlikely)
- If workspaces gain features beads can't provide (not planned)

---

## Other Observations

### What Workers Did Well

1. **Both workers used beads correctly** - `bd comment` for progress
2. **Both workers followed TDD/validation patterns** - proper testing
3. **Worker 2 properly escalated a blocker** - validator issue documented
4. **Both committed work properly** - clean git history

### No Other Major Anti-Patterns

The workers actually performed well:
- Followed skill guidance
- Used beads for progress (in addition to workspace)
- Properly documented blockers
- Committed work with clear messages

The ONLY issue is double-tracking, which is caused by conflicting spawn prompt instructions.

---

## Recommendations

### Immediate Action

1. **Implement orch-cli-30j** - Remove legacy WORKSPACE.md instructions from spawn_prompt.py

### Code Changes Required

```python
# spawn_prompt.py changes needed:

# 1. In fallback_template() - remove WORKSPACE.md references
# 2. In build_spawn_prompt() when beads_id present:
#    - Skip workspace verification/update instructions
#    - Skip Phase field tracking for WORKSPACE.md
#    - Rely on bd comment for progress tracking

# 3. In BEADS PROGRESS section - remove this line:
#    "Note: Workspace still tracks detailed work state."
#    Replace with: "Beads comments are the source of truth for progress tracking."
```

### Verification

After fix:
1. Spawn a test agent with `--issue`
2. Verify SPAWN_CONTEXT.md does NOT have WORKSPACE.md instructions
3. Verify agent only uses `bd comment` for progress
4. Verify `orch status` reads from beads (not workspace)

---

## Conclusion

**Root Cause:** spawn_prompt.py explicitly instructs workers to use BOTH workspaces AND beads for lifecycle tracking. The BEADS PROGRESS section even says "Workspace still tracks detailed work state."

**Fix:** Implement orch-cli-30j to remove legacy workspace instructions when beads tracking is active.

**Principle Applied:** Session amnesia - workers follow instructions literally. If we want beads-only tracking, instructions must be beads-only.
