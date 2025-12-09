**TLDR:** Question: How to implement --auto-track flag for orch spawn? Answer: Add `create_issue` method to BeadsIntegration class, add --auto-track flag that creates beads issue from task title and continues with existing --issue flow. High confidence (90%) - follows established patterns.

---

# Investigation: Add --auto-track flag to orch spawn

**Question:** How should --auto-track flag be implemented to automatically create beads issues when spawning agents?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** worker
**Phase:** Complete
**Next Step:** None - implementation complete
**Status:** Complete
**Confidence:** High (100%)

---

## Findings

### Finding 1: create_beads_issue function already exists in complete.py

**Evidence:** Function at `src/orch/complete.py:1052-1102` creates beads issues via `bd create` CLI command. Returns issue ID from output.

**Source:** `src/orch/complete.py:1052-1102`

**Significance:** Can reuse this pattern for BeadsIntegration.create_issue() method rather than duplicating logic.

---

### Finding 2: --issue flag already handles full beads integration flow

**Evidence:** `spawn_commands.py:165-294` handles --issue mode:
1. Looks up beads issue
2. Extracts title for task description
3. Marks issue as in_progress
4. Passes beads_id to spawn_with_skill

**Source:** `src/orch/spawn_commands.py:165-294`

**Significance:** --auto-track can reuse this entire flow by creating the issue first, then continuing as if --issue was passed.

---

### Finding 3: bd create supports --title and --type flags

**Evidence:** `bd create --help` shows:
- `--title string` - Issue title (alternative to positional argument)
- `-t, --type string` - Issue type (bug|feature|task|epic|chore) (default "task")
- Returns "Created: <issue-id>" on success

**Source:** `bd create --help` output

**Significance:** Can create issues programmatically with the type defaulting to "task".

---

## Implementation Plan

### Recommended Approach ⭐

**Add create_issue to BeadsIntegration, handle --auto-track in spawn_commands.py**

**Implementation sequence:**
1. Add `create_issue()` method to BeadsIntegration class
2. Add `--auto-track` flag to spawn command
3. When --auto-track is set: create issue, then delegate to existing --issue flow

**Trade-offs accepted:**
- Slight code duplication with create_beads_issue in complete.py (can refactor later)
- --auto-track requires task argument (reasonable constraint)

---

## References

**Files Examined:**
- `src/orch/spawn_commands.py` - Spawn command implementation
- `src/orch/beads_integration.py` - BeadsIntegration class
- `src/orch/complete.py:1052-1102` - create_beads_issue function

**Commands Run:**
```bash
bd create --help
```
