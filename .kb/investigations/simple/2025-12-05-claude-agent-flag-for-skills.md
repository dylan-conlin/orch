# Investigation: Leveraging Claude Code --agent Flag for Skill-Based Spawning

**Status:** Complete
**Date:** 2025-12-05
**Issue:** orch-cli-wsn

## TLDR

The Claude Code `--agent` flag (v2.0.59+) offers compelling benefits for orch-cli skill spawning: native tool restrictions, model selection, and system prompt customization. **Recommendation: Hybrid approach** - generate `.claude/agents/` files dynamically at spawn time from existing SKILL.md content, rather than migrating skills to static agent files.

---

## Current Approach Analysis

### How orch-cli currently spawns agents:

1. **SPAWN_CONTEXT.md** - Full skill content embedded in context file (~600-2000 lines)
2. **Environment variables** - `CLAUDE_CONTEXT=worker`, `CLAUDE_WORKSPACE`, etc.
3. **CLI flags** - `--allowed-tools '*' --dangerously-skip-permissions`
4. **Wrapper script** - `~/.orch/scripts/claude-code-wrapper.sh`

```python
# From spawn.py:717-737
backend_cmd = backend.build_command(minimal_prompt, backend_options)
# Results in:
# ~/.orch/scripts/claude-code-wrapper.sh --allowed-tools '*' --dangerously-skip-permissions "prompt"
```

### Pain points with current approach:
- No native tool restrictions (all tools allowed via `--allowed-tools '*'`)
- Model selection via `--model` flag, not agent config
- System prompt injected via `--append-system-prompt` workaround
- Skills defined as SKILL.md files, not native Claude Code agents

---

## Claude Code --agent Flag Capabilities

### What --agent provides (v2.0.59+):

| Feature | Description |
|---------|-------------|
| **Tool restrictions** | `tools: Read, Bash, Grep` - limit to specific tools |
| **Model selection** | `model: sonnet` - baked into agent config |
| **System prompt** | Markdown body becomes system prompt |
| **Permission mode** | `permissionMode: specified` - explicit tool allowlist |
| **Disallowed tools** | `disallowedTools: Write, Edit` - explicit blocklist |

### Agent file format:

```markdown
---
name: investigation-worker
description: Read-only investigation agent for codebase research
tools: Read, Bash, Grep, Glob, WebFetch, WebSearch, Task
model: sonnet
permissionMode: specified
---

You are an investigation agent. Your job is to research questions about codebases.

Focus on:
- Understanding existing patterns
- Finding relevant files
- Documenting findings

You DO NOT modify files - only read and report.
```

### Location precedence:
1. `.claude/agents/` (project-level, git-tracked)
2. `~/.claude/agents/` (user-level, global)

---

## Question-by-Question Analysis

### 1. Should skills become .claude/agents/ files?

**Answer: Partially - dynamic generation, not migration.**

**Why not full migration:**
- SKILL.md files contain rich phase-specific guidance (600-2000 lines)
- Agents' markdown body is for system prompt, not detailed procedures
- Would lose phase filtering (`filter_skill_phases()` in spawn_prompt.py)
- Would lose dynamic config substitution (beads ID, workspace path, etc.)

**What agents CAN do:**
- Define tool restrictions per skill type
- Set model defaults
- Provide role-specific system prompt header

**Recommended approach:**
```
Skills stay as SKILL.md (procedural guidance)
    +
Agents generated at spawn time (tool restrictions + model)
    =
Best of both worlds
```

### 2. How would tool restrictions work with current skill system?

**Skill-to-tool mapping:**

| Skill | Suggested Tools | Rationale |
|-------|-----------------|-----------|
| `investigation` | Read, Grep, Glob, Bash, WebFetch, WebSearch, Task | Read-only exploration |
| `systematic-debugging` | Read, Grep, Glob, Bash, Edit, Write, Task | Need to fix bugs |
| `feature-impl` | All (*) | Full implementation capabilities |
| `codebase-audit` | Read, Grep, Glob, Bash, Task | Analysis only |
| `research` | Read, WebFetch, WebSearch, Bash | External research |

**Implementation approach:**
```python
# In skill_discovery.py, add to SkillMetadata:
@dataclass
class SkillMetadata:
    ...
    allowed_tools: Optional[List[str]] = None  # New field
    disallowed_tools: Optional[List[str]] = None  # New field
    default_model: Optional[str] = None  # New field
```

SKILL.md frontmatter:
```yaml
---
name: investigation
allowed_tools: [Read, Grep, Glob, Bash, WebFetch, WebSearch, Task]
disallowed_tools: [Edit, Write, MultiEdit]
default_model: sonnet
---
```

### 3. Can we dynamically generate agents via --agents JSON flag?

**Yes, but with limitations.**

