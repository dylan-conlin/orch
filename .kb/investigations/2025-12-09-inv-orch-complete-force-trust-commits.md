**TLDR:** Question: Should `orch complete --force` bypass Phase: Complete verification? Answer: Yes - when --force is passed, the command now trusts that if work is committed (git validation passes), the agent's work is complete, skipping the Phase: Complete beads comment check. High confidence (95%) - validated with comprehensive tests.

---

# Investigation: orch complete --force should trust commits over phase status

**Question:** Should `orch complete --force` bypass the Phase: Complete verification and trust git commits as the source of truth?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: --force only bypassed active process checks, not phase verification

**Evidence:** The `force` parameter in `complete_agent_work()` was only passed to `clean_up_agent()`, not to `close_beads_issue()`. The `close_beads_issue()` function already had a `verify_phase` parameter but it was never utilized by the completion flow.

**Source:** `src/orch/complete.py:283-298` - force was only used at line 298 for `clean_up_agent()`

**Significance:** This meant agents that completed work but forgot to report "Phase: Complete" via beads comments could not be completed even with --force flag.

---

### Finding 2: CLI --issue path had duplicate phase verification

**Evidence:** The `--issue` path in `cli.py` (lines 515-526) performed its own phase verification independent of `close_beads_issue()`, and this path also didn't respect the --force flag.

**Source:** `src/orch/cli.py:515-526` - hardcoded phase check without force consideration

**Significance:** Both paths (agent completion and direct issue closing) needed to respect the --force flag.

---

### Finding 3: Git validation still provides meaningful verification

**Evidence:** The git validation in `validate_work_committed()` checks for uncommitted changes and unpushed commits. This provides a strong signal that work was actually done.

**Source:** `src/orch/git_utils.py:227-348`

**Significance:** When --force is used, git validation still runs. This means --force trusts "work is committed" over "agent said Phase: Complete", not bypassing all verification.

---

## Synthesis

**Key Insights:**

1. **Trust hierarchy:** Git commits are a stronger signal of completed work than beads comments. If work is committed, the agent did their job.

2. **Graceful degradation:** Agents may forget to report Phase: Complete but still have done excellent work. --force enables recovering from this.

3. **Safety preserved:** --force doesn't bypass git validation, only phase verification. Work must still be committed.

**Answer to Investigation Question:**

Yes, `orch complete --force` should bypass Phase: Complete verification and trust commits as the source of truth. This enables completing agents that did their work but forgot the completion protocol, while still requiring that work be actually committed.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

The implementation is straightforward and well-tested. The change aligns with the principle that git history is more reliable than beads comments for verifying work completion.

**What's certain:**

- The `--force` flag now bypasses phase verification in both paths (agent completion and --issue)
- Git validation still runs even with --force
- Default behavior (without --force) is unchanged
- 55 tests pass including 4 new tests specifically for this behavior

**What's uncertain:**

- Edge cases with cross-repo beads issues (tested but less common path)

**What would increase confidence to Very High:**

- Manual end-to-end testing (already at 95%, manual testing would confirm)

---

## Implementation Recommendations

**Purpose:** Document the implementation that was completed.

### Implemented Approach

**Changes made:**

1. `src/orch/complete.py:283` - Added `verify_phase=not force` to `close_beads_issue()` call
2. `src/orch/cli.py:516-535` - Added `if not force:` guard around phase verification in --issue path
3. Updated 3 existing tests to expect new call signature
4. Added 4 new tests in `TestForceBypassesPhaseCheck` class

**Why this approach:**

- Minimal code change (2 lines of logic)
- Reuses existing `verify_phase` parameter in `close_beads_issue()`
- Backward compatible - default behavior unchanged
- Clear user feedback when force-closing ("force-closed (phase check skipped)")

---

## References

**Files Modified:**
- `src/orch/complete.py:283` - Added verify_phase parameter
- `src/orch/cli.py:515-535` - Added force check and improved messaging

**Files Examined:**
- `src/orch/complete.py` - Core completion logic
- `src/orch/cli.py` - CLI command definitions
- `src/orch/git_utils.py` - Git validation logic
- `tests/test_complete.py` - Existing tests

**Tests Added:**
- `test_close_beads_issue_with_force_bypasses_phase_check`
- `test_complete_agent_work_with_force_bypasses_phase_check`
- `test_complete_agent_work_without_force_still_verifies_phase`
- `test_force_still_requires_committed_work`

---

## Investigation History

**2025-12-09 15:36:** Investigation started
- Initial question: Should --force bypass phase verification?
- Context: Spawned from beads issue orch-cli-cs2

**2025-12-09 15:45:** Implementation complete
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: --force now bypasses Phase: Complete check while preserving git validation
