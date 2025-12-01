---
date: "2025-12-01"
status: "Active"
---

# Quick Test: Read CLAUDE.md

**Phase:** Complete

**TLDR:** orch-cli is a CLI tool for AI agent orchestration - spawning, monitoring, and completing AI agents across multiple backends (Claude Code, Codex, OpenCode). It manages workspaces, agent state via registry, and integrates with skills and issue tracking systems.

## Question

What does this project (orch-cli) do? Summarize in 2-3 sentences by reading the CLAUDE.md file.

## What I tried

- Read the root CLAUDE.md file at /Users/dylanconlin/Documents/personal/orch-cli/CLAUDE.md
- Reviewed the project description and architecture overview

## What I observed

- The first line states: "CLI tools for AI agent orchestration"
- Key capabilities: spawning, monitoring, and completing AI agents
- Supports multiple backends: Claude Code, Codex, OpenCode
- Architecture includes: spawn logic, registry for agent state, skill discovery, issue tracking integration (beads)
- Spawn flow: creates workspaces, writes SPAWN_CONTEXT.md, opens tmux windows, registers agents

## Test performed

**Test:** Read the CLAUDE.md file (146 lines) using the Read tool and extracted the project description.

**Result:** Successfully read the file. The description is on line 7: "CLI tools for AI agent orchestration. Enables spawning, monitoring, and completing AI agents across multiple backends (Claude Code, Codex, OpenCode)."

## Conclusion

**orch-cli** is a CLI toolkit for orchestrating AI agents. It enables spawning agents with specific skills and tasks, monitoring their progress via tmux and a registry system, and completing their work when done. It supports multiple AI backends (Claude Code, Codex, OpenCode) and integrates with skills (reusable agent guidance) and beads (issue tracking) for structured agent workflows.

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED
