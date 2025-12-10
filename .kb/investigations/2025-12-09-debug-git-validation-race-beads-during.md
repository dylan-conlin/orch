**TLDR:** Question: Why does git validation fail during parallel completions even with `.beads/` exclusion? Answer: The fix at complete.py:268 only excludes `.beads/` but `.kn/entries.jsonl` also gets modified during parallel operations and isn't excluded. Very High confidence (95%) - analyzed 110 errors, found 47 `.beads/` errors (all before fix) and 3 `.kn/` errors that would be caught by expanded exclusion.

---

# Investigation: Git Validation Race on .beads/ During Parallel Completions

**Question:** Why does the git validation in `orch complete` still fail during parallel completions despite the `exclude_files=[".beads/"]` parameter?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** debug-git-validation-race-09dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: The `.beads/` exclusion IS working correctly

**Evidence:**
- Tested exclusion logic directly with Python: `.beads/issues.jsonl` IS correctly matched by `startswith('.beads/')`
- All 47 errors mentioning `.beads/` occurred BEFORE the fix (commit `f968a94` at 22:14 UTC)
- Zero `.beads/` errors after the fix was applied

**Source:**
- `git_utils.py:278-289` - exclusion logic uses `change_path.startswith(excluded)`
- `~/.orch/errors.jsonl` - 47/110 errors mention `.beads/`, all before fix timestamp

**Significance:** The original fix is working. The prior investigation correctly identified the problem and the fix resolved it.

---

### Finding 2: `.kn/` is NOT excluded but also causes race conditions

**Evidence:**
- 3 errors mention `.kn/entries.jsonl` being detected as uncommitted
- Current code at `complete.py:268` only excludes `.beads/`:
  ```python
  exclude_files=[".beads/"]
  ```
- `.kn/` (knowledge base) also gets modified during parallel operations via `kn` CLI

**Source:**
- `src/orch/complete.py:268` - only `.beads/` in exclude list
- Error log shows: "Uncommitted changes detected: M .kn/entries.jsonl"

**Significance:** The fix is incomplete - it only addressed `.beads/` but parallel agents also use `kn` commands which modify `.kn/entries.jsonl`.

---

### Finding 3: Some errors involve OTHER uncommitted changes (not tracking-related)

**Evidence:**
- Error at 20:40 UTC shows: `.gitignore`, `bun.lock`, `.gitattributes`, `.kn/`, `CLAUDE.md`
- These are legitimate uncommitted changes that SHOULD fail validation
- These are NOT race conditions - they're actual uncommitted work

**Source:**
- `~/.orch/errors.jsonl` entry at 2025-12-09T20:40:31

**Significance:** Not all git validation failures are race conditions. Some are legitimate catches of uncommitted work. The exclusion should only cover auto-managed tracking files (`.beads/`, `.kn/`).

---

## Synthesis

**Key Insights:**

1. **The original fix works** - The `.beads/` exclusion at `complete.py:268` successfully prevents race conditions from `.beads/issues.jsonl` modifications. Zero errors after the fix.

2. **Fix is incomplete** - `.kn/entries.jsonl` is also modified during parallel operations (via `kn constrain`, `kn decide`, etc.) and isn't excluded, causing 3 additional errors.

3. **Exclusion should be limited** - Only auto-managed tracking files should be excluded (`.beads/`, `.kn/`), not all uncommitted changes. Other files like `.gitignore`, `bun.lock` represent real uncommitted work that should trigger validation failure.

**Answer to Investigation Question:**

The git validation race condition during parallel completions is caused by incomplete exclusion. The fix at `complete.py:268` correctly excludes `.beads/` but misses `.kn/` which is also modified by the knowledge capture workflow. Expanding the exclusion to `[".beads/", ".kn/"]` will resolve the remaining race conditions.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Analyzed all 110 errors in the error log, tested the exclusion logic directly with Python, verified commit timestamps, and confirmed the fix behavior with unit tests.

**What's certain:**

- ✅ `.beads/` exclusion works - zero `.beads/` errors after fix was applied at 22:14 UTC
- ✅ `.kn/` is the missing exclusion - 3 errors specifically cite `.kn/entries.jsonl`
- ✅ Exclusion logic is sound - tested directly that `startswith()` correctly matches paths

**What's uncertain:**

- ⚠️ Other tracking directories might emerge - future tools may introduce similar race conditions
- ⚠️ Long-term error rate unknown - need to monitor for 7+ days after fix

**What would increase confidence to 100%:**

- Monitor error rates for 7 days after fix deployment
- Zero `.kn/` related errors after this fix

---

## Implementation Recommendations

### Recommended Approach ⭐

**Expand exclude_files to include `.kn/`** - One-line change to add `.kn/` to the existing exclusion list.

**Why this approach:**
- Minimal code change with maximum impact
- Follows same pattern as existing `.beads/` exclusion
- Addresses 3 additional race condition errors

**Trade-offs accepted:**
- Requires `kn sync` to be run separately to commit knowledge changes
- Acceptable because this is the intended workflow (same as `bd sync` for beads)

**Implementation sequence:**
1. Update `complete.py:268` to add `.kn/` - already done
2. Add test for `.kn/` exclusion - already done
3. Run tests to verify - already done

### Alternative Approaches Considered

**Option B: Parse .gitignore to exclude all ignored files**
- **Pros:** Automatically handles any future tracking directories
- **Cons:** Adds complexity, may exclude files that should be validated
- **When to use instead:** If more tracking tools are added frequently

**Rationale for recommendation:** Direct exclusion is simpler, more predictable, and matches the existing pattern.

---

## References

**Files Examined:**
- `src/orch/complete.py:265-272` - Git validation call with exclude_files
- `src/orch/git_utils.py:227-352` - validate_work_committed implementation
- `~/.orch/errors.jsonl` - 110 error entries for pattern analysis

**Commands Run:**
```bash
# Analyze errors by type
python3 -c "import json; ..." # Count .beads/ and .kn/ errors

# Test exclusion logic
python3 -c "# Test startswith logic..."

# Run tests
python3 -m pytest tests/test_complete.py -v -k "exclude"
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` - Prior investigation identifying 74% git validation errors

---

## Investigation History

**2025-12-09 21:30:** Investigation started
- Initial question: Why does git validation fail during parallel completions even with `.beads/` exclusion?
- Context: Prior investigation identified 110 daily errors, 74% from git validation

**2025-12-09 21:45:** Verified `.beads/` exclusion works
- Tested exclusion logic directly with Python
- Confirmed all 47 `.beads/` errors occurred BEFORE the fix (f968a94)
- Zero `.beads/` errors after fix applied at 22:14 UTC

**2025-12-09 22:00:** Found `.kn/` as remaining issue
- 3 errors cite `.kn/entries.jsonl` being uncommitted
- Current exclusion list only has `.beads/`, missing `.kn/`
- Implemented fix: expanded exclusion to `[".beads/", ".kn/"]`

**2025-12-09 22:10:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Added `.kn/` to exclude_files, added unit test, all tests passing
