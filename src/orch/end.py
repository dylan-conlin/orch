"""
End session functionality for orch tool.

Implements clean session exit with knowledge capture gates:
1. Detect tmux context (error if not in tmux)
2. Detect session type (orchestrator vs worker)
3. Check .kn/entries.jsonl for entries since session start
4. Soft gate: if no entries, prompt to confirm exit
5. Output guidance for agent to use /exit manually

Note: We don't send /exit via tmux because when this command runs from
a Bash tool call, the REPL isn't at its input prompt. The agent must
type /exit manually after running this command.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import click


def is_in_tmux() -> bool:
    """Check if running inside a tmux session."""
    return 'TMUX' in os.environ


def detect_session_type(cwd: str) -> str:
    """
    Detect the session type based on current directory.

    Args:
        cwd: Current working directory

    Returns:
        "orchestrator" - in project with .orch but not in workspace
        "worker" - in .orch/workspace/ directory
        "unknown" - no .orch directory found
    """
    if not cwd:
        return "unknown"

    cwd_path = Path(cwd)

    # Workers are in workspace directories
    if '/.orch/workspace/' in cwd or '/.orch/workspace' in str(cwd_path):
        return "worker"

    # Check if in a project with .orch/ or .kn/ directory
    for parent in [cwd_path] + list(cwd_path.parents):
        if (parent / ".orch").is_dir() or (parent / ".kn").is_dir():
            return "orchestrator"

    return "unknown"


def get_session_start_time() -> Optional[datetime]:
    """
    Get session start time.

    For orchestrators: reads ~/.orch/current-session.json
    For workers: falls back to 2 hours ago

    Returns:
        Session start datetime or None
    """
    session_file = Path.home() / ".orch" / "current-session.json"

    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)
                started_at = data.get("started_at", "")
                if started_at:
                    return datetime.fromisoformat(started_at)
        except (json.JSONDecodeError, ValueError, IOError):
            pass

    # Fallback: 2 hours ago
    return datetime.now().replace(hour=max(0, datetime.now().hour - 2))


def get_kn_entries_since(since: Optional[datetime], cwd: str) -> list:
    """
    Get kn entries created since the given time.

    Args:
        since: Only return entries created after this time
        cwd: Current working directory to find .kn directory

    Returns:
        List of kn entries (dicts with id, type, content, etc.)
    """
    if since is None:
        since = datetime.now().replace(hour=max(0, datetime.now().hour - 2))

    # Find .kn directory - check cwd and parent dirs
    cwd_path = Path(cwd)
    kn_file = None

    for parent in [cwd_path] + list(cwd_path.parents):
        candidate = parent / ".kn" / "entries.jsonl"
        if candidate.exists():
            kn_file = candidate
            break

    if kn_file is None:
        return []

    try:
        entries = []
        with open(kn_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    created_at_str = entry.get("created_at", "")
                    if created_at_str:
                        # Parse ISO format timestamp
                        created_at = datetime.fromisoformat(
                            created_at_str.replace('Z', '+00:00')
                        )

                        # Make since timezone-aware if created_at is
                        compare_since = since
                        if created_at.tzinfo is not None and since.tzinfo is None:
                            compare_since = since.astimezone()

                        if created_at >= compare_since:
                            entries.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue

        return entries
    except (IOError, OSError):
        return []


def format_knowledge_warning() -> str:
    """Return the soft gate warning message with guidance."""
    return """
⚠️  No knowledge captured this session.

Consider before exiting:
  kn decide "what" --reason "why"     # Decisions made
  kn tried "what" --failed "why"      # Failed approaches
  kn constrain "rule" --reason "why"  # Constraints discovered
"""


def end_session(skip_prompt: bool = False) -> bool:
    """
    End the current session cleanly with knowledge capture check.

    Args:
        skip_prompt: If True, skip the confirmation prompt

    Returns:
        True if session was ended, False if cancelled
    """
    # Step 1: Check tmux context
    if not is_in_tmux():
        click.echo("Error: orch end requires tmux", err=True)
        click.echo("Run this command from within a tmux session.", err=True)
        return False

    # Step 2: Get session start time
    session_start = get_session_start_time()

    # Step 3: Check for knowledge entries
    cwd = os.getcwd()
    entries = get_kn_entries_since(session_start, cwd)

    # Step 4: Show status and potentially prompt
    if len(entries) > 0:
        if len(entries) == 1:
            click.echo(f"✓ Knowledge captured: {len(entries)} entry")
        else:
            click.echo(f"✓ Knowledge captured: {len(entries)} entries")
    else:
        # No entries - soft gate
        click.echo(format_knowledge_warning())

        if not skip_prompt:
            if not click.confirm("Exit anyway?", default=False):
                click.echo("Exit cancelled.")
                return False

    # Step 5: Guide agent to exit
    # Note: We don't send /exit via tmux because when this command runs from
    # a Bash tool call, the REPL isn't at its input prompt (it's mid-tool-execution).
    # The /exit would arrive but not be processed as a command.
    # Instead, we output guidance for the agent to exit manually.
    click.echo("")
    click.echo("Ready to exit. Use /exit to close session.")
    return True
