# Pattern: TLDR Structure (30-Second Resumption Test)

**Source:** Workspace conventions, amnesia-resilience standards
**Related:** Amnesia compensation checklist, progressive disclosure pattern

---

## Summary

Every artifact starts with a TLDR section enabling 30-second resumption by fresh Claude instances. Answers three questions: What? Where are we? What's next?

**Pattern:**
```markdown
**TLDR:** [One sentence describing X.] [One sentence describing current status.] [One sentence describing next action or key constraint.]

<!--
Example TLDR:
"[Context-specific example showing pattern applied]"

Guidelines:
- Keep to 2-3 sentences maximum
- Answer: What? Where are we? What's next?
- Enable 30-second resumption check for fresh Claude
-->
```

---

## When to Use

**ALWAYS use for:**
- Workspaces (Problem/Goal → Status/Phase → Next action/Blocker)
- Investigations (Question → Answer → Confidence/Limitation)
- Knowledge artifacts (Pattern → When to apply → Confidence/Source)
- Any artifact spanning multiple sessions

**NEVER use for:**
- Code files (use docstrings/comments instead)
- Configuration files (context in comments)
- Single-session throwaway notes

---

## Application by Artifact Type

### Workspace TLDR

**Template:**
```markdown
**TLDR:** [One sentence describing the problem or goal.] [One sentence describing current status/phase.] [One sentence describing next action or blocker.]

<!--
Example TLDR:
"Investigating why worker agents aren't running tests despite documentation. Currently in Implementation phase, templates created and committed. Next: validate templates help agents follow test-running pattern."

Guidelines:
- Keep to 2-3 sentences maximum
- Answer: What problem? Where are we? What's next?
- Enable 30-second resumption check for fresh Claude
-->
```

**Key elements:**
- Sentence 1: Problem or goal (why does this exist?)
- Sentence 2: Current status/phase (where are we in the work?)
- Sentence 3: Next action or blocker (what happens next?)

---

### Investigation TLDR

**Template:**
```markdown
**TLDR:** [One sentence restating the investigation question.] [One-two sentences summarizing the answer/conclusion.] [Confidence level and key limitation.]

<!--
Example TLDR:
"Question: Why aren't worker agents running tests? Answer: Agents follow documentation literally but test-running guidance isn't in spawn prompts or CLAUDE.md, only buried in separate docs. High confidence (85%) - validated across 5 agent sessions but small sample size."

Guidelines:
- Keep to 2-3 sentences maximum
- Answer: What question? What's the answer? How confident?
- Enable 30-second understanding for fresh Claude
-->
```

**Key elements:**
- Sentence 1: Investigation question (what were we trying to learn?)
- Sentence 2: Answer/conclusion (what did we find?)
- Sentence 3: Confidence + limitation (how certain? what's uncertain?)

---

### Knowledge Artifact TLDR

**Template:**
```markdown
**TLDR:** [One sentence describing the pattern/principle.] [One sentence stating when to apply it.] [Confidence level and source.]

<!--
Example TLDR:
"Pattern: Directive guidance with transparency (strong recommendations + visible reasoning). Apply when presenting implementation options to enable informed single-word approvals. High confidence (98%) - derived from orchestrator interaction analysis across 8 sessions."

Guidelines:
- Keep to 2-3 sentences maximum
- Answer: What pattern? When to use? How confident?
- Enable 30-second understanding for fresh Claude
-->
```

**Key elements:**
- Sentence 1: Pattern/principle name and one-line explanation
- Sentence 2: When to apply (context and triggers)
- Sentence 3: Confidence + source (how certain? where from?)

---

## Guidelines for All TLDRs

**Length constraint:**
- 2-3 sentences MAXIMUM
- Each sentence should be clear and complete (no fragments)
- If you need more space, your TLDR isn't summarizing

**Content constraint:**
- Must answer artifact-specific questions (see above)
- Should enable resumption WITHOUT reading full artifact
- Include key constraint or limitation (confidence, blocker, trade-off)

**30-second resumption test:**
- Can a fresh Claude instance understand:
  - What this artifact is about?
  - Where things stand?
  - What to do next (or what the conclusion is)?
- If no → TLDR needs improvement

---

## Anti-Patterns

**❌ Don't:**
- Write multi-paragraph TLDRs (defeats purpose)
- Leave TLDR placeholder unfilled (template artifacts)
- Duplicate full content (it's a summary, not a copy)
- Use vague language ("working on improvements" - what improvements?)

**✅ Do:**
- Fill TLDR last (after artifact content is complete)
- Test by having someone read ONLY the TLDR
- Include specifics (names, numbers, states)
- Update TLDR when artifact status changes significantly

---

## Benefits

- **Fast resumption** - New Claude instance oriented in 30 seconds
- **Status at a glance** - Orchestrator can check multiple agents quickly
- **Reduces re-reading** - Context check without full artifact scan
- **Forces clarity** - If you can't summarize in 3 sentences, structure needs work

---

## Examples from Practice

### Good TLDR (Workspace)
```markdown
**TLDR:** Implementing Phase 2 of global knowledge distribution - extracting patterns to eliminate ~200 lines of duplication across templates. Currently in Planning phase, identified 3 patterns to extract (TLDR structure, confidence assessment, amnesia-resilience checklist). Next: extract patterns to patterns-src/ and update templates to reference them.
```

**Why this works:**
- Clear problem (Phase 2, eliminate duplication)
- Current state (Planning, 3 patterns identified)
- Next action (extract and update)

---

### Good TLDR (Investigation)
```markdown
**TLDR:** Question: Can we programmatically monitor Claude context usage to trigger checkpoints? Answer: No - Claude Code CLI provides no context metrics API, session transcripts are append-only JSONL without metadata. High confidence (95%) - confirmed via API docs, CLI source code, and direct testing.
```

**Why this works:**
- Clear question (programmatic monitoring?)
- Direct answer (No, here's why)
- Confidence + validation (95%, multiple sources)

---

### Bad TLDR (Too vague)
```markdown
**TLDR:** Working on improvements to the orchestration system. Making progress. More work needed.
```

**Why this fails:**
- No specifics (what improvements?)
- No current state (what's done? what phase?)
- No actionable next step (what work? when? who?)

---

**Location:** `docs/patterns/tldr-structure.md`

**Used in templates:**
- `WORKSPACE.md` - Top section (lines 7-17)
- `INVESTIGATION.md` - Top section (lines 7-17)
- `KNOWLEDGE.md` - Top section (lines 1-11)

**Related patterns:**
- Progressive disclosure (TLDR → Summary → Full details)
- Amnesia-resilience (enable resumption without memory)
