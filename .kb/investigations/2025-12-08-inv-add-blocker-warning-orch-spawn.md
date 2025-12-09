**TLDR:** Implemented blocker warning for `orch spawn --issue`. When spawning from a beads issue with open blocking dependencies, shows warning like "⚠️ This issue has 2 open blocker(s): ok-abc, ok-def". High confidence (95%) - feature implemented with TDD, all tests passing.

---

# Investigation: Add Blocker Warning to orch spawn --issue

**Question:** How to warn orchestrators when spawning from an issue that has unresolved blocking dependencies?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker agent (spawned from orch-cli-k90)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Findings

### Finding 1: Beads JSON includes dependencies with type and status

**Evidence:** Running `bd show orch-cli-5o2 --json` shows dependencies array with `dependency_type: "blocks"` and `status: "open"`.

**Source:** Direct CLI testing, `bd show` output

**Significance:** The beads CLI already exposes the data we need. We just need to parse it.

---

### Finding 2: Two dependency types exist - blocks and parent-child

**Evidence:** The `dependency_type` field can be either "blocks" (blocking relationship) or "parent-child" (epic/child relationship). Only "blocks" with status "open" should trigger warnings.

**Source:** `bd show orch-cli-k90 --json` (parent-child), `bd show orch-cli-5o2 --json` (blocks)

**Significance:** Need to filter for both `dependency_type == "blocks"` AND `status == "open"`.

---

## Implementation

### Changes Made

1. **BeadsDependency dataclass** (`beads_integration.py:27-34`)
   - Fields: id, title, status, dependency_type

2. **BeadsIssue dependencies field** (`beads_integration.py:47`)
   - Added `dependencies: Optional[list] = None`

3. **get_issue() parsing** (`beads_integration.py:114-126`)
   - Parses dependencies from bd show JSON output
   - Creates BeadsDependency objects for each dependency

4. **get_open_blockers() method** (`beads_integration.py:138-163`)
   - Filters dependencies for `dependency_type == "blocks"` and `status == "open"`
   - Returns list of BeadsDependency objects

5. **Warning in spawn_commands.py** (`spawn_commands.py:203-213`)
   - Checks for open blockers after fetching issue
   - Shows non-blocking warning if found
   - Silent failure on errors (don't block spawning)

### Tests Added

12 new tests covering:
- BeadsDependency dataclass creation
- BeadsIssue with dependencies field
- get_issue() parsing dependencies
- get_open_blockers() filtering logic

All 69 tests pass.

---

## References

**Files Modified:**
- `src/orch/beads_integration.py` - Added BeadsDependency, updated BeadsIssue, added get_open_blockers()
- `src/orch/spawn_commands.py` - Added blocker warning in spawn --issue
- `tests/test_beads_integration.py` - Added 12 tests

**Commit:** 6be2af6 feat(spawn): add blocker warning when spawning from beads issue

---

## Investigation History

**2025-12-08 18:36:** Investigation started
- Task: Add non-blocking warning when spawning from issue with open blockers

**2025-12-08 18:45:** Implementation complete
- TDD approach: tests written first, then implementation
- All tests passing
- Feature verified with real blocked issue (orch-cli-5o2)