**Syntax:**
```bash
claude --agents '{
  "investigation-worker": {
    "description": "Research agent for codebase questions",
    "prompt": "You are an investigation agent...",
    "tools": ["Read", "Bash", "Grep"],
    "model": "sonnet"
  }
}'
```

**Challenges:**
- JSON escaping in shell commands is error-prone
- Full SKILL.md content (600+ lines) would be unwieldy in JSON
- Better to write temp agent file, use `--agent` flag

**Recommended approach:**
1. Generate `.claude/agents/{skill}-worker.md` at spawn time
2. Include tool restrictions + system prompt header
3. Pass `--agent {skill}-worker` to Claude Code
4. Keep SPAWN_CONTEXT.md for detailed procedural guidance

### 4. What's the migration path from current SPAWN_CONTEXT.md approach?

**Phase 1: Add tool restrictions (low risk)**
```python
# In ClaudeBackend.build_command():
def build_command(self, prompt: str, options: Optional[Dict] = None) -> str:
    # Instead of --allowed-tools '*'
    if options and options.get('allowed_tools'):
        tools_list = ','.join(options['allowed_tools'])
        allowed_tools = f"--allowed-tools '{tools_list}'"
    else:
        allowed_tools = "--allowed-tools '*'"
```

**Phase 2: Generate agent files (medium risk)**
```python
# New function in spawn.py or new module
def generate_agent_file(config: SpawnConfig) -> Path:
    """Generate .claude/agents/{skill}-worker.md at spawn time."""
    agent_content = f"""---
name: {config.skill_name}-worker
description: {config.skill_metadata.description}
tools: {', '.join(config.skill_metadata.allowed_tools or ['*'])}
model: {config.model or 'sonnet'}
permissionMode: specified
---

{config.skill_metadata.system_prompt_header or ''}
"""
    agent_path = config.project_dir / ".claude" / "agents" / f"{config.skill_name}-worker.md"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(agent_content)
    return agent_path
```

**Phase 3: Use --agent flag (low risk)**
```python
# In ClaudeBackend.build_command():
if options and options.get('agent_name'):
    cmd_parts.append(f"--agent {options['agent_name']}")
```

**Keep SPAWN_CONTEXT.md:**
- Detailed procedural guidance stays in SPAWN_CONTEXT.md
- Agent file provides: tool restrictions, model, system prompt header
- Agent reads SPAWN_CONTEXT.md for full task context (current pattern)

### 5. How does this interact with subagents/Task tool?

**Key insight:** Agent definitions affect the **main** agent, not subagents.

**Subagent behavior:**
- Subagents spawned via Task tool have their own tool access
- Subagents cannot spawn further subagents (depth=1 limit)
- Parent agent can't monitor subagent tool usage
- Built-in subagents: Explore, general-purpose, Plan

**Impact on orch-cli:**
- If main agent has `tools: [Read, Grep, Glob]`, it can still spawn subagents with broader access
- Task tool agent definitions (if using `--agents` JSON) are separate from main agent
- Current architecture (orchestrator spawns workers) is compatible

**Example interaction:**
```
orchestrator (full tools)
    └── spawns → investigation-worker (read-only tools)
                     └── Task tool → Explore subagent (read-only, built-in)
```

---

## Recommendation

### Adopt hybrid approach:

1. **Keep SKILL.md files** for procedural guidance (no change)
2. **Add tool metadata to skills** via frontmatter extension
3. **Generate agent files at spawn time** from skill metadata
4. **Pass --agent flag** to Claude Code CLI
5. **Keep SPAWN_CONTEXT.md** for detailed task context

### Benefits:
- **Tool restrictions** - Investigations can't accidentally modify files
- **Model defaults** - Skills can specify optimal model
- **Native integration** - Uses Claude Code's built-in agent system
- **Backward compatible** - SPAWN_CONTEXT.md pattern unchanged
- **Minimal migration** - Additive changes only

### Implementation priority:
1. **P1:** Add `allowed_tools` to skill frontmatter (schema change)
2. **P2:** Generate agent files at spawn time (new function)
3. **P3:** Pass `--agent` flag in ClaudeBackend (minor change)
4. **P4:** Remove `--dangerously-skip-permissions` (security improvement)

---

## Files Changed (Estimated)

| File | Change |
|------|--------|
| `src/orch/skill_discovery.py` | Add `allowed_tools`, `disallowed_tools`, `default_model` to SkillMetadata |
| `src/orch/spawn.py` | Add `generate_agent_file()` function |
| `src/orch/backends/claude.py` | Add `--agent` flag support in `build_command()` |
| `~/.claude/skills/*/SKILL.md` | Add tool metadata to frontmatter |

---

## Next Actions

- [ ] Discuss hybrid approach with orchestrator
- [ ] Create beads issue for Phase 1 implementation (add tool metadata to skills)
- [ ] Create beads issue for Phase 2 implementation (generate agent files)
- [ ] Update skill files with tool metadata once schema is implemented
