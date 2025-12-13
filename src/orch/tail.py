"""
Agent output capture for passive monitoring.
"""

import subprocess
from typing import Dict, Any, List

from orch.backends.opencode import OpenCodeClient, discover_server


def tail_agent_output(agent: Dict[str, Any], lines: int = 20) -> str:
    """
    Capture recent output from an agent's tmux window or OpenCode session.

    Uses stable window_id if available (doesn't change with tmux renumbering),
    falls back to window target for legacy agents without window_id.
    For OpenCode agents, uses the HTTP API to retrieve recent messages.

    Args:
        agent: Agent dict with 'window' or 'window_id' key for tmux agents,
               or 'backend'='opencode' with 'session_id' for OpenCode agents
        lines: Number of lines to capture from bottom (default 20)

    Returns:
        Captured output as string

    Raises:
        RuntimeError: If tmux command fails or OpenCode API call fails
    """
    # Check if this is an opencode agent
    if agent.get('backend') == 'opencode':
        return _tail_opencode(agent, lines)

    # Tmux-based backends (claude, codex)
    return _tail_tmux(agent, lines)


def _tail_opencode(agent: Dict[str, Any], lines: int) -> str:
    """Capture recent output from an OpenCode agent via HTTP API."""
    import logging
    
    session_id = agent.get('session_id')
    
    # Fallback to tmux if no session_id (standalone TUI mode)
    # This matches the pattern in send.py for consistency
    if not session_id:
        logging.getLogger(__name__).info(
            f"OpenCode agent {agent['id']} has no session_id, using tmux fallback"
        )
        return _tail_tmux(agent, lines)

    # Discover server
    server_url = discover_server()
    if not server_url:
        raise RuntimeError(
            "OpenCode server not found. Start with: "
            "cd ~/Documents/personal/opencode && bun run dev serve --port 4096"
        )

    client = OpenCodeClient(server_url)

    # Check server health
    if not client.health_check():
        raise RuntimeError(f"OpenCode server at {server_url} not responding")

    # Get messages from the session
    try:
        messages = client.get_messages(session_id)
    except Exception as e:
        raise RuntimeError(f"Failed to get messages from OpenCode session {session_id}: {e}")

    # Format messages for display
    return _format_opencode_messages(messages, lines)


def _format_opencode_messages(messages: List[Any], lines: int) -> str:
    """
    Format OpenCode messages for display output.

    Args:
        messages: List of Message objects from OpenCode API
        lines: Maximum number of lines to return

    Returns:
        Formatted string with role labels and message content
    """
    output_lines = []

    for msg in messages:
        role = msg.role
        # Extract text content from message parts
        text_parts = []
        for part in msg.parts:
            if isinstance(part, dict) and part.get('type') == 'text':
                text_parts.append(part.get('text', ''))

        if text_parts:
            content = '\n'.join(text_parts)
            # Add role label and content
            output_lines.append(f"[{role}] {content}")

    # Join all content and limit to requested lines
    full_output = '\n'.join(output_lines)
    all_lines = full_output.split('\n')

    # Take last N lines
    if len(all_lines) > lines:
        all_lines = all_lines[-lines:]

    return '\n'.join(all_lines)


def _tail_tmux(agent: Dict[str, Any], lines: int) -> str:
    """Capture recent output from an agent's tmux window."""
    # Prefer stable window_id over window target (window indices change when tmux renumbers)
    window_target = agent.get('window_id', agent['window'])

    # Build tmux capture-pane command
    # -t: target window
    # -p: print to stdout
    # -S: start line (negative = relative to bottom)
    cmd = [
        'tmux', 'capture-pane',
        '-t', window_target,
        '-p',  # print to stdout
        '-S', f'-{lines}'  # lines from bottom
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to capture output from {agent['id']}: {result.stderr}"
        )

    return result.stdout
