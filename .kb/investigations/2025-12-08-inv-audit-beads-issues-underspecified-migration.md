**TLDR:** Question: Which issues in the simplification epic assume simple deletion but have hidden dependencies? Answer: Found 3 severely underspecified issues (nan, yno, ao0) with hidden dependencies, plus 3 missing prerequisite tasks that should be tracked as blockers. High confidence (90%) - validated with grep analysis and code examination.

---

# Investigation: Audit Beads Issues for Underspecified Migration Paths

**Question:** Which issues assume simple deletion but have hidden dependencies? Which need prerequisites not tracked as blockers?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker (spawned from orch-cli-c9o)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: orch-cli-nan (Delete lifecycle modules) is severely underspecified

**Evidence:**
- complete.py is 1244 lines with 19 functions/classes
- cli.py imports from complete.py at 6+ locations with 8 different imports:
  - `verify_agent_work`, `clean_up_agent` (line 14)
  - `complete_agent_work` (line 466)
  - `BeadsPhaseNotCompleteError` (line 484)
  - `prompt_for_discoveries`, `process_discoveries`, `format_discovery_summary` (line 498)
  - `complete_agent_async` (line 625)
- 10 test files depend on complete.py (test_complete.py, test_complete_beads_close.py, test_complete_areas_needing_investigation.py, etc.)

**Key functions requiring migration paths:**
1. `complete_agent_work()` - 229 lines of orchestration logic (verification, workspace sync, area surfacing)
2. `complete_agent_async()` - 215 lines for async completion with recommendations
3. `prompt_for_discoveries()`, `process_discoveries()`, `create_beads_issue()` - Discovery capture workflow
4. `surface_areas_needing_investigation()`, `extract_recommendations_section()` - Work surfacing
5. `close_beads_issue()` - Beads integration with phase verification

**Source:** `grep -c "from.*complete|import.*complete" *.py`, `wc -l src/orch/complete.py`

**Significance:** Issue says "Delete modules that duplicate beads capabilities" but these are orchestration logic ON TOP of beads, not duplicates. Deleting requires migrating 19 functions to beads or deciding which to deprecate.

---

### Finding 2: orch-cli-yno (Delete roadmap modules) has hidden blocker not tracked in beads

**Evidence:**
- Issue notes say: "BLOCKED: roadmap modules still wired into spawn_commands.py via --from-roadmap flag. Need to deprecate CLI flag first."
- `bd blocked` output shows only 3 blocked issues - orch-cli-yno is NOT among them
- spawn_commands.py:71 defines `--from-roadmap` option
- spawn.py has `spawn_from_roadmap()` function (lines 877-1115, ~238 lines)
- roadmap modules imported by: spawn.py, spawn_commands.py, project_resolver.py, roadmap_utils.py, roadmap_markdown.py

**Source:** `bd show orch-cli-yno`, `bd blocked`, `grep "from-roadmap|spawn_from_roadmap" *.py`

**Significance:** The blocker is documented as a note, not a dependency. Missing prerequisite task: "Deprecate --from-roadmap CLI flag". This should be a tracked beads issue blocking orch-cli-yno.

---

### Finding 3: orch-cli-ao0 (Unify path conventions to .kb/) has undefined scope

**Evidence:**
- Issue says "Remove all .orch/ references in code"
- Grep found 359 occurrences of `.orch/` across 74 files
- NOT all .orch/ references should be removed:
  - .orch/workspace/ for SPAWN_CONTEXT.md (spawn.py:810-816)
  - ~/.orch/agent-registry.json (registry.py)
  - ~/.orch/templates/ (config.py)
- Issue lacks enumeration of what to migrate vs what to keep

**Source:** `grep "\.orch/" *.py` - 359 matches in 74 files

**Significance:** Scope is unclear. Need intermediate task: "Enumerate .orch/ references: what migrates to .kb/ vs what stays in .orch/"

---

### Finding 4: orch-cli-wx1 (Remove WORKSPACE.md) missing dependency on orch-cli-6tr

**Evidence:**
- orch-cli-6tr: "Investigate removing .orch/workspace/ directory" is an investigation task
- orch-cli-wx1: "Remove WORKSPACE.md - use beads as only state"
- These are related but no dependency tracked
- Decision on workspace directory affects WORKSPACE.md removal

**Source:** `bd show orch-cli-wx1`, `bd show orch-cli-6tr`

**Significance:** Missing dependency. wx1 should block on 6tr investigation completing.

---

### Finding 5: orch-cli-nan mentions prerequisite not tracked as blocker

**Evidence:**
- Issue description says: "**Prerequisite:** Phase: Complete auto-close hook working in beads"
- This prerequisite is NOT tracked as a beads blocker
- No beads issue exists for "Phase: Complete auto-close hook"

**Source:** `bd show orch-cli-nan`

**Significance:** Missing prerequisite task that should block orch-cli-nan.

---

## Synthesis

**Key Insights:**

1. **Deletion issues hide migration complexity** - Issues saying "delete X" often have 10+ dependent functions, 200+ lines of orchestration logic, and 5+ test files. The issue title doesn't convey this.

2. **Notes != Dependencies** - orch-cli-yno has a "BLOCKED" note in description, but it's not tracked as a beads dependency. Notes are invisible to `bd blocked` and `bd ready`.

3. **Scope vagueness compounds risk** - orch-cli-ao0 says "remove all .orch/ references" but 74 files with 359 occurrences need analysis to determine what stays vs goes.

