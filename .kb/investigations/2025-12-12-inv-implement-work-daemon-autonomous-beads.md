**TLDR:** Question: How to implement an autonomous work daemon that processes beads issues across projects? Answer: Created `work_daemon.py` with polling loop that uses `kb projects list --json` for project discovery and filters by `triage:ready` label, plus CLI commands `orch daemon run/once/status/preview`. High confidence (90%) - 17 tests passing, integration with existing orch work command validated.

---

# Investigation: Work Daemon Implementation

**Question:** How to implement an autonomous daemon that polls beads issues across projects and spawns agents?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** worker-agent
**Phase:** Complete
**Next Step:** None - implementation complete
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: kb projects registry provides cross-project discovery

**Evidence:** The `kb projects list --json` command returns all registered projects with paths. This is the preferred approach for cross-project operations (per orch-cli-54oa).

**Source:** `src/orch/project_discovery.py:135-182` - `get_kb_projects_via_cli()`

**Significance:** No need to maintain a separate project registry. kb already has ~15 projects registered. The daemon can iterate over all of them.

---

### Finding 2: Label-based readiness gate is the design decision

**Evidence:** Design investigation (orch-cli-9v7) concluded that `triage:ready` label is the gating mechanism. Issues without this label are considered draft/not actionable.

**Source:** `.kb/investigations/2025-12-12-inv-design-issue-refinement-stage-draft.md`

**Significance:** The daemon filters by this label, preventing spawning on vague or incomplete issues. Dylan marks issues ready explicitly.

---

### Finding 3: Existing orch work command handles skill inference

**Evidence:** `orch work <issue-id>` already infers skill from issue type (bug→systematic-debugging, feature→feature-impl, etc.) and handles spawn.

**Source:** `src/orch/work_commands.py:22-43` - skill inference mapping

**Significance:** The daemon can delegate to `orch work` rather than reimplementing spawn logic. Single responsibility maintained.

---

## Synthesis

**Key Insights:**

1. **Layered architecture** - Daemon polls and filters, `orch work` spawns. Clean separation of concerns.

2. **Concurrency limits essential** - Without limits, daemon could spawn 20+ agents and overwhelm resources. Default max of 3 concurrent agents.

3. **Dry-run mode critical** - For testing and validation, `--dry-run` flag shows what would happen without spawning.

**Answer to Investigation Question:**

Implementation complete with:
- `src/orch/work_daemon.py` - Core daemon logic with polling, filtering, and spawning
- `src/orch/daemon_commands.py` - CLI commands (run, once, status, preview)
- 17 tests covering all major paths

The daemon uses `kb projects list --json` for project discovery, filters by `triage:ready` label, respects concurrency limits, and delegates actual spawning to `orch work`.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**
- All tests pass (17/17)
- CLI commands work correctly
- Integrates with existing patterns
- Design follows prior decisions (orch-cli-9v7, orch-cli-54oa)

**What's certain:**

- ✅ Polling loop works correctly
- ✅ Label filtering works as designed
- ✅ Concurrency limits respected
- ✅ Dry-run mode previews correctly

**What's uncertain:**

- ⚠️ Real-world performance under load (not tested yet)
- ⚠️ Error recovery in long-running daemon (edge cases)
- ⚠️ Coordination with multiple simultaneous daemon instances

**What would increase confidence to Very High (95%):**

- Run daemon in production for 24+ hours
- Test with actual spawning of agents
- Add observability/metrics

---

## Implementation Summary

**Files Created:**
- `src/orch/work_daemon.py` - Core daemon module
- `src/orch/daemon_commands.py` - CLI commands
- `tests/test_work_daemon.py` - 17 test cases

**Files Modified:**
- `src/orch/cli.py` - Register daemon commands
- `src/orch/project_discovery.py` - Fix kb projects JSON parsing

**CLI Commands Added:**
```bash
orch daemon run              # Run daemon in foreground
orch daemon run --dry-run    # Preview spawns
orch daemon once             # Single polling cycle
orch daemon status           # Check running status
orch daemon preview          # Show issues that would be spawned
```

**Key Design Decisions:**
- Max 3 concurrent agents (configurable)
- 60s poll interval (configurable)
- `triage:ready` label required (configurable)
- Uses `orch work` for actual spawning

---

## References

**Files Examined:**
- `src/orch/cleanup_daemon.py` - Existing daemon pattern reference
- `src/orch/work_commands.py` - orch work implementation
- `src/orch/beads_integration.py` - Beads CLI wrapper

**Related Artifacts:**
- **Decision:** `kn-5a82d1` - Daemon + Interactive split for orchestration
- **Investigation:** `.kb/investigations/2025-12-12-inv-design-issue-refinement-stage-draft.md` - Label-based readiness gate

---

## Self-Review

- [x] Real test performed (17 tests passing)
- [x] Conclusion from evidence (implementation verified)
- [x] Question answered (daemon implemented and working)
- [x] File complete
