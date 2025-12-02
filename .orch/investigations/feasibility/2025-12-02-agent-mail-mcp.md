# Research: Agent Mail MCP Server

**Question:** What is Agent Mail MCP, how does it work, and how do you install it in Claude Code?

**Confidence:** High (90%)
**Started:** 2025-12-02
**Updated:** 2025-12-02
**Status:** Complete
**Resolution-Status:** Resolved

---

## Summary

Agent Mail MCP is an asynchronous coordination layer for multiple coding agents, created by Jeffrey Emanuel (GitHub: Dicklesworthstone). It functions as "Gmail for your coding agents" - providing identities, inboxes/outboxes, searchable message history, and file reservation "leases" to prevent conflicts.

**Key stats:**
- Released: October 23, 2025
- GitHub stars: ~860+
- Estimated downloads: 118k+ (5.5k/week)
- License: MIT

---

## Options Evaluated

### Option 1: Agent Mail MCP (Dicklesworthstone/mcp_agent_mail)

**Overview:** Multi-agent coordination layer with Git-backed storage, messaging, and file reservations.

**Pros:**
- Human-auditable: All data stored as markdown files in Git
- Conflict prevention: Advisory file reservations with enforcement option
- Full-text search via SQLite FTS5
- Beads integration: Works with beads task planner
- Human overseer: Web UI for human intervention
- Active development: 860+ stars, frequent updates

**Cons:**
- HTTP-only (requires running a server process)
- Commercial companion features (iOS app, fleet management)
- Learning curve for file reservation patterns

**Evidence:**
- GitHub: https://github.com/Dicklesworthstone/mcp_agent_mail
- PulseMCP: https://www.pulsemcp.com/servers/dicklesworthstone-agent-mail

### Option 2: Composio AgentMail

**Overview:** Different project - provides AI agents with actual email inboxes (not agent-to-agent communication).

**Not evaluated further** - Different purpose (external email, not inter-agent coordination).

---

## Architecture Deep Dive

### Core Components

```
Agents → HTTP FastMCP Server (port 8765 default)
Server → Git repo (human-auditable artifacts)
Server → SQLite FTS5 (indexing/queries)
```

### Data Storage Structure

```
project_mailbox/
├── agents/
│   └── {agent_name}/profile.json
├── messages/
│   └── {year}/{month}/{message_id}.md
├── file_reservations/
│   └── {sha1(path)}.json
└── attachments/
    └── {sha1}.{ext}
```

### Agent Identity System

Agents register with memorable adjective+noun identities (e.g., "Cheerful-Penguin"). Each agent has:
- Profile JSON with metadata
- Inbox (messages TO them)
- Outbox (messages FROM them)
- File reservations they hold

### Message Format

Messages support:
- Threading via `thread_id`
- Subjects and GFM (GitHub Flavored Markdown) bodies
- Image attachments (stored by SHA1)
- Timestamps and sender/recipient metadata

### File Reservation System

Advisory locking mechanism:
- `exclusive=true`: Only holder can modify paths
- `exclusive=false`: Shared read access
- TTL (time-to-live) for automatic expiration
- Enforcement optional (`FILE_RESERVATIONS_ENFORCEMENT_ENABLED=true`)

---

## Available Tools/Capabilities

### Core Tools

| Tool | Purpose |
|------|---------|
| `ensure_project` | Initialize/ensure project exists |
| `register_agent` | Register agent identity with project |
| `send_message` | Send message to agent(s) |
| `file_reservation_paths` | Acquire/release file reservations |
| `search_messages` | Full-text search across messages |
| `get_directory` | Discover active agents and projects |

### Resources (Read-Only)

Resources use `resource://` URIs for fast reads:
- `resource://inbox/{Agent}?project=<path>&limit=20`
- `resource://thread/{thread_id}?project=<path>`
- `resource://product/{key}`

### Web UI Routes

- `/mail` - Unified inbox with project suggestions
- `/mail/{project}` - Project overview with search
- `/mail/{project}/inbox/{agent}` - Agent-specific inbox
- `/mail/{project}/message/{id}` - Message detail
- `/mail/{project}/file_reservations` - Active reservations
- `/mail/{project}/overseer/compose` - Human operator interface

---

## Installation in Claude Code

### Quick Install (One-Liner)

```bash
curl -fsSL https://raw.githubusercontent.com/Dicklesworthstone/mcp_agent_mail/main/scripts/install.sh | bash -s -- --yes
```

This installer:
1. Installs uv if needed
2. Clones the repository
3. Creates Python 3.14 venv
4. Auto-detects installed coding agents
5. Optionally starts the server

### Manual Installation

```bash
# Clone repo
git clone https://github.com/Dicklesworthstone/mcp_agent_mail.git
cd mcp_agent_mail

# Install with uv
uv sync

# Start server
./scripts/run_server_with_token.sh
```

### Claude Code MCP Configuration

**Method 1: CLI command**
```bash
claude mcp add-json agent-mail '{
  "command": "uv",
  "args": ["run", "python", "-m", "mcp_agent_mail.server"],
  "env": {
    "HTTP_ALLOW_LOCALHOST_UNAUTHENTICATED": "true"
  }
}'
```

**Method 2: .mcp.json file (project-scoped)**

