**TLDR:** Question: Was the plan to remove agent registry entirely and use beads only? Answer: No - the decided approach was to SIMPLIFY registry (not remove it). Registry keeps minimal tmux window tracking while beads is source of truth for agent state. The recent `registry.find()` fix (adding beads_id lookup) is CONSISTENT with the plan - it bridges the gap between beads IDs and tmux operations. High confidence (95%) - verified against multiple investigations and closed issues.

---

# Investigation: Clarify Registry vs Beads Architecture Direction

**Question:** Was the plan to remove agent registry and use beads only? Does the recent registry.find() fix contradict the plan?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent (orch-cli-l4q)
**Phase:** Complete
**Next Step:** None - investigation complete
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Epic clearly documents the original plan was DELETE registry.py

**Evidence:** The epic `orch-cli-dgy` titled "Epic: Simplify orch-cli from 20K to ~5K lines" explicitly lists registry.py as something to DELETE:

> ## What to DELETE (~7K lines):
> - registry.py (agent state → beads tracks this)
> - complete.py (→ beads auto-close on Phase: Complete)
> - monitoring_commands.py (→ bd show, bd list)
> - beads_integration.py (wrapper unnecessary)
> ...

**Source:** `bd show orch-cli-dgy`, epic description

**Significance:** The original intent was full registry deletion. This establishes the baseline plan.

---

### Finding 2: Implementation took a DIFFERENT path - "Option C" simplification

**Evidence:** The closed issue `orch-cli-nan` documents the actual decision:

> Simplify (not delete) lifecycle modules:
> - complete.py → thin wrapper: verify Phase: Complete, call bd close (~50 lines)
> - **registry.py → minimal agent tracking for tmux windows**
> - monitoring_commands.py → delegate to bd commands where possible
>
> Goal: reduce complexity while keeping orch self-contained (no beads modifications needed).
>
> **Reference: Option C from 2025-12-08 discussion - simpler path avoiding external dependency.**

**Source:** `bd show orch-cli-nan`, closed issue description

**Significance:** The plan EVOLVED. Instead of deleting registry, the decision was to SIMPLIFY it. This is a pivot from the original epic, choosing pragmatism over purity.

---

### Finding 3: Investigation documents 3 registry purposes, only 1 needs local state

**Evidence:** Investigation `2025-12-06-agent-registry-removal-remove-registry.md` identifies:

1. **Agent lookup during session** - hot path for commands - KEEP (simplified)
2. **Tmux reconciliation** - reconcile with window state - KEEP (minimal)
3. **History/analytics** - `get_history()`, `get_analytics()` - REMOVE (beads handles)

The recommendation was "Phased Migration with Beads-First, Registry-Fallback":
> The registry becomes a cache rather than primary storage.

**Source:** `.kb/investigations/2025-12-06-agent-registry-removal-remove-registry.md:180-214`

**Significance:** Registry's role is now clearly scoped: tmux window mapping only. Beads is source of truth for agent state.

---

### Finding 4: Implementation COMPLETED with registry simplified, not deleted

**Evidence:** Investigation `2025-12-08-inv-simplify-lifecycle-modules-registry-minimal.md` documents:

> **2025-12-08 23:30:** Implementation complete
> - complete.py: 1245 → 254 lines (80% reduction)
> - **registry.py: 626 → 298 lines (53% reduction)**
> - monitoring_commands.py: history --analytics now delegates to beads
> - Removed: get_history(), get_analytics(), reconcile_opencode(), complex artifact checking

**Source:** `.kb/investigations/2025-12-08-inv-simplify-lifecycle-modules-registry-minimal.md:131-139`

**Significance:** This is the implemented reality. Registry was simplified, not removed.

---

### Finding 5: Current registry.py docstring confirms the architectural intent

**Evidence:** The current file header states:

```python
"""
Agent Registry - Minimal agent tracking for tmux windows.

Simplified version: tracks agent_id ↔ window_id mapping for tmux operations.
Beads is the source of truth for agent state and lifecycle.
"""
```

And the class docstring:
```python
"""
Manages persistent state for spawned agents with file locking.

Minimal tracking for tmux window management:
- Agent ID ↔ window_id mapping
- Basic agent metadata (project_dir, beads_id)
- Status tracking (active, completed, abandoned, deleted)
"""
```

**Source:** `src/orch/registry.py:1-28`

**Significance:** The code explicitly documents registry's reduced role. This is the canonical definition.

---

### Finding 6: The registry.find() fix is CONSISTENT with the plan

**Evidence:** The recent commit `f055a1e` added beads_id lookup to `registry.find()`:

```python
def find(self, agent_id: str) -> Dict[str, Any] | None:
    """Find agent by ID or beads_id."""
    # First, try exact match on agent ID (workspace name)
    for agent in self._agents:
        if agent['id'] == agent_id:
            return agent

    # Second, try match on beads_id
    for agent in self._agents:
        if agent.get('beads_id') == agent_id:
            return agent

    return None
```

