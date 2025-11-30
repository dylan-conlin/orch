# Pattern: Confidence Assessment

**Source:** Investigation and knowledge artifact conventions
**Related:** Evidence-based decision making, amnesia-resilience standards

---

## Summary

Explicit confidence levels help future Claude instances calibrate trust in findings, decisions, and patterns. Uses 5-level scale with percentages, "what's certain/uncertain" breakdown, and conditions for increasing confidence.

**Confidence levels:**
- **Very High (95%+):** Strong evidence, minimal uncertainty, unlikely to change
- **High (80-94%):** Solid evidence, minor uncertainties, confident to act
- **Medium (60-79%):** Reasonable evidence, notable gaps, validate before major commitment
- **Low (40-59%):** Limited evidence, high uncertainty, proceed with caution
- **Very Low (<40%):** Highly speculative, more investigation needed

---

## When to Use

**ALWAYS use for:**
- Investigation findings (how certain is the answer?)
- Knowledge artifacts (how validated is this pattern?)
- Decision documents (how confident in this choice?)
- Any artifact containing durable recommendations

**NEVER use for:**
- Interactive recommendations (use ⭐ marker instead - see recommendation-patterns.md)
- Workspace status updates (use Phase/Status fields)
- Trivial facts ("Python uses indentation" - no confidence needed)
- Work-in-progress notes (confidence implies conclusion)

**Why the distinction?**
- **Durable artifacts** (investigations, decisions, knowledge) need confidence for future readers
- **Interactive contexts** (chat, real-time recommendations) benefit from simplicity
- Adding confidence to every statement creates noise, not clarity

---

## Full Assessment Template

Use this complete structure for investigations and knowledge artifacts:

```markdown
## Confidence Assessment

**Current Confidence:** [Level] ([Percentage])

**Why this level?**

[Explanation of why you chose this confidence level - what evidence supports it, what's strong vs uncertain]

**What's certain:**

- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]

**What's uncertain:**

- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]

**What would increase confidence to [next level]:**

- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]
```

---

## Abbreviated Template (Decisions)

For decision documents, use shorter confidence section:

```markdown
## Confidence Score

**[Level]** ([Percentage]) - [Brief confidence assessment]

**Why this level?**
- [Evidence supporting confidence]
- [What makes this reliable]

**What's certain:**
- [Known fact 1]
- [Known fact 2]

**What's uncertain:**
- [Unknown 1]
- [Unknown 2]

**Risk mitigation:**
- [How we handle uncertainty 1]
- [How we handle uncertainty 2]
```

---

## Choosing Confidence Levels

### Very High (95%+)

**When to use:**
- Strong direct evidence from multiple independent sources
- Validated through repeated application (5+ times)
- Minimal assumptions or dependencies
- Failure modes well understood and mitigated

**Example:**
"Very High (98%) - Pattern validated across 8 orchestration sessions with consistent results. Multiple agents applied successfully. Only uncertainty is edge cases at extreme scale (50+ concurrent agents)."

---

### High (80-94%)

**When to use:**
- Solid evidence from reliable sources
- Some validation in practice (2-4 applications)
- Minor uncertainties that don't affect core recommendation
- Edge cases identified but rare

**Example:**
"High (85%) - Investigated across 5 agent sessions showing consistent pattern. Small sample size is main limitation. Core mechanism understood and documented."

---

### Medium (60-79%)

**When to use:**
- Reasonable evidence but notable gaps
- Limited practical validation (1-2 applications)
- Some assumptions not fully tested
- Alternative explanations possible but less likely

**Example:**
"Medium (70%) - Evidence from code analysis and one agent session. Haven't tested at scale or with all agent types. Core logic sound but needs more validation before widespread use."

---

### Low (40-59%)

**When to use:**
- Limited evidence, mostly theoretical
- High degree of assumption
- Conflicting signals in data
- Significant unknowns affecting outcome

**Example:**
"Low (50%) - Based on initial code review only. No practical validation. Multiple factors could affect outcome. Requires experimentation before acting."

---

### Very Low (<40%)

**When to use:**
- Highly speculative
- Minimal evidence
- Many competing explanations equally plausible
- Preliminary exploration only

**Example:**
"Very Low (30%) - Initial hypothesis based on one observation. Many alternative explanations not ruled out. More investigation needed before drawing conclusions."

---

## Calibration Guidelines

**Avoid overconfidence:**
- Default to Medium (60-79%) unless strong evidence
- Very High requires extensive validation (5+ independent confirmations)
- If in doubt, go lower (easier to increase confidence than walk back overconfidence)

**Avoid underconfidence:**
- Don't use Low/Very Low for well-established facts
- Strong direct evidence → High minimum
- Replicated findings → Very High justified

**Update confidence as evidence changes:**
- Start Medium, increase with validation
- Document what evidence raised confidence in "Evolution History" section
- Lower confidence if contradictory evidence emerges

---

## What's Certain/Uncertain Breakdown

**Purpose:** Make uncertainty explicit and actionable

**What's certain:**
- List facts you're confident about (with evidence)
- These can be acted upon
- Mark with ✅

**What's uncertain:**
- List gaps, assumptions, unknowns
- These need validation or mitigation
- Mark with ⚠️

**Example:**
```markdown
**What's certain:**
- ✅ Agent-init script successfully logs spawn events (tested in 8 sessions)
- ✅ JSONL format is append-only and machine-readable
- ✅ Orchestrator can parse workspace files from agent sessions

**What's uncertain:**
- ⚠️ Unknown if pattern works with >10 concurrent agents (max tested: 4)
- ⚠️ Edge case: What happens if agent crashes before first workspace update?
- ⚠️ Performance impact of parsing large JSONL files (largest tested: 2MB)
```

---

## "What Would Increase Confidence" Section

**Purpose:** Create clear path to higher confidence

**Be specific:**
- Not: "More testing needed"
- Instead: "Test with 10+ concurrent agents across 3+ projects"

**Be actionable:**
- Not: "Better understanding of X"
- Instead: "Read source code for X at file.py:123-456, document findings"

**Be realistic:**
- List achievable next steps, not "solve all unknowns"
- Prioritize what would move confidence from Medium→High or High→Very High

**Example:**
```markdown
**What would increase confidence to Very High (95%+):**
- Test pattern across 5 more projects (currently only meta-orchestration)
- Validate with Large scope sessions (currently only Small/Medium tested)
- Confirm behavior with Python-based agents (currently only Claude Code CLI tested)
- Document and test failure modes (agent crash, JSONL corruption, etc.)
```

---

## Anti-Patterns

**❌ Don't:**
- Use confidence without justification ("High (85%)" with no explanation)
- Claim Very High confidence without extensive validation
- Leave What's Uncertain empty (everything has limitations)
- Use confidence scores in interactive contexts (chat messages, recommendations)

**✅ Do:**
- Explain WHY you chose that confidence level
- List specific evidence supporting confidence
- Be honest about limitations and gaps
- Update confidence as new evidence emerges
- Reserve confidence for durable artifacts only

---

## Examples from Practice

### Investigation: Programmatic Context Monitoring

```markdown
## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**
Direct evidence from three independent sources: API documentation review, CLI source code analysis, and hands-on testing. The answer is clear and unambiguous - no context monitoring API exists. Only minor uncertainty around potential undocumented features.

**What's certain:**
- ✅ Claude Code CLI provides no context usage metrics via API
- ✅ Session transcripts (JSONL) contain messages but no context metadata
- ✅ No /context command or equivalent in CLI
- ✅ Agent SDK documentation confirms no programmatic access to context

**What's uncertain:**
- ⚠️ Possible internal Anthropic tooling exists (not public)
- ⚠️ Future API additions might enable this (can't predict roadmap)

**What would increase confidence to 99%+:**
- Direct confirmation from Anthropic team (already Very High without this)
- Review of complete CLI source code (currently reviewed public parts only)
```

---

### Knowledge: Directive Guidance Pattern

```markdown
**Confidence:** Very High (98%)

**Why this level?**
Pattern derived from analysis of 8 orchestration sessions with consistent results. Multiple agents have applied successfully. Evidence shows clear benefit (single-word approvals, reduced re-analysis). Only limitation is small sample size relative to all possible contexts.

**What's certain:**
- ✅ Pattern works in orchestrator contexts (8/8 sessions successful)
- ✅ Enables single-word approvals ("proceed") without re-analysis
- ✅ Transparency + strong recommendation = better than neutral options
- ✅ Future Claude instances can see reasoning (amnesia-resilient)

**What's uncertain:**
- ⚠️ Effectiveness with users who prefer neutral analysis (not tested)
- ⚠️ Performance in time-critical contexts (usually collaborative contexts tested)
- ⚠️ Cross-cultural applicability (only tested with the user's communication style)

**What would increase confidence to 99%+:**
- Validation across 20+ sessions (currently 8)
- Testing with multiple users beyond the user
- Documented failure cases (haven't found any yet, which raises confidence)
```

---

**Location:** `docs/patterns/confidence-assessment.md`

**Used in templates:**
- `INVESTIGATION.md` - Full assessment template
- `KNOWLEDGE.md` - Full assessment template
- `DECISION.md` - Abbreviated confidence score section

**Related patterns:**
- Evidence-based decision making (confidence requires evidence)
- Amnesia-resilience (explicit confidence helps future Claude calibrate trust)
- Progressive disclosure (confidence in TLDR, details in assessment)
