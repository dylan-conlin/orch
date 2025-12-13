**TLDR:** Add focus.json integration to work daemon for issue prioritization. Daemon now reads ~/.orch/focus.json to prioritize spawning issues from specified projects, labels, or issue types first. High confidence (95%) - implemented with TDD, 38 tests passing.

---

# Investigation: Add Focus Integration to Work Daemon

**Question:** How should the work daemon prioritize issues based on ~/.orch/focus.json?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Focus configuration schema design

**Evidence:** Designed a simple JSON schema for ~/.orch/focus.json that supports three prioritization dimensions:
```json
{
  "priority_projects": ["orch-cli", "beads"],
  "priority_labels": ["P1", "urgent"],
  "priority_issue_types": ["bug"],
  "enabled": true
}
```

**Source:** src/orch/work_daemon.py:24-44 (FocusConfig dataclass)

**Significance:** Simple, extensible design that allows users to prioritize by project, label, or issue type. Gracefully handles missing file or invalid JSON.

---

### Finding 2: Prioritization algorithm uses cumulative scoring

**Evidence:** Issues are scored based on how many priority criteria they match:
- +1 point for matching a priority project
- +1 point for each matching priority label
- +1 point for matching a priority issue type

Issues with higher scores are spawned first. Uses stable sort to preserve relative order for equal scores.

**Source:** src/orch/work_daemon.py:98-128 (prioritize_issues function)

**Significance:** Simple cumulative scoring allows issues matching multiple criteria to bubble to the top while maintaining fairness.

---

### Finding 3: Integration into daemon cycle is minimal and safe

**Evidence:** Focus prioritization is applied after issue discovery but before spawning:
1. Get ready issues across all projects
2. Apply focus prioritization (if enabled)
3. Spawn agents up to concurrency limit

The `use_focus` flag defaults to True but can be disabled via `--no-focus` CLI flag.

**Source:** src/orch/work_daemon.py:330-336, daemon_commands.py (--no-focus flag)

**Significance:** Minimal change to existing daemon flow. Focus is purely a prioritization layer that doesn't affect filtering or other logic.

---

## Synthesis

**Key Insights:**

1. **Simple configuration is best** - The focus.json schema supports the three most useful prioritization dimensions without over-complicating.

2. **Graceful degradation** - Missing file, empty file, or invalid JSON all result in default behavior (no prioritization change).

3. **Easy to extend** - Adding new prioritization criteria (e.g., priority by age, by epic) would be straightforward.

**Answer to Investigation Question:**

The daemon should read ~/.orch/focus.json and prioritize issues using a cumulative scoring system. Issues matching more priority criteria are spawned first. The implementation adds a FocusConfig dataclass, load_focus_config() to parse the file, and prioritize_issues() to sort issues by focus score. This is integrated into run_daemon_cycle() with a use_focus flag that defaults to enabled.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Implemented using TDD with 38 passing tests covering all edge cases. The implementation is simple and follows existing patterns in the codebase.

**What's certain:**

- ✅ FocusConfig correctly loads from ~/.orch/focus.json
- ✅ Missing/invalid files gracefully return defaults
- ✅ Prioritization algorithm correctly scores and sorts issues
- ✅ Daemon cycle integrates focus without breaking existing behavior
- ✅ --no-focus flag works to disable prioritization

**What's uncertain:**

- ⚠️ No real-world testing with actual daemon running (only unit tests)

**What would increase confidence to Very High:**

- Manual testing with actual focus.json and multiple projects
- Integration testing in CI/CD

---

## Implementation Recommendations

**Implemented Approach:**

1. Added FocusConfig dataclass with priority_projects, priority_labels, priority_issue_types, enabled fields
2. Added get_focus_path() returning ~/.orch/focus.json
3. Added load_focus_config() with graceful fallback to defaults
4. Added prioritize_issues() with cumulative scoring
5. Integrated into run_daemon_cycle() with use_focus config option
6. Added --no-focus flag to daemon run and once commands
7. Added use_focus field to DaemonConfig (defaults to True)

---

## References

**Files Modified:**
- src/orch/work_daemon.py - Added FocusConfig, load_focus_config, prioritize_issues
- src/orch/daemon_commands.py - Added --no-focus flag to run and once commands

**Files Created:**
- tests/test_focus_integration.py - 21 tests for focus integration

**Tests Updated:**
- tests/test_work_daemon.py - Added use_focus assertions to DaemonConfig tests

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: How to integrate focus.json into work daemon?
- Context: Part of unified meta-orchestration daemon architecture

**2025-12-12:** Implementation complete
- TDD approach: Wrote failing tests first, then implemented
- 38 tests passing
- All daemon and focus integration tests pass
