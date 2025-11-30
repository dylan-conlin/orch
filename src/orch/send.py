"""
Send messages to spawned agents via tmux or OpenCode API.
"""

import subprocess
import time
from typing import Dict, Any
from orch.tmux_utils import get_window_by_target, get_window_by_id


def send_message_to_agent(agent: Dict[str, Any], message: str):
    """
    Send a message to an agent via tmux or OpenCode API.

    Uses stable window_id if available, falls back to window target for legacy agents.
    For opencode agents, uses the HTTP API to send messages.

    Args:
        agent: Agent dict from registry (must have 'window' or 'window_id' key,
               or 'backend'='opencode' with 'session_id')
        message: Message to send

    Raises:
        RuntimeError: If tmux window not found or OpenCode API call fails
    """
    # Check if this is an opencode agent
    if agent.get('backend') == 'opencode':
        _send_message_opencode(agent, message)
        return

    # Tmux-based backends (claude, codex)
    _send_message_tmux(agent, message)


def _send_message_opencode(agent: Dict[str, Any], message: str):
    """Send message to an OpenCode agent via HTTP API."""
    from orch.backends.opencode import OpenCodeClient, discover_server

    session_id = agent.get('session_id')
    if not session_id:
        raise RuntimeError(
            f"Agent '{agent['id']}' is an OpenCode agent but has no session_id. "
            f"Cannot send message."
        )

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

    # Send message via async API (returns immediately)
    try:
        client.send_message_async(session_id, message)
    except Exception as e:
        raise RuntimeError(f"Failed to send message to OpenCode session {session_id}: {e}")


def _send_message_tmux(agent: Dict[str, Any], message: str):
    """Send message to a tmux-based agent via send-keys."""
    # Prefer stable window_id over window target
    window_id = agent.get('window_id')
    if window_id:
        # Extract session name from window target (format: "session:index")
        window_target = agent.get('window', '')
        session_name = window_target.split(':')[0] if ':' in window_target else 'orchestrator'

        # Use stable window ID (doesn't change with tmux renumbering)
        window = get_window_by_id(window_id, session_name)
        if not window:
            raise RuntimeError(f"Window with ID '{window_id}' not found")
        # Tmux accepts window_id directly as target
        target = window_id
    else:
        # Fallback to window target for legacy agents
        window_target = agent['window']
        window = get_window_by_target(window_target)
        if not window:
            raise RuntimeError(f"Window '{window_target}' not found")
        target = window_target

    # Send message via tmux send-keys
    subprocess.run([
        "tmux", "send-keys",
        "-t", target,
        message
    ], check=True)

    # Wait for message to be pasted into terminal buffer
    # Without this sleep, Enter gets processed before message is fully pasted
    time.sleep(1)

    # Auto-append Enter
    subprocess.run([
        "tmux", "send-keys",
        "-t", target,
        "Enter"
    ], check=True)
