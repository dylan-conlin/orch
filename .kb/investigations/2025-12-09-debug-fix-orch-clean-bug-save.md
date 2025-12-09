**TLDR:** Why does `orch clean` fail with `save() got unexpected keyword argument 'skip_merge'`? The `registry.save()` method at `registry.py:50` was never updated to accept the `skip_merge` parameter that `cli.py:327` passes. High confidence (95%) - direct code examination confirms the mismatch.

---

# Investigation: Fix orch clean bug - save() got unexpected keyword argument 'skip_merge'

**Question:** Why does `orch clean` fail with `save() got unexpected keyword argument 'skip_merge'`?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: cli.py passes skip_merge parameter that doesn't exist

**Evidence:**
```python
# cli.py:324-327
# Save registry (skip merge to prevent re-adding removed agents)
# Bug fix: Merge logic would re-add deleted agents from disk
# Investigation: .orch/investigations/2025-11-17-investigate-from-roadmap-resume-failure.md
registry.save(skip_merge=True)
```

**Source:** `src/orch/cli.py:327`

**Significance:** The clean command intentionally wants to skip merge logic, but the parameter was never implemented in `save()`.

---

### Finding 2: registry.save() has no skip_merge parameter

**Evidence:**
```python
# registry.py:50-51
def save(self):
    """Persist registry to disk with exclusive lock and merge logic."""
```

The method signature only has `self` - no `skip_merge` parameter.

**Source:** `src/orch/registry.py:50`

**Significance:** Direct cause of the error - the method signature doesn't match the call site.

---

### Finding 3: Intent is to skip merge logic that re-adds deleted agents

**Evidence:** The merge logic at lines 79 re-reads current agents from disk and merges:
```python
# Line 70-79
# Re-read and merge to prevent concurrent overwrites
f.seek(0)
content = f.read()
if content.strip():
    current_data = json.loads(content)
    current_agents = current_data.get('agents', [])
else:
    current_agents = []

merged_agents = self._merge_agents(current_agents, self._agents)
```

The `_merge_agents` method (lines 91-122) re-adds agents from disk if they're not in the in-memory list, which would undo deletions.

**Source:** `src/orch/registry.py:70-122`

**Significance:** The merge logic is designed for concurrent safety but conflicts with deletion operations. Skipping merge for delete operations is the correct approach.

---

## Synthesis

**Key Insights:**

1. **Incomplete implementation** - The `skip_merge` feature was designed (per comments) but never implemented in `registry.save()`.

2. **Correct intent** - The clean command correctly identifies that merge logic would re-add deleted agents, defeating the purpose of cleaning.

3. **Simple fix** - Add `skip_merge=False` parameter to `save()` and conditionally skip `_merge_agents()`.

**Answer to Investigation Question:**

The bug occurs because `cli.py:327` calls `registry.save(skip_merge=True)` but `registry.save()` at `registry.py:50` only accepts `self`. The fix is to add the `skip_merge` parameter to the method signature and conditionally skip the merge logic when `skip_merge=True`.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct code examination shows exact mismatch between call site and method signature. The intent is clearly documented in comments.

**What's certain:**

- ✅ `cli.py:327` passes `skip_merge=True`
- ✅ `registry.py:50` defines `save(self)` with no `skip_merge` parameter
- ✅ The fix is straightforward - add the parameter and conditional logic

**What's uncertain:**

- ⚠️ Whether any other callers of `save()` might be affected (low risk - adding default `skip_merge=False` preserves existing behavior)

**What would increase confidence to 100%:**

- Running the actual test to reproduce the error
- Running tests after the fix

---

## Implementation Recommendations

### Recommended Approach: Add skip_merge parameter

**Why this approach:**
- Preserves existing behavior (default `skip_merge=False`)
- Matches documented intent in comments
- Single line change to method signature, minimal logic change

**Implementation:**
1. Change `def save(self):` to `def save(self, skip_merge: bool = False):`
2. Conditionally skip `_merge_agents` when `skip_merge=True`
3. Run tests to verify

---

## References

**Files Examined:**
- `src/orch/cli.py:324-327` - Call site with skip_merge=True
- `src/orch/registry.py:50-122` - save() method and merge logic

**Commands Run:**
```bash
# Find skip_merge references
rg "save.*skip_merge|skip_merge"

# Find save and clean definitions
rg "def clean|def save|orch clean" src/
```

---

## Investigation History

**2025-12-09 15:30:** Investigation started
- Initial question: Why does orch clean fail with save() unexpected keyword argument?
- Context: Bug report from orch error logs

**2025-12-09 15:32:** Root cause identified
- Found mismatch between cli.py:327 call and registry.py:50 signature
- Confirmed intent via comments at cli.py:324-326

**2025-12-09 15:33:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Simple fix - add skip_merge parameter to save() method
