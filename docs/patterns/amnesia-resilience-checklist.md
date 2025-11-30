# Pattern: Amnesia-Resilience Checklist

**Source:** CDD essentials, amnesia compensation checklist
**Related:** TLDR structure, progressive disclosure, confidence assessment

---

## Summary

Amnesia-resilience sections provide quick-reference checklists and red flag tests enabling fresh Claude instances to apply artifact guidance without reading full context or remembering previous sessions.

**Core principle:** Every artifact exists to help the NEXT Claude instance resume work without memory of previous sessions.

---

## When to Use

**ALWAYS use for:**
- Decision documents (how to apply this decision?)
- Knowledge artifacts (how to use this pattern?)
- Investigation recommendations (how to implement findings?)
- Any artifact with actionable guidance

**NEVER use for:**
- Workspaces (use Next Step field instead)
- Work-in-progress notes (not finalized guidance)
- Historical records (no action expected)

---

## Standard Template

```markdown
## Amnesia-Resilience

**For future Claude instances:**

[Clear, actionable guidance for applying this decision/pattern/finding]

**Checklist:**
- [ ] [Action 1 - specific, observable]
- [ ] [Action 2 - includes verification step]
- [ ] [Action 3 - with concrete example if helpful]
- [ ] [Action 4 - links to relevant files/docs]

**Red flag test:** [Simple yes/no question to check if guidance is being followed]

If no → [Corrective action - what to do instead]

**Success indicators:**
- ✅ [Observable outcome 1]
- ✅ [Observable outcome 2]

**Failure indicators:**
- ❌ [Red flag 1 - pattern not working]
- ❌ [Red flag 2 - misapplication]
```

---

## Checklist Guidelines

**Make items specific and actionable:**
- ❌ Bad: "Consider the architecture"
- ✅ Good: "Read `.orch/decisions/architecture.md` before adding new commands"

**Include verification steps:**
- ❌ Bad: "Update the workspace"
- ✅ Good: "Update workspace Phase field and verify Status aligns (see field validation rules)"

**Link to relevant context:**
- ❌ Bad: "Follow the pattern"
- ✅ Good: "Apply directive guidance pattern (see `directive-guidance.md`)"

**Keep items atomic:**
- Each checkbox should be a single, clear action
- If an item needs sub-items, it's probably multiple actions

---

## Red Flag Test Guidelines

**Purpose:** Quick binary check whether guidance is being followed

**Structure:**
1. Simple yes/no question
2. Clear corrective action if answer is "no"

**Examples:**

**Good red flag tests:**
```markdown
**Red flag test:** Are you presenting multiple options WITHOUT a clear recommendation?

If yes → You're not applying directive guidance pattern. Add ⭐ marker and "Why" reasoning.
```

```markdown
**Red flag test:** Does the workspace have Phase: Complete but Next Step lists more work?

If yes → Invalid state. Either mark Phase: Implementation or change Next Step to "None"
```

```markdown
**Red flag test:** Did you skip the pre-spawn artifact check (orch search)?

If yes → Search now before spawning. You might be duplicating existing work.
```

