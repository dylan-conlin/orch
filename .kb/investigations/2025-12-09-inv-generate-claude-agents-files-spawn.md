**TLDR:** How to generate .claude/agents/ files at spawn time? Add generate_agent_file() function that reads skill metadata (allowed_tools, disallowed_tools, default_model) and writes agent file with tool restrictions + model, then pass --agent flag to Claude Code CLI. High confidence (90%) - approach validated in prior investigation (2025-12-05).

---

# Investigation: Generate .claude/agents/ Files at Spawn Time

**Question:** How should orch spawn generate .claude/agents/ files from skill metadata to leverage Claude Code's native --agent flag for tool restrictions?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Implementing
**Next Step:** Write failing tests for generate_agent_file()
**Status:** Active
**Confidence:** High (90%)

---

## Findings

### Finding 1: SkillMetadata already has required fields

**Evidence:** SkillMetadata dataclass in skill_discovery.py already includes:
- `allowed_tools: Optional[List[str]]` - Tools the skill is allowed to use
- `disallowed_tools: Optional[List[str]]` - Tools the skill should NOT use
- `default_model: Optional[str]` - Default model for spawning

**Source:** `src/orch/skill_discovery.py:45-56`

**Significance:** No schema changes needed - can immediately generate agent files from existing metadata.

---

### Finding 2: ClaudeBackend currently uses hardcoded --allowed-tools '*'

**Evidence:** In build_command():
```python
allowed_tools = "--allowed-tools '*'"
skip_permissions = "--dangerously-skip-permissions"
```

**Source:** `src/orch/backends/claude.py:42-43`

**Significance:** Need to update to use --agent flag when agent file is generated.

---

### Finding 3: Prior investigation recommends hybrid approach

**Evidence:** Investigation 2025-12-05 concluded:
- Skills stay as SKILL.md (procedural guidance)
- Agents generated at spawn time (tool restrictions + model)
- Agent file provides: tool restrictions, model, system prompt header
- SPAWN_CONTEXT.md provides: detailed procedural guidance

**Source:** `.kb/investigations/2025-12-05-claude-agent-flag-for-skills.md`

**Significance:** Architecture decision already made - implement as specified.

---

## Synthesis

**Key Insights:**

1. **No schema changes needed** - SkillMetadata already supports allowed_tools, disallowed_tools, default_model

2. **Two-part change** - generate_agent_file() in spawn.py + --agent flag in ClaudeBackend

3. **Backward compatible** - Skills without tool restrictions continue to work (--allowed-tools '*' fallback)

**Answer to Investigation Question:**

Generate agent file at spawn time from skill metadata, write to .claude/agents/{skill}-worker.md, pass --agent flag to Claude Code CLI. SPAWN_CONTEXT.md continues to provide procedural guidance.

---

## Implementation Plan

1. **Write failing tests** for generate_agent_file()
2. **Implement generate_agent_file()** in spawn.py
3. **Update spawn_in_tmux()** to call generate_agent_file() when skill has tool restrictions
4. **Update ClaudeBackend.build_command()** to accept agent_name option
5. **Write integration test** verifying end-to-end flow

---

## References

**Files Examined:**
- `src/orch/spawn.py` - Main spawn logic
- `src/orch/skill_discovery.py` - SkillMetadata definition
- `src/orch/backends/claude.py` - ClaudeBackend implementation
- `.kb/investigations/2025-12-05-claude-agent-flag-for-skills.md` - Prior investigation

---

## Investigation History

**2025-12-09 19:30:** Investigation started
- Initial question: How to generate .claude/agents/ files at spawn time?
- Context: Beads issue orch-cli-71q - add generate_agent_file() function

**2025-12-09 19:35:** Pre-implementation exploration complete
- Found SkillMetadata already has required fields
- Found ClaudeBackend needs --agent flag support
- Confirmed approach from prior investigation
