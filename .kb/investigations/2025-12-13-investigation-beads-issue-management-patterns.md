# Investigation: Beads Issue Management Patterns

**Date:** 2025-12-13  
**Subject:** Analysis of Steve Yegge's beads database for issue tracking best practices  
**Purpose:** Extract actionable patterns for replicating this approach in other projects

---

## Executive Summary

After analyzing 465 issues in the beads repository, clear patterns emerge that make this issue tracking system highly effective for AI-supervised development workflows. The key insight: **treat issues as living documents with enough context for any future reader (human or AI) to resume work without prior knowledge**.

### Key Metrics

| Metric | Value | Significance |
|--------|-------|--------------|
| Total issues | 465 | High-volume usage indicates dogfooding |
| Completion rate | 79% (367/465) | Healthy closure rate |
| Average lead time | 39.7 hours | Fast cycle time |
| Issues with descriptions | 65% (302) | Most issues have context |
| Average description length | 609 characters | Substantial detail |
| Issues with dependencies | 112 (24%) | Active dependency tracking |

---

## Part 1: Issue Type Usage Patterns

### Distribution Analysis

```
task    274 (59%)  ████████████████████████████████████████
bug      97 (21%)  ██████████████
feature  54 (12%)  ████████
epic     29 (6%)   ████
chore    11 (2%)   █
```

### Pattern: Task-Heavy, Granular Decomposition

**Observation:** Tasks dominate (59%) over features (12%).

**Insight:** Large features are broken into small, closeable tasks. This aligns with AI agent workflows where:
- Smaller units = clearer success criteria
- Faster closure = better momentum
- Granular tracking = easier parallel work

**Example Pattern:**
```
bd-44d0 [epic]  "WASM port of bd for Claude Code Web sandboxes"
├── bd-197b [task]  "Set up WASM build pipeline"
├── bd-c77d [task]  "Test SQLite WASM compatibility"  
├── bd-1c77 [task]  "Implement filesystem shims for WASM"
├── bd-cc03 [task]  "Build Node.js CLI wrapper for WASM"
├── bd-374e [task]  "WASM integration testing"
└── bd-8507 [task]  "Publish bd-wasm to npm"
```

**Recommendation:** Default to `task` type. Use `feature` only for standalone, externally-visible changes. Use `epic` to group related tasks.

### Pattern: Bug Reports as Forensic Documents

**Observation:** 97 bugs (21%) with detailed reproduction context.

**Example (bd-f2f - Critical sync bug):**
```markdown
## Root Cause

The fix in bd-53c (reverse ZFC check) only checks COUNTS, not content.
The real corruption happens when:

1. Polecat A has stale DB with old status values
2. Polecat A runs bd sync:
   - **Export FIRST**: DB (status=closed) → JSONL
   - Commit: Stale JSONL committed
   - Pull: 3-way merge with remote
   - Merge uses 'closed wins' rule

## Evidence

From user investigation:
- At 595b7943 (13:20:30): 5 open issues
- At 10239812 (13:28:39): 0 open issues
- All 5 issues had their status changed from open to closed
```

**Forensic Elements Present:**
- Exact timestamps
- Git commit hashes
- Step-by-step reproduction
- Root cause analysis
- Why previous fixes failed
- Specific evidence with before/after states

**Recommendation:** Bugs should answer: What broke? When? How to reproduce? What was tried? What evidence proves the theory?

---

## Part 2: Priority Usage Patterns

### Distribution Analysis

```
P0 (Critical)   41 (9%)   █████
P1 (High)      148 (32%)  ████████████████████
P2 (Medium)    196 (42%)  ██████████████████████████
P3 (Low)        59 (13%)  ████████
P4 (Backlog)    21 (5%)   ███
```

### Pattern: P0 Reserved for Real Emergencies

**Observation:** Only 9% of issues are P0, but they include:
- "CRITICAL: bd sync exports before pull, allowing stale DB to corrupt JSONL"
- "CRITICAL: git-history-backfill purges entire database"
- Data corruption bugs
- CI failures blocking all development

**P0 Qualification Criteria (inferred):**
1. Data loss or corruption possible
2. Blocks all other development
3. Security vulnerability
4. Build/CI completely broken

**Recommendation:** P0 is for "stop everything and fix this." If you have many P0s, your system is in crisis or your priorities are miscalibrated.

### Pattern: P1 as the Active Work Queue

**Observation:** P1 is the largest priority bucket (32%).

**Insight:** P1 represents "important work that should happen soon." It's the natural queue for what to work on next. Combined with `bd ready` (unblocked issues), P1 ready items are the primary work source.

**Current Ready Queue:**
```
P1: 1 ready   ← Active work
P2: 8 ready   ← Backlog
P3: 1 ready   ← Low priority
```

**Recommendation:** Use P1 for "will work on this week." P2 is "will work on eventually." P3/P4 is "good ideas, not urgent."

---

## Part 3: Description Quality Patterns

### The 609-Character Average

Issues average 609 characters in descriptions—roughly 4-6 sentences or a focused paragraph with code snippets.

### Pattern: Problem-Solution-Evidence Structure

**Best descriptions follow this template:**

```markdown
## Problem [What's wrong / What's needed]
<1-2 sentences explaining the issue or requirement>

## Root Cause / Context [Why it happens]
<Technical explanation with file paths, code snippets>

## Solution / Approach [How to fix it]
<Proposed implementation with code examples>

## Evidence / Acceptance Criteria [How to verify]
<Test cases, expected behavior, or checklist>
```

**Example (bd-imj - Deletion propagation epic):**

| Section | Content |
|---------|---------|
| Problem | "When `bd cleanup` removes issues, deletions don't propagate to other clones" |
| Root Cause | "Import sees DB issues not in JSONL and assumes 'local unpushed work'" |
| Solution | "Add `.beads/deletions.jsonl` - append-only log with format spec" |
| Evidence | Conflict resolution rules, pruning policy, size estimates |

### Pattern: Code Snippets Embedded in Issues

**Observation:** Technical issues include inline code showing:
- Current behavior
- Proposed changes
- Configuration examples

**Example from bd-1r5 (TTL design):**
```go
func (t *Tombstone) IsExpired(ttl time.Duration) bool {
    expiresAt := t.DeletedAt.Add(ttl).Add(clockSkewGrace)
    return time.Now().After(expiresAt)
}
```

**Recommendation:** Include code snippets when they clarify the issue. A 10-line snippet is worth 100 words of description.

### Pattern: File Path References

Issues reference exact locations:
- `internal/importer/importer.go:865-869`
- `cmd/bd/compact.go:925-929`
- `internal/storage/sqlite/queries.go:1186`

**Recommendation:** Always include file:line references. Agents can jump directly to relevant code.

---

## Part 4: Epic Structure Patterns

### Anatomy of a Well-Structured Epic

**Example: bd-vw8 (12 child tasks)**

```
bd-vw8 [epic] "Switch from deletions manifest to inline tombstones"
│
├── Problem Statement (why change)
├── Proposed Solution (high-level design)
├── Design Decisions Needed (open questions)
├── Migration Strategy (rollout plan)
├── Related Issues (context)
│
└── Children:
    ├── bd-1r5 [task] "Design tombstone TTL and expiration semantics"
    ├── bd-2m7 [task] "Design tombstone storage format"
    ├── bd-dli [task] "Design migration path from deletions.jsonl"
    ├── bd-zvg [task] "Design tombstone merge semantics"
    ├── bd-6f9 [task] "Implement tombstone creation in bd delete"
    ├── bd-kp3 [task] "Implement tombstone filtering in queries"
    ├── bd-m8n [task] "Implement tombstone TTL expiration"
    ├── bd-q2w [task] "Update export to include tombstones"
    ├── bd-r5t [task] "Update import to handle tombstones"
    ├── bd-u9i [task] "Add tombstone compaction to bd compact"
    ├── bd-w4o [task] "Update bd deleted command for tombstones"
    └── bd-y7p [task] "Add migration command bd migrate-tombstones"
```

### Pattern: Design Tasks Before Implementation

**Observation:** Large epics have explicit "Design X" tasks that produce design documents.

