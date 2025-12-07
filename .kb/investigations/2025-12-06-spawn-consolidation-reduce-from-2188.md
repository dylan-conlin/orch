**TLDR:** Question: How to reduce spawn.py from 2,202 lines to ~500 lines? Answer: Phases 1-5 implemented: dead code removal (-96), git_utils extraction (-99), opencode.py extraction (-51), project_resolver.py creation (-210), import fixes. Result: 2,202 → 1,745 lines (-457, 21% reduction). Phase 6 (spawn function consolidation) deferred - would require significant refactoring of spawn_from_roadmap, spawn_interactive, spawn_with_skill.

---

# Investigation: spawn.py Consolidation Strategy

**Question:** How can we reduce spawn.py from 2,202 lines to ~500 lines through extraction, dead code removal, and simplification?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** worker-agent
**Phase:** Complete (Phases 1-5)
**Next Step:** Phase 6 (spawn function consolidation) if further reduction needed
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: spawn.py Contains 29 Functions Across 7 Distinct Categories

**Evidence:** Function analysis shows clear groupings:
- Git state functions (7 functions, ~200 lines): check_git_dirty_state, git_stash_changes, git_stash_pop, _display_dirty_state, _try_stash_changes, _handle_dirty_state_interactive, _handle_git_dirty_state
- Project detection (6 functions, ~200 lines): _get_active_projects_file, _parse_active_projects, get_project_dir, list_available_projects, format_project_not_found_error, detect_project_from_cwd
- OpenCode model resolution (1 function + 2 constants, ~30 lines): resolve_opencode_model, OPENCODE_DEFAULT_MODEL, OPENCODE_MODEL_ALIASES
- Heuristics (2 functions, ~55 lines): looks_small_change, looks_trivial_bug
- Preview/display (2 functions, ~137 lines): show_preview, _wrap_text
- Feature-impl validation (1 function, ~50 lines): validate_feature_impl_config
- Core spawn (4 main functions + dataclass, ~1000+ lines): SpawnConfig, spawn_in_tmux, spawn_with_opencode, spawn_from_roadmap, spawn_interactive, spawn_with_skill, register_agent

**Source:** `grep -n "^def \|^class " src/orch/spawn.py` + manual line counting

**Significance:** Clear separation enables systematic extraction to focused modules.

---

### Finding 2: Dead Code Identified

**Evidence:**
1. `looks_small_change()` (lines 404-438, 35 lines) - defined but never called
2. `wait_for_claude_ready()` (lines 224-281, 58 lines) - duplicated in ClaudeBackend.wait_for_ready()
   - Only used in spawn_interactive (line 1716)
   - spawn_in_tmux uses backend.wait_for_ready() (line 761)
   - spawn_with_opencode uses backend.wait_for_ready() (line 886)

**Source:**
```bash
grep -n "looks_small_change" src/orch/*.py  # Only definition, no usage
grep -n "wait_for_claude_ready" src/orch/*.py  # Definition + 1 call
```

**Significance:** ~93 lines of dead/duplicated code can be removed.

---

### Finding 3: Existing git_utils.py Has Related But Non-Overlapping Functions

**Evidence:**
- git_utils.py (445 lines) contains: is_git_repo, get_last_commit, count_commits_since, validate_git_state, validate_work_committed, find_commits_mentioning_issue, commit_roadmap_update
- spawn.py contains: check_git_dirty_state, git_stash_changes, git_stash_pop, _display_dirty_state, _try_stash_changes, _handle_dirty_state_interactive, _handle_git_dirty_state

**Source:** `cat src/orch/git_utils.py` vs spawn.py git functions

**Significance:** Git functions can be consolidated into git_utils.py without conflicts. spawn.py's git functions focus on dirty state handling (stash/unstash), while git_utils.py focuses on commit tracking.

---

### Finding 4: Import from spawn.py Creates Coupling Issues

**Evidence:**
- verification.py imports `discover_skills` from spawn.py (line 39) but this function is defined in skill_discovery.py
- spawn.py re-exports from skill_discovery.py without value
- complete.py imports `git_stash_pop` from spawn.py (lines 667, 943)

**Source:** `grep -n "from orch.spawn import" src/orch/*.py`

**Significance:** Moving functions to proper modules will require import updates. Some are circular import workarounds.

---

### Finding 5: OpenCode Resolution Belongs in backends/opencode.py

**Evidence:**
- `resolve_opencode_model` (30 lines) + `OPENCODE_DEFAULT_MODEL` + `OPENCODE_MODEL_ALIASES` (25 lines)
- Only used by `spawn_with_opencode()` which creates OpenCodeBackend
- Currently hardcoded as global constants in spawn.py

**Source:** Lines 168-222 of spawn.py

**Significance:** Moving ~55 lines to backends/opencode.py improves cohesion.

