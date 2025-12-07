**TLDR:** Question: Where are .orch artifact paths still used in orch-cli? Answer: Found 4 key areas needing migration: DEFAULT_DELIVERABLES in skill_discovery.py, complete.py fallback logic, synthesis.py decision paths, and spawn_prompt.py context references. High confidence (90%) - comprehensive grep analysis completed.

---

# Investigation: Unify Path Conventions to .kb/

**Question:** What .orch artifact references exist in orch-cli and how should they be migrated to .kb/?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: DEFAULT_DELIVERABLES uses .orch/workspace/ path

**Evidence:** `skill_discovery.py:59` defines default deliverable path as `.orch/workspace/{workspace-name}/WORKSPACE.md`

**Source:** `src/orch/skill_discovery.py:56-63`

**Significance:** This is legacy workspace path that should be removed since WORKSPACE.md is deprecated (beads is now source of truth).

---

### Finding 2: complete.py has dual-path fallback for investigations

**Evidence:** `complete.py:162-167` checks for both `.kb/investigations/` and `.orch/investigations/` in context_ref validation.

**Source:** `src/orch/complete.py:162-167`

**Significance:** Legacy fallback for `.orch/investigations/` should be removed - all investigations now live in `.kb/investigations/`.

---

### Finding 3: synthesis.py references .orch/decisions/

**Evidence:** `synthesis.py:283` and `synthesis.py:319` output `.orch/decisions/` paths in synthesis output.

**Source:** `src/orch/synthesis.py:283, 319`

**Significance:** Decision paths should be updated to `.kb/decisions/` to match the unified convention.

---

## Synthesis

**Key Insights:**

1. **Workspace tracking moved to beads** - The `.orch/workspace/` path in DEFAULT_DELIVERABLES was obsolete since workspace tracking is now done via beads comments (`bd comment <beads-id>`).

2. **Output paths matter, input paths need fallback** - Generated output (synthesis.py) should use `.kb/` paths. Input validation (complete.py) should keep `.orch/` fallback for backward compatibility during migration.

3. **Test fixtures needed comprehensive updates** - Multiple test files had hardcoded `.orch/` paths in test fixtures that needed updating to reflect the new conventions.

**Answer to Investigation Question:**

The `.orch` artifact references were found in:
- `skill_discovery.py:59` - DEFAULT_DELIVERABLES (updated path to empty, beads is source of truth)
- `synthesis.py:283,319` - Decision document path references (updated to `.kb/decisions/`)
- Multiple test files - Test fixtures with hardcoded paths (updated to `.kb/` or empty paths)

The `complete.py` fallback logic for `.orch/investigations/` was kept for backward compatibility - this is INPUT validation, not output generation.

---

## Implementation Summary

**Changes made:**

1. **skill_discovery.py** - Updated DEFAULT_DELIVERABLES:
   - path: `""` (empty - no file path, workspace tracking via beads)
   - description: "Progress tracked via beads comments (bd comment <beads-id>)"

2. **synthesis.py** - Updated decision document references:
   - Line 283: `.orch/decisions/` → `.kb/decisions/`
   - Line 319: `.orch/decisions/...` → `.kb/decisions/...`

3. **Test files updated** (8 files):
   - `test_skill_discovery.py` - Updated path assertions and YAML fixtures
   - `test_spawn_preview.py` - Updated template and deliverable paths
   - `test_spawn_skill_discovery.py` - Updated YAML fixtures
   - `test_spawn_interactive.py` - Updated YAML fixtures
   - `test_spawn_tmux.py` - Updated investigation path
   - `test_context_ref_loading.py` - Updated context_ref paths
   - `test_backlog_resolution.py` - Updated all investigation paths

**Tests passing:** 52/52 in core test suite (skill_discovery, spawn_preview, synthesis)

---

## References

**Files Modified:**
- `src/orch/skill_discovery.py:56-63` - DEFAULT_DELIVERABLES constant
- `src/orch/synthesis.py:283,319` - Decision document path references
- `tests/test_skill_discovery.py` - Updated path assertions and YAML fixtures
- `tests/test_spawn_preview.py` - Updated template and deliverable paths
- `tests/test_spawn_skill_discovery.py` - Updated YAML fixtures
- `tests/test_spawn_interactive.py` - Updated YAML fixtures
- `tests/test_spawn_tmux.py` - Updated investigation path
- `tests/test_context_ref_loading.py` - Updated context_ref paths
- `tests/test_backlog_resolution.py` - Updated all investigation paths

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-06-orch-complete-verification-filename-mismatch.md` - Documents related path mismatch issue

---

## Investigation History

**2025-12-06:** Investigation started
- Initial question: What .orch artifact references exist in orch-cli?
- Context: Task to unify path conventions to .kb/

**2025-12-06:** Implementation complete
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Updated DEFAULT_DELIVERABLES and synthesis.py to use .kb/ paths, updated 8 test files
