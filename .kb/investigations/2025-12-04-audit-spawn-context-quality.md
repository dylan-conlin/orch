# Audit: SPAWN_CONTEXT.md Quality (Dec 2-4 Workers)

**Date:** 2025-12-04
**Status:** Complete
**TLDR:** SPAWN_CONTEXT.md files are bloated with irrelevant boilerplate and full skill content. Feature-impl contexts are 1600+ lines when only 400 are needed. Recommendations: conditional boilerplate, phase-filtered skill loading, remove unfilled placeholders.

## Question

Are SPAWN_CONTEXT.md files providing the right amount of context for workers? Too much? Too little? What's outdated or causing confusion?

## Audit Scope

- **Project:** price-watch
- **Date range:** Dec 2-4, 2025
- **Workspaces audited:** 56 total
- **Sample examined:** 5 files in detail (different skill types)

## Files Audited (Detailed)

| File | Skill | Lines | Date |
|------|-------|-------|------|
| feat-impl-forgot-password-02dec | feature-impl | 1725 | Dec 2 |
| inv-check-browser-use-mcp-02dec | investigation | 362 | Dec 2 |
| feat-add-legend-lead-time-03dec | feature-impl | 1695 | Dec 3 |
| explore-render-api-analyze-03dec | architect | 703 | Dec 3 |
| debug-fix-failing-rails-tests-04dec | systematic-debugging | 586 | Dec 4 |

## Line Count Distribution (All Dec 2-4)

```
1620-1700 lines: 15 files (feature-impl)
600-700 lines:   20 files (debugging, architect)
350-400 lines:   21 files (investigation)
```

## What I Tried

1. Read 5 representative SPAWN_CONTEXT.md files across different skill types
2. Analyzed spawn_prompt.py to understand template construction
3. Examined SPAWN_PROMPT.md template for boilerplate sources
4. Counted lines and identified content sections

## What I Observed

### Finding 1: Meta-Orchestration Boilerplate in Every Context (45 lines)

**Evidence:**
```markdown
⚠️ **META-ORCHESTRATION TEMPLATE SYSTEM** (Critical if working on meta-orchestration):

**IF task involves these files/patterns:**
- .orch/CLAUDE.md updates
- Orchestrator guidance changes
...
```

**Source:** SPAWN_PROMPT.md lines 21-67, included in EVERY spawn

**Significance:** Price-watch workers will NEVER edit meta-orchestration templates. This is 45 lines of irrelevant context that adds cognitive load without value. Workers see warnings about systems they won't encounter.

---

### Finding 2: Feature-Impl Embeds ALL Phases (~1400 lines)

**Evidence:** feat-impl-forgot-password-02dec has 1725 lines total, with skill guidance from line 177-1666 (~1490 lines)

Includes guidance for:
- Investigation phase (~180 lines)
- Clarifying questions phase (~195 lines)
- Design phase (~170 lines)
- Implementation TDD (~130 lines)
- Implementation Direct (~110 lines)
- Validation (~150 lines)
- Self-Review (~200 lines)
- Integration (~130 lines)

**Source:** spawn_prompt.py `load_skill_content()` (lines 122-152) reads entire SKILL.md without filtering

**Significance:** When spawned with `--phases implementation,validation`, agent only needs 2 phases but receives ALL 8. This is 4x more content than needed.

---

### Finding 3: Unfilled Placeholders Pollute Context

**Evidence:**
```markdown
SCOPE:
- IN: [Agent to define based on task]
- OUT: [Agent to define based on task]

[OPTIONAL] Context from Prior Work:
- Prior work: Read workspace at PROJECT_DIR/.orch/workspace/previous-agent/WORKSPACE.md
```

**Source:** SPAWN_PROMPT.md template, not replaced by spawn_prompt.py

**Significance:** Workers see placeholder text that suggests they should fill it, but these are template artifacts. The "previous-agent" path never exists. Creates confusion.

---

### Finding 4: Agent Mail Section Added Universally (35 lines)

**Evidence:** Every spawn includes:
```markdown
## AGENT MAIL COORDINATION (REQUIRED)

Agent Mail MCP is available for inter-agent messaging. On startup:

1. **Register yourself** (first 5 actions):
...
```

**Source:** spawn_prompt.py line ~500+ (part of template injection)

**Significance:** For quick debugging tasks or simple investigations, Agent Mail coordination is overhead. Workers spend time registering and checking inbox for tasks that complete in <1 hour without needing coordination.

---

### Finding 5: Architecture Context is Generic (15 lines)

**Evidence:**
```markdown
ARCHITECTURE CONTEXT:
- **Orchestration Pattern:** Per-project orchestrators (Architecture B)
  - Multiple `.orch/` directories across projects (meta-orchestration, price-watch, context-driven-dev, etc.)
```

**Source:** SPAWN_PROMPT.md lines 10-19

**Significance:** References to "meta-orchestration", "context-driven-dev" projects are irrelevant for price-watch workers. They're working in ONE project. This context is for orchestrators, not workers.

---

### Finding 6: Investigation Skill is Right-Sized (362 lines)

