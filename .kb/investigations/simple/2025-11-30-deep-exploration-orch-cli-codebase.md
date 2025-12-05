# Deep Exploration of orch-cli Codebase

**TLDR:** Explored orch-cli architecture. Entry point is `src/orch/cli.py` using Click. Spawn system in `spawn.py` creates tmux windows with backend-specific commands. Registry (`registry.py`) tracks agent lifecycle with file locking. Beads integration via `bd` CLI wrapper.

**Date:** 2025-11-30
**Status:** Complete

## Question

What is the architecture of orch-cli, and what key information should be documented in CLAUDE.md for future Claude instances (orchestrators and workers)?

## What I tried

1. Read `pyproject.toml` to understand project structure and entry points
2. Read `src/orch/cli.py` to understand command organization
3. Read `src/orch/spawn.py` to trace spawn flow
4. Read `src/orch/registry.py` to understand agent tracking
5. Read `src/orch/beads_integration.py` for work tracking
6. Read `src/orch/skill_discovery.py` for skill system
7. Read `src/orch/backends/base.py` and `backends/claude.py` for backend abstraction

## What I observed

### Project Structure
```
src/orch/
├── cli.py                 # Entry point, Click groups, core commands
├── spawn.py               # Core spawn logic (~2100 lines)
├── spawn_commands.py      # Spawn command registration
├── spawn_prompt.py        # Prompt template generation
├── registry.py            # Agent state management
├── skill_discovery.py     # Skill metadata parsing
├── beads_integration.py   # bd CLI wrapper
├── backends/
│   ├── base.py           # Abstract Backend interface
│   ├── claude.py         # Claude Code adapter
│   ├── codex.py          # Codex adapter
│   └── opencode.py       # OpenCode adapter
├── monitoring_commands.py # Status, check, tail, etc.
├── workspace_commands.py  # Workspace operations
└── ... (40+ modules)
```

### Key Findings

1. **CLI Structure**: Uses Click with modular registration pattern:
   - Main CLI group in `cli.py` line 29-33
   - Commands registered via `register_*_commands()` functions
   - Subcommand groups: `build`, `projects`

2. **Spawn Flow**:
   - `spawn` command → `spawn_commands.py:spawn()`
   - Dispatches to: `spawn_from_roadmap()`, `spawn_with_skill()`, `spawn_interactive()`
   - Creates workspace dir, writes `SPAWN_CONTEXT.md`
   - Opens tmux window, sends backend command
   - Registers agent in registry

3. **Registry**:
   - JSON file at `~/.orch/agent-registry.json`
   - Uses fcntl file locking for concurrent access
   - Tombstone pattern for deletions
   - Reconciles with tmux state

4. **Backend Abstraction**:
   - Abstract `Backend` class in `backends/base.py`
   - Methods: `build_command()`, `wait_for_ready()`, `get_env_vars()`
   - Implementations: ClaudeBackend, CodexBackend, OpenCodeBackend

5. **Beads Integration**:
   - Thin wrapper around `bd` CLI
   - `BeadsIntegration.get_issue()` fetches issue by ID
   - `orch complete` auto-closes beads issues

## Test performed

**Test:** Ran `orch --help` and `orch spawn --help` to verify CLI structure matches analysis
**Result:** Commands match analysis. Help shows 4 spawn modes (roadmap, skill, interactive skill, interactive). Build has subcommands (skills, readme, global). Projects has scan/list.

## Conclusion

The codebase is well-organized with clear separation of concerns:
- **CLI layer**: Click-based with modular command registration
- **Spawn system**: Handles multiple backends, creates workspaces, sends prompts via tmux
- **Registry**: Thread-safe JSON persistence with file locking
- **Backend abstraction**: Pluggable adapters for Claude, Codex, OpenCode
- **Beads integration**: Thin wrapper enabling issue-driven spawning

Key files for understanding:
1. `cli.py` - Command structure
2. `spawn.py` - Core spawn logic
3. `registry.py` - Agent lifecycle
4. `skill_discovery.py` - Skill system

## Self-Review

- [x] Real test performed (ran CLI to verify analysis)
- [x] Conclusion from evidence (based on code reading + CLI verification)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED
