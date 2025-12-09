**TLDR:** Question: How to implement orch end for clean session exit with knowledge capture gates? Answer: Implemented using TDD with tmux context detection, kn entry checking, soft gate prompt, and /exit injection via tmux send-keys. High confidence (95%) - all 16 tests passing, reused proven patterns from existing codebase.

---

# Investigation: orch end Command Implementation

**Question:** How to implement `orch end` for clean session exit with knowledge capture gates?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent (feature-impl)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: tmux send-keys pattern works reliably

**Evidence:** Used existing pattern from `complete.py:send_exit_command()` which sends `/exit` + Enter via tmux send-keys. This pattern is already proven in production.

**Source:** `src/orch/complete.py` lines 54-69

**Significance:** No new infrastructure needed - reused proven pattern for clean /exit injection.

---

### Finding 2: Session detection already implemented

**Evidence:** Session start time detection exists in `orchestrator-session-kn-gate.py`:
- Orchestrators: `~/.orch/current-session.json` with `started_at` field
- Workers: Fallback to 2 hours ago

**Source:** `~/.orch/hooks/orchestrator-session-kn-gate.py` lines 81-101

**Significance:** Reused existing logic for session start detection.

---

### Finding 3: kn entry reading pattern works

**Evidence:** Reading `.kn/entries.jsonl` and filtering by timestamp is proven in hooks. Pattern handles:
- Timezone-aware/naive datetime comparison
- Invalid JSON lines
- Missing .kn directory

**Source:** `~/.orch/hooks/orchestrator-session-kn-gate.py` lines 104-160

**Significance:** Adapted this logic for the end command with minor modifications.

---

## Synthesis

**Key Insights:**

1. **TDD worked well** - Writing 16 tests first ensured comprehensive coverage of all behaviors

2. **Pattern reuse minimized risk** - All core patterns (tmux send-keys, session detection, kn reading) came from existing proven code

3. **Soft gate is appropriate** - Unlike hard gates, users can still exit when needed, but get reminded about knowledge capture

**Answer to Investigation Question:**

Implementation complete with:
- `src/orch/end.py` - Core logic (257 lines)
- `src/orch/end_commands.py` - CLI registration
- `tests/test_end.py` - 16 tests covering all behaviors

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

All tests pass. Implementation follows proven patterns. Design was pre-validated.

**What's certain:**

- ✅ tmux detection works (TMUX env var + pane ID)
- ✅ kn entry reading works (tested with fixtures)
- ✅ Soft gate prompts when no entries
- ✅ /exit injection uses proven pattern

**What's uncertain:**

- ⚠️ Real-world behavior when Claude Code receives /exit (not tested in CI)

**What would increase confidence to Very High (95%+):**

- Already at 95%

---

## Implementation Summary

**Files created:**
- `src/orch/end.py` - Core logic
- `src/orch/end_commands.py` - CLI command registration
- `tests/test_end.py` - Test suite (16 tests)

**Files modified:**
- `src/orch/cli.py` - Added end command registration

**Command behavior:**
```
$ orch end

# Success path (has knowledge entries):
✓ Knowledge captured: 2 entries
Sending /exit...

# Soft gate path (no entries):
⚠️  No knowledge captured this session.

Consider before exiting:
  kn decide "what" --reason "why"
  kn tried "what" --failed "why"
  kn constrain "rule" --reason "why"

Exit anyway? [y/N]: y
Sending /exit...

# Error path (not in tmux):
Error: orch end requires tmux
```

---

## References

**Files Examined:**
- `src/orch/complete.py` - tmux send-keys pattern
- `src/orch/tmux_utils.py` - tmux utilities
- `~/.orch/hooks/orchestrator-session-kn-gate.py` - session detection, kn reading

**Design Reference:**
- `~/orch-knowledge/.kb/investigations/2025-12-09-design-add-orch-end-command-clean.md`

---

## Investigation History

**2025-12-09 ~14:40:** Investigation started
- Initial question: How to implement orch end?
- Context: Design already complete, starting TDD implementation

**2025-12-09 ~14:45:** TDD cycle 1 complete
- Basic command skeleton with tests

**2025-12-09 ~15:00:** TDD cycle 2 complete
- Full implementation with all 16 tests passing

**2025-12-09 ~15:05:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: `orch end` command implemented and tested
