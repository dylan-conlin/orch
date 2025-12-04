#!/usr/bin/env python3
"""
Hook: Block 'bd close' commands in worker context.

Triggered by: PreToolUse (Bash)
When: Worker agent attempts to run 'bd close' command
Action: Deny with guidance to use 'bd comment' instead

This prevents workers from closing beads issues directly, which would bypass
the 'orch complete' verification process. Only orchestrators should close
issues after verifying agent work is complete.

Installation:
  Add to ~/.claude/settings.json:
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Bash",
          "hooks": [
            {
              "type": "command",
              "command": "$HOME/.orch/hooks/block-bd-close.py"
            }
          ]
        }
      ]
    }
  }
"""
import json
import os
import re
import sys


def check_command(input_data: dict) -> dict | None:
    """
    Check if a command should be blocked.

    Args:
        input_data: The tool input data from Claude Code

    Returns:
        None if command is allowed, or a dict with permissionDecision and reason if blocked
    """
    # Only check Bash commands
    if input_data.get("tool_name") != "Bash":
        return None

    # Only block in worker context
    context = os.environ.get("CLAUDE_CONTEXT", "")
    if context != "worker":
        return None

    # Get the command being executed
    command = input_data.get("tool_input", {}).get("command", "")

    # Check for 'bd close' pattern
    # Match: bd close, bd  close (multiple spaces), but not 'echo "bd close"' etc.
    # Use word boundary to avoid matching 'abcd close' or 'bd closed'
    if re.match(r'^\s*bd\s+close\b', command):
        return {
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "⛔ Workers cannot run 'bd close' directly. "
                "This bypasses verification and breaks tracking.\n\n"
                "Instead:\n"
                "1. Report completion via: bd comment <beads-id> \"Phase: Complete - [summary]\"\n"
                "2. Run /exit to close the agent session\n"
                "3. The orchestrator will verify and close the issue via 'orch complete'"
            )
        }

    return None


def main():
    """Main entry point for the PreToolUse hook."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Invalid JSON, allow command
        sys.exit(0)

    result = check_command(input_data)

    if result:
        # Block the command
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": result["permissionDecision"],
                "permissionDecisionReason": result["permissionDecisionReason"]
            }
        }
        print(json.dumps(output))

    # Exit 0 regardless - JSON controls behavior
    sys.exit(0)


if __name__ == '__main__':
    main()
