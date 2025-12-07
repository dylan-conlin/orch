**TLDR:** Question: What WORKSPACE.md dependencies remain and how do we complete the convergence to beads comments? Answer: WORKSPACE.md creation was already removed; the `requires_workspace` flag was misnamed (controls coordination instructions, not file creation). Renamed to `beads_only`, removed dead code, kept legacy reading for backwards compatibility. Implementation complete.

---

# Investigation: Single Coordination Mechanism - Converge on Beads Comments

**Question:** What code still references WORKSPACE.md and how do we complete the convergence to beads comments as the sole coordination mechanism?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (95%)

---

## Findings

### Finding 1: WORKSPACE.md creation already removed, but flag name is misleading

**Evidence:** Prior decision (2025-12-06-eliminate-workspace-md.md) documents removal of WORKSPACE.md creation. However, `SpawnConfig.requires_workspace` still exists with outdated comment:
```python
requires_workspace: bool = True  # Whether WORKSPACE.md is the coordination artifact
```

Current behavior:
- `requires_workspace=True` → Uses beads comments for coordination
- `requires_workspace=False` → Uses investigation file as primary artifact

Neither creates WORKSPACE.md files.

**Source:** src/orch/spawn.py:314

**Significance:** The flag name causes confusion. It should be renamed to reflect its actual purpose: choosing between beads comments vs investigation file for coordination.

---

### Finding 2: Dead code in spawn_prompt.py

**Evidence:** Variables defined but never used:
```python
workspace_file = workspace_path / "WORKSPACE.md"
workspace_check_path = f"{workspace_path}/WORKSPACE.md"
```

These were used when WORKSPACE.md was checked/created, but now they're orphaned.

**Source:** src/orch/spawn_prompt.py:738-739

**Significance:** Dead code that should be removed for clarity.

---

### Finding 3: Legacy WORKSPACE.md reading should be kept

**Evidence:** Two files still read WORKSPACE.md for backwards compatibility:
1. `history.py:62-148` - `extract_skill_from_workspace()` reads old WORKSPACE.md for analytics
2. `cli.py:1365-1382` - Scans for WORKSPACE.md files in `orch context` command

These handle legacy workspaces created before the migration.

**Source:** src/orch/history.py:74, src/orch/cli.py:1371

**Significance:** Should be kept for backwards compatibility with existing workspaces. Mark as legacy but don't remove.

---

## Synthesis

**Key Insights:**

1. **Migration is 95% complete** - WORKSPACE.md creation was already removed; only cleanup remains

2. **Naming is the main issue** - `requires_workspace` no longer means "requires WORKSPACE.md file"; it means "use beads for direct coordination vs investigation file as artifact"

3. **Backwards compatibility matters** - Legacy reading code should stay to support old workspaces

**Answer to Investigation Question:**

The convergence is nearly complete. Three changes needed:
1. Rename `requires_workspace` to `coordination_via_beads` (or similar) to reflect actual behavior
2. Remove dead code in spawn_prompt.py (unused variables)
3. Keep legacy WORKSPACE.md reading with deprecation comments

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?** Clear code paths identified, prior decision documents the context, changes are localized.

**What's certain:**

- ✅ WORKSPACE.md creation was already removed (verified via prior decision)
- ✅ `requires_workspace` flag is misnamed (checked actual usage)
- ✅ spawn_prompt.py has dead code (variables never used)

**What's uncertain:**

- ⚠️ Whether renaming `requires_workspace` affects external tools (need to check)
- ⚠️ Test coverage for the rename

---

## Implementation Recommendations

### Recommended Approach ⭐

**Rename and clean** - Rename `requires_workspace` to `coordination_via_beads` and remove dead code.

**Why this approach:**
- Eliminates confusion from misleading name
- Removes unused variables
- Keeps backwards compatibility for legacy workspaces

**Implementation sequence:**
1. Rename `requires_workspace` → `coordination_via_beads` in spawn.py SpawnConfig
2. Update all usages in spawn.py, spawn_prompt.py, tests
3. Remove dead variables in spawn_prompt.py (lines 738-739)
4. Update comment in spawn.py to describe actual behavior
5. Run tests to verify no regressions

---

## References

**Files Examined:**
- src/orch/spawn.py - SpawnConfig definition and usage
- src/orch/spawn_prompt.py - Coordination instructions generation
- src/orch/history.py - Legacy WORKSPACE.md reading
- src/orch/cli.py - Legacy workspace scanning
- .kb/decisions/2025-12-06-eliminate-workspace-md.md - Prior decision

**Related Artifacts:**
- **Decision:** .kb/decisions/2025-12-06-eliminate-workspace-md.md - Documents WORKSPACE.md removal
- **Investigation:** .kb/investigations/2025-12-06-eliminate-workspace-entirely-from-orch.md - Prior investigation

---

## Implementation Results

**Changes Made:**

1. **Renamed `requires_workspace` → `beads_only`** in SpawnConfig (spawn.py:314)
   - New comment: `True = use beads comments only, False = use investigation file as primary artifact`
   - Updated all usages in spawn.py (lines 1168, 1182, 2060, 2087)

2. **Removed dead code in spawn_prompt.py** (lines 738-739)
   - Removed unused variables: `workspace_file` and `workspace_check_path`
   - These were orphaned after WORKSPACE.md creation was removed

3. **Updated spawn_prompt.py** to use `beads_only` (lines 740, 781-785, 986)

4. **Updated test files:**
   - tests/test_spawn_prompt.py (3 occurrences)
   - tests/test_kb_path_migration.py (1 occurrence)
   - tests/e2e/test_spawn_context.py (4 occurrences)

5. **Kept legacy WORKSPACE.md reading** for backwards compatibility:
   - history.py - reads old WORKSPACE.md for analytics
   - cli.py - scans for WORKSPACE.md in orch context command

**Tests Verified:**
- All spawn_prompt tests pass (21 tests)
- All kb_path_migration tests pass (12 tests)
- All e2e/test_spawn_context tests pass (16 tests)

---

## Investigation History

**2025-12-06:** Investigation started
- Initial question: What WORKSPACE.md dependencies remain?
- Context: Converge on beads comments as only coordination mechanism

**2025-12-06:** Found prior work already done
- WORKSPACE.md creation removed in prior session
- Remaining work is cleanup: rename flag, remove dead code

**2025-12-06:** Implementation complete
- Renamed `requires_workspace` → `beads_only`
- Removed dead code (unused WORKSPACE.md variables)
- All relevant tests passing
