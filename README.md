# orch-cli

**kubectl for AI agents** - A CLI for orchestrating, monitoring, and coordinating AI coding agents.

> **Note:** This project is maintained opportunistically. PRs and issues may sit for extended periods.

## What is this?

`orch` is a command-line tool for managing AI coding agents (Claude Code, OpenCode, and similar tools). It provides:

- **Spawning**: Launch agents with structured context and skill-based guidance
- **Monitoring**: Track agent progress, status, and output in real-time
- **Coordination**: Manage multiple agents working on related tasks
- **Completion**: Verify agent work and clean up resources

Think of it as `kubectl` but for AI agents instead of containers.

## Installation

```bash
# From source
git clone https://github.com/dylanconlin/orch-cli.git
cd orch-cli
pip install -e .

# Or directly
pip install orch-cli
```

**Requirements:**
- Python 3.10+
- tmux (for agent session management)

## Quick Start

```bash
# Initialize orch in your project
orch init

# Spawn an agent for a task
orch spawn investigation "How does authentication work in this codebase?"

# Check status of running agents
orch status

# Monitor a specific agent
orch tail <agent-id>

# Send a message to an agent
orch send <agent-id> "Focus on the OAuth flow first"

# Complete an agent's work
orch complete <agent-id>
```

## Core Commands

| Command | Description |
|---------|-------------|
| `orch init` | Initialize orch in a project directory |
| `orch spawn SKILL "task"` | Spawn an agent with a specific skill |
| `orch status` | Show status of all agents |
| `orch check <id>` | Detailed check of a specific agent |
| `orch tail <id>` | Live output from an agent |
| `orch send <id> "msg"` | Send a message to an agent |
| `orch complete <id>` | Verify and complete agent work |
| `orch clean` | Clean up orphaned agents |

## How It Works

1. **Skills**: Agents are spawned with predefined skills (investigation, feature-impl, debugging, etc.) that provide structured guidance
2. **Workspaces**: Each agent gets a workspace directory for tracking progress and artifacts
3. **Registry**: Agent metadata is stored in a local registry for coordination
4. **tmux**: Agents run in tmux sessions for persistence and monitoring

## Project Structure

When you run `orch init`, it creates a `.orch/` directory in your project:

```
.orch/
├── CLAUDE.md           # Orchestration guidance for agents
├── workspace/          # Agent workspaces
├── investigations/     # Investigation artifacts
├── decisions/          # Decision records
└── backlog.json        # Work items and status
```

## Skills

Built-in skills include:

- **investigation**: Explore and understand codebases
- **feature-impl**: Implement features with TDD or direct mode
- **systematic-debugging**: Debug issues methodically
- **research**: Research external topics
- **codebase-audit**: Comprehensive code review

## AI Agent Setup

For AI agents (like Claude Code) to automatically load orchestration context:

### 1. Install the orchestrator skill

```bash
mkdir -p ~/.claude/skills/orchestrator
cp skills/orchestrator/SKILL.md ~/.claude/skills/orchestrator/
```

### 2. Install the SessionStart hook

```bash
mkdir -p ~/.orch/hooks
cp hooks/load-orchestration-context.py ~/.orch/hooks/
chmod +x ~/.orch/hooks/load-orchestration-context.py
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "python3 ~/.orch/hooks/load-orchestration-context.py"
      }
    ]
  }
}
```

Now when Claude Code starts in an orch project, it automatically loads orchestration context.

## Agent Compatibility

Designed to work with:
- Claude Code (primary target)
- OpenCode
- Any CLI-based AI coding agent

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/orch

# Format code
black src tests
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please note this project is maintained opportunistically - PRs may take time to review.

Before contributing:
1. Check existing issues/PRs for similar work
2. For significant changes, open an issue first to discuss
3. Follow existing code style (black formatting, type hints where possible)

---

*Not affiliated with Anthropic or any AI agent provider.*
