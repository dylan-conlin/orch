**TLDR:** Question: Why does orch check/complete flag missing WORKSPACE.md as critical for beads-tracked agents? Answer: patterns.py unconditionally flags missing WORKSPACE.md as critical, but verification.py already knows WORKSPACE.md is optional when beads tracks lifecycle. High confidence (90%) - clear code evidence but untested fix.

---

# Investigation: orch check false positive for missing WORKSPACE.md

**Question:** Why does `orch check` and `orch complete` flag missing WORKSPACE.md as critical when beads now tracks agent lifecycle?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Claude (systematic-debugging agent)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: patterns.py unconditionally flags missing WORKSPACE.md as critical

**Evidence:**
```python
# src/orch/patterns.py:40-48
# Check 2: WORKSPACE.md exists
workspace_file = full_workspace_path / 'WORKSPACE.md'
if not workspace_file.exists():
    violations.append(PatternViolation(
        type='missing_workspace_file',
        severity='critical',
        message='WORKSPACE.md file missing'
    ))
    return violations
```

The code checks if WORKSPACE.md exists and flags it as a critical violation if missing, with no consideration for whether beads is tracking the agent.

**Source:** src/orch/patterns.py:40-48

**Significance:** This is the root cause of the false positive. For agents tracked by beads (those with a beads_id), WORKSPACE.md is optional since beads comments provide phase information.

---

### Finding 2: verification.py already handles beads-tracked agents correctly

**Evidence:**
```python
# src/orch/verification.py:209-215
# WORKSPACE.md not required when beads is source of truth
# Beads phase verification happens separately in close_beads_issue()
if agent_info and agent_info.get('beads_id'):
    logger.log_event("verify", "Workspace missing - using beads as source of truth", {
        "workspace": str(workspace_path),
        "beads_id": agent_info.get('beads_id')
    }, level="INFO")
```

The verification module already recognizes that WORKSPACE.md is not required when beads is the source of truth (i.e., when agent has beads_id).

**Source:** src/orch/verification.py:209-215

**Significance:** The correct behavior already exists in one part of the codebase. This provides a clear pattern to follow for fixing patterns.py.

---

### Finding 3: Phase detection hierarchy prefers beads over WORKSPACE.md

**Evidence:**
```python
# src/orch/monitor.py:127-160
# Phase 3: Prefer beads-based phase detection when agent has beads_id
beads_id = agent_info.get('beads_id')
beads_phase = None
if beads_id:
    try:
        beads = BeadsIntegration()
        beads_phase = beads.get_phase_from_comments(beads_id)
    except (BeadsCLINotFoundError, BeadsIssueNotFoundError):
        pass  # Fallback to workspace-based detection

# ...
# Determine phase: beads > workspace > fallback
if beads_phase:
    status.phase = beads_phase
elif signal.phase:
    status.phase = signal.phase
```

The monitoring code already implements a hierarchy where beads phase takes priority over WORKSPACE.md phase.

**Source:** src/orch/monitor.py:127-160

**Significance:** The system design already treats beads as the authoritative source for lifecycle tracking when available. The pattern validation is out of sync with this design.

---

## Synthesis

**Key Insights:**

1. **Inconsistent beads awareness across modules** - verification.py and monitor.py correctly handle agents with beads_id, but patterns.py does not check for beads_id before flagging missing WORKSPACE.md as critical.

2. **System design treats beads as authoritative** - The phase detection hierarchy (Finding 3) and verification logic (Finding 2) both recognize beads as the source of truth when available. Pattern validation should align with this design.

3. **Simple fix with clear precedent** - The verification.py code at lines 209-215 provides the exact pattern needed: check if agent has beads_id, and if so, skip WORKSPACE.md validation.

**Answer to Investigation Question:**

`orch check` flags missing WORKSPACE.md as critical because `validate_workspace_patterns()` in src/orch/patterns.py:40-48 unconditionally checks for WORKSPACE.md existence without considering whether the agent has a beads_id. This is inconsistent with verification.py and monitor.py, which both correctly recognize that beads-tracked agents don't require WORKSPACE.md. The fix is to add a beads_id check in patterns.py before flagging the missing file violation.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

The root cause is clearly identified with direct code evidence from three modules (patterns.py, verification.py, monitor.py). The fix pattern already exists in verification.py, making this a straightforward alignment issue rather than a novel solution. Confidence is not Very High because the fix hasn't been tested yet.

**What's certain:**

- ✅ patterns.py:40-48 unconditionally flags missing WORKSPACE.md as critical (direct code evidence)
- ✅ verification.py:209-215 already implements the correct behavior for beads-tracked agents (direct code evidence)
- ✅ monitor.py:127-160 treats beads as authoritative source for phase detection (direct code evidence)
- ✅ The system design intends beads to be the source of truth for lifecycle tracking (consistent pattern across modules)

**What's uncertain:**

- ⚠️ Whether there are edge cases where WORKSPACE.md is required even with beads_id
- ⚠️ Whether validate_workspace_patterns has access to agent_info (may need signature change)
- ⚠️ Impact on existing agents - need to verify fix doesn't break non-beads agents

