**TLDR:** Question: How to make orch CLI AI-first by removing interactive prompts? Answer: Added TTY detection to all `click.confirm` calls - when stdin is not a TTY (programmatic use), confirmations are auto-skipped. High confidence (95%) - pattern already existed in spawn.py, applied consistently to 5 confirmation points.

---

# Investigation: Remove Interactive Prompts from orch CLI

**Question:** How do we make orch CLI AI-first by eliminating interactive prompts that block agent execution?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Existing TTY Detection Pattern in spawn.py

**Evidence:** spawn.py already implemented TTY detection at line 910:
```python
is_interactive = sys.stdin.isatty()
if not yes:
    if not is_interactive:
        yes = True
    elif os.getenv('ORCH_AUTO_CONFIRM') == '1':
        yes = True
```

**Source:** `src/orch/spawn.py:905-917`

**Significance:** Pattern was already established for AI-first behavior. Needed to apply consistently to other commands.

---

### Finding 2: Five Confirmation Points Identified

**Evidence:** Found all interactive prompts via grep:
1. `cli.py:400-402` - abandon command
2. `init.py:240` - create_project_claude_md
3. `init.py:506` - init_project reinitialize
4. `init.py:538` - init_project continue
5. `work_commands.py:217` - start_work
6. `spawn_commands.py:259` - spawn with prior commits

**Source:** `grep -n "click\.confirm" src/orch/*.py`

**Significance:** Comprehensive list of all blocking prompts that needed TTY detection.

---

### Finding 3: Missing sys Import in spawn_commands.py

**Evidence:** `sys.stdin.isatty()` was used at line 156 but `sys` wasn't explicitly imported at module level.

**Source:** `src/orch/spawn_commands.py:1-17`

**Significance:** Bug waiting to happen. Fixed by adding explicit `import sys`.

---

## Synthesis

**Key Insights:**

1. **AI-first design principle** - When stdin is not a TTY, assume programmatic/agent use and auto-confirm operations.

2. **Consistent pattern** - All confirmation points now follow the same logic: `should_skip = yes or not sys.stdin.isatty() or os.getenv('ORCH_AUTO_CONFIRM') == '1'`

3. **Backward compatible** - Interactive users with TTY still get confirmation prompts. Only non-TTY calls are auto-confirmed.

**Answer to Investigation Question:**

Added TTY detection (`sys.stdin.isatty()`) to all `click.confirm` calls. When stdin is not a TTY (indicating programmatic use by AI agents), confirmations are automatically skipped. This matches the existing pattern in spawn.py and maintains backward compatibility for interactive human users.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Existing pattern in spawn.py validates approach. Applied consistently to all confirmation points. Tests updated and passing.

**What's certain:**

- Pattern was already established and working in spawn.py
- All confirmation points identified and fixed
- Tests verify both interactive (TTY) and non-interactive (no TTY) behavior

**What's uncertain:**

- Edge cases with environment variable `ORCH_AUTO_CONFIRM` may need documentation

---

## Implementation Summary

**Files Modified:**

1. `src/orch/cli.py` - abandon command (line 400-407)
2. `src/orch/init.py` - two confirmations (lines 240-244, 506-511, 530-546)
3. `src/orch/work_commands.py` - added `import sys`, confirmation (lines 10, 216-222)
4. `src/orch/spawn_commands.py` - added `import sys`, confirmation (lines 8, 245-263)

**Tests Updated:**

1. `tests/test_abandon.py` - Added TTY mocking, new test for non-TTY auto-confirm
2. `tests/test_init.py` - Added TTY mocking for reinitialize test
3. `tests/test_spawn_commit_check.py` - Updated to verify non-TTY auto-confirm behavior

---

## References

**Files Examined:**
- `src/orch/spawn.py:905-917` - Reference implementation of TTY detection
- `src/orch/cli.py` - abandon command
- `src/orch/init.py` - init commands
- `src/orch/work_commands.py` - work command
- `src/orch/spawn_commands.py` - spawn command

**Commands Run:**
```bash
# Find all interactive prompts
grep -n "click\.confirm\|input()\|[y/N]" src/orch/*.py

# Run affected tests
pytest tests/test_abandon.py tests/test_init.py tests/test_spawn_commit_check.py -v
```

---

## Investigation History

**2025-12-09 12:17:** Investigation started
- Initial question: Remove interactive prompts blocking AI agent execution
- Context: `orch abandon` hanging for 1+ minute waiting for confirmation

**2025-12-09 12:25:** Pattern identified in spawn.py

**2025-12-09 12:30:** All fixes implemented and tests updated

**2025-12-09 12:35:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: All interactive prompts now auto-skip when stdin is not a TTY
