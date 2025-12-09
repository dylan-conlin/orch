**TLDR:** Changed `orch work` without args from interactive picker to list-and-exit mode. High confidence (95%) - all 13 tests pass, behavior now matches AI-first design pattern like `bd ready`.

---

# Implementation: orch work without args shows list instead of interactive mode

**Question:** How should `orch work` without arguments behave?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Summary

Changed `orch work` (without arguments) from interactive picker mode to list-and-exit mode to align with orch's AI-first design.

**Before:** Prompted user to select from numbered list
**After:** Shows ready issues with inferred skills and suggested commands, then exits

---

## Changes Made

### 1. Removed Interactive Picker

**File:** `src/orch/work_commands.py:119-143`

**Evidence:** Removed `click.prompt()` call that waited for user input. Now just displays list and returns.

**Significance:** Aligns with AI-first design - orchestrator reads output and decides which issue to work on (similar to `bd ready`).

---

### 2. Added Suggested Commands

**Evidence:** Each issue now shows the command to work on it:
```
[feature] orch-cli-abc: Task 1
   Skill: feature-impl
   → orch work orch-cli-abc
```

**Significance:** Makes it easy for AI orchestrator to select and spawn.

---

### 3. Updated Tests

**File:** `tests/test_work_command.py`

**Evidence:**
- Renamed `TestWorkCommandInteractive` to `TestWorkCommandNoArgs`
- Rewrote tests to verify list-and-exit behavior (no input required)
- Added test for suggested command format
- All 13 work command tests pass

---

## Deliverables

- ✅ Implementation: `src/orch/work_commands.py`
- ✅ Tests: `tests/test_work_command.py` (13 tests passing)
- ✅ Commits: 2 commits (failing test, then implementation)

---

## References

**Files Modified:**
- `src/orch/work_commands.py:84-143` - Command implementation and docstring
- `tests/test_work_command.py:163-206` - Test class renamed and rewritten

**Commands Run:**
```bash
# Verify tests fail (RED)
python -m pytest tests/test_work_command.py::TestWorkCommandNoArgs -v

# Verify tests pass (GREEN)
python -m pytest tests/test_work_command.py -v
```