**Example (bd-2m7 design field):**
```markdown
# Design: Tombstone Storage Format

**Issue:** bd-2m7  
**Author:** beads/refinery  
**Status:** Draft  

## Overview
Defines JSON schema for tombstone records...

## Design Decision: Minimal Tombstone with Audit Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Original issue ID |
| status | string | Yes | Always "tombstone" |
...
```

**Recommendation:** For complex features, create design tasks that produce written decisions before implementation tasks.

### Pattern: Child Tasks Reference Parent

Child task descriptions start with parent reference:
```markdown
Parent: bd-imj

## Task
Optionally prune deletions manifest during sync...
```

**Recommendation:** Always link children to parents in descriptions. Dependency tracking is structural; description references are navigational.

---

## Part 5: Dependency Usage Patterns

### Statistics

- 112 issues (24%) have dependencies
- Largest dependency trees: bd-vw8 (12), bd-imj (9)
- Most dependencies are `blocks` type (hard dependencies)

### Pattern: Dependencies for Sequencing, Not Just Blocking

**Example dependency chain:**
```
bd-197b "Set up WASM build pipeline"
    ↓ blocks
bd-c77d "Test SQLite WASM compatibility"
    ↓ blocks
bd-374e "WASM integration testing"
    ↓ blocks  
bd-8507 "Publish bd-wasm to npm"
```

**Insight:** Dependencies create a natural execution order. `bd ready` shows what's unblocked.

### Pattern: discovered-from Links

When work discovers new issues:
```bash
bd create "Found bug in auth" --deps discovered-from:bd-123
```

This creates audit trail: "This bug was discovered while working on bd-123."

**Recommendation:** Use `discovered-from` liberally. It explains why issues exist and prevents duplicate discovery.

---

## Part 6: Workflow Velocity Patterns

### Issue Creation Velocity

Recent 2-week activity:
```
2025-12-05: 28 issues  ← Highest activity day
2025-12-02: 22 issues
2025-12-13: 15 issues
2025-11-30: 15 issues
2025-11-27: 11 issues
```

**Insight:** Issue creation is bursty—discovery happens in waves during active development.

### Pattern: Rapid Closure on Critical Bugs

P0 bugs show fast turnaround:
- bd-pg1: Created 17:27, closed 17:42 (15 minutes)
- bd-0v4: Created 00:54, closed 01:36 (42 minutes)

**Recommendation:** P0 should have <4 hour resolution target. If P0s linger, they're misprioritized.

---

## Part 7: The Notes Field Pattern

### Usage Statistics

- 32 issues (7%) have notes
- Notes contain progress updates, code review results, investigation findings

### Example (bd-1022 - External ref import)

```markdown
## Code Review Complete ✅

**Overall Assessment**: EXCELLENT - Production ready

### Implementation Quality
- ✓ Clean architecture with proper interface extension
- ✓ Dual backend support (SQLite + Memory)
- ✓ Smart matching priority: external_ref → ID → content hash

### Follow-up Issues Filed
High Priority (P2):
- bd-897a: Add UNIQUE constraint on external_ref column
- bd-7315: Add validation for duplicate external_ref

**Confidence Level**: 95% - Ship it! 🚀
```

**Recommendation:** Use `notes` for:
- Progress updates during work
- Code review summaries
- Investigation findings
- Anything that enriches but doesn't change the core issue

---

## Part 8: Anti-Patterns Observed

### What's NOT in the Database

1. **No vague titles:** Every title is specific and actionable
2. **No empty descriptions on complex issues:** P0/P1 issues always have context
3. **No orphan tasks:** Most tasks link to epics or have discovery chains
4. **No stale in_progress:** Only 1 issue is `in_progress` currently

### Implicit Rules (Inferred)

| Anti-Pattern | Evidence of Avoidance |
|--------------|----------------------|
| "Fix bug" titles | All bugs have specific identifiers: "Fix G104 errors in queries.go:1186" |
| Scope creep | Issues stay focused; new discoveries become new issues |
| Priority inflation | P0 reserved for genuine emergencies (9%) |
| Zombie issues | 79% closure rate; stale issues get triaged |

