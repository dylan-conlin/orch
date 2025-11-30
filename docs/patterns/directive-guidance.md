# Pattern: Directive Guidance with Transparency

**Source:** Decision `2025-11-15-directive-guidance-transparency-principle.md`

---

## Summary

Present options with clear recommendations + visible reasoning. Enables informed single-word approvals ("proceed") while maintaining transparency.

**Pattern:**
```markdown
⭐ **RECOMMENDED:** [Option A]
- **Why:** [Reasoning based on evidence/findings]
- **Trade-off:** [What we're accepting and why that's OK]
- **Expected outcome:** [What this achieves]

**Alternative: [Option B]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended given context]
- **When to choose:** [Conditions where this makes sense]
```

---

## When to Use

**This pattern is ONLY for presenting alternatives** (Intent #3 in Communication Intent Taxonomy)

Use when you need to present **multiple viable approaches and recommend one**.

**ALWAYS use for:**
- Implementation recommendations (investigations → action with multiple approaches)
- Architectural choices (multiple viable approaches to choose between)
- Alternative completion paths (could finish via A or B or C)
- Task delegation decisions (continue vs checkpoint vs pivot)

**NEVER use for:**
- **Sequential workflows** (where all steps must be done in order - use sequential-plan-approval pattern instead)
- **Progress updates** ("I've done X, next I'll do Y" - just state it)
- **Procedural workflows** ("Step 1, Step 2, Step 3" - use numbered list, not A/B/C)
- Single obvious path (just state it directly)
- User explicitly asking for neutral analysis
- Trivial choices with no trade-offs

**Key distinction:**
- **Alternative choices** (choose A OR B OR C) → Use this pattern ✅
- **Sequential steps** (do 1 THEN 2 THEN 3) → Use sequential-plan-approval pattern ❌

---

## Application Examples

### In Investigation Templates

```markdown
## Implementation Recommendations

### Recommended Approach ⭐

**[Approach Name]** - [One sentence stating the recommendation]

**Why this approach:**
- [Key benefit 1 based on findings]
- [How this addresses investigation findings]

**Trade-offs accepted:**
- [What we're giving up]
- [Why that's acceptable given findings]
```

### In Workspace Handoff Notes

```markdown
**Recommendations for next steps:**

⭐ **RECOMMENDED:** [Specific next action]
- **Why:** [Reasoning based on work completed]
- **Trade-off:** [What we're accepting/deferring]
- **Expected outcome:** [What this achieves]

**Alternative: [Other option]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended given current state]
```

### In Decision Documents

```markdown
## Options Considered

### Option A: [Name]
[Description, Pros, Cons, Effort, Impact]

### Option B: [Name]
[Description, Pros, Cons, Effort, Impact]

### Option C: [Name] ⭐ SELECTED
[Description, Pros, Cons, Effort, Impact]

## Rationale

**Why Option C was selected:** [Synthesis of why C beats alternatives]
```

### Hybrid Case: Embedded Within Sequential Plans

Directive-guidance can be embedded as a sub-step within sequential plans when a choice point exists:

```markdown
## Migration Plan

**Goal:** Migrate database schema with version control

**Steps:**
1. Backup current database
2. **Choose migration tool:**

   ⭐ **RECOMMENDED:** Alembic
   - **Why:** Better version control, already in use
   - **Trade-off:** Learning curve

   **Alternative:** Django migrations
   - **Pros:** Simpler, team knows it
   - **Cons:** Less flexible

3. Set up migration tool
4. Test migration on staging

**Proceed with this plan?** (If you prefer Django migrations, say so)
```

**Key insight:** This is still sequential-plan-approval at the top level (steps 1→2→3→4), but step 2 contains a genuine choice that benefits from directive-guidance.

---

## Anti-Patterns

**❌ Don't:**
- Present neutral options without recommendation ("Here are 3 options, which do you prefer?")
- Hide reasoning ("Use Option A" without explaining why)
- Over-qualify ("Maybe consider possibly using Option A if that seems reasonable...")
- **Force sequential steps into choice format** (the "False Choice Fatigue" anti-pattern)

**✅ Do:**
- State recommendation clearly (⭐ marker)
- Explain reasoning (why this beats alternatives)
- Show trade-offs (what we're accepting)
- Provide escape hatch (when to use alternatives)

### Common Misapplication: Sequential Workflow Forced into Choice Format

**❌ WRONG - "False Choice Fatigue":**
```markdown
What do you want to do next:
  A) Run the tests
  B) Fix the failing tests
  C) Update the documentation
```
This presents sequential steps (all must be done) as alternatives (choose one).

**✅ CORRECT - Sequential Plan Approval:**
```markdown
Next steps:
  1. Run the tests
  2. Fix any failing tests
  3. Update the documentation

Proceed with this plan?
```
This correctly shows these are sequential steps, not alternatives.

**When to use directive-guidance instead:**
If there are genuinely *alternative* approaches (e.g., "We could test manually OR add automated tests OR skip testing" with different trade-offs), then directive-guidance applies.

---

## Benefits

- **Single-word approvals** - the user can respond "proceed" without re-analysis
- **Visible reasoning** - Future Claude sees WHY decision was made
- **Informed consent** - Trade-offs explicit, not hidden
- **Respects autonomy** - Strong opinion + transparency ≠ no choice

---

**Canonical source:** `.orch/decisions/2025-11-15-directive-guidance-transparency-principle.md`

**Part of:** Communication Intent Taxonomy (`.orch/decisions/2025-11-20-communication-intent-taxonomy.md`)
- This pattern is for **Intent #3: Presenting Alternatives**
- See taxonomy for when to use other intents/patterns

**Used in templates:**
- `INVESTIGATION.md` - Implementation Recommendations section (when multiple approaches exist)
- `WORKSPACE.md` - Recommendations for next steps section (when alternative completion paths exist)
- `DECISION.md` - Options Considered section

**Related patterns:**
- **Sequential-plan-approval** - Use for Intent #4 (sequential workflows)
- Progressive disclosure (TLDR → Details)
- Amnesia-resilience (externalize reasoning)
