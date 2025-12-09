**TLDR:** Question: How to validate beads issues for common problems before spawning? Answer: Implemented `orch lint --issues` with 5 validation checks (deletion without migration, hidden blockers, vague scope, stale issues, missing acceptance criteria). High confidence (90%) - tested against 26 real issues with accurate detection.

---

# Investigation: orch lint --issues: Validate Beads Issues

**Question:** How to implement validation of beads issues for common problems like underspecified migration paths, hidden blockers, and vague scope?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker (spawned from orch-cli-abt)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: bd list vs bd show output structure

**Evidence:** `bd list --status=open --json` returns summary fields including `dependency_count` and `dependent_count` but NOT the full `dependencies` array with `dependency_type`. `bd show <id> --json` returns the full dependency details.

**Source:** Ran `bd list --status=open --json | head -50` and compared with `bd show orch-cli-nan --json`

**Significance:** For accurate "hidden blocker" detection, we need to distinguish "blocks" type dependencies from "parent-child" type. Using `dependency_count > 0` as a proxy creates false negatives because parent-child dependencies don't represent blockers.

---

### Finding 2: bd blocked provides accurate blocker detection

**Evidence:** `bd blocked --json` returns all issues that have blocking dependencies with a `blocked_by` array. This is the accurate source for detecting which issues are properly blocked.

**Source:** Ran `bd blocked --json | head -50`

**Significance:** Using `bd blocked` list allows accurate detection of hidden blockers - issues that mention "BLOCKED:" or "Prerequisite:" in text but aren't in the blocked list have untracked dependencies.

---

### Finding 3: Deletion issues pattern detection is effective

**Evidence:** Pattern matching for keywords "delete", "remove", "eliminate", "deprecate" in issue titles correctly identifies deletion-type issues. Testing against 26 issues found 7 deletion issues without migration paths.

**Source:** Output of `orch lint --issues` against real beads issues

**Significance:** The pattern detection has acceptable precision - all flagged issues are genuinely deletion-related and would benefit from migration documentation.

---

## Synthesis

**Key Insights:**

1. **Multi-source validation** - Combining `bd list` (for issue content) with `bd blocked` (for dependency accuracy) provides reliable validation.

2. **Pattern-based detection works** - Regex patterns for blocker text (BLOCKED:, Prerequisite:) and deletion keywords have good precision with few false positives.

3. **Stale detection requires timezone handling** - Issue timestamps are ISO format with timezone; proper parsing with `datetime.fromisoformat()` is needed.

**Answer to Investigation Question:**

Implemented `orch lint --issues` in `src/orch/cli.py` with 5 validation checks:
1. Deletion issues without migration path section
2. Hidden blockers in description without bd dependency
3. Vague scope without enumeration
4. Stale issues (open >7 days without activity)
5. Epics missing success criteria

The implementation uses `bd list` for issue data and `bd blocked` for accurate dependency detection. Tested against 26 real issues, found 9 with problems and correctly passed 17.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Implementation is complete and tested against real issues. Validation checks are working correctly with few false positives.

**What's certain:**

- ✅ All 5 validation checks implemented and functional
- ✅ Hidden blocker detection correctly handles issues in/not in bd blocked list
- ✅ Deletion pattern detection has good precision (7 issues found, all legitimate)
- ✅ Output format is clear with actionable suggestions

**What's uncertain:**

- ⚠️ Edge cases with unusual issue formatting may not be caught
- ⚠️ Stale threshold (7 days) may need tuning based on workflow
- ⚠️ Epic success criteria check only applies to issue_type="epic"

**What would increase confidence to Very High:**

- Extended testing with larger issue sets
- User feedback on false positive/negative rates
- Integration with `orch spawn --issue` for automatic pre-spawn validation

---

## Implementation Recommendations

### Recommended Approach: Use as pre-spawn validation

**Why this approach:**
- Catches underspecified issues before agent time is wasted
- Provides actionable suggestions for fixing issues
- Integrates with existing lint command infrastructure

**Trade-offs accepted:**
- Additional bd commands (bd list, bd blocked) add ~100ms latency
- Some false positives possible (e.g., simple deletions that truly need no migration)

**Implementation sequence:**
1. Run `orch lint --issues` manually to review issues
2. Consider adding to `orch spawn --issue` with `--force` override
3. Could add to CI/pre-commit for issue quality enforcement

### Implementation Details

**Files changed:**
- `src/orch/cli.py`: Added `_lint_issues()` function (~190 lines) and `--issues` flag to lint command

**What to watch out for:**
- ⚠️ bd blocked JSON format may change; handle gracefully
- ⚠️ Timezone parsing for stale check; use timezone-aware datetimes

**Success criteria:**
- ✅ `orch lint --issues` runs without errors
- ✅ Correctly identifies underspecified issues
- ✅ Output provides actionable suggestions

---

## References

**Files Examined:**
- `src/orch/cli.py` - Existing lint command structure
- `src/orch/beads_integration.py` - BeadsIntegration class (not used directly, referenced for API)
- `.kb/investigations/2025-12-08-inv-audit-beads-issues-underspecified-migration.md` - Prior audit investigation

**Commands Run:**
```bash
# Get open issues
bd list --status=open --json

# Get blocked issues
bd blocked --json

# Test issue details
bd show orch-cli-nan --json
bd show orch-cli-9sv --json

# Test implementation
orch lint --issues
```

**Related Artifacts:**
- **Issue:** orch-cli-abt - Parent beads issue for this work
- **Investigation:** .kb/investigations/2025-12-08-inv-audit-beads-issues-underspecified-migration.md - Audit that inspired this feature

---

## Investigation History

**2025-12-08 20:00:** Investigation started
- Initial question: How to implement `orch lint --issues` validation
- Context: Prior audit found underspecified issues; need automated detection

**2025-12-08 20:15:** Design completed
- Defined 5 validation checks based on audit findings
- Analyzed bd list vs bd show output structure

**2025-12-08 20:30:** Implementation completed
- Added `_lint_issues()` function to cli.py
- Updated lint command with `--issues` flag
- Fixed blocker detection using `bd blocked` for accuracy

**2025-12-08 20:45:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: `orch lint --issues` implemented with 5 validation checks, tested against 26 real issues
