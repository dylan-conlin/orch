# Multi-Phase Feature Validation Pattern

**Pattern Type:** Orchestrator workflow pattern
**When to Use:** Features with sequential phases (A, B, C, D) requiring validation before proceeding
**Created:** 2025-11-21
**Source Investigation:** `.orch/investigations/2025-11-18-multi-phase-feature-orchestration-process-gaps.md`

---

## Pattern Overview

Multi-phase features require explicit validation after EACH phase before spawning the next phase. This prevents cascading failures where later phases build on broken foundations.

**Core principle:** STOP and validate after each phase. Don't auto-spawn next phase based on agent claims of completion.

---

## When This Pattern Applies

**Triggers:**
- Feature explicitly broken into phases (A, B, C, D)
- Sequential dependencies (Phase B requires Phase A working)
- Complex UI work requiring browser verification
- Backend work with integration points

**Examples:**
- "Phase A: Foundation, Phase B: UX Wins, Phase C: Validation"
- "Implement comparison view in 3 phases"
- Any work labeled "Phase 1, Phase 2, etc."

---

## The Five-Step Workflow

### Step 1: STOP - Don't Auto-Spawn Next Phase

**When agent marks Phase N complete:**

❌ **DON'T:**
- Immediately spawn Phase N+1
- Trust "tests pass" without verification
- Assume completion means working

✅ **DO:**
- Pause and review workspace
- Check for validation evidence
- Ask the user to validate manually

