**TLDR:** Question: Why do git validation errors persist despite .beads/ and .kn/ exclusions? Answer: Recent errors (2025-12-10) are caused by untracked `.kb/` investigation files, which are NOT in the exclusion list. The exclusion list needs `.kb/` added. High confidence (90%) - verified by testing validation function and analyzing 20 recent errors.

---

# Investigation: Expand Git Validation Exclusions for .kb/

**Question:** Why does `orch complete` still fail with git validation errors despite having `.beads/` and `.kn/` in the exclusion list?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** debug-expand-git-validation-10dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: `.kn/` and `.beads/` exclusions are working correctly

**Evidence:**
- Ran `validate_work_committed(Path('.'), exclude_files=['.beads/', '.kn/'])`
- Result: `Valid: True` despite `M .beads/issues.jsonl` in git status
- The filtering logic at `git_utils.py:264-292` correctly excludes matching files

**Source:** `src/orch/git_utils.py:264-292`, `src/orch/complete.py:269`

**Significance:** The existing exclusions work. The problem is that `.kb/` is NOT in the exclusion list, causing errors when investigation files are created/modified.

---

### Finding 2: `.kb/` directory is causing recent errors

**Evidence:** Recent errors from `~/.orch/errors.jsonl` (2025-12-10):
- `09:11:02` - `?? .kb/investigations/` - UNTRACKED .kb files
- `09:11:04` - `?? .kb/investigations/` - Same pattern
- `09:20:01` - `?? .kb/nate-jones-agen...` - UNTRACKED .kb files
- `09:20:26` - `?? .kb/investigations/` - Multiple parallel agents failing

Pattern: Agents create investigation files in `.kb/investigations/`, which appear as untracked (`??`), triggering git validation failures.

**Source:** `~/.orch/errors.jsonl` (last 20 entries), analyzed with timestamps 2025-12-10

**Significance:** `.kb/` needs to be added to the exclusion list alongside `.beads/` and `.kn/`. All three directories are "knowledge management" directories that are managed separately from code commits.

---

### Finding 3: Parallel completion timing creates race conditions

**Evidence:** Errors at `09:20:01`, `09:20:03`, `09:20:05`, `09:20:26` show multiple agents completing within seconds:
- `decision-integration-wiring-10dec`
- `update-feature-impl-skill-10dec`
- `add-integration-audit-step-10dec`

All failed due to the same untracked `.kb/` files, indicating parallel completions where one agent creates files that block others.

**Source:** Error timestamps in `~/.orch/errors.jsonl`

**Significance:** The exclusion fix will resolve this race condition by ignoring `.kb/` files during validation, allowing parallel completions to succeed.

---

## Synthesis

**Key Insights:**

1. **Exclusion logic works** - The `.beads/` and `.kn/` exclusions are functioning correctly. Files matching these patterns are filtered out before validation checks.

2. **`.kb/` is missing from exclusions** - The investigation/knowledge base directory (`.kb/`) follows the same pattern as `.beads/` and `.kn/` but was not included in the exclusion list. This causes failures when agents create investigation files.

3. **Parallel completions amplify the issue** - Multiple agents completing simultaneously all see the same untracked `.kb/` files, causing cascading failures. Adding `.kb/` to exclusions will fix all of them at once.

**Answer to Investigation Question:**

Git validation errors persist because the `.kb/` directory is NOT in the exclusion list at `complete.py:269`. The current code excludes `[".beads/", ".kn/"]` but `.kb/` (where investigation files live) needs to be added. Recent errors (2025-12-10) all involve untracked `.kb/investigations/` files causing validation failures.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Direct evidence from error logs shows `.kb/` patterns in failure messages. Verified that existing exclusion logic works by testing `validate_work_committed()` function directly. Small gap: haven't confirmed there aren't other directories that also need exclusion.

**What's certain:**

- ✅ `.beads/` and `.kn/` exclusions work correctly (tested)
- ✅ `.kb/` is NOT in the exclusion list (verified in code)
- ✅ Recent errors (2025-12-10) are caused by `.kb/` files (analyzed error logs)

**What's uncertain:**

- ⚠️ Whether other directories might also need exclusion in future
- ⚠️ Whether there are edge cases in path matching for `.kb/`

**What would increase confidence to Very High (95%+):**

- Run test with `.kb/` added and verify no more errors
- Monitor error rates for 24 hours after fix

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add `.kb/` to exclusion list** - One-line change to `complete.py:269`

**Why this approach:**
- Directly addresses root cause (`.kb/` not excluded)
- Consistent with existing pattern for `.beads/` and `.kn/`
- Zero risk, minimal change

**Trade-offs accepted:**
- Relies on file path patterns staying consistent
- Users must still run `kb sync` or commit `.kb/` changes separately

**Implementation sequence:**
1. Add `.kb/` to exclusion list in `complete.py:269`
2. Verify fix with test
3. Commit and observe error rates

### Alternative Approaches Considered

**Option B: Use gitignore-based exclusion**
- **Pros:** Would catch any project-specific patterns automatically
- **Cons:** More complex implementation, requires parsing gitignore spec
- **When to use instead:** If we keep discovering new directories to exclude

**Rationale for recommendation:** Adding `.kb/` is the simplest fix that addresses 100% of recent errors. Gitignore-based exclusion can be a future enhancement.

---

## Implementation Details

**What to implement first:**
- Change `exclude_files=[".beads/", ".kn/"]` to `exclude_files=[".beads/", ".kn/", ".kb/"]` in `complete.py:269`

**Success criteria:**
- ✅ `validate_work_committed()` returns `True` when only `.kb/` files are dirty
- ✅ Existing tests pass
- ✅ Error rate for git validation drops

---

## References

**Files Examined:**
- `src/orch/complete.py:266-272` - git validation call with exclude_files
- `src/orch/git_utils.py:227-352` - validate_work_committed implementation
- `~/.orch/errors.jsonl` - recent error log (last 20 entries)

**Commands Run:**
```bash
# Check current git status
git status --porcelain
# Result: M .beads/issues.jsonl

# Test validation function
python3 -c "from orch.git_utils import validate_work_committed; ..."
# Result: Valid: True with current exclusions

# Analyze recent errors
tail -20 ~/.orch/errors.jsonl | python3 -c "import json; ..."
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` - Root cause analysis of all errors

---

## Investigation History

**2025-12-10 09:30:** Investigation started
- Initial question: Why do git validation errors persist despite exclusions?
- Context: SessionStart hook showed 93 UNEXPECTED_ERROR from orch complete

**2025-12-10 09:35:** Verified existing exclusions work
- Tested `validate_work_committed()` with `.beads/` and `.kn/` exclusions
- Confirmed they work correctly

**2025-12-10 09:40:** Identified root cause
- Analyzed recent errors from `~/.orch/errors.jsonl`
- Found all recent errors (2025-12-10) involve `.kb/` files
- Root cause: `.kb/` not in exclusion list

**2025-12-10 09:45:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Add `.kb/` to exclusion list at `complete.py:269`
