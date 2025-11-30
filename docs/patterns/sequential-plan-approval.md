# Pattern: Sequential Plan Approval

**Source:** Decision `2025-11-20-communication-intent-taxonomy.md`

---

## Summary

Present multi-step sequential workflows as numbered plans with clear goal and simple approval question. Used when all steps are required (not alternatives) and must be executed in order.

**Pattern:**
```markdown
## Proposed Plan

**Goal:** [What this plan achieves]

**Steps:**
1. [First step - what happens first]
2. [Second step - what happens next]
3. [Third step - what follows]
4. [Final step - completion action]

**Proceed with this plan?**
```

**Contrast with directive-guidance:** No recommendation/alternatives needed because these are sequential steps (all must happen), not alternative approaches (choose one).

---

## When to Use

**This pattern is for sequential workflows** (Intent #4 in Communication Intent Taxonomy)

Use when you need to present **multi-step workflow where all steps are required**.

**ALWAYS use for:**
- Multi-step implementation plans (setup → build → test → deploy)
- Sequential debugging workflows (reproduce → isolate → fix → verify)
- Procedural workflows with natural ordering (backup → migrate → verify)
- Any workflow where steps depend on prior steps completing

**NEVER use for:**
- **Alternative approaches** (choose A or B or C - use directive-guidance pattern instead)
- Single-step actions ("Should I run tests?" - just ask directly)
- Informational updates ("I did X, next doing Y" - just state it)
- Optional steps (if steps can be skipped, use directive-guidance to explain trade-offs)

**Key distinction:**
- **Sequential steps** (do 1 THEN 2 THEN 3) → Use this pattern ✅
- **Alternative choices** (choose A OR B OR C) → Use directive-guidance pattern ❌

---

## Structure Elements

### Required Elements

**Goal:** One sentence describing what the plan achieves
- Why: Provides context for evaluating whether steps make sense
- Example: "Migrate database schema to support multi-tenancy"

**Steps:** Numbered list in execution order
- Why: Shows sequence clearly, makes dependencies obvious
- Use numbered list (1, 2, 3) not lettered (A, B, C) - numbers imply sequence, letters imply choice

**Proceed question:** Simple approval request
- Standard phrasing: "Proceed with this plan?" or "Proceed?"
- Invites approval or modification, not selection between alternatives

### Optional Elements

**Context:** Brief setup if plan needs justification
- When to include: If the user might ask "why this approach?"
- Keep brief: 1-2 sentences maximum

**Checkpoints:** Note where approval/verification needed mid-plan
- Example: "After step 2, I'll verify migrations succeeded before proceeding to step 3"
- Useful for long plans (5+ steps) or risky operations

**Estimated duration:** Time expectation for completing plan
- Example: "Estimated duration: 2-3 hours"
- Helps the user decide if timing works

---

## Application Examples

### Example 1: Simple Implementation Plan

```markdown
## Proposed Implementation Plan

**Goal:** Add rate limiting to API endpoints

**Steps:**
1. Add rate-limit middleware to Express app
2. Configure limits (100 req/min per IP)
3. Add tests for rate limit enforcement
4. Deploy to staging for verification

**Proceed with this plan?**
```

**Why this works:** Clear sequence, obvious order, all steps required. No alternatives to compare.

### Example 2: Debugging Plan with Checkpoints

```markdown
## Debugging Plan

**Goal:** Fix intermittent test failures in authentication suite

**Steps:**
1. Reproduce failure locally (run tests 50 times)
2. Add verbose logging around auth flow
3. Identify root cause from logs
4. Implement fix
5. Verify fix (run tests 100 times, expect 0 failures)

**Checkpoints:**
- After step 1: If can't reproduce, will escalate for guidance
- After step 3: Will share root cause analysis before implementing fix

**Proceed with this plan?**
```

**Why this works:** Shows checkpoints where I'll pause for alignment. Longer plan benefits from explicit verification points.

### Example 3: Plan with Context

```markdown
## Migration Plan

**Context:** Investigation showed current schema can't support upcoming multi-tenant feature.

**Goal:** Migrate database schema to support multi-tenancy

**Steps:**
1. Backup production database
2. Run schema migration scripts on staging
3. Verify data integrity on staging
4. Schedule production migration window with team
5. Execute migration on production
6. Verify production deployment

**Estimated duration:** 4-6 hours (steps 1-3 today, steps 4-6 scheduled for maintenance window)

**Proceed with this plan?**
```

**Why this works:** Context explains *why* (investigation finding), steps show *what*, duration sets expectations.

---

## Hybrid Case: Sequential Plan with Embedded Choice

Sometimes a sequential plan contains a decision point. Embed directive-guidance pattern as a sub-step:

```markdown
## Database Migration Plan

**Goal:** Migrate to new schema with version control

**Steps:**
1. Backup current database
2. **Choose migration tool:**

   ⭐ **RECOMMENDED:** Alembic
   - **Why:** Better version control, already in use for other services
   - **Trade-off:** Learning curve if team unfamiliar

   **Alternative:** Django migrations
   - **Pros:** Simpler, team already knows it
   - **Cons:** Less flexible for complex migrations

3. Set up migration tool with version control
4. Create initial migration from current schema
5. Test migration on staging database
6. Document migration process for team

**Proceed with this plan?** (If you prefer Django migrations, say so and I'll adjust steps 3-6)
```

**Why this works:**
- Overall structure is sequential (steps 1→2→3→4→5→6)
- Step 2 contains a genuine choice (Alembic vs Django migrations)
- Directive-guidance pattern embedded within step 2 for that choice
- Final question acknowledges the user can override the recommended choice

**Key insight:** Directive-guidance and sequential-plan-approval are composable - embed alternatives within sequential plans when sub-decisions exist.

---

## Anti-Patterns

**❌ Don't:**
- Use lettered lists (A, B, C) - implies choice, not sequence
- Ask "Which step should I do?" - they're sequential, do all in order
- Include optional steps without explaining when to skip
- Mix alternatives and sequences without clear distinction

**✅ Do:**
- Use numbered lists (1, 2, 3) - implies sequence
- Ask "Proceed with this plan?" - seeks approval for whole sequence
- Make all steps required, or explicitly note which are optional
- Embed directive-guidance for sub-decisions within the sequence

### Common Anti-Pattern: False Choice from Sequential Steps

**❌ WRONG:**
```markdown
What should we do next:
  A) Run the tests
  B) Fix the failing tests
  C) Update the documentation
```
This presents sequential steps as alternatives.

**✅ CORRECT:**
```markdown
Next steps:
  1. Run the tests
  2. Fix any failing tests
  3. Update the documentation

Proceed?
```

---

## Comparison with Directive-Guidance

| Aspect | Sequential Plan Approval | Directive Guidance |
|--------|-------------------------|-------------------|
| **Purpose** | Present sequential workflow | Present alternative approaches |
| **Structure** | Numbered steps (1, 2, 3) | Lettered options (A, B, C) |
| **Question** | "Proceed with plan?" | "Which approach?" (implied) |
| **Recommendation** | Not needed (only one path) | Required (⭐ marker) |
| **Trade-offs** | Not needed (no alternatives) | Required (compare options) |
| **Use when** | All steps must happen | Choose one approach |

**They're complementary, not competing:**
- If you have one sequential path → Sequential plan approval
- If you have multiple alternative paths → Directive guidance
- If you have sequential path with embedded choice → Sequential plan with directive-guidance sub-step

---

## Benefits

- **Clarity:** Numbered sequence makes order obvious
- **Simplicity:** No trade-off analysis needed (only one path)
- **Modifiability:** the user can say "proceed but skip step 3" or "add step X between 2 and 3"
- **No false choices:** Doesn't force sequential steps into alternative format
- **Composability:** Can embed directive-guidance for sub-decisions

---

## When NOT to Use This Pattern

**Use directive-guidance instead if:**
- Multiple viable approaches exist (implement via A or B or C)
- Steps are alternatives, not sequence (choose testing strategy: manual OR automated OR skip)
- Trade-offs between approaches need explanation

**Just state it directly if:**
- Single obvious next step ("Running tests now...")
- Progress update ("Completed step 1 of 3, continuing...")
- Informational FYI ("Tests passed, moving to deployment")

**Use checkpoint pattern if:**
- Mid-work alignment check ("Completed Phase 1. Continue to Phase 2?")
- Context approaching limits (need pause before continuing)

---

**Canonical source:** `.orch/decisions/2025-11-20-communication-intent-taxonomy.md`

**Part of:** Communication Intent Taxonomy
- This pattern is for **Intent #4: Sequential Plan Approval**
- See taxonomy for when to use other intents/patterns

**Related patterns:**
- **Directive-guidance** - Use for Intent #3 (alternative approaches)
- **Hybrid case** - Embed directive-guidance within sequential plan for sub-decisions
- Progressive disclosure (TLDR → Details)
- Amnesia-resilience (externalize reasoning)

---

## Quick Reference

**Before presenting a plan, ask:**

1. **Are these sequential steps or alternatives?**
   - Sequential (all required in order) → Use this pattern ✅
   - Alternatives (choose one path) → Use directive-guidance ❌

2. **Does the sequence contain any choices?**
   - No choices → Pure sequential plan
   - Yes, sub-decisions exist → Hybrid (embed directive-guidance for those sub-steps)

3. **Is this even a plan or just an update?**
   - Multi-step plan needing approval → Use this pattern
   - Single step or progress update → Just state it directly

**Success criteria:**
- ✅ Steps numbered (1, 2, 3) not lettered (A, B, C)
- ✅ All steps are required (or explicitly marked optional)
- ✅ Clear goal stated upfront
- ✅ Simple proceed question (not choosing between alternatives)
- ✅ the user can approve/modify easily