**Source:** `git log -1 -p -- src/orch/registry.py`, commit f055a1e

**Significance:** This fix BRIDGES beads (source of truth) with registry (tmux operations). It allows `orch complete <beads-id>` to find the right tmux window. This is exactly what the simplified architecture requires.

---

## Synthesis

**Key Insights:**

1. **The plan evolved from "delete" to "simplify"** - The original epic said delete registry.py. The actual implementation (Option C) simplified it instead. This was a pragmatic choice to avoid modifying beads externally.

2. **Registry's role is now well-defined** - Registry handles ONLY tmux window ↔ agent_id mapping. Beads is source of truth for agent lifecycle (status, completion, history).

3. **The recent fix is CORRECT behavior** - Adding beads_id lookup to `registry.find()` is consistent with the architecture: it allows beads-based operations to work with tmux windows.

**Answer to Investigation Question:**

**No, the plan was NOT to remove registry entirely.** The final decision (Option C, per orch-cli-nan) was to:
- SIMPLIFY registry to minimal tmux tracking (~300 lines)
- Make beads source of truth for agent state
- Keep orch self-contained (no external beads modifications needed)

**The recent registry.find() fix does NOT contradict the plan.** It's an essential bridge between beads IDs and tmux operations. Without it, `orch complete <beads-id>` couldn't find the tmux window to close.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Multiple closed issues, completed investigations, and actual code all tell the same story. The architecture is documented, implemented, and working.

**What's certain:**

- ✅ Original epic said "delete registry.py"
- ✅ Actual implementation (Option C) simplified instead of deleted
- ✅ registry.py docstrings explicitly define its minimal role
- ✅ beads is documented as source of truth for agent lifecycle
- ✅ Recent fix is consistent with the bridge pattern between beads and tmux

**What's uncertain:**

- ⚠️ Epic orch-cli-dgy is still "open" even though implementation deviated - may confuse future readers
- ⚠️ Whether the original "delete" intent should be revisited later

**What would increase confidence to 100%:**

- Update epic orch-cli-dgy to reflect the Option C decision
- Add explicit documentation linking registry.find() beads_id lookup to the architecture

---

## References

**Files Examined:**
- `src/orch/registry.py` - Current implementation (321 lines)
- `.kb/investigations/2025-12-06-agent-registry-removal-remove-registry.md` - Original registry removal investigation
- `.kb/investigations/2025-12-08-inv-simplify-lifecycle-modules-registry-minimal.md` - Simplification implementation

**Commands Run:**
```bash
# Find beads issues about registry
bd list | grep -i "registry\|simplify"

# Show epic details
bd show orch-cli-dgy

# Show implementation issue
bd show orch-cli-nan

# Check recent registry changes
git log --oneline -- src/orch/registry.py
git log -1 -p -- src/orch/registry.py
```

**Related Artifacts:**
- **Issue:** `orch-cli-dgy` - Epic: Simplify orch-cli (original plan)
- **Issue:** `orch-cli-nan` - Simplify lifecycle modules (implementation)
- **Investigation:** `2025-12-06-agent-registry-removal-remove-registry.md` - Deep dive

---

## Test Performed

**Test:** Traced the commit history and issue trail to verify what was planned vs what was implemented

**Result:**
1. Epic orch-cli-dgy (2025-12-07) said "delete registry.py"
2. Issue orch-cli-nan (2025-12-07) said "simplify, not delete" with "Option C" reference
3. Commit 4befc90 (2025-12-08) titled "refactor: simplify lifecycle modules"
4. Current registry.py has explicit docstrings about minimal tmux role
5. Recent fix f055a1e adds beads_id lookup to bridge beads → tmux

All evidence points to: simplify (not delete), beads as source of truth, registry for tmux only.

---

## Conclusion

The architectural direction is clear and documented:

1. **What was decided:** Simplify registry.py to minimal tmux tracking (~300 lines). Beads is source of truth for agent lifecycle. This was "Option C" - the simpler path avoiding external beads modifications.

2. **Current state:** Registry.py is simplified (626→298 lines). It handles only agent_id ↔ window_id mapping for tmux operations. Beads tracks agent status, completion, and history.

3. **Does recent fix contradict the plan?** NO. The `registry.find()` beads_id lookup is the essential bridge between beads (source of truth) and tmux (window operations). It allows `orch complete <beads-id>` to work correctly.

---

## Self-Review

- [x] Real test performed (traced commits and issues)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-09 12:00:** Investigation started
- Initial question: Was plan to remove registry and use beads only?
- Context: Spawned to clarify architecture direction after recent registry.find() fix

**2025-12-09 12:15:** Evidence gathered
- Read epic orch-cli-dgy, issue orch-cli-nan
- Read two prior investigations about registry
- Examined current registry.py and recent git history

**2025-12-09 12:25:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Plan was SIMPLIFY (not delete) registry. Recent fix is consistent with the architecture.
