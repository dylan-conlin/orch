# Agent Mail MCP Setup

**Date:** 2025-12-02
**Updated:** 2025-12-02
**Status:** Fully configured (launchd + spawn integration)

---

## Overview

Agent Mail MCP is an inter-agent coordination layer by Jeffrey Emanuel (Dicklesworthstone). It provides:
- Agent identities and mailboxes
- Message passing between agents
- File reservation system (advisory locking)
- Human overseer web UI

## Installation Location

```
~/.local/share/mcp_agent_mail/
```

## Modifications Made

The upstream project requires Python 3.14 (alpha), which has build issues. Modified:
- `pyproject.toml`: Changed `requires-python = ">=3.14"` to `>=3.12`
- Works fine with Python 3.12

## Running the Server

**Start server:**
```bash
cd ~/.local/share/mcp_agent_mail
uv run python -m mcp_agent_mail.cli serve-http --port 8765
```

**With authentication token:**
```bash
cd ~/.local/share/mcp_agent_mail
HTTP_BEARER_TOKEN=$(uv run python -c "import secrets; print(secrets.token_hex(32))") \
  uv run python -m mcp_agent_mail.cli serve-http --port 8765
```

**Stop server:**
```bash
pkill -f "mcp_agent_mail.cli serve-http"
```

## Claude Code Configuration

Added via:
```bash
claude mcp add -s user -t http agent-mail http://127.0.0.1:8765/mcp/
```

Configuration in `~/.claude.json`:
```json
{
  "mcpServers": {
    "agent-mail": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp/"
    }
  }
}
```

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `http://127.0.0.1:8765/mcp/` | MCP protocol endpoint |
| `http://127.0.0.1:8765/mail` | Web UI for viewing messages |
| `http://127.0.0.1:8765/mail/{project}/inbox/{agent}` | Agent-specific inbox |
| `http://127.0.0.1:8765/mail/{project}/overseer/compose` | Human intervention |

## Available Tools

| Tool | Purpose |
|------|---------|
| `ensure_project` | Initialize project |
| `register_agent` | Register agent identity |
| `send_message` | Send message to agent(s) |
| `file_reservation_paths` | Acquire/release file locks |
| `search_messages` | Full-text search |
| `get_directory` | List active agents/projects |

## Persistence (Active)

### launchd (macOS) - CONFIGURED

Plist installed at `~/Library/LaunchAgents/com.agentmail.server.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agentmail.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/dylanconlin/.local/share/mcp_agent_mail/.venv/bin/python</string>
        <string>-m</string>
        <string>mcp_agent_mail.cli</string>
        <string>serve-http</string>
        <string>--port</string>
        <string>8765</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/dylanconlin/.local/share/mcp_agent_mail</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/dylanconlin/.local/share/mcp_agent_mail/src</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/agent-mail.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/agent-mail.err</string>
</dict>
</plist>
```

**Management commands:**
```bash
# Check status
launchctl list | grep agentmail

# Restart
launchctl stop com.agentmail.server && launchctl start com.agentmail.server

# Reload config (after editing plist)
launchctl unload ~/Library/LaunchAgents/com.agentmail.server.plist
launchctl load ~/Library/LaunchAgents/com.agentmail.server.plist
```

### Alternative: tmux (manual)

```bash
tmux new-session -d -s agent-mail "cd ~/.local/share/mcp_agent_mail && uv run python -m mcp_agent_mail.cli serve-http --port 8765"
```

## Troubleshooting

**Server not starting:**
```bash
# Check if port is in use
lsof -i :8765

# Kill existing process
pkill -f "mcp_agent_mail.cli serve-http"
```

**Module not found:**
```bash
cd ~/.local/share/mcp_agent_mail
pip install -e .
```

**Check server health:**
```bash
curl http://127.0.0.1:8765/
```

## Related Documentation

- Research: `.orch/investigations/feasibility/2025-12-02-agent-mail-mcp.md`
- Architecture: `.orch/investigations/design/2025-12-01-orch-cli-role-in-agent-ecosystem.md`
- GitHub: https://github.com/Dicklesworthstone/mcp_agent_mail

## Integration with orch-cli (IMPLEMENTED)

**Spawn context integration** (`src/orch/spawn_prompt.py`):

Spawned agents automatically receive instructions to:
1. Register with Agent Mail on startup (first 5 actions)
2. Check inbox periodically (every 30 min or at phase transitions)
3. Acknowledge urgent messages (`ack_required=true`)
4. Message orchestrator when blocked

**Commit:** `23cb4d6` - feat(spawn): add Agent Mail coordination to spawn context

**Tested workflow:**
```
Orchestrator (ChartreuseCreek) → send_message → Worker (BlueCastle)
Worker → acknowledge_message → Orchestrator
Worker → reply_message → Orchestrator
Orchestrator → fetch_inbox → sees reply
```

**Complementary to `orch send`:**
- `orch send`: Immediate tmux injection (synchronous, ephemeral)
- Agent Mail: Persistent messaging with history, search, threading

**Future possibilities:**
- File reservations to prevent conflicts in multi-agent scenarios
- Orchestrator web UI for human oversight
- Cross-project agent coordination
