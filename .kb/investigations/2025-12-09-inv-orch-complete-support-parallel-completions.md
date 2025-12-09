**TLDR:** Question: Why do parallel `orch complete` commands fail? Answer: When closing beads issues, `.beads/issues.jsonl` is modified but the git validation in `complete.py` fails for uncommitted changes. Fix: exclude `.beads/` from validation using existing `exclude_files` parameter. High confidence (90%) - code path is clear and the fix is minimal.

---

# Investigation: Parallel orch complete Support for Beads

**Question:** Why do parallel `orch complete` commands fail and how can we fix it?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** None - implement fix
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Git validation blocks parallel completions

**Evidence:** Error message from error log:
```
Git validation error:
  Uncommitted changes detected:
  M .beads/issues.jsonl
```

**Source:** `src/orch/complete.py:266-269` - `validate_work_committed()` call

**Significance:** The `complete_agent_work()` function calls `validate_work_committed(project_dir)` without excluding `.beads/` files. When the first completion closes a beads issue, it modifies `.beads/issues.jsonl`. Subsequent completions see this as uncommitted changes and fail.

---

### Finding 2: validate_work_committed already supports exclusions

**Evidence:** Function signature in `git_utils.py:227`:
```python
def validate_work_committed(directory: Path, exclude_files: Optional[list[str]] = None) -> tuple[bool, str]:
```

The function has logic at lines 262-288 to filter out excluded files from the validation.

**Source:** `src/orch/git_utils.py:227-348`

**Significance:** The fix is simple - pass `exclude_files=[".beads/"]` to exclude the beads directory from validation. No new logic needed.

---

### Finding 3: Beads sync happens after each close

**Evidence:** The `bd close` command writes to `.beads/issues.jsonl` immediately. The `bd sync` command commits these changes but is not called by `orch complete`.

**Source:** Beads CLI behavior and error log showing "bd sync" as workaround

**Significance:** The current workaround is to serialize completions with `bd sync` after each one. But this is unnecessary if we simply exclude `.beads/` from the git validation - the changes will be committed by the eventual `bd sync` at session end per the hooks workflow.

---

## Synthesis

**Key Insights:**

1. **Root cause is overly strict validation** - The git validation in `complete_agent_work()` checks ALL uncommitted changes, but `.beads/` changes are expected and should be excluded.

2. **Fix exists but unused** - The `exclude_files` parameter in `validate_work_committed()` already supports this use case.

3. **Minimal change required** - Just pass `exclude_files=[".beads/"]` at the call site in `complete.py`.

**Answer to Investigation Question:**

Parallel `orch complete` commands fail because each completion that closes a beads issue modifies `.beads/issues.jsonl`, and subsequent completions fail the git validation check for uncommitted changes. The fix is to exclude `.beads/` directory from the validation by passing `exclude_files=[".beads/"]` to `validate_work_committed()`.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

The code path is straightforward - traced from error to source. The `exclude_files` mechanism is already implemented and used elsewhere. The only uncertainty is whether there are edge cases in the exclusion pattern matching.

**What's certain:**

- The error originates from `validate_work_committed()` checking `.beads/issues.jsonl`
- The `exclude_files` parameter exists and handles path exclusion
- Excluding `.beads/` is safe because beads changes are committed by the hooks workflow

**What's uncertain:**

- Whether the existing pattern matching handles `.beads/` correctly (it uses startswith matching)
- Whether there are other files in `.beads/` that should also be excluded

**What would increase confidence to Very High:**

- Test the fix with actual parallel completions
- Verify the startswith matching handles `.beads/` prefix correctly

---

## Implementation Recommendations

### Recommended Approach: Exclude .beads/ from validation

**Pass `exclude_files=[".beads/"]` to `validate_work_committed()` in `complete.py`**

**Why this approach:**
- Minimal code change (one line)
- Uses existing, tested functionality
- Doesn't require changes to beads workflow
- `.beads/` changes are expected to be uncommitted during parallel work

**Trade-offs accepted:**
- Slightly looser validation (but only for `.beads/` which is managed separately)

**Implementation sequence:**
1. Write failing test for parallel completion scenario
2. Modify `complete.py:266` to pass `exclude_files=[".beads/"]`
3. Verify test passes

### Alternative Approaches Considered

**Option B: Auto-sync beads before/after completion**
- **Pros:** Keeps validation strict
- **Cons:** Adds latency, still racy if multiple complete in same moment
- **When to use instead:** If `.beads/` exclusion is unacceptable

**Option C: Add --batch flag for atomic completions**
- **Pros:** Most correct solution
- **Cons:** Much more complex, changes UX
- **When to use instead:** If frequent parallel completions are common

**Rationale for recommendation:** The exclusion approach is simplest and aligns with existing workflow where `.beads/` changes are committed by hooks, not by `orch complete`.

---

## References

**Files Examined:**
- `src/orch/complete.py` - Complete command logic, validation call at line 266
- `src/orch/git_utils.py` - `validate_work_committed()` with exclude_files support
- `src/orch/beads_integration.py` - BeadsIntegration.close_issue() method

**Commands Run:**
```bash
# Error analysis
bd comment orch-cli-a6p "Phase: Planning - Analyzing parallel completion issue with beads"

# Code search
grep -r "validate_work_committed" src/
```

---

## Investigation History

**2025-12-09 14:XX:** Investigation started
- Initial question: Why do parallel orch complete commands fail?
- Context: Error logs show git validation failures for uncommitted .beads/issues.jsonl

**2025-12-09 14:XX:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Simple fix - exclude `.beads/` from git validation using existing `exclude_files` parameter
