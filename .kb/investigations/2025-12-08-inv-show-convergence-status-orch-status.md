**TLDR:** How to show convergence status in orch status for parent issues? Added `dependents` field to BeadsIssue and convergence display showing "[X/Y children complete]". High confidence (95%) - TDD implementation with comprehensive tests.

---

# Investigation: Show Convergence Status in orch status

**Question:** How to show convergence status in orch status for agents spawned from parent issues?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: BeadsIssue needed `dependents` field

**Evidence:** The `bd show --json` output includes a `dependents` array for parent issues:
```json
{
  "id": "orch-cli-y59",
  "dependents": [
    {"id": "abc", "title": "C1", "status": "closed", "dependency_type": "parent-child"},
    ...
  ]
}
```

**Source:** `bd show orch-cli-y59 --json`, `src/orch/beads_integration.py:38-50`

**Significance:** Added `dependents: Optional[list] = None` field to BeadsIssue dataclass to store child issues.

---

### Finding 2: get_issue() needed to parse dependents

**Evidence:** The existing `get_issue()` method already parsed `dependencies` (blockers), but didn't parse `dependents` (children).

**Source:** `src/orch/beads_integration.py:82-159`

**Significance:** Added parsing logic for `dependents` array, creating BeadsDependency objects for each child.

---

### Finding 3: Convergence calculation logic

**Evidence:** Child convergence stats needed: total, closed, in_progress, open counts.

**Source:** `src/orch/beads_integration.py:188-223`

**Significance:** Added `get_child_convergence()` method that returns stats dict or None if no children.

---

## Synthesis

**Key Insights:**

1. **Data model extension** - BeadsIssue.dependents parallels BeadsIssue.dependencies for tracking children vs blockers.

2. **Convergence display format** - `[X/Y children complete]` format shows closed/total, easy to scan.

3. **Minimal code changes** - Convergence display integrates naturally with existing title_suffix pattern in orch status.

**Answer to Investigation Question:**

Added convergence display to orch status by:
1. Adding `dependents` field to BeadsIssue dataclass
2. Parsing `dependents` from bd show --json in get_issue()
3. Adding get_child_convergence() method for stats
4. Adding convergence display in monitoring_commands.py using existing title_suffix pattern

---

## Implementation Summary

**Files Modified:**

1. `src/orch/beads_integration.py`:
   - Added `dependents` field to BeadsIssue (line 50)
   - Added dependents parsing in get_issue() (lines 134-146)
   - Added get_child_convergence() method (lines 188-223)

2. `src/orch/monitoring_commands.py`:
   - Added _get_issue_convergence() helper (lines 57-77)
   - Added _format_convergence() helper (lines 80-93)
   - Added issue_convergence cache alongside issue_titles
   - Updated title_suffix to include convergence info

3. `tests/test_beads_integration.py`:
   - Added TestBeadsIssueWithDependents tests
   - Added TestBeadsIntegrationGetIssueWithDependents tests
   - Added TestBeadsIntegrationGetChildConvergence tests

4. `tests/test_status.py`:
   - Added TestConvergenceDisplay tests

**Test Results:** All 98 related tests pass.

---

## References

**Files Examined:**
- `src/orch/beads_integration.py` - Core beads integration module
- `src/orch/monitoring_commands.py` - Status command implementation
- `tests/test_beads_integration.py` - Beads integration tests
- `tests/test_status.py` - Status command tests

**Commands Run:**
```bash
# Check parent issue structure
bd show orch-cli-y59 --json

# Verify convergence calculation
python -c "from orch.beads_integration import BeadsIntegration; print(BeadsIntegration().get_child_convergence('orch-cli-y59'))"
# Output: {'total': 8, 'closed': 6, 'in_progress': 2, 'open': 0}

# Verify format
python -c "from orch.monitoring_commands import _format_convergence; print(_format_convergence({'total': 8, 'closed': 6}))"
# Output:  [6/8 children complete]
```

---

## Investigation History

**2025-12-08 21:14:** Investigation started
- Initial question: How to show convergence status for parent issues in orch status?
- Context: Orchestrators need visibility into multi-issue initiative progress

**2025-12-08 21:20:** TDD implementation completed
- Added dependents field to BeadsIssue
- Added get_child_convergence() method
- Added convergence display in status output
- All tests pass