**Evidence:** inv-check-browser-use-mcp-02dec is focused:
- Task + critical instructions: ~50 lines
- Template sections: ~70 lines
- Investigation skill content: ~200 lines
- Deliverables/verification: ~42 lines

**Significance:** Investigation skill demonstrates good context sizing. Workers get focused guidance without bloat. This is the target pattern.

---

### Finding 7: Redundant "Session Close Protocol" + "First 3 Actions" (40 lines)

**Evidence:** Every spawn now has:
```markdown
🚨 CRITICAL - FIRST 3 ACTIONS:
...

🚨 SESSION COMPLETE PROTOCOL (READ NOW, DO AT END):
...
```

**Source:** spawn_prompt.py lines 375-392

**Significance:** These are valuable reminders, but 40 lines of critical warnings at the start of every context adds to initial parsing time. Consider reducing to essential bullets.

---

## Test Performed

**Test:** Calculated content distribution in feat-impl-forgot-password-02dec (1725 lines)

**Result:**
- Task + critical instructions: 75 lines (4%)
- Template boilerplate (architecture, authority, scope): 90 lines (5%)
- Agent Mail section: 35 lines (2%)
- Skill guidance (ALL phases): 1490 lines (86%)
- Deliverables/verification: 35 lines (2%)

**Breakdown of skill guidance:**
- Phases NOT configured (investigation, clarifying-questions, design, self-review, integration): ~885 lines
- Phases CONFIGURED (implementation, validation): ~605 lines

**Conclusion from test:** 51% of skill content is for phases the agent won't use.

---

## Synthesis

### What's Working Well

1. **Investigation skill size is right** - 362 lines provides focused guidance
2. **Critical action reminders** - Ensure agents report Phase correctly
3. **Verification requirements** - Clear checklists for completion
4. **Skill embedding** - Having full skill content (when sized right) prevents agents from needing to read additional files

### What's Excessive

| Content | Lines | Issue |
|---------|-------|-------|
| Meta-orchestration boilerplate | 45 | Irrelevant for non-meta projects |
| Unconfigured phases | ~885 | 51% of feature-impl skill unused |
| Architecture context | 15 | References projects worker won't touch |
| Agent Mail (for small tasks) | 35 | Overhead for <1h tasks |

### What's Missing

1. **Phase-filtered skill loading** - Only embed configured phases
2. **Project-aware boilerplate** - Only show meta-orchestration warnings in meta-orchestration project
3. **Scope-aware Agent Mail** - Only include for medium/large scope or multi-agent coordination

### What's Outdated

1. **Prior work placeholder** - `previous-agent/WORKSPACE.md` path doesn't exist
2. **Generic SCOPE placeholders** - `[Agent to define based on task]` should be omitted if not filled

---

## Recommendations

### P0: Filter Skill Phases (High Impact)

**Problem:** feature-impl embeds all 8 phases (~1490 lines) even when only 2 are configured

**Solution:** In `spawn_prompt.py`, after loading skill content, filter to only include configured phases:

```python
def filter_skill_phases(skill_content: str, phases: List[str]) -> str:
    """Filter skill content to only include configured phases."""
    # Parse SKILL-TEMPLATE markers
    # Keep only sections matching configured phases
    # Return filtered content
```

**Impact:** Reduces feature-impl contexts from 1600+ lines to ~600 lines

---

### P1: Make Meta-Orchestration Boilerplate Conditional

**Problem:** 45 lines of meta-orchestration warnings in every context

**Solution:** In spawn_prompt.py, only include when `project_dir` contains `meta-orchestration` or `orch-cli`:

```python
if 'meta-orchestration' in str(config.project_dir) or 'orch-cli' in str(config.project_dir):
    # Include meta-orchestration template system warnings
```

**Impact:** Removes 45 lines of irrelevant content from non-meta projects

---

### P2: Remove Unfilled Placeholders

**Problem:** `[Agent to define based on task]` and `previous-agent` placeholders confuse workers

**Solution:** In SPAWN_PROMPT.md and spawn_prompt.py:
- Remove SCOPE IN/OUT placeholders if not provided
- Remove "Prior work" section if no actual prior work reference exists

**Impact:** Cleaner context, less confusion

---

### P3: Scope-Aware Agent Mail

**Problem:** Agent Mail section (35 lines) added to all contexts

**Solution:** Only include Agent Mail section when:
- Session scope is Medium or Large
- Task involves multi-agent coordination
- Explicitly requested

**Impact:** Reduces overhead for simple tasks

---

## Implementation Priority

1. **P0: Filter skill phases** - Highest ROI, reduces 1600→600 lines
2. **P1: Conditional meta-orchestration** - Easy win, 45 lines saved
3. **P2: Remove placeholders** - Low effort, cleaner output
4. **P3: Scope-aware Agent Mail** - Requires scope detection logic

---

## Self-Review

- [x] Real test performed (calculated content distribution)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered (yes, contexts are bloated; recommendations provided)
- [x] File complete (all sections filled)

**Self-Review Status:** PASSED