**Answer to Investigation Question:**

Three issues have significantly underspecified migration paths:
1. **orch-cli-nan** - 19 functions need migration paths, not just deletion
2. **orch-cli-yno** - Hidden dependency on --from-roadmap deprecation
3. **orch-cli-ao0** - Scope unclear (359 occurrences, 74 files, what stays vs goes?)

Three missing prerequisite tasks need to be created:
1. "Deprecate --from-roadmap CLI flag" (blocks orch-cli-yno)
2. "Implement Phase: Complete auto-close hook in beads" (blocks orch-cli-nan)
3. "Enumerate .orch/ references: migrate vs keep" (blocks orch-cli-ao0)

One missing dependency relationship:
- orch-cli-wx1 should be blocked by orch-cli-6tr

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**
Evidence is concrete from grep output and beads show commands. Examined actual code to verify dependencies. Not speculating.

**What's certain:**

- ✅ complete.py has 19 functions/classes and 1244 lines (verified via grep + wc)
- ✅ 10 test files import from complete.py (verified via grep)
- ✅ orch-cli-yno has "BLOCKED" note but no beads dependency (verified via bd show + bd blocked)
- ✅ 359 .orch/ references exist in 74 files (verified via grep count)

**What's uncertain:**

- ⚠️ Whether ALL 19 complete.py functions need migration or some can be deprecated
- ⚠️ Whether the --from-roadmap flag is actively used or already obsolete
- ⚠️ Exact breakdown of 359 .orch/ references (which are legitimate vs migratable)

**What would increase confidence to Very High:**

- Full enumeration of complete.py functions with keep/migrate/deprecate decisions
- Usage analysis of --from-roadmap flag in real workflows
- Per-reference analysis of .orch/ occurrences

---

## Implementation Recommendations

### Recommended Approach ⭐

**Create missing prerequisite tasks before attempting deletion issues**

**Why this approach:**
- Exposes hidden complexity before work begins
- Prevents underestimation of deletion issues
- Creates clear dependency graph

**Trade-offs accepted:**
- More beads issues to track
- Epic may take longer than originally scoped
- Acceptable: better to know true scope than fail mid-implementation

**Implementation sequence:**
1. Create 3 prerequisite tasks as beads issues
2. Add dependency relationships (bd dep)
3. Re-estimate affected deletion issues
4. Update orch-cli-nan with function-by-function migration plan

### Implementation Details

**Issues to create:**

```bash
# Prerequisite for orch-cli-yno
bd create --title="Deprecate --from-roadmap CLI flag" --type=task
bd dep <new-id> orch-cli-yno

# Prerequisite for orch-cli-nan
bd create --title="Implement Phase: Complete auto-close hook in beads" --type=task
bd dep <new-id> orch-cli-nan

# Prerequisite for orch-cli-ao0
bd create --title="Enumerate .orch/ references: migrate vs keep" --type=task
bd dep <new-id> orch-cli-ao0

# Missing dependency
bd dep orch-cli-6tr orch-cli-wx1
```

**Things to watch out for:**
- ⚠️ complete.py verification logic may need to stay even if completion flow changes
- ⚠️ Discovery capture workflow (prompt_for_discoveries) is valuable - don't lose it
- ⚠️ Test files may need updating even after function migration

**Success criteria:**
- ✅ All deletion issues have clear migration paths documented
- ✅ `bd blocked` shows accurate blockers
- ✅ No "BLOCKED" notes in descriptions - all blockers tracked as dependencies

---

## References

**Files Examined:**
- src/orch/complete.py - 19 functions, 1244 lines, complex orchestration
- src/orch/cli.py:460-560 - orch complete command wiring
- src/orch/spawn_commands.py:71 - --from-roadmap option
- src/orch/spawn.py:877-1115 - spawn_from_roadmap function

**Commands Run:**
```bash
# Count complete.py dependencies
grep "from.*complete|import.*complete" *.py

# Count .orch/ references
grep "\.orch/" *.py  # 359 matches in 74 files

# Check blocked issues
bd blocked

# Show issue details
bd show orch-cli-nan
bd show orch-cli-yno
bd show orch-cli-ao0
```

**Related Artifacts:**
- **Issue:** orch-cli-c9o - Parent audit issue
- **Issue:** orch-cli-dgy - Simplification epic containing these issues
- **Decision:** .kb/decisions/2025-12-06-eliminate-workspace-md.md - Related WORKSPACE.md decision

---

## Investigation History

**2025-12-08 19:45:** Investigation started
- Initial question: Which issues assume simple deletion but have hidden dependencies?
- Context: orch-cli-nan was found to be underspecified (said 'delete' but has 8 functions needing migration)

**2025-12-08 19:50:** Code analysis performed
- Ran grep across all .py files for imports from target modules
- Found complete.py has 19 functions, not 8
- Found 359 .orch/ references across 74 files

**2025-12-08 19:55:** Dependency analysis completed
- Identified 3 missing prerequisite tasks
- Identified 1 missing dependency relationship
- Verified blocker notes vs actual beads dependencies

**2025-12-08 20:00:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: 3 underspecified issues identified, 3 missing prerequisite tasks documented

---

## Self-Review

- [x] Real test performed (grep counts, bd commands, code examination)
- [x] Conclusion from evidence (specific line counts, function counts, file counts)
- [x] Question answered (3 underspecified issues, 3 missing prerequisites)
- [x] File complete

**Self-Review Status:** PASSED
