# Design Investigation: Orchestrator-Human Interaction Patterns

**Date:** 2025-12-04
**Status:** Complete
**Type:** Design Investigation

## Design Question

What is the optimal interaction dynamic between human (Dylan) and orchestrator? Specifically:
1. Command granularity - Should human say "fix this bug" or "create a beads issue and spawn a worker"?
2. Orchestrator authority - What should orchestrator decide autonomously vs ask about?
3. Strategic vs tactical - Should orchestrator do more upfront analysis before creating issues/spawning?
4. Code writing - Should orchestrator be allowed to write code, or purely delegate?

## Problem Framing

### Success Criteria
- Clear division of responsibility between human and orchestrator
- Orchestrator acts as strategic partner, not just dispatcher
- Minimal friction for common workflows
- Trust-based system where orchestrator handles work smoothly

### Constraints
- Must work within existing orch-cli and beads infrastructure
- Should not require major tooling changes initially
- Must be learnable by future Claude instances (amnesia-resilient)

### Scope
- IN: Orchestrator skill guidance, backlog management patterns, tracking heuristics
- OUT: Major CLI refactors, new command implementations (deferred to follow-up)

## Exploration

### Current State Analysis

The orchestrator skill (~850 lines) has sophisticated autonomy guidance:
- "Always Act (Silent)" for obvious actions
- "Propose-and-Act" for single operations
- "Actually Ask" for genuine ambiguity

However, the **backlog relationship is passive**:
- Orchestrator reads/writes beads issues but doesn't "own" the backlog
- No guidance on WHEN to create beads issues vs ad-hoc spawn
- Investigation outcomes can create issues, but this is reactive, not proactive

**Gap identified:** Orchestrator is a dispatcher, not a strategic partner.

### Approach 1: Skill-Only Changes

Add "Backlog Ownership" responsibilities to orchestrator skill with explicit proactive behaviors.

**Pros:** No tooling changes. Just clearer guidance.
**Cons:** Relies on orchestrator discipline. No enforcement.

### Approach 2: CLI Enhancements

Add commands like `bd health`, `bd suggest`, `orch spawn --auto-track`.

**Pros:** Tooling makes patterns easier to follow.
**Cons:** Implementation work. Might over-engineer.

### Approach 3: Explicit Modes

Formalize `orch work` (tracked) vs `orch explore` (ad-hoc).

**Pros:** Very clear. Hard to mess up.
**Cons:** Another command. Might be too rigid.

## Synthesis

### Recommendation

⭐ **RECOMMENDED: Approach 1 (Skill-Only) with convenience tooling**

Start with skill changes that establish the "strategic orchestrator" pattern. Add minimal convenience tooling (`bd health` alias) to support the pattern. Defer CLI enhancements until patterns are validated.

**Principle guiding this:** Trust the system handles work smoothly. The orchestrator's value is strategic thinking, not execution shortcuts.

### Key Decisions

#### 1. Backlog Ownership: Propose-and-Act

Orchestrator owns the backlog strategically, using Propose-and-Act autonomy:
- Surfaces backlog health at session start
- Proposes issue creation, closure, prioritization
- Acts unless Dylan interrupts

#### 2. Tracking Heuristic

**TRACK (beads issue) when ALL of:**
- Should be discoverable later
- Has clear completion criteria
- Might span sessions OR be handed off
- Part of larger goal

**AD-HOC spawn when ANY of:**
- Exploratory/interactive (artifact IS deliverable)
- Time-sensitive (tracking overhead not worth it)
- Truly one-off (no one needs to find it later)

#### 3. Code Writing Boundary

**Orchestrator may directly fix:**
- Literal typos
- Single-line config changes
- Obvious syntax errors

**Orchestrator delegates everything else.**

Principle: Trust the system. If it requires *thinking about implementation* → delegate.

### Trade-offs Accepted

- **No enforcement mechanism:** Relying on skill guidance rather than tooling constraints
- **Learning curve:** Future orchestrator instances need to internalize these patterns
- **Potential drift:** Without tooling, patterns may erode over time

### When This Would Change

- If orchestrators consistently fail to follow patterns → add enforcement tooling
- If `bd health` proves valuable → formalize as proper command
- If tracking heuristic proves wrong → refine based on evidence

## Recommendations

### Immediate: Skill Section Addition

Add to `~/.claude/skills/orchestrator/SKILL.md`:

```markdown
---

## Backlog Ownership (Proactive)

**Principle:** Orchestrator is a strategic partner, not just a dispatcher. Own the backlog.

### At Session Start

Run backlog health check:
```bash
bd stats && bd ready && bd blocked
```

Surface summary to Dylan:
- "X issues ready, Y blocked, Z open >2 weeks"
- Propose action if warranted: "Recommend closing stale issue ABC, tackling blocker XYZ first..."

### Before Non-Trivial Work

1. **Check if tracked:** `bd list | grep keywords`
2. **Apply tracking heuristic:**
   - TRACK when: discoverable later + clear completion + spans sessions + part of larger goal
   - AD-HOC when: exploratory + time-sensitive + one-off + artifact is deliverable
3. **State intent:** "Creating beads issue for this..." or "Ad-hoc spawn (artifact is deliverable)..."

### After Agent Completion

1. **Discovered work?** → `bd create --discovered-from <parent-id>`
2. **Stale issues surfaced?** → Propose closing with reason
3. **Dependency shifts?** → Surface to Dylan: "Completing X unblocks Y and Z"

### Tracking Heuristic (Reference)

| Track (beads) | Ad-hoc spawn |
|---------------|--------------|
| Discoverable later | Exploratory/interactive |
| Clear completion criteria | Time-sensitive |
| Spans sessions | One-off |
| Part of larger goal | Artifact IS deliverable |

---

## Code Writing Boundary

**Orchestrator may directly fix:**
- Literal typos
- Single-line config changes
- Obvious syntax errors

**Orchestrator delegates everything else.**

**Principle:** Trust the system handles work smoothly. If it requires *thinking about implementation* → delegate.

**Anti-pattern:** "I'll just quickly fix this..." for anything beyond trivial. That's worker work.
```

### Convenience: bd-health alias

Add to shell config or `~/.local/bin/bd-health`:

```bash
#!/bin/bash
echo "=== Backlog Health ==="
bd stats
echo ""
echo "=== Ready (unblocked) ==="
bd ready
echo ""
echo "=== Blocked ==="
bd blocked
```

### Optional Follow-up (create beads issues if desired)

1. **Formalize `bd health` command** - Add to beads CLI proper
2. **Add `--auto-track` to orch spawn** - Auto-apply tracking heuristic
3. **Stale issue detection** - `bd stale` command for issues open >N days

## Artifacts Produced

- This investigation: `.orch/investigations/design/2025-12-04-orchestrator-human-interaction-patterns.md`

## Decision Status

**Recommendation made.** Awaiting Dylan's approval to:
1. Promote to decision record
2. Implement skill changes
3. Create follow-up beads issues for optional tooling
