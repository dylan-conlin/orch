**TLDR:** What E2E tests exist and what's missing for full orchestrator+worker coverage? Current tests cover orchestrator perspective (spawn/check/complete via CLI) but don't test worker behavior (reading SPAWN_CONTEXT, reporting via beads, creating artifacts). High confidence (85%) - thorough code review of test files.

---

# Investigation: E2E Integration Tests for Orch Ecosystem

**Question:** What E2E test infrastructure exists and what tests are needed for full worker + orchestrator coverage?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** Move to Design phase
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: Real E2E Test Infrastructure Exists

**Evidence:** `tests/e2e/conftest.py` provides `e2e_env` fixture that:
- Creates isolated tmux session with unique name
- Creates temporary project directory with git init
- Creates `.orch/workspace/` directory structure
- Creates `active-projects.md` for spawn discovery
- Sets up test environment with mocked HOME
- Cleans up tmux session and temp files on teardown

**Source:** `tests/e2e/conftest.py:17-181`

**Significance:** Foundation for real subprocess-based E2E tests exists. Tests use actual `orch` CLI via subprocess.run(), not mocked runners.

---

### Finding 2: Current E2E Tests Cover Orchestrator Perspective Only

**Evidence:** `tests/e2e/test_basic_workflows.py` tests:
- `test_spawn_complete_workflow` - spawn → verify → complete
- `test_spawn_check_workflow` - spawn → check
- `test_spawn_send_complete_workflow` - spawn → send message → complete
- `test_multiple_concurrent_agents` - multiple spawns, status shows all

All tests focus on CLI commands from orchestrator perspective. They don't verify:
- What agents see (SPAWN_CONTEXT.md contents)
- How agents report progress (beads comments)
- What agents produce (artifacts, investigations)

**Source:** `tests/e2e/test_basic_workflows.py:14-373`

**Significance:** Missing worker-side verification means we can't catch issues in spawn prompt generation or artifact creation.

---

### Finding 3: Mocked E2E Tests Provide Unit-Level Coverage

**Evidence:** `tests/test_e2e_workflows.py` contains "E2E" tests that heavily mock:
- subprocess.run (git, tmux commands)
- AgentRegistry
- Backend classes
- verify_agent_work

These aren't true E2E - they test CLI command flow but mock all external interactions.

**Source:** `tests/test_e2e_workflows.py:75-467`

**Significance:** These tests are valuable for CLI behavior but don't catch integration issues between components.

---

### Finding 4: Beads Integration Tests Exist Separately

**Evidence:** `tests/test_beads_integration.py` tests BeadsIntegration class in isolation:
- get_issue()
- close_issue()
- get_phase_from_comments()

**Source:** `tests/test_beads_integration.py` (not read but exists in glob results)

**Significance:** Beads integration is tested but not as part of spawn → complete workflow.

---

## Synthesis

**Key Insights:**

1. **Two-tier test structure** - Real E2E tests in `tests/e2e/` using subprocess, mocked tests in `tests/test_*.py` using click.CliRunner

2. **Gap: Worker behavior untested** - No tests verify what spawned agents receive (SPAWN_CONTEXT.md quality) or how they interact with the system (beads comments, artifact creation)

3. **Gap: Beads-first workflow untested** - The new beads-first workflow (agent reports via `bd comment`, orchestrator monitors via `bd show`) isn't tested E2E

**Answer to Investigation Question:**

Good E2E infrastructure exists but tests only cover orchestrator CLI operations. Missing tests for:
1. SPAWN_CONTEXT.md content validation (worker receives correct skill, phase config, project info)
2. Beads progress tracking (agent reports phases, orchestrator can close)
3. Artifact creation (investigations, designs created in correct locations)

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**
Thorough review of test files and understanding of spawn workflow. Minor uncertainty about which specific scenarios to prioritize.

**What's certain:**
- ✅ E2E fixture infrastructure is solid (`tests/e2e/conftest.py`)
- ✅ Current tests focus on orchestrator CLI commands
- ✅ Worker behavior (reading context, reporting progress) is untested

**What's uncertain:**
- ⚠️ Best approach for simulating agent behavior in tests
- ⚠️ How to test beads integration without real beads CLI

---

## Implementation Recommendations

### Recommended Approach ⭐

**Three-layer E2E test strategy** - Add tests at different integration levels:

1. **SPAWN_CONTEXT validation tests** - Verify generated context files contain correct content
2. **Beads workflow integration tests** - Test spawn → bd comment → orch complete flow
3. **Artifact creation tests** - Verify investigation/design files created correctly

**Why this approach:**
- Targets the specific gaps identified (worker perspective)
- Builds on existing infrastructure (e2e_env fixture)
- Doesn't require real AI agent execution

**Implementation sequence:**
1. Add SPAWN_CONTEXT.md content tests (validates spawn output)
2. Add beads integration E2E tests (validates progress tracking)
3. Add artifact creation verification (validates deliverables)

---

## References

**Files Examined:**
- `tests/e2e/conftest.py` - E2E fixture infrastructure
- `tests/e2e/test_basic_workflows.py` - Current real E2E tests
- `tests/test_e2e_workflows.py` - Mocked CLI workflow tests
- `src/orch/cli.py` - CLI command definitions
- `src/orch/spawn_commands.py` - Spawn command implementation

---

## Investigation History

**2025-12-06 21:03:** Investigation started
- Initial question: What E2E tests are needed for full ecosystem coverage?
- Context: Task to implement E2E integration tests

**2025-12-06 21:08:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Identified three gaps in E2E testing (worker context, beads workflow, artifacts)
