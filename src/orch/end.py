"""
End session functionality for orch tool.

Implements clean session exit with knowledge capture gates:
1. Detect tmux context (error if not in tmux)
2. Detect session type (orchestrator vs worker)
3. Check .kn/entries.jsonl for entries since session start
4. Soft gate: if no entries, prompt to confirm exit
5. Send /exit + Enter via tmux send-keys to trigger SessionEnd hooks
"""

import click


def end_session(skip_prompt: bool = False) -> bool:
    """
    End the current session cleanly with knowledge capture check.

    Args:
        skip_prompt: If True, skip the confirmation prompt

    Returns:
        True if session was ended, False if cancelled
    """
    # TODO: Implement the full logic
    click.echo("orch end: Not yet implemented")
    return False
