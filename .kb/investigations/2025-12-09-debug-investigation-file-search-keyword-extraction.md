**TLDR:** Question: Why doesn't `_search_investigation_file` find files when agents use wrong prefix (e.g., `inv-` vs `debug-`)? Answer: Current search uses exact workspace name matching, but agents may use different naming conventions. Fix: Extract core keywords from workspace name and search by today's date + keyword combinations. High confidence (90%) - direct code analysis with concrete failing example.

---

# Investigation: File Search Keyword Extraction

**Question:** Why does `_search_investigation_file` fail to find files when workspace name differs from investigation file name?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Current search uses exact workspace name pattern

**Evidence:**
```python
# verification.py:404-413
for pattern in [
    f"**/*{workspace_name}*.md",
    f"**/{today}-*{workspace_name}*.md",
    f"*{workspace_name}*.md",
    f"{today}-*{workspace_name}*.md",
]:
```

Current search tries patterns like `**/*debug-orch-end-race-condition-09dec*.md` which won't match `inv-orch-end-race-condition-exit.md`.

**Source:** `src/orch/verification.py:404-413`

**Significance:** When workspace name is `debug-X` but file is `inv-X`, exact substring matching fails.

---

### Finding 2: Date suffix stripping is too narrow

**Evidence:**
```python
# verification.py:415-427
if '-' in workspace_name:
    parts = workspace_name.rsplit('-', 1)
    if len(parts[1]) <= 5:  # Likely a date suffix
        base_name = parts[0]
```

This strips `-09dec` from `debug-orch-end-race-condition-09dec` to get `debug-orch-end-race-condition`, but:
1. Still includes prefix (`debug-`)
2. Doesn't extract individual keywords
3. Won't match files that use different prefix (`inv-`)

**Source:** `src/orch/verification.py:415-427`

**Significance:** The fallback logic helps with date suffixes but doesn't address prefix mismatches.

---

### Finding 3: Concrete failing case demonstrates the gap

**Evidence:**
- Workspace: `debug-orch-end-race-condition-09dec`
- Expected file: `.kb/investigations/2025-12-09-debug-orch-end-race-condition-exit.md`
- Actual file: `.kb/investigations/2025-12-09-inv-orch-end-race-condition-exit.md`

Search patterns tried:
- `**/*debug-orch-end-race-condition-09dec*.md` - no match (file uses `inv-`)
- `**/*debug-orch-end-race-condition*.md` - no match (file uses `inv-`)

What would match:
- Search for `*2025-12-09*orch*end*race*condition*.md` - would find the file

**Source:** Orchestrator's error summary and file listing

**Significance:** Core keywords (`orch`, `end`, `race`, `condition`) are present in both names. Keyword-based search would find the file.

---

## Synthesis

**Key Insights:**

1. **Workspace and file prefixes diverge** - Agents may use `inv-` when spawned with `debug-` or vice versa, because the prefix is a human convention not enforced by tooling.

2. **Core keywords are preserved** - Despite prefix differences, the meaningful keywords (`orch`, `end`, `race`, `condition`) are always present in both workspace name and investigation file.

3. **Keyword-based search is robust fallback** - Extracting 2+ keywords and matching today's files reliably finds the correct investigation even with prefix mismatches.

**Answer to Investigation Question:**

The search fails because it relies on exact substring matching of the workspace name, which doesn't account for prefix variations. Fix: add keyword extraction that strips common prefixes (debug, inv, fix, etc.) and date suffixes, then search today's files for those that match 2+ keywords.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Direct code analysis with concrete failing case. Fix tested and verified to work.

**What's certain:**

- ✅ Workspace `debug-orch-end-race-condition-09dec` was not finding `inv-orch-end-race-condition-exit.md`
- ✅ Keywords `['orch', 'end', 'race', 'condition']` are correctly extracted
- ✅ New search finds the correct file in testing

**What's uncertain:**

- ⚠️ Edge cases with very short keywords or unusual workspace names
- ⚠️ Performance with many investigation files (currently uses glob + score)

---

## Implementation (Completed)

### Solution Implemented

Added keyword-based search as fallback in `_search_investigation_file()` (`src/orch/verification.py:434-441`).

**New helper functions:**
- `_extract_keywords_from_workspace()` - Extracts meaningful keywords, filtering common prefixes (debug, inv, fix, test, etc.)
- `_search_by_keywords()` - Searches today's files for 2+ keyword matches, returns best match

**Test results:**
```
Workspace: debug-orch-end-race-condition-09dec
Keywords: ['orch', 'end', 'race', 'condition']
Search result: .kb/investigations/2025-12-09-inv-orch-end-race-condition-exit.md
```

**Success criteria:**
- ✅ Workspace with `debug-` prefix finds file with `inv-` prefix
- ✅ Multiple test cases verified working
- ✅ Existing search behavior preserved (exact match tried first)

---

## References

**Files Examined:**
- `src/orch/verification.py:374-429` - Existing `_search_investigation_file` function
- `.kb/investigations/2025-12-06-orch-complete-verification-filename-mismatch.md` - Prior investigation on related issue

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-06-orch-complete-verification-filename-mismatch.md` - Documents the three-way path mismatch issue

---

## Investigation History

**2025-12-09 17:09:** Investigation started
- Initial question: Why doesn't search find files with different prefix?
- Context: orch complete failing with VERIFICATION_FAILED errors

**2025-12-09 17:15:** Root cause identified
- Keywords are preserved but prefixes differ
- Keyword-based search would solve the issue

**2025-12-09 17:20:** Fix implemented and tested
- Added `_extract_keywords_from_workspace()` and `_search_by_keywords()`
- Verified with concrete failing case

**2025-12-09 17:25:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Added keyword-based fallback search that finds files despite prefix mismatches
