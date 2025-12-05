# Decision: Strategic Orchestrator Pattern

**Date:** 2025-12-04
**Status:** Accepted
**Source:** `.orch/investigations/design/2025-12-04-orchestrator-human-interaction-patterns.md`

## Context

The orchestrator was functioning as a dispatcher (spawn when asked, complete when done) rather than a strategic partner. The human-orchestrator interaction model felt ad-hoc with unclear division of responsibility.

## Decision

Adopt the **Strategic Orchestrator Pattern** with three key components:

### 1. Backlog Ownership (Propose-and-Act)

Orchestrator proactively owns the beads backlog:
- Surfaces backlog health at session start
- Proposes issue creation, closure, prioritization
- Acts unless human interrupts

### 2. Tracking Heuristic

**TRACK (beads issue) when ALL of:**
- Should be discoverable later
- Has clear completion criteria
- Might span sessions OR be handed off
- Part of larger goal

**AD-HOC spawn when ANY of:**
- Exploratory/interactive (artifact IS deliverable)
- Time-sensitive (tracking overhead not worth it)
- Truly one-off (no one needs to find it later)

### 3. Code Writing Boundary

**Orchestrator may directly fix:**
- Literal typos
- Single-line config changes
- Obvious syntax errors

**Orchestrator delegates everything else.**

**Principle:** Trust the system handles work smoothly. If it requires *thinking about implementation* → delegate.

## Consequences

### Positive
- Clear division of responsibility
- Orchestrator adds strategic value, not just execution
- Reduced friction for common workflows

### Negative
- Learning curve for future orchestrator instances
- No enforcement mechanism (relies on skill guidance)
- Patterns may drift without tooling support

### Mitigations
- Skill guidance is explicit and reference-able
- Follow-up tooling (`bd health`, `--auto-track`) can add support later
- Pattern violations become learning opportunities (post-mortems)

## Implementation

- Skill changes: `~/.claude/skills/orchestrator/SKILL.md`
- Convenience alias: `bd-health` (optional)
- Follow-up beads issues for tooling enhancements
