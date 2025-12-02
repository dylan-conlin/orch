---
date: "2025-12-01"
status: "Accepted"
topic: "architecture, separation-of-concerns"
context: "Interactive exploration of orch-cli and beads layered architecture"
scope: "How orchestration tooling should be organized across projects"
source: "Interactive architect session: .orch/workspace/explore-orch-cli-beads-01dec/"
---

# Decision: Five Concerns Architecture

---

## Problem

orch-cli and orch-knowledge are conflating multiple concerns:

1. **orch-cli** has `investigations.py` and `decisions.py` - lifecycle tool creating knowledge artifacts
2. **orch-knowledge** contains skills, templates, patterns, AND knowledge artifacts - too many things
3. **Workspaces** duplicate beads functionality (already decided to converge)

Applied "evolve by distinction" - discovered we were conflating:
- Task memory (what to do)
- Knowledge (what we learned)
- Skills (how agents behave)
- Lifecycle (spawn/monitor/complete)
- Session management (persistence/attach)

---

## Decision

**Five distinct concerns, five tools:**

| Tool | Layer | Storage | Purpose |
|------|-------|---------|---------|
| `bd` | Memory | `.beads/` | Task state, dependencies, execution log |
| `kb` | Knowledge | `.kb/` | Investigations, decisions, patterns |
| `skills` | Guidance | `~/.claude/skills/` | Agent behavioral procedures |
| `orch` | Lifecycle | (stateless) | Spawn, monitor, complete, verify |
| `tmux` | Session | (runtime) | Persistence, attach, output |

**Key architectural principle:** Each tool owns one concern. Lifecycle layer (orch) has no state of its own - it orchestrates, but state lives in beads (tasks) and kb (knowledge).

---

## What Changes

### orch-cli loses:
- `orch create-investigation` → moves to `kb`
- `orch create-decision` → moves to `kb`
- `orch search` (artifact search) → moves to `kb`
- Workspace file creation → already migrating to beads

### kb (new project) gains:
- `kb create investigation <slug>`
- `kb create decision <slug>`
- `kb create pattern <slug>`
- `kb search <query>`
- `kb list investigations|decisions|patterns`
- Templates for knowledge artifacts

### skills (new project) gains:
- `skills build` - compile SKILL.md from phases/techniques
- `skills deploy` - install to ~/.claude/skills/
- `skills list` - show available skills
- `skills new <category>/<name>` - scaffold new skill
- Skill source management

### orch-knowledge splits:
- `skills/src/` → skills project
- `templates-src/` (knowledge templates) → kb project
- `templates-src/` (other templates) → stays with orch or kb
- `.orch/investigations/`, `.orch/decisions/` → kb project (as Dylan's personal archive)
- `patterns-src/` → kb project

### orch-cli keeps:
- Skill discovery and consumption (reads from ~/.claude/skills/)
- Beads integration (reads/writes task state)
- Spawn, monitor, complete, verify commands
- tmux session management

---

## Data Flow

```
AUTHORING                              CONSUMPTION
─────────                              ───────────

skills/src/ ───build───> ~/.claude/skills/ ───read───> orch spawn
                                                           │
                                                           ▼
                                                     SPAWN_CONTEXT.md

kb create ─────────────> .kb/investigations/
                         .kb/decisions/
                         .kb/patterns/

bd create ─────────────> .beads/issues.jsonl ◄───────── orch complete
bd comment                    │
bd close ◄────────────────────┘
```

---

## Rationale

**Why separate kb from orch:**
- Knowledge artifacts have no lifecycle (not "open → closed")
- Different access patterns ("what do we know about X?" vs "what's ready to work?")
- Lifecycle tool shouldn't create reference material

**Why separate skills from kb:**
- Skills are prescriptive (how to do things)
- Knowledge is descriptive (what we learned)
- Different authoring workflow (skills have build step, knowledge is direct)

**Why orch becomes stateless:**
- Cleaner architecture - orchestrates but doesn't own state
- State belongs in memory layer (beads) or knowledge layer (kb)
- Easier to reason about what each tool owns

---

## Trade-offs Accepted

- **More tools to install** → But each is focused and composable
- **Coordination overhead** → But concerns are now explicit
- **Migration effort** → But pays off in clarity

---

## Migration Path

**Phase 1:** Create `kb` project
- Extract knowledge artifact creation from orch-cli
- Move investigation/decision templates
- Establish .kb/ directory structure

**Phase 2:** Create `skills` project
- Extract skill build/deploy from orch-knowledge
- Skill authoring and management tooling

**Phase 3:** Clean up orch-cli
- Remove investigations.py, decisions.py
- Remove artifact search
- Keep only lifecycle commands

**Phase 4:** Split orch-knowledge
- Skills source → skills project
- Knowledge artifacts → kb project (or stays as Dylan's archive)

---

## Open Questions

1. **Where do templates live?** WORKSPACE.md template - with orch? DECISION.md template - with kb?
2. **Is .kb/ per-project or global?** Probably per-project like .beads/
3. **What about orch-knowledge as archive?** Keep as Dylan's personal history, or merge into kb?

---

## Related Documents

- `.orch/investigations/design/2025-12-01-orch-cli-role-in-agent-ecosystem.md` - Prior investigation establishing layers
- `.orch/decisions/2025-11-30-artifact-orch-cli-knowledge-split.md` - Earlier split decision (now superseded)
- Beads issues: orch-cli-iv6, orch-cli-csx, orch-cli-bve - Workspace→beads convergence

---

## Confidence

**High (85%)** - Clean separation of concerns, follows "evolve by distinction" principle

**What's certain:**
- The five concerns are distinct
- Current state conflates them
- Separation will improve clarity

**What's uncertain:**
- Exact CLI interface for kb and skills
- Whether all five need separate repos or some can share
- Migration sequencing details
