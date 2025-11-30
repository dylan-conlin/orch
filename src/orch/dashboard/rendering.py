"""Rendering components for dashboard UI."""
from typing import Dict, Any
from rich.text import Text
from rich.markup import escape
from datetime import datetime, timezone


def get_status_badge(status: str, phase: str) -> str:
    """Get colored status badge for agent.

    Args:
        status: Agent status (active, blocked, complete, failed)
        phase: Agent phase (Planning, Implementing, etc.)

    Returns:
        Rich-formatted status badge string
    """
    # Map status to color and badge text
    status_map = {
        'active': ('[green]', '[ACTIVE]'),
        'blocked': ('[yellow]', '[BLOCKED]'),
        'complete': ('[dim white]', '[COMPLETE]'),
        'failed': ('[red]', '[FAILED]'),
    }

    # Check status first (blocked/complete/failed take precedence)
    if status.lower() in status_map:
        color, text = status_map[status.lower()]
    # Then check phase for planning
    elif phase.lower() == 'planning':
        color, text = '[blue]', '[PLANNING]'
    else:
        color, text = '[white]', f'[{status.upper()}]'

    return f"{color}{text}[/]"


def format_agent_line(agent: Dict[str, Any], is_focused: bool) -> str:
    """Format agent as single line for tree display.

    Args:
        agent: Agent dict with workspace_name, status, phase
        is_focused: Whether this agent has cursor focus

    Returns:
        Formatted string with badge and workspace name
    """
    badge = get_status_badge(agent['status'], agent['phase'])
    name = agent['workspace_name']

    # Truncate long names
    if len(name) > 40:
        name = name[:37] + '...'

    cursor = '→ ' if is_focused else '  '

    # Escape name to prevent Rich markup interpretation (e.g., paths with [/])
    return f"{cursor}{badge} {escape(name)}"


def format_agent_detail_line(agent: Dict[str, Any]) -> str:
    """Format agent detail line (shown below agent name).

    Args:
        agent: Agent dict with phase, last_updated

    Returns:
        Formatted detail string
    """
    phase = agent.get('phase', 'Unknown')
    last_updated = agent.get('last_updated', '')

    # Format timestamp as relative time
    try:
        dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - dt

        if delta.total_seconds() < 60:
            time_str = 'just now'
        elif delta.total_seconds() < 3600:
            mins = int(delta.total_seconds() / 60)
            time_str = f'{mins}m ago'
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            time_str = f'{hours}h ago'
        else:
            days = int(delta.total_seconds() / 86400)
            time_str = f'{days}d ago'
    except:
        time_str = 'unknown'

    # Escape phase to prevent Rich markup interpretation
    return f"  └ Phase: {escape(phase)} | Updated: {time_str}"