---

## Part 9: Recommendations for Adoption

### Starting from Scratch

1. **Initialize with clear prefix:**
   ```bash
   bd init --prefix myproj
   ```

2. **Set priority definitions in your AGENTS.md:**
   ```markdown
   - P0: Production down, data loss, security breach
   - P1: Blocks release, major functionality broken
   - P2: Should fix soon, impacts users
   - P3: Nice to have, polish
   - P4: Future ideas, backlog
   ```

3. **Establish issue templates mentally:**
   - Bug: Problem → Reproduction → Evidence → Fix
   - Task: Context → Implementation → Verification
   - Epic: Problem → Solution → Children

### Daily Workflow

```bash
# Start of session
bd ready                    # What's unblocked?
bd stats                    # Overall health check

# During work
bd update <id> --status in_progress
bd create "Found issue" --deps discovered-from:<id>  # Discoveries

# End of session
bd close <id> --reason "Completed"
bd sync                     # Commit and push
```

### Epic Creation Workflow

```bash
# 1. Create epic with full design
bd create "Large feature name" -t epic -p 1 \
  --description="## Problem\n...\n## Solution\n...\n## Tasks\n..."

# 2. Create child tasks
bd create "Design phase" -t task -p 1 --deps parent-child:<epic-id>
bd create "Implementation" -t task -p 1 --deps blocks:<design-task-id>
bd create "Testing" -t task -p 2 --deps blocks:<impl-task-id>

# 3. Verify structure
bd dep tree <epic-id>
```

### Quality Checklist for New Issues

Before creating, ensure:

- [ ] Title is specific and searchable
- [ ] Description explains WHY (not just what)
- [ ] File paths included if code-related
- [ ] Priority reflects actual urgency
- [ ] Dependencies set if sequencing matters
- [ ] Type accurately reflects the work

---

## Part 10: Key Takeaways

### For AI Agent Workflows

1. **Self-contained issues:** Any agent should understand the issue without conversation history
2. **Granular tasks:** Smaller = easier to complete in one session
3. **Discovery chains:** Link new findings to source issues
4. **JSON output:** Always use `--json` for programmatic consumption

### For Human Oversight

1. **P0 alerts:** Few P0s = healthy system
2. **Ready queue:** `bd ready` is the primary work source
3. **Epic progress:** Track completion via dependency trees
4. **Velocity:** Monitor creation vs closure rates

### For Both

1. **Descriptions are documentation:** Write for the reader who has no context
2. **Dependencies are contracts:** They define execution order
3. **Notes are progress journals:** Update as work progresses
4. **Closure is commitment:** Close with reason, not just status change

---

## Appendix: Example Issue Templates

### Bug Report Template

```markdown
## Problem
<What's broken? User-visible impact?>

## Reproduction
1. Step one
2. Step two
3. Observe: <broken behavior>

## Expected
<What should happen>

## Evidence
- Commit: <hash>
- Timestamp: <when observed>
- Logs: <relevant output>

## Root Cause (if known)
<Technical explanation>

## Proposed Fix
<Implementation approach>
```

### Task Template

```markdown
## Context
<Why does this task exist? Link to parent epic if applicable>

## Implementation
<What needs to be done? Include code examples if helpful>

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests pass

## Files to Modify
- `path/to/file.go:123` - Add X
- `path/to/other.go` - Update Y
```

### Epic Template

```markdown
## Problem Statement
<What problem does this epic solve?>

## Proposed Solution
<High-level approach>

## Design Decisions
1. Decision 1: <option chosen> because <reason>
2. Decision 2: TBD (task bd-xxx)

## Tasks
1. [ ] Design: <aspect 1>
2. [ ] Implement: <component 1>
3. [ ] Implement: <component 2>
4. [ ] Test: <integration>
5. [ ] Document: <user-facing changes>

## Success Criteria
<How do we know the epic is complete?>

## Related
- GitHub #123: <external reference>
- bd-xxx: <related issue>
```

---

*Investigation complete. Apply these patterns incrementally—start with good descriptions, add dependencies as complexity grows, graduate to epics for large features.*
