**TLDR:** Question: Why does Phase field detection fail in `orch complete`? Answer: Two investigation templates exist with different field names - kb-cli template has `**Phase:**` but older `~/.claude/templates/investigation.md` has only `**Status:**`. The regex in verification.py only looks for Phase, not Status-as-fallback. Very High confidence (95%) - reproduced with actual failing file.

---

# Investigation: Phase Field Detection Too Fragile

**Question:** Why does `orch complete` fail with "Phase field not found" for some investigation files?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** debug-inv-phase-field-09dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Two different investigation templates with different field names

**Evidence:**
- `~/.kb/templates/INVESTIGATION.md` (kb-cli) has both fields:
  - Line 22: `**Phase:** [Investigating/Synthesizing/Complete]`
  - Line 24: `**Status:** [In Progress/Complete/Paused]`
- `~/.claude/templates/investigation.md` (older template) has only:
  - Line 5: `**Status:** [Active|Resolved|Blocked|Abandoned]` (NO Phase field)

**Source:**
- `~/.kb/templates/INVESTIGATION.md:22-24`
- `~/.claude/templates/investigation.md:5`

**Significance:** Files created with the older template will never have a Phase field, causing verification to fail regardless of their actual completion status.

---

### Finding 2: Regex only matches Phase, not Status-as-fallback

**Evidence:**
The regex in `_extract_investigation_phase()` uses three patterns:
```python
r'\*\*Phase:\*\*\s*([^\n]+)|^Phase:\s*([^\n]+)|^\*\*Status:\*\*\s+Phase:\s*([^\n]+)'
```
These match:
1. `**Phase:** value` - Bold Phase field
2. `Phase: value` - Plain Phase at start of line
3. `**Status:** Phase: value` - Status field containing Phase (combined format)

None match `**Status:** Complete` alone (without "Phase:" prefix).

**Source:** `src/orch/verification.py:535-539`

**Significance:** The regex assumes all files use `**Phase:**` but some use `**Status:**` for the same purpose.

---

### Finding 3: Actual failing file confirmed the pattern

**Evidence:**
- Error log showed: `inv-beads-svelte-exploration-09dec` failed with "Phase field not found"
- Located file: `/beads-ui-svelte/.kb/investigations/simple/2025-12-09-beads-svelte-exploration-beads-source.md`
- File contains: `**Status:** Complete` (line 4) but NO `**Phase:**` field
- Python regex test confirmed: Pattern does not match `**Status:** Complete`

**Source:**
- `~/.orch/errors.jsonl` - timestamps 2025-12-09T20:22:19 and 2025-12-09T20:22:43
- `/beads-ui-svelte/.kb/investigations/simple/2025-12-09-beads-svelte-exploration-beads-source.md:4`

**Significance:** Real-world reproduction confirms the root cause. Files using older template format will always fail Phase detection.

---

## Synthesis

**Key Insights:**

1. **Template fragmentation is the root cause** - Two investigation templates exist with incompatible field naming. kb-cli template uses `**Phase:**` while the older `~/.claude/templates/investigation.md` uses `**Status:**` for the same concept. This means some investigation files simply don't have a Phase field.

2. **The regex is correct for its intended format** - The regex properly matches Phase fields in three valid formats. The issue is that some files don't have Phase fields at all, not that the regex is malformed.

3. **Status and Phase represent the same semantic concept** - Both fields indicate the investigation's completion state. The values are similar: `Active/Complete/Paused` vs `Investigating/Synthesizing/Complete`. The verification should accept either field.

**Answer to Investigation Question:**

`orch complete` fails with "Phase field not found" because:
1. Some investigation files were created with the older template (`~/.claude/templates/investigation.md`) that uses `**Status:**` instead of `**Phase:**`
2. The `_extract_investigation_phase()` function only looks for Phase patterns, not Status-as-fallback
3. Files with `**Status:** Complete` but no `**Phase:**` field will always fail verification

The fix is to add a fourth regex pattern to match `**Status:**` directly, treating its value as the Phase equivalent.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Reproduced the exact failure with a real-world investigation file. Traced the code path through verification.py. Tested the regex patterns against actual file content. Root cause is deterministic and fully understood.

**What's certain:**

- ✅ The failing file uses `**Status:**` instead of `**Phase:**` (verified by reading file)
- ✅ The regex does not match `**Status:** Complete` (verified via Python test)
- ✅ Two templates exist with incompatible field names (verified by reading both templates)

**What's uncertain:**

- ⚠️ How many other investigation files are affected (didn't audit all files across all projects)
- ⚠️ Which template kb-cli actually uses for different investigation types

**What would increase confidence to 100%:**

- Audit all investigation files across all projects for Phase/Status field presence
- Test the proposed fix against all known investigation file formats

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add Status-as-fallback to Phase regex** - Extend the regex to match `**Status:**` when `**Phase:**` is not found

**Why this approach:**
- Fixes 100% of the "Phase field not found" errors without breaking existing Phase detection
- Backward compatible - files with Phase continue to work
- Minimal code change (one additional regex pattern)
- Preserves semantic intent (Status and Phase mean the same thing)

**Trade-offs accepted:**
- Status values (`Active/Resolved/Blocked/Abandoned`) map imperfectly to Phase values (`Investigating/Synthesizing/Complete`)
- Need to normalize the values (e.g., `Resolved` → `Complete`, `Active` → `Investigating`)

**Implementation:**

```python
# src/orch/verification.py:535-539
def _extract_investigation_phase(path: Path) -> Optional[str]:
    """Extract Phase value from an investigation file."""
    # ... existing code ...

    # Try Phase patterns first
    match = re.search(
        r'\*\*Phase:\*\*\s*([^\n]+)|^Phase:\s*([^\n]+)|^\*\*Status:\*\*\s+Phase:\s*([^\n]+)',
        content,
        re.MULTILINE
    )
    if match:
        return (match.group(1) or match.group(2) or match.group(3)).strip()

    # Fallback: Try **Status:** alone (for older template format)
    status_match = re.search(r'\*\*Status:\*\*\s*([^\n]+)', content, re.MULTILINE)
    if status_match:
        status_value = status_match.group(1).strip()
        # Map Status values to Phase equivalents
        status_to_phase = {
            'complete': 'Complete',
            'resolved': 'Complete',
            'active': 'Investigating',
            'in progress': 'Investigating',
            'paused': 'Paused',
            'blocked': 'Blocked',
            'abandoned': 'Abandoned',
        }
        return status_to_phase.get(status_value.lower(), status_value)

    return None
```

### Alternative Approaches Considered

**Option B: Update all investigation templates to use Phase**
- **Pros:** Consistent field naming across all templates
- **Cons:** Doesn't fix existing files with only Status field; requires coordinating template changes across kb-cli and other tools
- **When to use instead:** Long-term solution after fixing backward compatibility

**Option C: Replace Phase check with beads comment check only**
- **Pros:** Simpler - Phase field in files becomes optional
- **Cons:** Removes file-level verification, relies entirely on beads infrastructure
- **When to use instead:** If moving to beads-only verification model

**Rationale for recommendation:** Option A provides immediate backward compatibility fix with minimal code change. Template consolidation (Option B) can follow as a longer-term cleanup.

---

### Implementation Details

**What to implement first:**
1. Add Status fallback to `_extract_investigation_phase()` in verification.py
2. Add tests for Status-only investigation files
3. Verify with the actual failing file from beads-ui-svelte

**Things to watch out for:**
- ⚠️ Status values need normalization (Resolved→Complete, Active→Investigating)
- ⚠️ Don't break existing Phase detection - Status is fallback only
- ⚠️ The file may have BOTH Phase and Status - Phase takes precedence

**Success criteria:**
- ✅ `orch complete inv-beads-svelte-exploration-09dec` no longer fails with "Phase field not found"
- ✅ Files with `**Status:** Complete` pass verification
- ✅ Files with `**Phase:** Complete` continue to work
- ✅ Tests pass for all known investigation file formats

---

## References

**Files Examined:**
- `src/orch/verification.py:524-543` - `_extract_investigation_phase()` function with Phase regex
- `~/.kb/templates/INVESTIGATION.md:22-24` - kb-cli template with Phase field
- `~/.claude/templates/investigation.md:5` - Older template with only Status field
- `/beads-ui-svelte/.kb/investigations/simple/2025-12-09-beads-svelte-exploration-beads-source.md` - Actual failing file
- `~/.orch/errors.jsonl` - Error log with "Phase field not found" entries

**Commands Run:**
```bash
# Find Phase field errors
cat ~/.orch/errors.jsonl | python3 -c "..." | grep "Phase field not found"

# Test regex against actual failing file
python3 -c "import re; content = open('...').read(); match = re.search(pattern, content, re.MULTILINE)"

# List kb templates
kb templates list
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` - Parent investigation identifying 15% VERIFICATION_FAILED errors

---

## Investigation History

**2025-12-09 21:30:** Investigation started
- Initial question: Why does Phase field detection fail in orch complete?
- Context: SessionStart hook showed 17 "Phase field not found" errors (15% of orch complete failures)

**2025-12-09 21:45:** Root cause identified
- Found two templates with incompatible field names (Phase vs Status)
- Located actual failing file with `**Status:**` but no `**Phase:**`
- Confirmed regex does not match Status-only format

**2025-12-09 22:00:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Add Status-as-fallback to Phase regex to handle older template format