**What would increase confidence to Very High (95%+):**

- Write test case reproducing the false positive
- Implement the fix and verify tests pass
- Validate that non-beads agents still correctly require WORKSPACE.md

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**Skip workspace pattern checks for beads-tracked agents** - Modify the skip_workspace_checks condition in monitor.py:266 to also skip when agent has beads_id.

**Why this approach:**
- Minimal code change - single line modification
- Leverages existing skip pattern (already used for primary_artifact)
- Aligns with existing system design (beads as authoritative source)
- No changes to check_patterns signature needed

**Trade-offs accepted:**
- Doesn't fix patterns.py directly - leaves the unconditional check in place
- If check_patterns is called from other locations, they won't benefit from this fix

**Implementation sequence:**
1. Modify monitor.py:266 to skip workspace checks when beads_id present
2. Write test case to verify beads-tracked agents don't get false positive
3. Verify non-beads agents still get violations when WORKSPACE.md missing

### Alternative Approaches Considered

**Option B: Modify check_patterns to accept agent_info parameter**
- **Pros:** Fixes the root cause in patterns.py directly, benefits all call sites
- **Cons:** Requires signature change, more invasive, need to update all call sites
- **When to use instead:** If there are multiple call sites that would benefit

**Option C: Create separate check_patterns_with_beads function**
- **Pros:** No signature changes, backward compatible
- **Cons:** Code duplication, maintenance burden
- **When to use instead:** If there's concern about breaking existing callers

**Rationale for recommendation:** Option A is simplest and aligns with existing patterns in the codebase. The skip_workspace_checks pattern at line 266 is already established for primary_artifact, so extending it to beads_id is the path of least resistance.

---

### Implementation Details

**What to implement first:**
- Modify src/orch/monitor.py:266 from:
  ```python
  skip_workspace_checks = primary_artifact_path is not None
  ```
  to:
  ```python
  skip_workspace_checks = primary_artifact_path is not None or agent_info.get('beads_id')
  ```

**Things to watch out for:**
- ⚠️ Ensure beads_id check doesn't break if beads_id is missing (use .get() with falsy check)
- ⚠️ Test both beads-tracked and non-beads agents to avoid regression
- ⚠️ Consider whether other call sites to check_patterns exist (grep showed only one call site)

**Areas needing further investigation:**
- Are there other locations that call check_patterns beyond monitor.py:267?
- Should patterns.py eventually be refactored to accept agent_info for future extensibility?
- Are there edge cases where beads-tracked agents SHOULD have WORKSPACE.md?

**Success criteria:**
- ✅ Beads-tracked agents without WORKSPACE.md no longer flagged with critical violation
- ✅ Non-beads agents without WORKSPACE.md still correctly flagged
- ✅ Existing tests pass (verify no regression in pattern validation)
- ✅ New test case added: agent with beads_id but no WORKSPACE.md passes validation

---

## References

**Files Examined:**
- src/orch/patterns.py:40-48 - Root cause: unconditional WORKSPACE.md validation
- src/orch/verification.py:209-215 - Existing pattern for handling beads-tracked agents
- src/orch/monitor.py:127-160 - Phase detection hierarchy (beads > workspace)
- src/orch/monitor.py:266-267 - Call site for check_patterns with skip logic

**Commands Run:**
```bash
# Find beads issue ID
bd list --status=in_progress | grep -i "orch check\|workspace\|false positive"

# Search for WORKSPACE.md validation logic
rg "WORKSPACE\.md" src/orch/complete.py -C 5

# Find check_patterns call sites
rg "check_patterns\(" src/orch/ -C 5

# Search for pattern validation
rg "missing.*workspace|workspace.*missing|critical.*workspace" src/orch/ -i -C 3
```

**Related Artifacts:**
- **Beads issue:** orch-cli-b3w - "orch complete fails for ad-hoc spawns without WORKSPACE.md"

---

## Investigation History

**2025-12-06 (Session Start):** Investigation started
- Initial question: Why does orch check flag missing WORKSPACE.md as critical for beads-tracked agents?
- Context: Beads issue orch-cli-b3w reported that orch complete fails for ad-hoc spawns without WORKSPACE.md
- Spawned as systematic-debugging agent

**2025-12-06 (Finding 1):** Located root cause in patterns.py
- Found unconditional WORKSPACE.md validation at lines 40-48
- No check for beads_id before flagging violation

**2025-12-06 (Finding 2):** Discovered existing correct pattern in verification.py
- Lines 209-215 already implement correct behavior for beads-tracked agents
- Provides template for fix

**2025-12-06 (Finding 3):** Confirmed system design treats beads as authoritative
- monitor.py phase detection hierarchy: beads > workspace > fallback
- Consistent pattern across modules except patterns.py

**2025-12-06 (Investigation Complete):**
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Root cause identified with clear fix path (modify skip_workspace_checks in monitor.py:266)
