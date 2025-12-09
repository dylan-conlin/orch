**TLDR:** Question: How to simplify complete.py, registry.py, and monitoring_commands.py? Answer: DONE. complete.py reduced 1245→254 lines (80%); registry.py reduced 626→298 lines (53%); monitoring_commands.py history --analytics delegates to beads. All core tests pass (34 tests).

---

# Investigation: Simplify Lifecycle Modules

**Question:** How to simplify complete.py → thin bd wrapper (~50 lines), registry.py → minimal tmux tracking, monitoring_commands.py → delegate to bd where possible?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker agent (orch-cli-nan)
**Phase:** Complete
**Next Step:** None - implementation complete
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: complete.py has 8 functions but only 2 are essential

**Evidence:** Based on prior investigation (2025-12-08-inv-investigate-when-orch-complete-removed.md):
1. **Verification** - checks deliverables (can simplify to Phase: Complete check)
2. **Beads Issue Closing** - `close_beads_issue()` - KEEP THIS
3. **Investigation Surfacing** - extracts recommendations (remove - move to skills)
4. **Git Validation** - commits exist (remove - trust agent)
5. **Git Stash Restoration** - (remove - rarely used)
6. **Cross-repo Workspace Sync** - (remove - complex, rarely used)
7. **Tmux Window Cleanup** - `clean_up_agent()` - KEEP THIS
8. **Registry Updates** - (simplify with registry)

**Source:** `src/orch/complete.py:1-1245`

**Significance:** From 1245 lines to ~50 lines by keeping only: `close_beads_issue()`, `BeadsPhaseNotCompleteError`, `clean_up_agent()`, simplified `complete_agent_work()`.

---

### Finding 2: registry.py serves 3 purposes, only 1 is essential

**Evidence:** Based on prior investigation (2025-12-06-agent-registry-removal-remove-registry.md):
1. **Agent lookup during session** - hot path for commands - KEEP (simplified)
2. **Tmux reconciliation** - reconcile with window state - KEEP (minimal)
3. **History/analytics** - `get_history()`, `get_analytics()` - REMOVE (beads handles)

Current fields stored: 15+ fields. Minimal needed: id, window_id, project_dir, beads_id, status

**Source:** `src/orch/registry.py:1-626`

**Significance:** From 626 lines to ~200 lines by removing: history/analytics, complex merge logic, tombstone pattern, OpenCode reconciliation.

---

### Finding 3: monitoring_commands.py mostly needs tmux access

**Evidence:** Commands breakdown:
- `status` - needs registry + tmux - keep (already uses `bd show` for titles)
- `check` - has `--issue` flag that delegates to beads - keep
- `tail`, `send`, `question`, `resume` - need tmux window access - keep
- `wait` - needs phase checking - can use beads phase
- `history --analytics` - calls registry analytics - simplify (delegate to beads)
- `logs` - orch logging - keep

**Source:** `src/orch/monitoring_commands.py:1-1368`

**Significance:** Most commands stay as-is. Simplification opportunities: `history --analytics` can delegate to `bd stats`, phase checking can use beads comments.

---

## Synthesis

**Key Insights:**

1. **complete.py is 95% overhead** - Investigation surfacing, discovery capture, async daemons are rarely used. Core is just: verify Phase: Complete, close beads issue, kill tmux window.

2. **registry.py can be transient-only** - Beads is source of truth for agent state. Registry only needs: agent_id ↔ window_id mapping for tmux operations.

3. **monitoring_commands.py is already well-structured** - Most complexity comes from formatting and filtering, not redundant logic. Keep as-is except for history analytics.

**Answer to Investigation Question:**

Simplification path:
1. **complete.py** → 50 lines: Keep only `close_beads_issue()`, `BeadsPhaseNotCompleteError`, `clean_up_agent()`, thin `complete_agent_work()`
2. **registry.py** → 200 lines: Keep minimal agent tracking (id, window_id, project_dir, beads_id, status), remove history/analytics/complex merge
3. **monitoring_commands.py** → minimal changes: Remove `history --analytics`, keep rest as-is

---

## Implementation Plan

### Phase 1: Simplify complete.py (TDD)
1. Write test for thin complete_agent_work
2. Reduce to essential functions only
3. Update cli.py imports

### Phase 2: Simplify registry.py (TDD)
1. Write tests for minimal registry
2. Remove history/analytics/complex merge
3. Keep file locking for safety

### Phase 3: Simplify monitoring_commands.py
1. Remove history --analytics or delegate to bd stats
2. Verify other commands work with simplified registry

---

## References

**Files Examined:**
- `src/orch/complete.py` - 1245 lines, target ~50
- `src/orch/registry.py` - 626 lines, target ~200
- `src/orch/monitoring_commands.py` - 1368 lines, minimal changes
- `src/orch/cli.py` - imports from complete.py

**Related Investigations:**
- `.kb/investigations/2025-12-06-agent-registry-removal-remove-registry.md`
- `.kb/investigations/2025-12-08-inv-investigate-when-orch-complete-removed.md`

---

## Investigation History

**2025-12-08 22:30:** Investigation started
- Initial question: How to simplify lifecycle modules per orch-cli-nan
- Context: Part of orch-cli simplification epic

**2025-12-08 22:45:** Planning complete
- Identified clear reduction targets for each module
- Moving to implementation phase

**2025-12-08 23:30:** Implementation complete
- complete.py: 1245 → 254 lines (80% reduction)
- registry.py: 626 → 298 lines (53% reduction)
- monitoring_commands.py: history --analytics now delegates to beads
- Removed: async completion, discovery capture, investigation surfacing, cross-repo sync
- Removed: get_history(), get_analytics(), reconcile_opencode(), complex artifact checking
- All 34 core tests pass
- Removed 7 test files for removed functionality
