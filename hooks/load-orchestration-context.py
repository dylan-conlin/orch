#!/usr/bin/env python3
"""
Hook: Auto-load orchestration context at session start.

Triggered by: SessionStart (startup, resume)
When: Claude Code/OpenCode session starts or resumes in an orch project
Action: Load orchestrator skill and show active agents

Installation (Claude Code):
  Add to ~/.claude/settings.json:
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

Installation (OpenCode):
  Add to opencode.json in project root:
  {
    "experimental": {
      "hook": {
        "session_started": [
          {
            "command": ["python3", "hooks/load-orchestration-context.py", "--opencode"]
          }
        ]
      }
    }
  }
"""
import argparse
import json
import os
import sys
import subprocess
from pathlib import Path


def load_orchestrator_skill():
    """Load orchestrator skill from ~/.claude/skills/orchestrator/SKILL.md."""
    skill_path = Path.home() / '.claude' / 'skills' / 'orchestrator' / 'SKILL.md'

    if not skill_path.exists():
        return None

    try:
        return skill_path.read_text()
    except Exception:
        return None


def find_orch_directory():
    """Find .orch directory in current directory or parents."""
    cwd = Path.cwd()

    if (cwd / '.orch').is_dir():
        return cwd / '.orch'

    for parent in cwd.parents:
        orch_dir = parent / '.orch'
        if orch_dir.is_dir():
            return orch_dir

    return None


def load_kn_recent():
    """Load recent kn entries if .kn exists."""
    kn_dir = Path.cwd() / '.kn'
    if not kn_dir.exists():
        return None

    try:
        result = subprocess.run(
            ['kn', 'recent', '--limit', '10'],
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        return result.stdout.strip()

    except (subprocess.TimeoutExpired, Exception):
        return None


def load_active_agents():
    """Load active agents via orch status."""
    try:
        result = subprocess.run(
            ['orch', 'status', '--format', 'json'],
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        agents = data.get('agents', [])

        if not agents:
            return "**Active Agents:** None\n"

        lines = ["**Active Agents:**\n"]
        for agent in agents[:5]:
            agent_id = agent.get('agent_id', 'Unknown')
            phase = agent.get('phase', 'Unknown')
            window = agent.get('window', 'N/A')

            alerts = agent.get('alerts', [])
            alert_str = ""
            if alerts:
                alert_types = [a.get('type', '') for a in alerts]
                alert_str = f" ⚠️ {', '.join(alert_types)}"

            lines.append(f"- `{agent_id}` - Phase: {phase} | Window: {window}{alert_str}")

        if len(agents) > 5:
            lines.append(f"\n*...and {len(agents) - 5} more agents*")

        return "\n".join(lines) + "\n"

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--opencode', action='store_true', 
                        help='Run in OpenCode mode (no stdin, plain output)')
    args = parser.parse_args()

    # Skip for worker agents (they have skill embedded in SPAWN_CONTEXT.md)
    if os.environ.get('ORCH_WORKER'):
        sys.exit(0)

    # Claude Code mode: read from stdin
    if not args.opencode:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)

        # Only load on startup/resume
        source = input_data.get('source', '')
        if source not in ['startup', 'resume']:
            sys.exit(0)

    # Must be in an orch project
    orch_dir = find_orch_directory()
    if not orch_dir:
        sys.exit(0)

    # Build context
    context_parts = []
    context_parts.append("# Orchestration Context\n")
    backend = "OpenCode" if args.opencode else "Claude Code"
    context_parts.append(f"*Auto-loaded via session hook ({backend})*\n\n")

    # Load orchestrator skill
    skill_content = load_orchestrator_skill()
    if skill_content:
        context_parts.append("---\n\n")
        context_parts.append(skill_content)
        context_parts.append("\n\n---\n\n")

    # Load active agents
    agents = load_active_agents()
    if agents:
        context_parts.append("## Active Agents\n\n")
        context_parts.append(agents)

    # Load recent kn entries
    kn_recent = load_kn_recent()
    if kn_recent:
        context_parts.append("\n## Recent Knowledge (kn)\n\n")
        context_parts.append("*Quick decisions, constraints, failed attempts, questions*\n\n")
        context_parts.append("```\n")
        context_parts.append(kn_recent)
        context_parts.append("\n```\n\n")
        context_parts.append("*Run `kn context \"<topic>\"` to get knowledge about a specific area*\n")

    # Output if we have context
    if len(context_parts) > 2:
        if args.opencode:
            # OpenCode: just print the context directly
            print(''.join(context_parts))
        else:
            # Claude Code: JSON protocol
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": ''.join(context_parts)
                }
            }
            print(json.dumps(output, indent=2))

    sys.exit(0)


if __name__ == '__main__':
    main()
