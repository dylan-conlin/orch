# Design: E2E Integration Tests for Orch Ecosystem

**Status:** In Review
**Created:** 2025-12-06
**Author:** Worker Agent
**Related Investigation:** `.kb/investigations/2025-12-06-e2e-integration-tests-orch-ecosystem.md`

---

## Problem Statement

Current E2E tests only validate orchestrator CLI behavior (spawn, check, complete commands). They don't verify:
1. What content agents receive in SPAWN_CONTEXT.md
2. Whether beads-based progress tracking works end-to-end
3. Whether artifacts are created in correct locations

**Success criteria:**
- Tests catch regressions in spawn prompt generation
- Tests verify beads workflow (spawn → bd comment → complete)
- Tests validate worker perspective (what agents see/produce)

---

## Approach

Add three categories of E2E tests building on existing `tests/e2e/` infrastructure:

### Category 1: SPAWN_CONTEXT Validation Tests

**Purpose:** Verify spawn prompt generation produces correct content.

**Tests:**
1. `test_spawn_context_contains_task` - Task description is substituted
2. `test_spawn_context_contains_skill` - Skill content is loaded
3. `test_spawn_context_contains_beads_id` - Beads tracking info included
4. `test_spawn_context_contains_phases` - Phase configuration present
5. `test_spawn_context_contains_project_dir` - Absolute path substituted
6. `test_spawn_context_filtered_phases` - Only configured phases included

**Implementation:** After `orch spawn`, read the generated `SPAWN_CONTEXT.md` file and assert on content.

### Category 2: Beads Workflow Integration Tests

**Purpose:** Test beads-based progress tracking end-to-end.

**Tests:**
1. `test_spawn_with_beads_issue` - Spawn creates context with beads ID
2. `test_complete_closes_beads_issue` - Complete closes the issue when Phase: Complete
3. `test_complete_fails_without_phase_complete` - Complete fails if phase not reported
4. `test_beads_phase_detection` - Phase is correctly extracted from comments

**Implementation:** Use subprocess to run `bd` and `orch` commands against isolated test environment.

### Category 3: Worker Perspective Tests

**Purpose:** Verify agents can use the provided context correctly.

**Tests:**
1. `test_investigation_path_guidance` - Investigation path in context is correct
2. `test_deliverables_list` - Required deliverables are listed
3. `test_verification_requirements` - Skill verification requirements present
4. `test_context_available_section` - CLAUDE.md paths listed

**Implementation:** Parse SPAWN_CONTEXT.md and verify each section.

---

## Architecture

### Test Location

```
tests/e2e/
├── conftest.py              # Existing fixture (e2e_env)
├── test_basic_workflows.py   # Existing tests
├── test_spawn_context.py     # NEW: SPAWN_CONTEXT validation
├── test_beads_workflow.py    # NEW: Beads integration
└── test_worker_perspective.py # NEW: Worker view tests
```

### Fixture Extension

Extend `e2e_env` fixture to support:
- Creating `.beads/` directory for beads tests
- Mock `bd` CLI responses when real beads not available
- Read SPAWN_CONTEXT.md content after spawn

### Mock Strategy

For beads integration tests:
1. **With real beads CLI:** Run actual `bd` commands
2. **Without beads CLI:** Skip tests with `pytest.mark.skipif`

---

## Testing Strategy

### TDD Mode

Write failing tests first, then implementation:

1. Write test for SPAWN_CONTEXT content → Verify it fails/passes correctly
2. Write test for beads workflow → Ensure it catches issues
3. Write worker perspective tests → Validate agent experience

### Test Isolation

Each test uses isolated:
- Temp directory
- Tmux session
- Registry
- Mocked HOME

### Markers

```python
@pytest.mark.e2e  # Real subprocess E2E test
@pytest.mark.beads  # Requires beads CLI
@pytest.mark.spawn_context  # Tests spawn prompt content
```

---

## Implementation Sequence

1. **Create test_spawn_context.py** - SPAWN_CONTEXT validation tests
   - Test task substitution
   - Test skill content loading
   - Test phase configuration
   - Test beads ID inclusion

2. **Create test_beads_workflow.py** - Beads integration tests
   - Test spawn with --issue
   - Test complete with phase detection
   - Mock beads CLI for CI environments

3. **Create test_worker_perspective.py** - Worker view tests
   - Test deliverables section
   - Test verification requirements
   - Test context paths

---

## Data Model

N/A - Tests only, no schema changes.

---

## UI/UX

N/A - Tests only, no UI.

---

## Testing Strategy

Tests will be run:
- Locally with `pytest tests/e2e/ -m e2e`
- In CI with `pytest tests/e2e/ -m "e2e and not beads"` (beads not available)
- Full integration with `pytest tests/e2e/` when beads installed

---

## Security Considerations

- Tests use isolated temp directories
- No real credentials used
- Mocked HOME prevents polluting user config

---

## Performance Requirements

- Each E2E test should complete in <30 seconds
- Total suite should run in <5 minutes

---

## Alternatives Considered

### Option A: Extend mocked tests in test_e2e_workflows.py

**Pros:** Faster execution, no subprocess overhead
**Cons:** Doesn't catch real integration issues
**Why not:** We want true E2E validation, not mocked behavior

### Option B: Use pytest-bdd for behavior-driven tests

**Pros:** More readable test descriptions
**Cons:** Additional dependency, learning curve
**Why not:** Overkill for this scope, standard pytest sufficient

---

## Open Questions

1. Should we require beads CLI for CI or always mock?
   - **Recommendation:** Skip beads tests in CI, run full suite locally

2. Should tests verify skill content matches source files?
   - **Recommendation:** No, that's skill build testing, not E2E

---

## Success Criteria

- [ ] 10+ new E2E tests added
- [ ] Tests catch known failure modes (task not substituted, beads not tracked)
- [ ] Tests run successfully in isolation
- [ ] Tests are marked appropriately for CI/local execution
- [ ] No flaky tests after 10 runs
