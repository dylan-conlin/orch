"""
Agent output capture for passive monitoring.
"""

import subprocess
from typing import Dict, Any


def tail_agent_output(agent: Dict[str, Any], lines: int = 20) -> str:
    """
    Capture recent output from an agent's tmux window.

    Uses stable window_id if available (doesn't change with tmux renumbering),
    falls back to window target for legacy agents without window_id.

    Args:
        agent: Agent dict with 'window' or 'window_id' key
        lines: Number of lines to capture from bottom (default 20)

    Returns:
        Captured output as string

    Raises:
        RuntimeError: If tmux command fails
    """
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