Create `.mcp.json` in project root:
```json
{
  "mcpServers": {
    "agent-mail": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_agent_mail.server"],
      "cwd": "/path/to/mcp_agent_mail",
      "env": {
        "HTTP_ALLOW_LOCALHOST_UNAUTHENTICATED": "true",
        "PROJECT_DIR": "/path/to/your/project"
      }
    }
  }
}
```

**Method 3: Global settings (~/.claude.json)**
```json
{
  "mcpServers": {
    "agent-mail": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_agent_mail.server"],
      "cwd": "/path/to/mcp_agent_mail"
    }
  }
}
```

### Post-Install: Add Agent Blurbs

Run the blurb inserter to update CLAUDE.md/AGENTS.md:
```bash
uv run python -m mcp_agent_mail.cli docs insert-blurbs
```

---

## Common Use Cases & Patterns

### 1. Multi-Agent Development

**Scenario:** Multiple agents working on same codebase.

**Pattern:**
1. Each agent registers identity: `register_agent(project, "Agent-Name", repo_path)`
2. Reserve files before editing: `file_reservation_paths(project, agent, ['src/**'], exclusive=true)`
3. Communicate via messages: `send_message(project, agent, recipient, subject, body)`
4. Release reservations when done

### 2. Beads Task Integration

**Scenario:** Task planner + communication layer.

**Pattern:**
1. Pick work: `bd ready`
2. Reserve files with reason: `file_reservation_paths(..., reason="bd-123")`
3. Message in task thread: `send_message(..., thread_id="bd-123")`
4. Complete task: `bd close bd-123`

### 3. Human Overseer

**Scenario:** Human needs to intervene with agent.

**Pattern:**
1. Open web UI: `http://localhost:8765/mail/{project}/overseer/compose`
2. Send high-priority message (auto-preamble instructs agent to pause)
3. Agent receives and prioritizes human request

### 4. Conflict Prevention

**Scenario:** Prevent simultaneous edits to same files.

**Pattern:**
1. Before editing, check reservations: `get_file_reservations(project)`
2. Acquire exclusive lease: `file_reservation_paths(project, agent, paths, exclusive=true, ttl_seconds=3600)`
3. If conflict, message holder to coordinate
4. Release when done

---

## Integration with orch-cli

**Potential synergies:**

1. **Agent-to-agent messaging:** Instead of `orch send` via tmux, agents could use Agent Mail for persistent, searchable communication.

2. **File conflict prevention:** Agent Mail's reservation system could complement orch-cli's workspace isolation.

3. **Beads integration:** Both systems support beads - could unify task tracking with communication.

4. **Human oversight:** Agent Mail's web UI provides browser-based agent intervention.

**Considerations:**

- Agent Mail requires running an HTTP server (additional process)
- Different model from orch-cli's tmux-based orchestration
- Could be complementary rather than replacement

---

## Recommendation

**I recommend trying Agent Mail MCP** for multi-agent coordination scenarios because:

1. **Mature solution:** 860+ stars, 118k downloads, active development
2. **Human-auditable:** Git-backed storage means all messages are inspectable
3. **Beads integration:** Works with task tracking already in use
4. **Conflict prevention:** File reservations solve a real pain point

**When to use:**
- Multiple agents working on shared codebase
- Need persistent, searchable message history
- Want human oversight capabilities
- Beads-based task tracking

**When NOT to use:**
- Single-agent workflows
- Simple spawn-and-forget tasks
- Environments where running server process is problematic

---

## Confidence Assessment

**Current Confidence:** High (90%)

**What's certain:**
- Origin and creator verified (Jeffrey Emanuel, GitHub repo)
- Architecture documented in detail (README, source code)
- Installation methods confirmed (multiple sources)
- Tool capabilities documented

**What's uncertain:**
- Claude Code integration specifics (may need testing)
- Performance at scale (no benchmarks found)
- Commercial vs OSS feature boundary

**What would increase confidence to 95%+:**
- Hands-on installation and testing
- Verify all tools work in Claude Code
- Test beads integration in real workflow

---

## Research History

**2025-12-02:** Research completed
- Searched official docs, GitHub, MCP registries
- Found Agent Mail MCP by Jeffrey Emanuel
- Documented architecture, installation, tools
- Created recommendation with confidence assessment

---

## Self-Review

- [x] Each option has evidence with sources
- [x] Clear recommendation (not "it depends")
- [x] Confidence assessed honestly
- [x] Research file complete and ready for commit

**Self-Review Status:** PASSED

---

## Sources

- [GitHub - mcp_agent_mail](https://github.com/Dicklesworthstone/mcp_agent_mail)
- [PulseMCP - Agent Mail Server](https://www.pulsemcp.com/servers/dicklesworthstone-agent-mail)
- [AWS - Inter-Agent Communication on MCP](https://aws.amazon.com/blogs/opensource/open-protocols-for-agent-interoperability-part-1-inter-agent-communication-on-mcp/)
- [Microsoft - Agent2Agent Communication on MCP](https://developer.microsoft.com/blog/can-you-build-agent2agent-communication-on-mcp-yes)
- [Claude Code MCP Docs](https://docs.claude.com/en/docs/claude-code/mcp)
- [MCPcat Guide - Adding MCP Server to Claude Code](https://mcpcat.io/guides/adding-an-mcp-server-to-claude-code/)
