**TLDR:** Question: How to add meta CLI commands (focus, drift, next) for cross-project orchestration? Answer: Implemented three new commands following existing CLI patterns - `orch focus` sets north star in ~/.orch/focus.json, `orch drift` checks project alignment, `orch next` suggests focus-aligned work. Very High confidence (95%) - all 24 tests pass, commands verified interactively.

---

# Investigation: Add Meta CLI Commands (focus, drift, next)

**Question:** How to implement meta orchestration CLI commands for cross-project coordination?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent (feature-impl)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Existing CLI patterns provide clear template for new commands

**Evidence:** Examined daemon_commands.py which uses `register_*_commands(cli)` pattern for modular command registration. Each command module defines functions and a registration function that adds commands to the Click group.

**Source:** 
- `src/orch/daemon_commands.py:48-66` - register_daemon_commands pattern
- `src/orch/cli.py:66-81` - command registration imports and calls

**Significance:** New meta commands can follow exact same pattern - create `meta_commands.py` with `register_meta_commands(cli)` function.

---

### Finding 2: Config module shows global ~/.orch/ state management pattern

**Evidence:** config.py uses `~/.orch/` for global state (config.yaml, initialized-projects.json). Focus state naturally fits here as `~/.orch/focus.json`.

**Source:**
- `src/orch/config.py:41-55` - get_config() uses ~/.orch/config.yaml
- `src/orch/config.py:75-77` - get_initialized_projects_cache() pattern

**Significance:** Focus state should follow same pattern - global file, simple JSON, lazy loading with caching.

---

### Finding 3: Design documents specify clear data model and behavior

**Evidence:** Two design investigations specify the architecture:
- Focus state with description, aligned_projects, success_criteria
- Drift detection based on project alignment and time
- Next suggestions sorted by focus alignment then priority

**Source:**
- `orch-knowledge/.kb/investigations/2025-12-12-design-unified-meta-orchestration-daemon-architecture.md`
- `orch-knowledge/.kb/investigations/2025-12-12-design-meta-orchestration-cross-project-coordination.md`

**Significance:** Clear requirements allow direct implementation without design decisions.

---

## Synthesis

**Key Insights:**

1. **Modular command pattern** - Following daemon_commands.py pattern keeps CLI organized
2. **Focus state as global JSON** - ~/.orch/focus.json is natural location for cross-project state
3. **Project detection from cwd** - get_current_project() enables automatic alignment checking

**Answer to Investigation Question:**

Implemented three meta orchestration commands:
- `orch focus [DESCRIPTION]` - Set or show north star with aligned projects and success criteria
- `orch drift` - Check if current project aligns with focus, warn on time-based drift
- `orch next` - Suggest next work items, prioritizing focus-aligned projects

All functionality encapsulated in `src/orch/meta_commands.py` with 24 passing tests.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

All tests pass, commands work correctly when tested interactively, follows established patterns.

**What's certain:**

- ✅ Commands registered and accessible via CLI
- ✅ Focus state persists correctly to ~/.orch/focus.json
- ✅ Drift detection works (tested with orch-cli vs snap focus)
- ✅ Next suggestions integrate with kb projects and beads ready

**What's uncertain:**

- ⚠️ Cross-project beads aggregation depends on kb project registry being populated
- ⚠️ Focus history pruning (currently keeps last 10) may need adjustment

**What would increase confidence to 100%:**

- Integration testing with actual multi-project workflow
- User feedback on drift detection thresholds

---

## Implementation Recommendations

### Recommended Approach ⭐

**Commands implemented as designed** - Direct implementation of design spec

**Why this approach:**
- Follows established orch-cli patterns exactly
- Matches design investigation specifications
- TDD approach ensures correctness

**Implementation sequence:**
1. Created test_meta_commands.py with 24 tests (RED)
2. Created meta_commands.py with FocusState dataclass and command functions (GREEN)
3. Registered commands in cli.py

### Files Changed

- `src/orch/meta_commands.py` - New module with all meta command logic
- `src/orch/cli.py` - Added import and registration call
- `tests/test_meta_commands.py` - 24 tests covering all functionality

---

## References

**Files Examined:**
- `src/orch/daemon_commands.py` - Pattern for command modules
- `src/orch/config.py` - Pattern for global state management
- `src/orch/cli.py` - Command registration

**Design Documents:**
- `orch-knowledge/.kb/investigations/2025-12-12-design-unified-meta-orchestration-daemon-architecture.md`
- `orch-knowledge/.kb/investigations/2025-12-12-design-meta-orchestration-cross-project-coordination.md`

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: How to implement focus/drift/next commands
- Context: Beads issue orch-cli-0hkc

**2025-12-12:** Implementation complete
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Three meta commands implemented with full test coverage
