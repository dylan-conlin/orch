**TLDR:** Implement `--issues` flag for spawning agents to work on multiple beads issues. Changes needed in spawn_commands.py, spawn.py, registry.py, and complete.py. High confidence - straightforward extension of existing single-issue pattern.

---

# Investigation: Support --issues flag for multi-issue spawns

**Question:** How to implement multi-issue spawning where one agent works on multiple beads issues?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (95%)

---

## Findings

### Finding 1: Current single-issue implementation pattern

**Evidence:**
- `spawn_commands.py:87` - `--issue` option takes single ID
- `spawn_commands.py:292` - calls `beads.update_issue_status(issue_id, "in_progress")`
- `spawn.py:1298-1299` - `beads_id` and `beads_db_path` passed to spawn
- `registry.py:194-195` - stores single `beads_id` and `beads_db_path`
- `complete.py:279-296` - closes single beads issue via `agent.get('beads_id')`

**Source:**
- `src/orch/spawn_commands.py:87, 292`
- `src/orch/spawn.py:1298-1299`
- `src/orch/registry.py:194-195`
- `src/orch/complete.py:279-296`

**Significance:** Pattern is well-established. Extension to multiple IDs follows same structure.

---

### Finding 2: BeadsIntegration has all needed methods

**Evidence:**
- `update_issue_status()` - can call for each issue
- `close_issue()` - can call for each issue
- `get_issue()` - can validate each issue exists

**Source:** `src/orch/beads_integration.py:262-310`

**Significance:** No changes needed to BeadsIntegration - just call existing methods in a loop.

---

## Implementation Plan

### Changes Required

1. **spawn_commands.py** - Add `--issues` option (comma-separated list)
   - Validate all issues exist and aren't closed
   - Update all to `in_progress` on spawn
   - Pass list to spawn functions
   - Mutual exclusion with `--issue` (single)

2. **spawn.py (SpawnConfig)** - Support list field
   - Add `beads_ids: Optional[List[str]]` alongside `beads_id`
   - Pass to registry registration

3. **registry.py** - Store list of beads IDs
   - Add `beads_ids` field
   - Backward compatible with single `beads_id`

4. **complete.py** - Close all linked issues
   - Check for `beads_ids` (list) or `beads_id` (single)
   - Loop to close all issues

---

## References

**Files Examined:**
- `src/orch/spawn_commands.py` - spawn command entry point
- `src/orch/spawn.py` - SpawnConfig and spawn logic
- `src/orch/registry.py` - agent registration
- `src/orch/complete.py` - completion logic
- `src/orch/beads_integration.py` - beads CLI wrapper

---

## Investigation History

**2025-12-09 16:45:** Investigation started
- Initial question: How to support --issues flag for multi-issue spawns
- Context: Post-mortem 2025-12-09 - spawned for 3 issues, none marked in_progress

**2025-12-09 16:50:** Analysis complete, starting implementation
- All integration points identified
- Extension is straightforward
