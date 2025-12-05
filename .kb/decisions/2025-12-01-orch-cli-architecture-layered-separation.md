---
date: "2025-12-01"
status: "Accepted"
deciders: ["Dylan Conlin"]
---

# Decision: orch-cli Layered Architecture with Beads as Memory Layer

## Context

Yegge's beads model separates concerns:
- **beads** = passive shared memory (issues, dependencies, status)
- **Agent Mail** = peer-to-peer messaging between agents
- **Orchestration** = separate concern

Question arose: Does orch-cli (centralized orchestration) complement or compete with this model? And why is orch-cli creating memory-like artifacts (workspaces) if beads is the memory layer?

## Decision

### 1. orch-cli is the Lifecycle Layer (complements beads/Agent Mail)

orch-cli's value is lifecycle management, not memory or messaging:
- Spawn agents with context
- Monitor agent progress
- Complete/verify agent work
- Error recovery patterns

This complements beads (memory) and Agent Mail (messaging) - different layers, not competing.

### 2. `orch send` is Primitive Agent Mail (upgrade path exists)

`orch send` already implements agent messaging via tmux. The transport can evolve:
- **Now:** tmux send-keys (one-way, unstructured)
- **Future:** Agent Mail MCP (bidirectional, structured)

tmux remains for session management (persistence, attach, tail). Agent Mail upgrades messaging.

### 3. Workspaces Converge into Beads (eliminate duplication)

**Problem:** Workspaces duplicate beads functionality - both track execution state.

**Solution:** Beads issues ARE the workspaces:
- `description` = spawn context
- `comments` = execution log (append-only progress)
- `status` = phase (open → in_progress → closed)
- `close --reason` = final summary

Investigations and decisions stay in `.orch/` as knowledge artifacts (different category).

## Architecture

```
┌─────────────────────────────────────────┐
│        orch-cli (Lifecycle Layer)       │
│  spawn, monitor, complete, verify       │
│  NO memory artifacts of its own         │
├─────────────────────────────────────────┤
│      Messaging Layer (upgradeable)      │
│  current: tmux send-keys               │
│  future:  Agent Mail MCP               │
├─────────────────────────────────────────┤
│        tmux (Session Layer)             │
│  persistence, attach, output capture    │
├─────────────────────────────────────────┤
│        beads (Memory Layer)             │
│  issues = task state + execution log    │
├─────────────────────────────────────────┤
│     .orch/ (Knowledge Layer)            │
│  investigations, decisions, patterns    │
└─────────────────────────────────────────┘
```

**Key principle:** Each layer has clear responsibility. Lifecycle layer orchestrates but holds no state.

## Consequences

### Positive

- Single source of truth for task state (beads)
- Clean separation of concerns
- Aligns with Yegge's vision
- Simpler cleanup (`bd cleanup` handles task state)
- Path to swarm mode via Agent Mail

### Negative

- Migration work required (3 phases)
- Agents need updated guidance (use `bd comment` not workspace files)
- Less rich workspace format (beads comments vs structured markdown)

### Migration Path

1. **Phase 1:** Make beads-first spawning default (`orch-cli-iv6`)
2. **Phase 2:** Remove workspace file creation (`orch-cli-csx`)
3. **Phase 3:** Update orch commands to read from beads (`orch-cli-bve`)

## Alternatives Considered

### Keep Workspaces Separate from Beads
- Pros: No migration, richer format
- Cons: Duplicates memory layer, two sources of truth
- **Rejected:** Architectural smell - lifecycle layer shouldn't create memory artifacts

### Full Swarm Mode (Replace Centralized Orchestration)
- Pros: Scales better, removes human bottleneck
- Cons: Less control, harder to debug, premature for solo workflow
- **Rejected for now:** Can add swarm as option later, not replacement

## Process Note: Evolve Through Distinction

This architecture wasn't designed upfront - it emerged from a series of distinctions that resolved conflations:

| Question Asked | Conflation Found | Distinction Made |
|----------------|------------------|------------------|
| "Does orch-cli compete with Agent Mail?" | "Orchestration" meant both lifecycle AND messaging | Lifecycle layer ≠ Messaging layer |
| "What about `orch send`?" | `orch send` is messaging disguised as lifecycle | Session management (tmux) ≠ Message transport (MCP) |
| "Why is lifecycle creating memory artifacts?" | Workspaces duplicate beads | Task state (beads) ≠ Knowledge artifacts (.orch/) |

Each distinction clarified responsibility and removed duplication. The five-layer architecture fell out naturally:

```
Lifecycle → Messaging → Sessions → Memory → Knowledge
```

**Principle applied:** "When problems recur, ask 'what are we conflating?'"

## Related

- **Investigation:** `.orch/investigations/design/2025-12-01-orch-cli-role-in-agent-ecosystem.md`
- **Beads issues:** `orch-cli-iv6`, `orch-cli-csx`, `orch-cli-bve`
