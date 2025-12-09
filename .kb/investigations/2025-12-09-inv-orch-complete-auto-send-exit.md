**TLDR:** Feature implementation: Auto-send /exit when orch complete detects Phase: Complete but processes still running. Implemented send_exit_command helper and modified clean_up_agent to try /exit before failing. All 24 tests pass.

---

# Feature: orch complete auto-send /exit

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Status:** Complete

---

## Problem

When running `orch complete`, if the agent workspace shows Phase: Complete but the Claude Code process is still running in the tmux window, the command failed with:

```
RuntimeError: Agent xyz has active processes that did not terminate.
Cannot safely kill window @56.
Try 'orch send xyz "/exit"' first.
```

This required a manual 3-step workaround:
```bash
orch send <agent> "/exit"
sleep 3
orch complete <agent>
```

## Solution Implemented

### 1. Added `send_exit_command` helper function

**Location:** `src/orch/complete.py:39-78`

Sends `/exit` command to a tmux window and waits for processes to terminate:
- Sends `/exit` via `tmux send-keys`
- Sends `Enter` to execute
- Waits for configurable timeout (default 5 seconds)
- Returns True if processes terminated, False if still running

### 2. Modified `clean_up_agent` to use auto-exit

**Location:** `src/orch/complete.py:162-173`

When graceful shutdown (Ctrl+C) fails:
1. Prints message: "Sending /exit to agent {agent_id}..."
2. Calls `send_exit_command(window_id)`
3. If /exit succeeds (processes terminate), continues with cleanup
4. If /exit also fails, THEN raises RuntimeError

## Tests Added

**Location:** `tests/test_complete.py`

### TestAutoExitOnComplete
- `test_clean_up_agent_sends_exit_when_graceful_shutdown_fails` - verifies /exit is called
- `test_clean_up_agent_raises_error_if_exit_fails` - verifies error raised when /exit fails
- `test_clean_up_agent_shows_exit_message` - verifies user feedback message

### TestSendExitCommand
- `test_send_exit_command_sends_exit_and_waits` - verifies /exit sent via tmux
- `test_send_exit_command_returns_false_if_timeout` - verifies timeout behavior

## Acceptance Criteria

- [x] `orch complete` auto-exits agent when Phase: Complete but process running
- [x] Shows message: "Sending /exit to agent..."
- [x] Respects timeout (don't hang forever)
- [x] Still fails if process doesn't terminate after exit attempt

## Files Changed

1. `src/orch/complete.py` - Added `send_exit_command()`, modified `clean_up_agent()`
2. `tests/test_complete.py` - Added 5 new tests (TestAutoExitOnComplete, TestSendExitCommand)

## Test Results

All 24 tests in `test_complete.py` pass:
- 5 TestVerification
- 3 TestCompleteIntegration
- 2 TestSessionPreservation
- 5 TestProcessChecking
- 5 TestAutoExitOnComplete (NEW)
- 4 TestInvestigationArtifactFallback
