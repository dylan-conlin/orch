"""
Resume paused agents with workspace-aware continuation.

Note: WORKSPACE.md is no longer used for agent state tracking.
Beads is the source of truth. Resume context now focuses on
SPAWN_CONTEXT.md and primary artifacts.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone


def parse_resume_context(workspace_path: Path) -> Dict[str, Any]:
    """
    Parse workspace directory to extract resume context.

    Now reads from SPAWN_CONTEXT.md instead of WORKSPACE.md.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        dict with resume context:
            - next_step: Specific next action (if found)
            - task: Original task from SPAWN_CONTEXT.md

    Returns empty dict if workspace not found or can't parse.
    """
    workspace_path = Path(workspace_path).expanduser()
    if not workspace_path.is_dir():
        return {}

    context = {}

    # Read SPAWN_CONTEXT.md for task info
    spawn_context_path = workspace_path / 'SPAWN_CONTEXT.md'
    if spawn_context_path.exists():
        try:
            content = spawn_context_path.read_text()

            # Extract task from SPAWN_CONTEXT.md
            task_match = re.search(r'^##\s*Task\s*\n\n(.+?)(?:\n##|\Z)', content, re.MULTILINE | re.DOTALL)
            if task_match:
                context['task'] = task_match.group(1).strip()
        except Exception:
            pass

    return context


def update_workspace_timestamps(workspace_path: Path) -> None:
    """
    Update workspace timestamps for resumption.

    DEPRECATED: WORKSPACE.md is no longer used.
    This function is a no-op for backward compatibility.

    Args:
        workspace_path: Path to workspace directory
    """
    # WORKSPACE.md no longer used - no-op for backward compatibility
    pass


def generate_continuation_message(
    workspace_name: str,
    context: Dict[str, Any],
    custom_message: Optional[str] = None
) -> str:
    """
    Generate continuation message for agent resumption.

    Args:
        workspace_name: Workspace name
        context: Resume context from parse_resume_context()
        custom_message: Optional custom message (overrides auto-generation)

    Returns:
        Formatted continuation message
    """
    if custom_message:
        return custom_message

    # Auto-generate message from workspace context
    parts = ["Resuming work."]

    if context.get('task'):
        parts.append(f"\nOriginal task: {context['task']}")

    parts.append("\nPlease continue where you left off.")

    return " ".join(parts)
