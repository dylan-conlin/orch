# Agent Salvage vs Fresh Spawn Pattern

**Pattern Type:** Orchestrator decision tree
**When to Use:** Agent needs redirection or validation fails
**Created:** 2025-11-21
**Source Investigation:** `.orch/investigations/2025-11-18-multi-phase-feature-orchestration-process-gaps.md` (Failure 3)

---

## Pattern Overview

**Core question:** Should I send more instructions to an existing agent, or spawn a fresh agent?

**Core principle:** Fresh is almost always better. Salvaging rarely works and usually makes things worse.

**Why this matters:** Context-exhausted agents produce worse results, waste time, and create frustration. Spawning fresh is faster and more reliable.

---

## The Five-Question Decision Tree

**When agent needs redirection, ask these questions in order:**

### Question 1: Did the user say "out of context"?

**If YES → Spawn fresh immediately**
- No debate
- No salvage attempts
- No questions

**Why:** the user's signal is ground truth. If the user says "out of context," the agent IS out of context.

---

### Question 2: Has agent worked 2+ hours?

**If YES → Spawn fresh (likely context-exhausted)**

**Signs of context exhaustion:**
- Repeating same suggestions
- Missing obvious solutions
- Asking questions about things already discussed
- Making errors in basic understanding
- Taking longer for simple tasks

**Why:** Long-running agents accumulate context and make mistakes. Fresh start is faster.

---

### Question 3: Is pivot unrelated to current task?

**If YES → Spawn fresh (different context needed)**

**Example:**
- Agent A: "Implement user authentication"
- Pivot request: "Now add billing system"
- → Unrelated, spawn fresh

**vs**

- Agent A: "Implement user authentication"
- Pivot request: "Now add password reset"
- → Related refinement, can pivot

**Why:** Unrelated tasks need different context and mental model.

---

### Question 4: Agent already pivoted once?

**If YES → Spawn fresh (too many direction changes)**

**Pattern:**
- Initial task: A
- Pivot 1: B (related to A)
- Pivot 2: C (related to B)
- → Too many pivots, spawn fresh for C

**Why:** Multiple pivots indicate fuzzy requirements. Fresh agent starts with clear scope.

---

### Question 5: Agent just started (<30 min)?

**If YES → Can try pivot with clear instructions**

**Requirements for successful pivot:**
- Pivot is refinement of current task
- Simple scope change
- Agent confirms understanding clearly
- No signs of confusion

**If NO (agent worked >30 min) → Spawn fresh**

**Why:** After 30 minutes, agent has significant context. Pivoting risks confusion.

---

## Specific Scenarios

### Scenario 1: Agent Completion with Issues

**Situation:** Agent marks complete but the user finds bugs during validation

**NEVER:**
- ❌ Send more instructions to completed agent
- ❌ Try to resume for "one more fix"
- ❌ Argue about whether it's actually complete
- ❌ Salvage out-of-context agents

**ALWAYS:**
- ✅ Spawn fresh debugging agent immediately
- ✅ Reference completed workspace for context
- ✅ Focused scope: "Fix issues X, Y, Z"

**Example:**
```bash
# Agent claims complete but validation fails
orch spawn systematic-debugging "Fix Phase A validation failures: no styling, $0.00 prices, run selector broken" --project price-watch
```

**Why this works:**
- Completed agent is mentally "done" and won't context-switch well
- Debugging needs different mindset than building
- Fresh agent reads workspace for full context
- Focused scope prevents scope creep

---

### Scenario 2: Mid-Work Redirection

**Situation:** Agent is working on Task A, the user wants pivot to Task B

**Decision tree:**

```
Is Task B related to Task A?
  ├─ YES: Is Task B refinement or expansion?
  │   ├─ Refinement → Can pivot if <30 min work so far
  │   └─ Expansion → Spawn fresh (preserve A's work, start B cleanly)
  └─ NO: Is Task A complete or incomplete?
      ├─ Complete → Spawn fresh for Task B
      └─ Incomplete → Ask the user: Complete A first or switch to B?
          ├─ Complete A → Let agent finish
          └─ Switch to B → Spawn fresh (abandon A or save for later)
```

**Example (Can Pivot):**
- Agent A: Implementing login form
- the user: "Actually, add password strength meter to login form"
- → Refinement, can pivot if <30 min work

**Example (Spawn Fresh):**
- Agent A: Implementing login form
- the user: "Actually, implement billing system instead"
- → Unrelated, spawn fresh

---

### Scenario 3: Agent Seems Confused

**Situation:** Agent is asking repeated questions or suggesting wrong approaches

**Red flags:**
- Agent asks about requirements already specified
- Suggests solutions that don't match the problem
- Repeats same suggestions after feedback
- Takes multiple attempts for simple changes
- Outputs code that doesn't compile/run

**Action: Spawn fresh**

**Why:** Confusion indicates context issues or misunderstanding. Salvaging deepens confusion.

**How to spawn fresh:**
```bash
# Reference previous agent's workspace for context
orch spawn feature-impl "Implement login form (see previous attempt in workspace/2025-11-21-feat-login)" --project myapp
```

---

## Red Flags (Spawn Fresh)

**Time-based:**
- Agent worked 2+ hours
- Agent worked >30 min and needs redirection

**Behavior-based:**
- Agent seems confused or repeating itself
- Agent asking questions about previously discussed topics
- Agent making basic errors

**Feedback-based:**
- the user says "out of context"
- the user says "spawn fresh"
- the user reports context issues

**Task-based:**
- Pivot is unrelated to current task
- Agent already pivoted once
- Validation failed after completion

---

## Green Lights (Can Pivot)

