**TLDR:** Why are status changes from `reconcile()` being discarded? Root cause: `_merge_agents` uses `spawned_at` for conflict resolution, but `spawned_at` is identical for both disk and in-memory versions (set once at registration), so disk always wins. Fix: use `updated_at` timestamp that reflects when the agent was last modified.

---

# Investigation: Fix Registry Merge Logic Bug

**Question:** Why are status changes from `reconcile()` being discarded when `save()` is called?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Findings

### Finding 1: `_merge_agents` uses `spawned_at` for conflict resolution

**Evidence:**
```python
# registry.py:117-122
current_ts = current_agent.get('spawned_at', '')
our_ts = our_agent.get('spawned_at', '')
if current_ts >= our_ts:
    merged[agent_id] = current_agent
else:
    merged[agent_id] = our_agent
```

**Source:** `src/orch/registry.py:117-122`

**Significance:** The merge logic intends to use "newer wins" semantics, but `spawned_at` is set once at registration and never changes. This means for the same agent, both disk and in-memory versions have identical `spawned_at` values.

---

### Finding 2: `spawned_at` equality causes disk to always win

**Evidence:** When comparing identical timestamps, `current_ts >= our_ts` evaluates to `True` (string equality in >= comparison). Since both versions have the same `spawned_at`, the disk version (`current_agent`) always wins.

**Source:** `src/orch/registry.py:119-120`

**Significance:** This is the root cause of the bug. Any in-memory changes (like status updates from `reconcile()`) are discarded because the disk version is always preferred.

---

### Finding 3: Status changes happen in multiple places without timestamp update

**Evidence:** Status is modified in:
- Line 220: `existing_window['status'] = 'abandoned'` (in `register`)
- Line 276: `agent['status'] = 'deleted'` (in `remove`)
- Line 288: `agent['status'] = 'abandoned'` (in `abandon_agent`)
- Line 318: `agent['status'] = 'completed'` (in `reconcile`)

None of these update any timestamp that would indicate the record was modified.

**Source:** `src/orch/registry.py` - lines 220, 276, 288, 318

**Significance:** Even if merge logic were fixed, there's no `updated_at` field to track when modifications occurred. This needs to be added alongside the merge fix.

---

## Synthesis

**Key Insights:**

1. **Timestamp comparison logic is correct, but wrong timestamp** - The `>=` comparison for "newer wins" is semantically correct, but using `spawned_at` (creation time) instead of `updated_at` (modification time) defeats the purpose.

2. **Missing `updated_at` field** - The data model lacks a field to track when agents are modified, making proper conflict resolution impossible.

3. **All status mutations need timestamp updates** - Any place that modifies an agent should update `updated_at` to ensure merge logic works correctly.

**Answer to Investigation Question:**

Status changes from `reconcile()` are discarded because `_merge_agents` compares `spawned_at` timestamps, which are identical for both disk and in-memory versions of the same agent. Since `current_ts >= our_ts` evaluates to `True` when timestamps are equal, the disk version always wins, discarding any in-memory modifications. The fix requires: (1) adding an `updated_at` field, (2) updating it on every status change, and (3) using it for merge conflict resolution.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct code analysis confirms the exact mechanism causing the bug. The comparison logic and data flow are clearly documented in the code.

**What's certain:**

- ✅ `_merge_agents` uses `spawned_at` for conflict resolution (lines 117-122)
- ✅ `spawned_at` is set once and never changes (line 232)
- ✅ String comparison `current_ts >= our_ts` returns `True` for equal values
- ✅ This causes disk version to always win over in-memory changes

**What's uncertain:**

- ⚠️ Whether other code depends on the current merge behavior (unlikely but possible)

**What would increase confidence to 100%:**

- Unit test demonstrating the bug before fix
- Integration test confirming fix works end-to-end

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add `updated_at` field and use it for merge conflict resolution**

**Why this approach:**
- Semantic correctness: `updated_at` represents when record was modified, which is what we want to compare
- Minimal code change: Only affects registry.py
- Backwards compatible: Existing agents without `updated_at` will default to `spawned_at`

**Trade-offs accepted:**
- Slightly more disk I/O from updating timestamp on every modification
- Why acceptable: The registry is small and modifications are infrequent

**Implementation sequence:**
1. Add `updated_at` field in `register()` method - set to same value as `spawned_at`
2. Update `updated_at` in all status modification points (reconcile, remove, abandon_agent, register window conflict)
3. Change `_merge_agents` to use `updated_at` with fallback to `spawned_at` for backwards compatibility

### Alternative Approaches Considered

**Option B: Field-level merging**
- **Pros:** More sophisticated conflict resolution
- **Cons:** Complex implementation, might merge incompatible states
- **When to use instead:** When agents have independent fields modified by different processes

**Option C: Skip merge entirely on status changes**
- **Pros:** Simple to implement
- **Cons:** Could lose concurrent modifications from other processes
- **When to use instead:** Never - we want proper concurrent access

**Rationale for recommendation:** Option A (updated_at) provides clean last-writer-wins semantics with minimal code change and full backwards compatibility.

---

## References

**Files Examined:**
- `src/orch/registry.py` - Main registry module with merge logic

**Commands Run:**
```bash
# Find status modification points
grep -n "agent\['status'\] =" src/orch/registry.py
```

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: Why are reconcile() status changes discarded?
- Context: Evidence showed 127 'active' agents in registry but only 6 have valid tmux windows

**2025-12-12:** Root cause identified
- `_merge_agents` uses `spawned_at` which is identical for both versions
- Disk always wins due to `>=` comparison with equal values

**2025-12-12:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Fix requires adding `updated_at` field and using it for merge resolution
