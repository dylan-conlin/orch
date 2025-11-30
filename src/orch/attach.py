"""
Attach to agent's window with three-layer activation.

This module implements the `orch attach` command which activates the correct
Ghostty window and switches to the agent's tmux session/window.

Three-layer activation:
1. yabai layer: Focus the Ghostty window containing the target session
2. Ghostty layer: Ensure window is visible (handled by yabai)
3. tmux layer: Switch to correct session and window within tmux
"""

import json
import subprocess
from typing import Dict, Optional, Any


def find_ghostty_window_for_session(session_name: str) -> Optional[Dict[str, Any]]:
    """
    Find which Ghostty window contains the given tmux session.

    Args:
        session_name: Name of tmux session (e.g., 'main', 'orchestrator')

    Returns:
        Dict with window info (id, title) or None if not found/yabai unavailable

    Strategy:
        Parse yabai window titles which contain session names in format:
        "Mac ❐ {session_name} ● {window_number} {window_name}"
    """
    try:
        # Query yabai for all windows
        result = subprocess.run(
            ['yabai', '-m', 'query', '--windows'],
            capture_output=True,
            text=True,
            check=True,
            timeout=2
        )

        windows = json.loads(result.stdout)

        # Find Ghostty windows containing the session name
        for window in windows:
            if window.get('app') == 'Ghostty':
                title = window.get('title', '')
                # Check if title contains session name
                # Format: "Mac ❐ {session_name} ● {window_number} {window_name}"
                if f"❐ {session_name} ●" in title:
                    return {
                        'id': window['id'],
                        'title': title,
                        'frame': window.get('frame', {})
                    }

        return None

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        # yabai not running, not installed, or query failed
        return None


def activate_ghostty_window(window_id: int) -> bool:
    """
    Activate (focus) Ghostty window via yabai.

    Args:
        window_id: yabai window ID to focus

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ['yabai', '-m', 'window', '--focus', str(window_id)],
            check=True,
            capture_output=True,
            timeout=2
        )
        return True

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def switch_tmux_session(window_target: str) -> bool:
    """
    Switch to tmux session and window.

    Args:
        window_target: Tmux window target (e.g., 'orchestrator:2', '@30')
                      Prefer stable window_id format (@30) over unstable index

    Returns:
        True if successful, False otherwise
    """
    try:
        # Use select-window which works without an attached client
        # (unlike switch-client which requires current client to exist)
        # This is critical for agent-picker which calls via detach-client -E
        subprocess.run(
            ['tmux', 'select-window', '-t', window_target],
            check=True,
            capture_output=True,
            timeout=2
        )
        return True

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def extract_session_from_window(window_target: str) -> str:
    """
    Extract session name from window target.

    Args:
        window_target: Window target like 'orchestrator:2'

    Returns:
        Session name (e.g., 'orchestrator')
    """
    if ':' in window_target:
        return window_target.split(':')[0]
    return window_target
