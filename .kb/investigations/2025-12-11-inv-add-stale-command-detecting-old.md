**TLDR:** Question: How to add stale issue detection to orch-cli? Answer: Added `get_stale_issues` wrapper to BeadsIntegration (wraps `bd stale`) and `orch stale` CLI command with orchestrator-focused defaults (14 days vs bd's 30 days). Implementation complete with TDD. High confidence.

---

# Investigation: Add bd stale command for detecting old issues

**Question:** How to add stale issue detection to orch-cli for identifying forgotten/abandoned work?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** worker
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (95%)

---

## Findings

### Finding 1: bd stale command already exists

**Evidence:** `bd stale --help` shows the command exists with flags:
- `--days` (default 30)
- `--status` filter (open|in_progress|blocked)
- `--limit` (default 50)
- `--json` output mode

**Source:** `/Users/dylanconlin/Documents/personal/beads/cmd/bd/stale.go`

**Significance:** No need to implement the core stale logic - just wrap existing bd command

---

### Finding 2: BeadsIntegration lacks stale method

**Evidence:** `beads_integration.py` has methods for `get_issue`, `list_active_agents`, `close_issue`, etc., but no `get_stale_issues` method.

**Source:** `src/orch/beads_integration.py`

**Significance:** Need to add wrapper method following existing patterns in the file

---

### Finding 3: Task specifies 14-day default (differs from bd's 30)

**Evidence:** SPAWN_CONTEXT notes: "Detect issues open longer than N days (default 14?)"

**Source:** SPAWN_CONTEXT.md

**Significance:** orch-cli should use different default (14 days) than bd CLI (30 days) to catch issues earlier for orchestrator backlog review

---

## Implementation Complete

### Files Changed:
1. `src/orch/beads_integration.py` - Added `get_stale_issues(days=14, status=None, limit=50)`
2. `src/orch/monitoring_commands.py` - Added `orch stale` CLI command
3. `tests/test_beads_integration.py` - 8 tests for get_stale_issues
4. `tests/test_cli.py` - 6 tests for orch stale command

### Commits:
1. `ecf1cb8` - feat(beads): add get_stale_issues method to BeadsIntegration
2. `4c4ce05` - feat(cli): add orch stale command for detecting old beads issues

### Usage:
```bash
orch stale                          # Issues not updated in 14 days
orch stale --days 7                 # Issues not updated in 7 days
orch stale --status in_progress     # Only in-progress issues
orch stale --json                   # Output as JSON
```

---

## References

**Files Examined:**
- `/Users/dylanconlin/Documents/personal/beads/cmd/bd/stale.go` - bd stale implementation
- `src/orch/beads_integration.py` - BeadsIntegration class patterns
- `src/orch/cli.py` - CLI command patterns
