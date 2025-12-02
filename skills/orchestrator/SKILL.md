# Orchestrator Skill

Guidance for AI agents coordinating work via the `orch` CLI.

---

## Am I Orchestrator or Worker?

**Orchestrator indicators:**
- Working directory is project root
- No SPAWN_CONTEXT.md in current directory
- No "TASK:" prefix in initial prompt

**Worker indicators:**
- SPAWN_CONTEXT.md exists in workspace
- "TASK:" in initial prompt
- Spawned via `orch spawn`

**Rule:** If orchestrator + non-trivial work → delegate via `orch spawn`.

---

## Core Lifecycle

```
orch spawn SKILL "task"  →  Agent works in tmux window
        ↓
orch status              →  Monitor progress (Phase field)
        ↓
orch complete AGENT-ID   →  Verify and clean up
```

---

## Delegate vs Execute

**Delegate when:**
- 5+ files to read/modify
- Produces an artifact (investigation, feature, fix)
- Estimated >10 minutes of work
- Clear, well-defined scope

**Execute yourself when:**
- Trivial (<5 files, <10 min)
- Quick fixes, config changes
- Interactive discussion needed
- Time-critical

---

## Spawning Agents

**Basic spawn:**
```bash
orch spawn SKILL "task description"
```

**Available skills:** `orch skills`

**Common skills:**
- `feature-impl` - Build features (default)
- `investigation` - Research/understand codebase
- `systematic-debugging` - Fix bugs methodically
- `architect` - Design decisions

**Spawn creates:**
1. Workspace at `.orch/workspace/{name}/WORKSPACE.md`
2. Tmux window for agent session
3. Registry entry for tracking

---

## Monitoring Agents

**Quick status:**
```bash
orch status
```

**Detailed check:**
```bash
orch check AGENT-ID
```

**Watch output:**
```bash
orch tail AGENT-ID
```

**Send guidance:**
```bash
orch send AGENT-ID "Your message here"
```

---

## Completing Agents

**When agent shows Phase: Complete:**
```bash
orch complete AGENT-ID
```

This:
1. Verifies deliverables exist
2. Checks verification requirements
3. Closes tmux window
4. Removes from registry

**If blocked:** Check workspace for issues, address them, retry.

---

## Discovery Linking

When agents discover work beyond their scope, track the lineage:

```bash
bd create "New issue title" --discovered-from PARENT-ID
```

**When to use:**
- Agent punts work ("out of scope, but noticed X needs attention")
- Investigation reveals larger problem ("iceberg" - more underneath)
- Fix exposes related issues

**Why it matters:**
- Tracks where work came from
- Enables convergence checking ("is all work from this spawn done?")
- Prevents orphaned issues

**Example:**
```bash
# Agent working on auth fix discovers logging issue
bd create "Logging not capturing auth failures" --discovered-from orch-cli-abc

# Later, check the tree
bd show orch-cli-abc
# Shows: Discovered → orch-cli-xyz (logging issue)
```

---

## Workspace Conventions

Agents update their workspace as they work:

**Key fields:**
- `Phase:` Planning → Implementation → Complete
- `Status:` Active, BLOCKED, QUESTION, Complete
- `TLDR:` 30-second summary at top

**Orchestrator reads these via `orch status` and `orch check`.**

---

## Proactive Patterns

**Do automatically:**
- Complete agents at Phase: Complete
- Check status periodically
- Synthesize findings after completion

**State intent, then act:**
- "Spawning for this task..."
- "Completing the ready agent..."

**Actually ask when:**
- Multiple valid approaches
- Unclear scope or priority
- Costly irreversible actions

---

## Command Reference

| Command | Purpose |
|---------|---------|
| `orch spawn SKILL "task"` | Start agent work |
| `orch status` | Overview of all agents |
| `orch check ID` | Detailed agent inspection |
| `orch tail ID` | Recent agent output |
| `orch send ID "msg"` | Send message to agent |
| `orch complete ID` | Finish and clean up |
| `orch skills` | List available skills |
| `orch clean` | Remove completed agents |

---

## Getting Started

1. **Initialize project:** `orch init` (creates `.orch/` directory)
2. **Spawn your first agent:** `orch spawn investigation "understand how X works"`
3. **Monitor:** `orch status`
4. **Complete:** `orch complete AGENT-ID`

For more details, see: https://github.com/dylan-conlin/orch
