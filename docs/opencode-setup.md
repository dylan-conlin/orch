# OpenCode Setup for orch-cli

This guide covers how to set up OpenCode to work with orch-cli for orchestrating AI agents.

## Overview

OpenCode and Claude Code have different extension mechanisms:
- **Claude Code**: Uses hooks in `~/.claude/settings.json`
- **OpenCode**: Uses plugins in `.opencode/plugin/` and configuration in `opencode.json`

Both approaches achieve the same goal: automatically loading orchestration context when sessions start.

## Quick Start

### 1. Configure opencode.json

Create or update `opencode.json` in your project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "~/.claude/skills/orchestrator/SKILL.md"
  ]
}
```

This tells OpenCode to load the orchestrator skill as context for every session.

### 2. Install the Session Hook (Optional)

For richer context loading (active agents, recent knowledge), install the session hook as a plugin:

```bash
# Create the plugin directory
mkdir -p .opencode/plugin

# Copy the hook script
cp hooks/load-orchestration-context.py .opencode/plugin/
```

Create `.opencode/plugin/orch-context.js`:

```javascript
export const OrchContextPlugin = async ({ project, client, $, directory }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        // Load orchestration context on session start
        const result = await $`python3 ${directory}/hooks/load-orchestration-context.py --opencode`.quiet()
        if (result.stdout) {
          console.log(result.stdout)
        }
      }
    }
  }
}
```

## Configuration Options

### Using `instructions` (Recommended)

The simplest approach is to add instruction files to your `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "~/.claude/skills/orchestrator/SKILL.md",
    "CLAUDE.md"
  ]
}
```

**Benefits:**
- No plugin code needed
- Instructions automatically merged with AGENTS.md
- Works with glob patterns

### Using Plugins (Advanced)

For dynamic context (like active agent status), use a plugin:

```
.opencode/
  plugin/
    orch-context.js       # Session hook plugin
    load-orchestration-context.py  # Context loader script
```

**Benefits:**
- Can run commands to gather dynamic state
- Can show active agents at session start
- Can integrate with `kn` for recent knowledge

## Environment Detection

The context loader script (`hooks/load-orchestration-context.py`) detects whether it's running in orchestrator or worker mode:

```python
# Worker agents skip context loading (skill is embedded in SPAWN_CONTEXT.md)
if os.environ.get('ORCH_WORKER'):
    sys.exit(0)
```

When spawning agents via `orch spawn --backend opencode`, the `ORCH_WORKER` environment variable is set, so workers don't redundantly load the orchestrator skill.

## Differences from Claude Code

| Feature | Claude Code | OpenCode |
|---------|-------------|----------|
| Hook location | `~/.claude/settings.json` | `.opencode/plugin/*.js` |
| Context source | SessionStart hook | `instructions` array or plugin |
| Event format | JSON stdin/stdout | JavaScript event handlers |
| Installation | Global hooks directory | Per-project or `~/.config/opencode/plugin/` |

### Claude Code Hook Configuration

For reference, the Claude Code approach uses:

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

### OpenCode Plugin Equivalent

The OpenCode plugin equivalent uses the `session.created` event:

```javascript
export const MyPlugin = async ({ $, directory }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        // Your session start logic here
      }
    }
  }
}
```

## Plugin Directory Structure

Plugins can be placed in two locations:

1. **Project-specific:** `.opencode/plugin/` in your project root
2. **Global:** `~/.config/opencode/plugin/`

OpenCode automatically loads all `.js` and `.ts` files from these directories.

## Available Events

Relevant events for orch-cli integration:

| Event | Description | Use Case |
|-------|-------------|----------|
| `session.created` | New session started | Load context, show active agents |
| `session.idle` | Session waiting for input | Notify when agent completes |
| `tool.execute.before` | Before tool runs | Validate operations, protect files |
| `tool.execute.after` | After tool runs | Log actions, update state |

See [OpenCode Plugins docs](https://opencode.ai/docs/plugins/) for the full event list.

## Troubleshooting

### Context not loading

1. Check that `opencode.json` exists in your project root
2. Verify the instruction paths are correct (supports `~` for home directory)
3. Run `opencode` and check for any plugin errors at startup

### Plugin not executing

1. Ensure the plugin file exports a named async function
2. Check the plugin file has correct JavaScript syntax
3. Look for errors in the OpenCode terminal output

### Worker agents getting orchestrator context

If spawned workers are loading orchestrator context:
1. Verify `ORCH_WORKER` environment variable is set during spawn
2. Check that your plugin checks for this variable before loading context

## Example: Complete Setup

Here's a complete working setup:

**opencode.json:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "~/.claude/skills/orchestrator/SKILL.md"
  ]
}
```

**.opencode/plugin/orch-context.js:**
```javascript
import { execSync } from 'child_process'

export const OrchContextPlugin = async ({ directory }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          // Check if we're in an orch project
          const orchDir = `${directory}/.orch`
          
          // Skip if not an orch project
          try {
            execSync(`test -d ${orchDir}`)
          } catch {
            return
          }
          
          // Skip for worker agents
          if (process.env.ORCH_WORKER) {
            return
          }
          
          // Show active agents
          try {
            const status = execSync('orch status --format json', {
              encoding: 'utf8',
              timeout: 5000
            })
            const data = JSON.parse(status)
            if (data.agents && data.agents.length > 0) {
              console.log('\n## Active Agents\n')
              for (const agent of data.agents.slice(0, 5)) {
                console.log(`- ${agent.agent_id}: ${agent.phase}`)
              }
            }
          } catch {
            // orch status failed, ignore
          }
        } catch (error) {
          // Plugin errors shouldn't break the session
          console.error('Orch context plugin error:', error.message)
        }
      }
    }
  }
}
```

## Related Documentation

- [OpenCode Plugins](https://opencode.ai/docs/plugins/) - Official plugin documentation
- [OpenCode Config](https://opencode.ai/docs/config/) - Configuration reference
- [OpenCode Rules](https://opencode.ai/docs/rules/) - Custom instructions with AGENTS.md
- [orch-cli README](../README.md) - Main project documentation