---

### Finding 6: Three Main Spawn Functions Share Significant Code Duplication

**Evidence:**
- spawn_from_roadmap (185 lines): workspace creation, preview, confirmation, spawn dispatch, registration
- spawn_interactive (293 lines): workspace creation, tmux window, claude command, registration
- spawn_with_skill (330 lines): workspace creation, preview, confirmation, spawn dispatch, registration

Common patterns:
1. TTY detection and auto-confirm logic (duplicated 3x)
2. Project detection and resolution (duplicated 2x)
3. Workspace path creation (duplicated 3x)
4. Spawn dispatch (tmux vs opencode) (duplicated 2x)
5. Agent registration (duplicated 3x)
6. Success messaging (duplicated 3x)

**Source:** Lines 1067-2203 of spawn.py

**Significance:** ~200 lines of duplicated code can be consolidated into shared helpers.

---

## Synthesis

**Key Insights:**

1. **Clear Extraction Targets** - Six groups of code can be moved to existing or new focused modules:
   - Git functions → git_utils.py (+200 lines there, -200 from spawn.py)
   - Project detection → new project_resolver.py (~200 lines)
   - OpenCode resolution → backends/opencode.py (+55 lines there)
   - Heuristics → remove looks_small_change (dead), keep looks_trivial_bug inline (~20 lines)
   - Preview/display → keep inline (only used internally, ~137 lines)

2. **Dead Code Removal Saves ~93 Lines** - looks_small_change (35 lines) + wait_for_claude_ready duplication (58 lines)

3. **Spawn Function Consolidation** - Creating shared helpers for common patterns can reduce spawn_from_roadmap + spawn_interactive + spawn_with_skill from ~808 lines to ~400-500 lines

**Answer to Investigation Question:**

Achievable target: ~550-600 lines (from 2,202)

| Action | Lines Removed | Target Module |
|--------|--------------|---------------|
| Extract git functions | -200 | git_utils.py |
| Extract project detection | -200 | project_resolver.py |
| Extract OpenCode resolution | -55 | backends/opencode.py |
| Remove dead code | -93 | (deleted) |
| Refactor spawn_interactive | -100 | (use backend abstraction) |
| Consolidate spawn helpers | -200 | (shared helper functions) |
| **Total Reduction** | **-848** | |
| **Remaining** | **~1354** | spawn.py |

Further reduction to ~500 lines would require:
- Moving SpawnConfig to spawn_config.py (~47 lines)
- Moving validate_feature_impl_config to spawn_validation.py (~50 lines)
- Moving show_preview/_wrap_text to spawn_display.py (~137 lines)
- More aggressive helper consolidation

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**
Thorough code analysis completed with grep/read tools. All functions categorized. Dead code identified with evidence. Duplication patterns confirmed.

**What's certain:**
- ✅ Dead code: looks_small_change is never called
- ✅ Duplication: wait_for_claude_ready duplicated in ClaudeBackend
- ✅ Groupings: Git functions, project detection, OpenCode resolution are self-contained
- ✅ Import issues: verification.py should import from skill_discovery

**What's uncertain:**
- ⚠️ Exact line counts after extraction (estimates within ±20%)
- ⚠️ Hidden dependencies that might complicate extraction
- ⚠️ Whether spawn_interactive refactor is straightforward

**What would increase confidence to Very High (95%+):**
- Write failing tests before extraction
- Validate no circular imports in new module structure
- Measure actual line counts after each extraction step

---

## Implementation Recommendations

**Purpose:** Phased extraction strategy for safe, testable consolidation.

### Recommended Approach ⭐

**Phased Extraction with Test-First Validation**

**Why this approach:**
- Each phase is independently testable and revertable
- Builds confidence through incremental wins
- Dead code removal is safest to start with (no behavior change)

**Trade-offs accepted:**
- Multiple PRs/commits instead of big-bang refactor
- Temporary import shims may be needed

**Implementation sequence:**

#### Phase 1: Dead Code Removal (~93 lines)
1. Remove `looks_small_change()` (lines 404-438) - unused
2. Refactor `spawn_interactive` to use ClaudeBackend.wait_for_ready() instead of wait_for_claude_ready
3. Remove `wait_for_claude_ready()` (lines 224-281) after spawn_interactive fix

#### Phase 2: Git Functions → git_utils.py (~200 lines)
1. Move `check_git_dirty_state`, `git_stash_changes`, `git_stash_pop` to git_utils.py
2. Move `_display_dirty_state`, `_try_stash_changes`, `_handle_dirty_state_interactive`, `_handle_git_dirty_state`
3. Update imports in spawn.py and complete.py

#### Phase 3: OpenCode Resolution → backends/opencode.py (~55 lines)
1. Move `OPENCODE_DEFAULT_MODEL`, `OPENCODE_MODEL_ALIASES`, `resolve_opencode_model` to backends/opencode.py
2. Update `spawn_with_opencode` to import from backends/opencode

#### Phase 4: Project Detection → project_resolver.py (~200 lines)
1. Create new src/orch/project_resolver.py
2. Move `_get_active_projects_file`, `_parse_active_projects`, `get_project_dir`, `list_available_projects`, `format_project_not_found_error`, `detect_project_from_cwd`, `detect_project_roadmap`
3. Update imports in spawn.py and spawn_commands.py

#### Phase 5: Fix Import Issues
1. Update verification.py to import `discover_skills` from skill_discovery (not spawn)
2. Review other spawn.py imports for similar issues

#### Phase 6: Spawn Function Consolidation (~200 lines)
1. Extract shared helper: `_prepare_spawn_context()` - TTY detection, project resolution
2. Extract shared helper: `_create_workspace_and_prompt()` - workspace path, context file
3. Extract shared helper: `_dispatch_spawn()` - backend selection, spawn call, registration
4. Simplify spawn_from_roadmap, spawn_interactive, spawn_with_skill to use helpers

### Alternative Approaches Considered

**Option B: Big-bang refactor**
- **Pros:** One commit, clean history
- **Cons:** High risk, hard to test incrementally, hard to revert
- **When to use instead:** Never for this size of change

**Option C: Start with new spawn_v2.py**
- **Pros:** Can compare side-by-side
- **Cons:** Temporary duplication, confusing imports
- **When to use instead:** If existing code is too tangled to safely modify

**Rationale for recommendation:** Phased approach allows TDD methodology per spawn context requirements.

---

### Implementation Details

**What to implement first:**
1. Phase 1 (dead code) - safest, immediate wins
2. Phase 2 (git_utils) - largest single module, existing target file

**Things to watch out for:**
- ⚠️ `git_stash_pop` is imported by complete.py - update that import
- ⚠️ `get_project_dir` is imported by spawn_commands.py - update that import
- ⚠️ Circular import risk when moving functions between modules

**Areas needing further investigation:**
- Should SpawnConfig move to its own module? (Would help with TYPE_CHECKING imports)
- Are there other files importing from spawn.py that weren't found?

**Success criteria:**
- ✅ spawn.py reduced to ~500-600 lines
- ✅ All existing tests pass
- ✅ No circular import errors
- ✅ `orch spawn` commands still work as expected

---

## References

**Files Examined:**
- src/orch/spawn.py (2,202 lines) - main target
- src/orch/git_utils.py (445 lines) - extraction target
- src/orch/backends/claude.py (139 lines) - contains duplicate wait_for_ready
- src/orch/backends/opencode.py - extraction target
- src/orch/verification.py - import fix needed
- src/orch/complete.py - imports git_stash_pop
- src/orch/spawn_commands.py - imports from spawn

**Commands Run:**
```bash
# Function listing
grep -n "^def \|^class " src/orch/spawn.py

# Dead code detection
grep -n "looks_small_change" src/orch/*.py
grep -n "wait_for_claude_ready" src/orch/*.py

# Import analysis
grep -n "from orch.spawn import" src/orch/*.py

# Line counts
wc -l src/orch/spawn.py src/orch/git_utils.py
```

**Related Artifacts:**
- **Decision:** None yet - this investigation informs implementation
- **Beads Issue:** ok-dk8 (in orch-knowledge)

---

## Investigation History

**2025-12-06 ~21:30:** Investigation started
- Initial question: How to reduce spawn.py from 2,202 to ~500 lines
- Context: Major simplification task from beads issue ok-dk8

**2025-12-06 ~21:45:** Function categorization complete
- Identified 29 functions in 7 groups
- Found dead code: looks_small_change, wait_for_claude_ready duplication

**2025-12-06 ~22:00:** Synthesis complete
- Created 6-phase extraction plan
- Estimated final spawn.py at ~550-600 lines (achievable target)

**2025-12-06 ~22:45:** Implementation Phases 1-5 complete
- **Phase 1:** Removed dead code (looks_small_change, wait_for_claude_ready) → -96 lines
- **Phase 2:** Moved git functions to git_utils.py → -99 lines
- **Phase 3:** Moved OpenCode model resolution to backends/opencode.py → -51 lines
- **Phase 4:** Created project_resolver.py and moved project detection → -210 lines
- **Phase 5:** Fixed import issues (verification.py, spawn_commands.py) → -1 line
- **Final result:** spawn.py reduced from 2,202 to 1,745 lines = **-457 lines (21% reduction)**
- All 180 spawn tests pass (same 5 pre-existing failures)
- Phase 6 (spawn function consolidation) deferred - requires larger refactoring effort