**All must be true:**
- ✅ Agent just started (<30 min)
- ✅ Task B is refinement of Task A (not new direction)
- ✅ Simple scope change (not complete rewrite)
- ✅ Agent confirms understanding clearly
- ✅ No signs of confusion

**Example successful pivot:**
```
Orchestrator: "Agent, please implement login form with email and password fields"
[Agent works for 15 minutes, creates basic form]
the user: "Add remember me checkbox to the form"
Orchestrator: "Adding remember me checkbox to the login form you're building"
[Agent adds checkbox successfully]
```

---

## Trust the user's Signals

**the user's feedback is ground truth.** Don't question or argue.

| the user Says | You Do | Don't Do |
|------------|--------|----------|
| "Out of context" | Spawn fresh | Question or salvage |
| "Spawn fresh" | Spawn fresh | Try to convince otherwise |
| "Test it first" | STOP and wait | Proceed with next phase |
| "This is broken" | Spawn debug agent | Question the bug report |
| "Agent is confused" | Spawn fresh | Explain more to agent |

**Why:** the user has context you don't (actual validation, system behavior, broader goals). Trust the signal.

---

## Anti-Patterns

### Anti-Pattern 1: "One More Try" Salvage

❌ **Wrong:**
```
the user: "This is broken, validation fails"
Orchestrator: "Let me send more detailed instructions to the agent..."
[Agent tries again, makes it worse]
```

✅ **Right:**
```
the user: "This is broken, validation fails"
Orchestrator: "Spawning fresh debug agent with focused scope..."
[Fresh agent reads workspace, fixes cleanly]
```

### Anti-Pattern 2: Pivot Chain

❌ **Wrong:**
```
Task A → Pivot to B → Pivot to C → Pivot to D
[Agent is lost, context scattered]
```

✅ **Right:**
```
Task A → Complete
Task B → Spawn fresh agent
Task C → Spawn fresh agent
[Each agent has clear focus]
```

### Anti-Pattern 3: Arguing with "Out of Context"

❌ **Wrong:**
```
the user: "Agent is out of context"
Orchestrator: "But the agent only worked 1 hour, let me try..."
[Wastes time, frustrates the user]
```

✅ **Right:**
```
the user: "Agent is out of context"
Orchestrator: "Spawning fresh agent immediately"
[Respects the user's signal, moves forward]
```

---

## Real-World Examples

### Example 1: Price-Watch Multi-Phase Validation

**Context:** Agent completed Phase A but validation failed

**Wrong approach (salvage):**
```
the user: "Phase A broken - $0.00 prices, styling missing"
Orchestrator: "Let me ask the agent to fix those issues..."
[Agent tries, but context-exhausted, makes more errors]
```

**Right approach (fresh spawn):**
```
the user: "Phase A broken - $0.00 prices, styling missing"
Orchestrator: "Spawning fresh debug agent..."
Command: orch spawn systematic-debugging "Fix Phase A: $0.00 prices, missing styling" --project price-watch
[Fresh agent reads workspace, fixes cleanly]
```

**Outcome:** Fresh agent fixed issues in 45 minutes. Salvage attempt would have taken 2+ hours and made things worse.

---

### Example 2: Mid-Work Pivot (Successful)

**Context:** Agent building feature, scope refinement needed

**Scenario:**
```
Initial: "Implement comparison view"
After 20 min: "Add export button to comparison view"
```

**Analysis:**
- Related: ✅ (export is part of comparison view)
- < 30 min: ✅
- Refinement: ✅ (not new direction)
- Agent understanding: ✅

**Action:** Pivot successful

**Command:**
```
"Please add export button to the comparison view you're building"
```

**Outcome:** Agent added feature cleanly without issues.

---

### Example 3: Mid-Work Pivot (Should Spawn Fresh)

**Context:** Agent building feature, unrelated task requested

**Scenario:**
```
Initial: "Implement comparison view"
After 1 hour: "Actually, work on billing system instead"
```

**Analysis:**
- Related: ❌ (billing unrelated to comparison)
- >30 min: ❌
- Unrelated: ❌

**Action:** Spawn fresh

**Why:** Comparison view context is irrelevant to billing. Fresh agent starts with billing context, not comparison baggage.

---

## Integration with Other Patterns

**Related patterns:**
- **Multi-Phase Validation:** When validation fails → spawn fresh debug agent (see `multi-phase-feature-validation.md`)
- **Trust User Signals:** Cross-cutting principle appearing in multiple patterns

**Cross-references:**
- Multi-phase validation Step 4 references this pattern

---

## Quick Reference Card

**Default assumption: Spawn fresh**

**Only salvage (pivot) if ALL true:**
- ✅ Agent worked <30 min
- ✅ Task B is refinement of Task A
- ✅ No confusion signs
- ✅ Agent confirms understanding
- ✅ the user hasn't said "out of context"

**the user signal → Action:**
- "Out of context" → Spawn fresh (no debate)
- "Spawn fresh" → Spawn fresh (trust signal)
- "This is broken" → Spawn fresh debug agent

**Common salvage temptations to resist:**
- "But agent only worked 1 hour..." → Still spawn fresh
- "Just one more fix..." → Spawn fresh debug agent
- "Agent is close to done..." → Spawn fresh if validation failed

---

## Maintenance

**When to update:**
- New failure pattern discovered (add to red flags)
- Successful pivot pattern identified (add to green lights)
- Integration with new patterns (update cross-references)

**Version history:**
- v1.0 (2025-11-21): Extracted from inline CLAUDE.md guidance

**Source in orchestration system:**
- Inline reference: `.orch/CLAUDE.md` (brief summary + link)
- Full pattern: `./agent-salvage-vs-fresh.md` (this file)
- Investigation origin: `.orch/investigations/2025-11-18-multi-phase-feature-orchestration-process-gaps.md`
