**TLDR:** Question: How to make orch status show only active agents by default while allowing completed agents via flag? Answer: Added `--include-completed` flag; by default `orch status` now shows only active agents. High confidence (95%) - all 30 status tests pass, behavior verified manually.

---

# Investigation: orch status default to active-only

**Question:** How to modify `orch status` to show only active agents by default, with `--include-completed` flag to include completed agents?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Completed agents fetched unconditionally

**Evidence:** In `monitoring_commands.py:250`, completed agents were always fetched regardless of user intent:
```python
completed_agents = [a for a in registry.list_agents() if a.get('status') == 'completed']
```

**Source:** `src/orch/monitoring_commands.py:250`

**Significance:** This was the root cause of always showing completed agents. Needed conditional fetching.

---

### Finding 2: JSON output only included active agents

**Evidence:** The JSON output section (lines 345-390) only iterated over `agent_statuses` (active agents), not `completed_statuses`. This was inconsistent with human output.

**Source:** `src/orch/monitoring_commands.py:345-390`

**Significance:** Required update to include completed agents in JSON output when flag is set.

---

### Finding 3: Existing test patterns well-established

**Evidence:** Found comprehensive tests in `tests/test_status_filtering.py` and `tests/test_status.py` demonstrating mocking patterns for registry, logger, and status checking.

**Source:** `tests/test_status_filtering.py`, `tests/test_status.py`

**Significance:** Enabled TDD approach with confidence tests would properly validate behavior.

---

## Implementation Summary

### Changes Made

1. **Added `--include-completed` flag** (`monitoring_commands.py:134`)
   - New click option: `@click.option('--include-completed', 'include_completed', is_flag=True, help='Include completed agents (default: active only)')`

2. **Conditional completed agent fetching** (`monitoring_commands.py:250-255`)
   ```python
   if include_completed:
       completed_agents = [a for a in registry.list_agents() if a.get('status') == 'completed']
   else:
       completed_agents = []
   ```

3. **JSON output includes completed agents when flag set** (`monitoring_commands.py:378-384`)
   - Added helper function to serialize agents
   - Now iterates over both `agent_statuses` and `completed_statuses`
   - Added `status` field to JSON output

4. **Updated logging** to include `include_completed` flag

### Tests Added

Created `tests/test_status_include_completed.py` with 5 tests:
- `test_status_defaults_to_active_only` - Verifies default shows no completed
- `test_status_include_completed_shows_all` - Verifies flag shows completed
- `test_status_include_completed_with_json` - Verifies JSON output respects flag
- `test_status_help_shows_include_completed_option` - Verifies help text
- `test_status_no_completed_message_when_empty` - Edge case handling

---

## Verification

**Test Results:** All 30 status tests pass (5 new + 25 existing)

**Manual Verification:**
- `orch status` - Shows only active agents, no COMPLETED sections
- `orch status --include-completed` - Shows active + completed agents
- `orch status --help` - Shows `--include-completed` option

---

## References

**Files Modified:**
- `src/orch/monitoring_commands.py` - Core implementation

**Files Created:**
- `tests/test_status_include_completed.py` - New test file

**Commands Run:**
```bash
# Run new tests
python -m pytest tests/test_status_include_completed.py -v

# Run all status tests
python -m pytest tests/test_status*.py -v

# Verify help text
orch status --help

# Verify behavior
orch status
orch status --include-completed
```

---

## Investigation History

**2025-12-09 15:30:** Investigation started
- Initial question: Make orch status show active-only by default
- Context: Spawned from beads issue orch-cli-krc

**2025-12-09 15:45:** Implementation complete
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Added `--include-completed` flag, default now shows active only
