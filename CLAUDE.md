# orch-cli - Worker Context

---

# orch-cli

CLI tools for AI agent orchestration. Enables spawning, monitoring, and completing AI agents across multiple backends (Claude Code, Codex, OpenCode).

## Architecture Overview

```
src/orch/
├── cli.py                 # Entry point, Click groups, command registration
├── spawn.py               # Core spawn logic (workspace creation, tmux, prompts)
├── spawn_commands.py      # spawn command (4 modes: roadmap, skill, interactive-skill, interactive)
├── spawn_prompt.py        # SPAWN_CONTEXT.md template generation
├── registry.py            # Agent state management (JSON + file locking)
├── skill_discovery.py     # Skill metadata parsing from ~/.claude/skills/
├── beads_integration.py   # bd CLI wrapper for issue tracking
├── backends/
│   ├── base.py           # Abstract Backend interface
│   ├── claude.py         # Claude Code adapter
│   ├── codex.py          # Codex CLI adapter
│   └── opencode.py       # OpenCode API adapter
├── monitoring_commands.py # status, check, tail, wait, question
├── workspace_commands.py  # Workspace lifecycle operations
├── complete_commands.py   # Agent completion logic
└── build_commands.py      # orch build subcommands
```

## Key Modules

### cli.py (Entry Point)
- Uses Click framework with modular command registration
- Main CLI group at line 29-33
- Commands registered via `register_*_commands()` pattern
- Subcommand groups: `build`, `projects`

### spawn.py (Core Spawn Logic)
- `SpawnConfig` dataclass: all spawn parameters
- `spawn_with_skill()`: Main skill-based spawn (~800 lines)
- `spawn_from_roadmap()`: ROADMAP-driven spawning
- `spawn_interactive()`: Human-guided sessions
- Creates workspace, writes SPAWN_CONTEXT.md, opens tmux window

### registry.py (Agent State)
- `AgentRegistry` class managing `~/.orch/agent-registry.json`
- File locking via `fcntl` (Unix only - not Windows compatible)
- Tombstone pattern for deletions (prevents re-animation race)
- `reconcile()`: Syncs registry with tmux window state
- Agent states: `active`, `completed`, `terminated`, `abandoned`, `deleted`

### backends/ (Backend Abstraction)
- `Backend` abstract base class defines interface:
  - `build_command()`: Construct CLI invocation
  - `wait_for_ready()`: Poll for backend readiness
  - `get_env_vars()`: Backend-specific environment
- Adapters: `ClaudeBackend`, `CodexBackend`, `OpenCodeBackend`

### skill_discovery.py (Skill System)
- Scans `~/.claude/skills/{category}/{skill}/SKILL.md`
- Parses YAML frontmatter for metadata
- Caches discovery via `lru_cache`
- `SkillMetadata`: name, triggers, deliverables, verification

### beads_integration.py (Issue Tracking)
- Thin wrapper around `bd` CLI
- `BeadsIntegration.get_issue()`: Fetch issue by ID
- `close_issue()`: Auto-close on `orch complete`
- Exceptions: `BeadsCLINotFoundError`, `BeadsIssueNotFoundError`

## Spawn Flow

1. `orch spawn SKILL "task"` invokes `spawn_commands.py:spawn()`
2. Dispatches to `spawn_with_skill()` in `spawn.py`
3. Creates workspace directory: `.orch/workspace/{name}/`
4. Writes `SPAWN_CONTEXT.md` with skill content + task context
5. Opens tmux window in target session
6. Sets `CLAUDE_CONTEXT=worker` environment
7. Sends backend command (e.g., claude-code-wrapper.sh with prompt)
8. Registers agent in `~/.orch/agent-registry.json`

## Development

```bash
pip install -e .
pytest
```

### Adding New CLI Commands

1. Create `src/orch/{name}_commands.py`
2. Define `register_{name}_commands(cli)` function
3. Add registration call in `cli.py` (import + call in `cli()` function)

### Adding New Backends

1. Create `src/orch/backends/{name}.py`
2. Implement `Backend` abstract class
3. Add to `get_backend()` factory in `spawn.py`

### Testing Patterns

- Tests in `tests/` directory
- Fixtures in `tests/conftest.py`
- Use `pytest-mock` for mocking subprocess/tmux calls
- Registry tests use temp files (avoid polluting `~/.orch/`)

## Cross-Repo Sync Requirements

**When adding or changing CLI commands:**

Update the orchestrator skill in orch-knowledge to reflect the changes:
- Source: `orch-knowledge/skills/src/orchestrator/SKILL.md`
- Deployed to: `~/.claude/skills/orchestrator/SKILL.md`

This prevents amnesia gaps where new commands exist but future sessions don't know about them.

**Validation:** `orch lint --skills` validates skill CLI references against actual commands.

## Key Files for Quick Understanding

1. `cli.py:29-50` - Command structure overview
2. `spawn_commands.py:68-115` - Spawn command signature and modes
3. `spawn.py` - Search for `def spawn_with_skill` (~line 400)
4. `registry.py:223-330` - Agent registration logic
5. `backends/base.py` - Backend interface contract

## Gotchas

- **File locking**: Registry uses `fcntl` - Unix only
- **Window IDs**: Use `window_id` (@-prefixed) not `window` (index) for tmux targeting
- **Skill paths**: Hierarchical `~/.claude/skills/{category}/{skill}/SKILL.md`
- **Tombstones**: Deleted agents stay in registry with `status='deleted'`

## Versioning & Releases

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Conventional commit format (required for changelog)
- Semantic versioning policy
- Release process with git-cliff

## Related Repos

- **orch-knowledge** - Knowledge archive (decisions, investigations, skill sources)