**Red flags (don't proceed):**
- Agent says "tests pass" but no smoke test in workspace
- No screenshot of working feature (for UI)
- No browser verification mentioned (for UI)
- Claims "complete" in < 1 hour for complex UI
- No example request/response (for API work)

---

### Step 2: Review Workspace for Validation Evidence

**Read the workspace file and check for validation evidence.**

#### For UI Features (views/controllers)

**Required evidence:**
- ✅ Smoke test section in workspace
- ✅ Browser verification (loaded actual URL in browser)
- ✅ Screenshot or detailed description of rendered output
- ✅ No console errors reported
- ✅ Visual confirmation of feature working

**Example good evidence:**
```markdown
## Smoke Test

Loaded URL: http://localhost:3000/comparison/123
Result: ✅ Comparison view rendered correctly
- Both datasets loaded
- Chart displays price trends
- Styling matches design
- No console errors

Screenshot: workspace/screenshot-comparison-view.png
```

**Example insufficient evidence:**
```markdown
## Testing

Tests pass: ✅
- test_comparison_view.py (12 passing)
```
→ Missing: Browser verification, screenshot, actual usage

#### For API/Backend Features

**Required evidence:**
- ✅ Smoke test with curl/Postman
- ✅ Example request documented
- ✅ Example response documented
- ✅ Integration test coverage
- ✅ Error cases handled

**Example good evidence:**
```markdown
## Smoke Test

Request:
```bash
curl -X POST http://localhost:3000/api/comparison \
  -H "Content-Type: application/json" \
  -d '{"dataset_a": 1, "dataset_b": 2}'
```

Response:
```json
{
  "comparison_id": 123,
  "datasets": [1, 2],
  "status": "ready"
}
```

Integration tests: ✅ 8 passing
```

---

### Step 3: Ask the user to Validate

**Don't assume tests = working.** Always ask the user to validate manually.

**Template question:**
```
"Phase N claims complete with tests passing.

Before spawning Phase N+1, please validate Phase N manually:
- URL: [specific endpoint or page]
- Expected behavior: [what should work]
- Test data: [what to try]

Report: Working ✅ or Issues found ❌"
```

**Example:**
```
"Phase A (Foundation) claims complete.

Before spawning Phase B, please validate Phase A:
- URL: http://localhost:3000/comparison/create
- Expected: Form to select two datasets
- Test: Try selecting datasets 1 and 2, click compare

Report: Working ✅ or Issues found ❌"
```

**Key points:**
- Provide specific URL or command to run
- Describe expected behavior clearly
- Make it easy for the user to verify (< 1 minute)
- Wait for the user's response before proceeding

---

### Step 4: Handle Validation Results

#### If Validation PASSES ✅

```
✅ Phase N validated

Ask the user: "Phase N validated ✅. Proceed with Phase N+1?"

Wait for explicit approval before spawning next phase.
```

**Don't auto-proceed** even if the user says "working" - ask permission to continue.

#### If Validation FAILS ❌

```
❌ Phase N has issues

DON'T: Try to salvage completed agent
DON'T: Send more instructions to Phase N agent
DON'T: Try one more fix

DO: Spawn fresh debugging agent immediately
```

**Example spawn command:**
```bash
orch spawn systematic-debugging "Fix Phase A validation failures: form doesn't submit, getting 404 error" --project price-watch
```

**Why spawn fresh:**
- Completed agent is out of context
- Debugging needs different mindset than building
- Fresh agent can read workspace for full context
- Salvaging rarely works for validation failures

---

### Step 5: Trust the user's Signals

**the user's feedback is ground truth.** Don't question or argue.

**Signal interpretation:**

| the user Says | You Do | Why |
|------------|--------|-----|
| "It's broken" | Spawn debug agent | Don't question - believe the bug report |
| "Out of context" | Spawn fresh agent | Agent is context-exhausted, can't continue |
| "Test it first" | STOP and wait | Don't proceed until validated |
| "Tests pass but feature doesn't work" | Believe it | Common for UI - tests miss real issues |
| "Working ✅" | Ask permission to proceed | Don't auto-spawn next phase |
| "Needs X before continuing" | Implement X first | Blocking dependency identified |

**Don't:**
- Argue about whether it's "really" broken
- Explain why tests should mean it works
- Try to convince the user to proceed
- Salvage when the user says "out of context"

---

## Phase Progress Tracking

**Maintain visual status in session notes or workspace:**

```markdown
## Feature: Time-Series Comparison

**Phases:**
  Phase A: Foundation [✅ VALIDATED - 2025-11-18]
  Phase B: UX Wins [⏳ IN PROGRESS]
  Phase C: Validation [❌ NOT STARTED]
  Phase D: Expansion [❌ NOT STARTED]

**Current:** Working on Phase B
**Next:** Phase C (after Phase B validated)
```

**Rules:**
- Cannot start Phase C until A and B validated
- Cannot mark feature "complete" until all phases done
- Each phase spawn references validated dependencies
- Update status in real-time as work progresses

**Phase states:**
- ❌ NOT STARTED - Not begun
- ⏳ IN PROGRESS - Agent working
- 🔍 NEEDS VALIDATION - Agent claims complete, awaiting validation
- ✅ VALIDATED - the user confirmed working, can proceed
- 🐛 FAILED VALIDATION - Issues found, needs debug

---

## Common Failure Modes (Anti-Patterns)

### Anti-Pattern 1: Auto-Spawning Next Phase

❌ **Wrong:**
```
Agent completes Phase A
→ Immediately spawn Phase B
→ Phase B fails because Phase A has bugs
```

✅ **Right:**
```
Agent completes Phase A
→ Review workspace for validation evidence
→ Ask the user to validate
→ the user confirms working ✅
→ Ask permission to proceed
→ Spawn Phase B with reference to validated Phase A
```

### Anti-Pattern 2: Trusting "Tests Pass" for UI Work

❌ **Wrong:**
```
Agent: "Phase A complete. Tests pass: 12/12 ✅"
Orchestrator: "Great! Spawning Phase B..."
the user: "Phase A is broken - no styling, form doesn't work"
```

✅ **Right:**
```
Agent: "Phase A complete. Tests pass: 12/12 ✅"
Orchestrator: "Before spawning Phase B, please validate Phase A in browser"
the user: "Phase A broken - no styling"
Orchestrator: "Spawning debug agent to fix styling issues"
```

### Anti-Pattern 3: Salvaging Failed Validation

❌ **Wrong:**
```
the user: "Phase A broken - form submit fails"
Orchestrator: "Let me send more instructions to Phase A agent..."
→ Agent context-exhausted, makes it worse
```

✅ **Right:**
```
the user: "Phase A broken - form submit fails"
Orchestrator: "Spawning fresh debug agent..."
→ Fresh agent reads workspace, fixes issue cleanly
```

### Anti-Pattern 4: Phase Skipping

❌ **Wrong:**
```
Phase A: Foundation [⏳ IN PROGRESS]
Phase B: UX Wins [⏳ IN PROGRESS]  ← Started before A validated
Phase C: Validation [❌ NOT STARTED]
```

✅ **Right:**
```
Phase A: Foundation [✅ VALIDATED - 2025-11-18]
Phase B: UX Wins [⏳ IN PROGRESS]  ← Only starts after A validated
Phase C: Validation [❌ NOT STARTED]
```

---

## Real-World Example

**Context:** Price-watch comparison feature, 4 phases (A, B, C, D)

**Phase A: Foundation**
1. Agent completes Phase A
2. Workspace shows: "Tests pass: 8/8 ✅"
3. Orchestrator: "Before spawning Phase B, validate Phase A: http://localhost:3000/comparison/create"
4. the user: "Broken - getting $0.00 prices, run selector not working"
5. Orchestrator: Spawns debug agent (doesn't salvage Phase A agent)
6. Debug agent fixes issues
7. the user: "Working now ✅"
8. Orchestrator: "Phase A validated ✅. Proceed with Phase B?"
9. the user: "Yes"
10. Orchestrator: Spawns Phase B with reference to validated Phase A

**Key lessons:**
- Tests passed but feature was broken (UI issue)
- Orchestrator caught it by requiring manual validation
- Fresh debug agent was more effective than salvaging
- Explicit approval before proceeding to Phase B

**Source investigation:** `.orch/investigations/2025-11-18-multi-phase-feature-orchestration-process-gaps.md`

---

## Integration with Other Patterns

**Related patterns:**
- **Agent Salvage vs Fresh:** When validation fails, spawn fresh (see `agent-salvage-vs-fresh.md`)

**Trust User Signals** is a cross-cutting principle appearing in:
- Multi-phase validation (this pattern)
- Context management (pivot vs respawn)

---

## Template Questions for Validation

**For UI features:**
```
Please validate Phase [N]:
- URL: [specific page]
- Expected: [visual behavior]
- Test: [user actions to try]
- Look for: [specific elements or functionality]

Report: Working ✅ or Issues found ❌
```

**For API features:**
```
Please validate Phase [N]:
- Endpoint: [API endpoint]
- Request: [example curl command or Postman collection]
- Expected: [status code and response structure]
- Test: [edge cases to try]

Report: Working ✅ or Issues found ❌
```

**For multi-component features:**
```
Please validate Phase [N] end-to-end:
1. [Step 1 - what to do]
2. [Step 2 - what to do]
3. [Step 3 - what to do]

Expected outcome: [overall behavior]

Report: Working ✅ or Issues found ❌ (specify which step fails)
```

---

## Quick Reference Card

**Five-step checklist:**
1. ✅ STOP - Don't auto-spawn next phase
2. ✅ Review workspace for validation evidence
3. ✅ Ask the user to validate manually
4. ✅ Handle results (spawn fresh if failed, ask permission if passed)
5. ✅ Trust the user's signals (ground truth)

**Red flags:**
- "Tests pass" but no browser verification (UI)
- No screenshot or smoke test in workspace
- Claims complete in < 1 hour for complex UI
- No example request/response (API)

**Decision tree:**
```
Agent claims Phase N complete
  ↓
Workspace has validation evidence?
  No → Ask the user to validate anyway (don't trust tests alone)
  Yes → Ask the user to validate (confirm evidence is accurate)
  ↓
the user validates
  ↓
Working ✅?
  Yes → Ask permission to proceed with Phase N+1
  No → Spawn fresh debug agent
```

---

## Maintenance

**When to update this pattern:**
- New failure mode discovered (add to anti-patterns)
- Better validation questions identified (add to templates)
- Integration with new patterns (update related patterns)

**Source in orchestration system:**
- Inline reference: `.orch/CLAUDE.md` (brief summary + link to this file)
- Full pattern: `./multi-phase-feature-validation.md` (this file)
- Investigation origin: `.orch/investigations/2025-11-18-multi-phase-feature-orchestration-process-gaps.md`

**Last updated:** 2025-11-21
**Version:** 1.0 (extracted from inline CLAUDE.md guidance)
