**TLDR:** WORKSPACE.md was deprecated on Dec 6, 2025 with beads comments now the source of truth for agent state. Need to remove all WORKSPACE.md creation, parsing, and checking from 5 files (workspace.py, registry.py, patterns.py, resume.py, context_capture.py, cli.py). High confidence (95%) - straightforward removal with clear dependency chain.

---

# Investigation: Eliminate WORKSPACE.md from orch-cli

**Question:** What code references WORKSPACE.md and needs to be removed now that beads is the source of truth?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: workspace.py contains extensive WORKSPACE.md infrastructure (to remove)

**Evidence:** Functions for reading, parsing, and creating WORKSPACE.md files:
- `read_workspace_safe()` - reads with locking (lines 105-176)
- `parse_workspace()` - parses for signals (lines 449-512)
- `parse_workspace_verification()` - parses for verification (lines 515-604)
- `extract_tldr()` - extracts TLDR section (lines 607-651)
- `is_unmodified_template()` - checks template state (lines 654-709)
- `detect_workspace_state()` - includes WORKSPACE.md states (lines 916-954)
- `create_workspace()` - creates from template (lines 959-1062)
- `render_template()` - renders WORKSPACE.md template (lines 850-902)
- `WorkspaceSignal`, `WorkspaceVerificationData` classes
- Various validation and helper functions

**Source:** src/orch/workspace.py

**Significance:** This is the core WORKSPACE.md infrastructure. Removing these functions eliminates the creation and parsing capability.

---

### Finding 2: Files importing parse_workspace need updates

**Evidence:** Four files import `parse_workspace` from workspace.py:
- `registry.py` (lines 442, 580) - used in `_sync_with_workspace()` and similar
- `patterns.py` (line 45) - used in `check_patterns()`
- `resume.py` (line 41) - used in `get_workspace_signal()`
- `context_capture.py` (line 124) - used in `capture_context()`

**Source:** grep search for `from orch.workspace import`

**Significance:** These usages need to be removed or refactored to use beads instead.

---

### Finding 3: cli.py imports other WORKSPACE.md utilities

**Evidence:** cli.py imports `is_unmodified_template` and `extract_tldr` from workspace.py (line 16)

**Source:** src/orch/cli.py:16

**Significance:** These imports need to be removed along with any code that uses them.

---

### Finding 4: Keep workspace naming utilities (NOT WORKSPACE.md related)

**Evidence:** workspace.py contains naming utilities that are NOT related to WORKSPACE.md files:
- `ABBREVIATIONS` constant
- `apply_abbreviations()` - used by workspace_naming.py
- `truncate_at_word_boundary()` - used by spawn.py

**Source:** src/orch/workspace.py lines 22-100, src/orch/spawn.py line 23

**Significance:** These should be kept as they're used for workspace directory naming, not WORKSPACE.md file management.

---

## Synthesis

**Key Insights:**

1. **Clean separation possible** - WORKSPACE.md functions are separable from naming utilities

2. **Pattern check already degraded** - patterns.py already has comments noting WORKSPACE.md is deprecated

3. **verification.py already updated** - Has explicit note that WORKSPACE.md is no longer used

**Answer to Investigation Question:**

WORKSPACE.md code exists in 6 files and can be safely removed:
1. workspace.py - Remove all parse/create functions, keep naming utilities
2. registry.py - Remove calls to parse_workspace
3. patterns.py - Simplify check_patterns since WORKSPACE.md checks are deprecated
4. resume.py - Remove parse_workspace usage
5. context_capture.py - Remove parse_workspace usage
6. cli.py - Remove is_unmodified_template and extract_tldr imports/usage

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?** Clear code paths identified, beads integration already complete, verification.py already updated.

**What's certain:**
- ✅ All WORKSPACE.md references identified
- ✅ Naming utilities are separate and should be kept
- ✅ Beads is working as source of truth

**What's uncertain:**
- ⚠️ Tests may need updates (not examined in detail)

---

## Implementation Recommendations

### Recommended Approach ⭐

**Incremental removal** - Remove WORKSPACE.md code file by file, running tests after each change.

**Implementation sequence:**
1. Remove WORKSPACE.md functions from workspace.py (keep naming utilities)
2. Update registry.py to not use parse_workspace
3. Update patterns.py to remove WORKSPACE.md checking
4. Update resume.py to not use parse_workspace
5. Update context_capture.py to not use parse_workspace
6. Update cli.py to remove WORKSPACE.md imports
7. Run tests and fix any failures

---

## References

**Files Examined:**
- src/orch/workspace.py - Main WORKSPACE.md infrastructure
- src/orch/registry.py - Agent registry with parse_workspace calls
- src/orch/patterns.py - Pattern checking (deprecated)
- src/orch/resume.py - Agent resume logic
- src/orch/context_capture.py - Context capture logic
- src/orch/cli.py - CLI entry point
- src/orch/verification.py - Already updated to not use WORKSPACE.md
- src/orch/complete.py - Agent completion logic
- src/orch/spawn.py - Agent spawning
- src/orch/monitor.py - Agent monitoring

---

## Investigation History

**2025-12-06 20:45:** Investigation started
- Initial question: What WORKSPACE.md code needs to be removed?
- Context: Beads is now source of truth for agent state

**2025-12-06 20:50:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: 6 files need updates, clear implementation path identified
