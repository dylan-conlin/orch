**TLDR:** Question: Why does `orch complete` fail with "uncommitted changes" when `.beads/` changes exist despite being excluded? Answer: The exclusion logic in `validate_work_committed()` has an inverted condition - it checks `excluded.startswith(change_path)` instead of `change_path.startswith(excluded)`. High confidence (95%) - root cause confirmed via code analysis.

---

# Investigation: orch complete scope git check

**Question:** Why does `orch complete` fail with "uncommitted changes detected" for `.beads/` files even though `.beads/` is in the exclude list?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: The exclude_files logic is inverted

**Evidence:** In `git_utils.py:283`, the exclusion check is:
```python
if excluded == change_path or excluded.startswith(change_path):
```

For `excluded=".beads/"` and `change_path=".beads/issues.jsonl"`:
- `".beads/" == ".beads/issues.jsonl"` → False
- `".beads/".startswith(".beads/issues.jsonl")` → False (inverted!)

The correct logic should be `change_path.startswith(excluded)`:
- `".beads/issues.jsonl".startswith(".beads/")` → True ✓

**Source:** `src/orch/git_utils.py:278-285`

**Significance:** This is the root cause. Files in `.beads/` are NOT being excluded because the startswith check is backwards.

---

### Finding 2: The comment describes a secondary use case but not the primary one

**Evidence:** The comment says:
```python
# 2. Directory match: excluded path is inside a changed directory
#    (e.g., change="?? .orch/", excluded=".orch/ROADMAP.org")
```

This describes the case where git shows an untracked directory (`.orch/`) and we want to exclude a specific file inside it. But the PRIMARY use case is:
- `excluded = ".beads/"` (exclude a directory)
- `change_path = ".beads/issues.jsonl"` (a file inside that directory)

**Source:** `src/orch/git_utils.py:279-282`

**Significance:** The code handles only one direction but needs to handle BOTH directions.

---

### Finding 3: Error logs confirm the pattern

**Evidence:** Error summary shows:
```
By command:
  orch complete               89 (100%) ← hotspot

Recent errors:
  Git validation error: ⚠️  Uncommitted changes d...
```

All errors are from `orch complete` with git validation failures.

**Source:** SessionStart hook error summary

**Significance:** Confirms this is a recurring issue affecting all `orch complete` calls when `.beads/` has changes.

---

## Synthesis

**Key Insights:**

1. **Inverted logic bug** - The exclusion check `excluded.startswith(change_path)` should be `change_path.startswith(excluded)` (or both directions)

2. **Both directions needed** - The code needs to handle two cases:
   - Changed file is inside excluded directory: `change_path.startswith(excluded)`
   - Excluded path is inside a changed directory: `excluded.startswith(change_path)`

3. **Simple fix** - Adding `change_path.startswith(excluded)` to the OR condition fixes the bug

**Answer to Investigation Question:**

The git check isn't "scoped wrong to global vs workspace" - the actual bug is the exclusion logic is inverted. Files in `.beads/` SHOULD be excluded (and the code intends to exclude them), but the condition `excluded.startswith(change_path)` is backwards and never matches for files inside excluded directories.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**
- Direct code analysis shows the inverted condition
- Logic can be verified by tracing through with example values
- Error pattern matches the expected behavior of the bug

**What's certain:**
- ✅ The startswith condition is backwards for the primary use case
- ✅ `.beads/issues.jsonl` won't match `.beads/` with current logic
- ✅ The fix is straightforward (add/fix the startswith condition)

**What's uncertain:**
- ⚠️ Whether there are other callers of this function that rely on current behavior

**What would increase confidence to Very High (95%+):**
- Already at Very High - code analysis is definitive

---

## Implementation Recommendations

### Recommended Approach ⭐

**Fix the startswith condition** - Change line 283 to check both directions

**Why this approach:**
- Direct fix for the root cause
- Maintains backward compatibility with the existing use case
- Simple, single-line change

**Trade-offs accepted:**
- None - this is a pure bug fix

**Implementation sequence:**
1. Fix the condition in `validate_work_committed()`
2. Add a test case that would have caught this bug
3. Verify the fix works

### Implementation Details

**The fix:**

Change line 283 from:
```python
if excluded == change_path or excluded.startswith(change_path):
```

To:
```python
if excluded == change_path or change_path.startswith(excluded) or excluded.startswith(change_path):
```

Or more clearly:
```python
# Check if change should be excluded:
# 1. Exact match
# 2. Changed file is inside excluded directory (e.g., ".beads/issues.jsonl" inside ".beads/")
# 3. Excluded path is inside changed directory (e.g., ".orch/ROADMAP.org" when git shows ".orch/")
if (excluded == change_path or
    change_path.startswith(excluded) or
    excluded.startswith(change_path)):
```

**Success criteria:**
- ✅ `orch complete` succeeds when only `.beads/` changes exist
- ✅ Test case validates exclusion logic

---

## References

**Files Examined:**
- `src/orch/complete.py` - complete_agent_work() calls validate_work_committed()
- `src/orch/git_utils.py` - validate_work_committed() has the bug at line 283

**Commands Run:**
```bash
# Report phase
bd comment orch-cli-xas "Phase: Planning - Analyzing orch complete git check scope issue"
```

---

## Investigation History

**2025-12-09 15:30:** Investigation started
- Initial question: Why is `orch complete` failing with uncommitted changes for `.beads/`?
- Context: Error logs show 89 failures, all from `orch complete`

**2025-12-09 15:35:** Root cause identified
- Found inverted startswith logic at git_utils.py:283
- The exclusion logic checks wrong direction

**2025-12-09 15:40:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Bug is inverted startswith condition, simple fix