**Bad red flag tests:**
```markdown
**Red flag test:** Is everything working correctly?

If no → Fix it
```
*(Too vague - what's "correctly"? What specifically to check?)*

```markdown
**Red flag test:** Have you considered all architectural implications?

If no → Think more about architecture
```
*(Not binary - hard to answer yes/no. No specific corrective action.)*

---

## Success/Failure Indicators

**Success indicators:**
- Observable outcomes showing pattern is working
- Specific, measurable (not "things are better")
- Mark with ✅

**Failure indicators:**
- Red flags showing misapplication or not working
- Help Claude recognize when to stop/adjust
- Mark with ❌

**Examples:**

```markdown
**Success indicators:**
- ✅ Orchestrator can approve with single word ("proceed") without asking clarifying questions
- ✅ Decision documents include ⭐ marker showing recommended option
- ✅ Alternatives listed with "Cons" explaining why not recommended

**Failure indicators:**
- ❌ Orchestrator asking "which option do you think is best?" (recommendation wasn't clear)
- ❌ Options presented neutrally without star marker or preference stated
- ❌ Alternatives missing "when to use instead" guidance (incomplete directive guidance)
```

---

## Context-Specific Variations

### For Decision Documents

Focus on application of the decision:

```markdown
## Amnesia-Resilience

**For future Claude instances:**

When [triggering condition], apply this decision by [specific action].

**Checklist:**
- [ ] Verify [precondition] before applying
- [ ] Follow [specific pattern or process]
- [ ] Document [what needs tracking]
- [ ] Validate [success criteria]

**Red flag test:** [Check if decision is being followed]

If no → [Corrective action]
```

---

### For Knowledge Artifacts (Patterns)

Focus on how to apply the pattern:

```markdown
## Amnesia-Resilience

**For future Claude instances:**

**Quick application checklist:**
- [ ] Verify pattern applies (check "When to Use" section)
- [ ] Apply core element 1 (see "The Pattern" section)
- [ ] Apply core element 2
- [ ] Validate outcome (see "Success indicators")

**Common mistakes to avoid:**
1. [Mistake 1 and how to catch it]
2. [Mistake 2 and how to prevent it]

**Success indicators:**
- ✅ [Observable outcome 1]
- ✅ [Observable outcome 2]

**Failure indicators:**
- ❌ [Red flag 1]
- ❌ [Red flag 2]
```

---

### For Investigations

Focus on implementing the findings:

```markdown
## Amnesia-Resilience

**For future Claude instances:**

Key finding: [One sentence summary of answer]

**To implement this finding:**
- [ ] [Specific action based on finding 1]
- [ ] [Specific action based on finding 2]
- [ ] [Verification step]

**Red flag test:** [Check if finding is being applied correctly]

If no → [What to do instead]

**This replaces:** [What old approach/assumption this finding invalidates]
```

---

## Examples from Practice

### Decision Document Example

```markdown
## Amnesia-Resilience

**For future Claude instances:**

When presenting implementation options (investigations → recommendations, architectural choices, next steps), use directive guidance pattern: strong recommendation + visible reasoning.

**Checklist:**
- [ ] Mark recommended option with ⭐
- [ ] Explain WHY (benefits, how it addresses findings)
- [ ] Show trade-offs accepted (what we're giving up, why that's OK)
- [ ] Provide alternatives with "when to use instead" guidance

**Red flag test:** Are you presenting options WITHOUT stating which you recommend?

If yes → Add ⭐ marker, "Why" section, and trade-offs. Enable single-word approval.

**Success indicators:**
- ✅ the user can respond "proceed" without asking "which one?"
- ✅ Future Claude can see WHY decision was made
- ✅ Trade-offs are explicit, not hidden

**Failure indicators:**
- ❌ Neutral presentation ("here are 3 options, which do you prefer?")
- ❌ No reasoning visible ("use Option A" without explaining why)
- ❌ the user asks clarifying questions that should have been answered
```

---

### Knowledge Artifact Example

```markdown
## Amnesia-Resilience

**For future Claude instances:**

**Quick application checklist:**
- [ ] Check trigger: Multiple options exist AND trade-offs matter
- [ ] Mark recommendation with ⭐ RECOMMENDED
- [ ] Add "Why this approach:" section with 2-3 key benefits
- [ ] Add "Trade-offs accepted:" section with what we're giving up
- [ ] Add "Alternative:" sections with "When to use instead"
- [ ] Verify the user can approve with one word

**Common mistakes to avoid:**
1. Neutral presentation - If you have an opinion, state it clearly
2. Missing alternatives - Always show what else was considered
3. Hidden reasoning - "Why" must be visible, not just in your head

**Success indicators:**
- ✅ ⭐ marker clearly shows recommendation
- ✅ Reasoning is visible and evidence-based
- ✅ Alternatives include "when to use instead"

**Failure indicators:**
- ❌ All options presented equally (no star marker)
- ❌ Recommendation without reasoning (just "use X")
- ❌ Alternatives missing usage guidance
```

---

## Anti-Patterns

**❌ Don't:**
- Write checklists that require prior session memory
- Use vague items ("consider the implications")
- Skip red flag tests (they're critical for self-correction)
- Make success indicators subjective ("code quality improves")

**✅ Do:**
- Write checklists that work from cold start (links to relevant docs)
- Use specific, actionable items
- Include red flag tests that catch common mistakes
- Make success/failure indicators observable and concrete

---

## Benefits

- **Cold start resumption** - Fresh Claude can apply guidance immediately
- **Self-correction** - Red flags catch mistakes before they compound
- **Quality baseline** - Success indicators define "good enough"
- **Reduces re-work** - Clear checklist prevents forgetting steps

---

**Location:** `docs/patterns/amnesia-resilience-checklist.md`

**Used in templates:**
- `DECISION.md` - Amnesia-Resilience section
- `KNOWLEDGE.md` - Amnesia-Resilience section
- `INVESTIGATION.md` - Could add (currently missing)

**Related patterns:**
- TLDR structure (first-pass understanding)
- Progressive disclosure (quick reference → full details)
- Confidence assessment (calibrates trust in checklist guidance)
