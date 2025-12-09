**TLDR:** Implemented local error telemetry for orch-cli. Errors logged to ~/.orch/errors.jsonl with `orch errors` command for analytics. TDD approach with 40 tests passing. High confidence (90%) - core functionality works, may need extended error coverage over time.

---

# Investigation: Add Local Error Logging with Analytics

**Question:** How to implement error telemetry that captures CLI errors for pattern detection?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** worker-agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Deliverables

### 1. Error Logging Module (error_logging.py)

**Location:** `src/orch/error_logging.py`

**Features:**
- `ErrorType` enum with taxonomy (AGENT_NOT_FOUND, VERIFICATION_FAILED, SPAWN_FAILED, etc.)
- `ErrorEntry` dataclass for structured error data
- `ErrorLogger` class with JSONL storage to `~/.orch/errors.jsonl`
- `get_error_stats(days=7)` for aggregated statistics by type/command
- `get_recent_errors(limit=10)` for retrieving recent entries
- Automatic log rotation (default 10K entries)
- `log_cli_error()` helper for CLI command error logging

### 2. Error Analytics Command (error_commands.py)

**Location:** `src/orch/error_commands.py`

**Usage:**
```bash
orch errors                    # Show last 7 days summary
orch errors --days 30          # Show last 30 days
orch errors --type AGENT_NOT_FOUND  # Filter by type
orch errors --json             # Output as JSON
orch errors --limit 20         # Show more recent errors
```

**Output format:**
```
Error summary (last 7 days):

By type:
  AGENT_NOT_FOUND              12 (40%)
  VERIFICATION_FAILED           8 (27%)
  BEADS_ERROR                   6 (20%)

By command:
  orch complete                18 (60%) ← hotspot
  orch spawn                    4 (13%)

Recent errors:
  2025-12-09 10:42  complete  AGENT_NOT_FOUND  Agent 'pw-k2r' not found
  2025-12-09 10:41  complete  VERIFICATION_FAILED  Investigation not found
```

### 3. CLI Error Logging Integration

**Location:** `src/orch/cli.py`

**Errors now logged:**
- Agent not found (AGENT_NOT_FOUND)
- Beads CLI not found (BEADS_ERROR)
- Beads issue not found (BEADS_ERROR)
- Phase not complete verification failure (VERIFICATION_FAILED)

### 4. Tests

**New test files:**
- `tests/test_error_logging.py` (19 tests)
- `tests/test_error_commands.py` (15 tests)
- `tests/test_cli_error_wrapper.py` (6 tests)

**All 40 tests passing.**

---

## Implementation Notes

### Error Entry Schema
```json
{
  "timestamp": "2025-12-09T10:42:00Z",
  "command": "orch complete pw-k2r",
  "subcommand": "complete",
  "error_type": "AGENT_NOT_FOUND",
  "error_code": "AGENT_NOT_FOUND",
  "message": "Agent 'pw-k2r' not found in registry",
  "context": {"agent_id": "pw-k2r"},
  "stack_trace": null,
  "duration_ms": null
}
```

### Error Type Taxonomy
- `AGENT_NOT_FOUND` - Agent not in registry
- `VERIFICATION_FAILED` - Phase/investigation verification failed
- `INVESTIGATION_NOT_FOUND` - Investigation file not found
- `SPAWN_FAILED` - Spawn operation failed
- `REGISTRY_LOCKED` - Registry file lock issue
- `BEADS_ERROR` - Beads CLI or issue errors
- `TMUX_ERROR` - Tmux operation failed
- `CONFIG_ERROR` - Configuration issues
- `UNEXPECTED_ERROR` - Catch-all for unknown errors

### Reusable Pattern

This pattern can be replicated across other Dylan CLIs (bd, kb, kn):
- Same JSONL format
- Same analytics structure
- Could extract to shared library: `cli-error-telemetry`

---

## Confidence Assessment

**Current Confidence:** High (90%)

**What's certain:**
- ✅ Core error logging works with JSONL storage
- ✅ `orch errors` command shows correct analytics
- ✅ Error taxonomy covers main error types
- ✅ 40 tests pass with TDD approach
- ✅ Log rotation prevents unbounded file growth

**What's uncertain:**
- ⚠️ Not all error paths in CLI are instrumented yet (spawn, status, etc.)
- ⚠️ Long-term pattern detection depends on usage data

**Future enhancements:**
- Add error logging to more commands (spawn, status, clean)
- Add duration_ms tracking for performance analysis
- Extract to shared library when other CLIs adopt

---

## References

**Files Created/Modified:**
- `src/orch/error_logging.py` - New module
- `src/orch/error_commands.py` - New command module
- `src/orch/cli.py` - Added import and error logging calls
- `tests/test_error_logging.py` - Unit tests
- `tests/test_error_commands.py` - Command tests
- `tests/test_cli_error_wrapper.py` - Integration tests

**Commands Verified:**
```bash
# Run tests
python -m pytest tests/test_error_logging.py tests/test_error_commands.py tests/test_cli_error_wrapper.py -v
# All 40 passed
```

---

## Investigation History

**2025-12-09 ~14:00:** Investigation started
- Initial question: How to capture CLI errors for pattern detection?
- Context: orch complete failures showed recurring patterns (beads ID lookup)

**2025-12-09 ~14:30:** TDD implementation started
- Created failing tests for error_logging module
- Implemented ErrorLogger class with JSONL storage

**2025-12-09 ~15:00:** orch errors command implemented
- Added error_commands.py with CLI command
- Summary stats, filtering, JSON output all working

**2025-12-09 ~15:30:** CLI error wrapper added
- Integrated error logging into complete command
- Agent not found, beads errors, verification failures now logged

**2025-12-09 ~16:00:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Local error telemetry with analytics available via `orch errors`
