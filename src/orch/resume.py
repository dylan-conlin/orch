"""
Resume paused agents with workspace-aware continuation.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from orch.workspace import parse_workspace


def parse_resume_context(workspace_path: Path) -> Dict[str, Any]:
    """
    Parse workspace file to extract resume context.

    Args:
        workspace_path: Path to WORKSPACE.md file or directory

    Returns:
        dict with resume context:
            - next_step: Specific next action from Summary section
            - last_completed: Last completed task from Progress Tracking
            - phase: Current phase
            - session_time: Elapsed session time (if tracked)
            - budget_remaining: Remaining time budget (if tracked)

    Returns empty dict if workspace not found or can't parse.
    """
    # Expand ~ and handle directory vs file path
    workspace_path = Path(workspace_path).expanduser()
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        return {}

    content = workspace_path.read_text()
    context = {}

    # Extract basic phase info using existing parser
    signal = parse_workspace(workspace_path)
    if signal.phase:
        context['phase'] = signal.phase

    # Extract "Next Step" from Summary section
    # Pattern: - **Next Step:** [text]
    next_step_match = re.search(
        r'^\s*-\s*\*\*Next Step:\*\*\s*(.+?)$',
        content,
        re.MULTILINE
    )
    if next_step_match:
        context['next_step'] = next_step_match.group(1).strip()

    # Extract last completed task from Progress Tracking
    # Pattern: - [x] Task N: Description
    completed_tasks = re.findall(
        r'^\s*-\s*\[x\]\s*(.+?)$',
        content,
        re.MULTILINE
    )
    if completed_tasks:
        context['last_completed'] = completed_tasks[-1].strip()

    # Extract session time tracking (if present)
    # Pattern: Session time: X.Xh elapsed, X.Xh budget remaining
    time_match = re.search(
        r'Session time:\s*([\d.]+)h\s+elapsed.*?([\d.]+)h\s+budget remaining',
        content,
        re.IGNORECASE
    )
    if time_match:
        context['session_time'] = time_match.group(1)
        context['budget_remaining'] = time_match.group(2)

    return context


def update_workspace_timestamps(workspace_path: Path) -> None:
    """
    Update workspace timestamps for resumption.

    Updates:
        - Resumed At: [ISO timestamp] (in header)
        - Last Activity: [ISO timestamp] (in Session Scope section if present)
        - Current Status: RESUMING (in Checkpoint Opportunities section if present)

    Args:
        workspace_path: Path to WORKSPACE.md file or directory

    Raises:
        FileNotFoundError: If workspace file doesn't exist
    """
    # Expand ~ and handle directory vs file path
    workspace_path = Path(workspace_path).expanduser()
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace file not found: {workspace_path}")

    content = workspace_path.read_text()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Update "Resumed At" field in header (or add if missing)
    if re.search(r'^\*\*Resumed At:\*\*', content, re.MULTILINE):
        # Update existing field
        content = re.sub(
            r'(^\*\*Resumed At:\*\*\s+)(.+?)$',
            f'\\1{now_iso}',
            content,
            flags=re.MULTILINE
        )
    else:
        # Add field after "Last Updated" if not present
        content = re.sub(
            r'(^\*\*Last Updated:\*\*.+?)$',
            f'\\1\n**Resumed At:** {now_iso}',
            content,
            flags=re.MULTILINE
        )

    # Update "Last Activity" in Session Scope section (if present)
    content = re.sub(
        r'(^\*\*Last Activity:\*\*\s+)(.+?)$',
        f'\\1{now_iso}',
        content,
        flags=re.MULTILINE
    )

    # Update "Current Status" in Checkpoint Opportunities section (if present)
    content = re.sub(
        r'(^\*\*Current Status:\*\*\s+)(.+?)$',
        r'\1RESUMING',
        content,
        flags=re.MULTILINE
    )

    # Write updated content back
    workspace_path.write_text(content)


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
    parts = ["Resuming work. Your workspace shows:"]

    if context.get('last_completed'):
        parts.append(f"- Last completed: {context['last_completed']}")

    if context.get('next_step'):
        parts.append(f"- Next step: {context['next_step']}")

    if context.get('session_time') and context.get('budget_remaining'):
        parts.append(
            f"- Session time: {context['session_time']}h elapsed, "
            f"{context['budget_remaining']}h budget remaining"
        )

    # If we have next step, use it as continuation directive
    if context.get('next_step'):
        parts.append(f"\nContinue with: {context['next_step']}")
    else:
        parts.append(f"\nPlease continue where you left off.")

    return "\n".join(parts)
