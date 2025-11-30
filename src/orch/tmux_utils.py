import libtmux
from typing import Optional, List, Dict, Any

def get_server():
    """Get libtmux server instance."""
    try:
        return libtmux.Server()
    except Exception:
        return None

def is_tmux_available() -> bool:
    """Check if tmux is available and running."""
    server = get_server()
    if not server:
        return False
    try:
        # Try to list sessions to verify connection works
        _ = server.sessions
        return True
    except Exception:
        return False

def find_session(session_name: str):
    """Find tmux session by name."""
    server = get_server()
    if not server:
        return None

    for session in server.sessions:
        if session.session_name == session_name:
            return session
    return None

def list_windows(session_name: str) -> List[Dict[str, Any]]:
    """
    List all windows in a session.

    Returns empty list if tmux unavailable or session not found.
    """
    session = find_session(session_name)
    if not session:
        return []

    windows = []
    for window in session.windows:
        windows.append({
            'index': window.window_index,
            'name': window.window_name,
            'id': window.window_id,
        })
    return windows

def get_window_by_target(window_target: str) -> Optional[Any]:
    """
    Get window by target string (e.g., 'orchestrator:5').

    Args:
        window_target: Format 'session_name:window_index'

    Returns:
        Window object or None
    """
    if window_target is None:
        return None
    if ':' not in window_target:
        return None

    session_name, window_index = window_target.split(':', 1)
    session = find_session(session_name)

    if not session:
        return None

    for window in session.windows:
        if window.window_index == window_index:
            return window

    return None

def get_window_by_id(window_id: str, session_name: str = "workers") -> Optional[Any]:
    """
    Get window by stable window ID (e.g., '@157').

    Window IDs are stable and don't change when tmux renumbers windows,
    making them more reliable than window indices for tracking agents.

    Args:
        window_id: Window ID in format '@NNN'
        session_name: Tmux session name (default: 'workers')

    Returns:
        Window object or None
    """
    session = find_session(session_name)
    if not session:
        return None

    for window in session.windows:
        if window.window_id == window_id:
            return window

    return None


def has_active_processes(window_id: str) -> bool:
    """
    Check if a tmux window has active child processes.

    Args:
        window_id: Tmux window ID (e.g., '@123')

    Returns:
        True if window has running child processes, False otherwise
    """
    import subprocess

    try:
        # Get the PID of the tmux pane/window
        result = subprocess.run(
            ['tmux', 'list-panes', '-t', window_id, '-F', '#{pane_pid}'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            # Window doesn't exist or error getting PID
            return False

        pid = result.stdout.strip()
        if not pid:
            return False

        # Check for child processes using pgrep
        children = subprocess.run(
            ['pgrep', '-P', pid],
            capture_output=True,
            text=True,
            check=False
        )

        # pgrep returns 0 if processes found, 1 if none found
        return children.returncode == 0

    except Exception:
        # If any error occurs, assume no active processes (fail safe)
        return False


def graceful_shutdown_window(window_id: str, wait_seconds: int = 5) -> bool:
    """
    Attempt graceful shutdown of tmux window by sending Ctrl+C and waiting.

    Args:
        window_id: Tmux window ID (e.g., '@123')
        wait_seconds: How long to wait for processes to terminate (default: 5)

    Returns:
        True if shutdown successful (no processes remain), False if processes still active
    """
    import subprocess
    import time

    # Check if processes exist before attempting shutdown
    if not has_active_processes(window_id):
        return True

    try:
        # Send Ctrl+C (SIGINT) to the pane
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_id, 'C-c'],
            check=False,
            stderr=subprocess.DEVNULL
        )

        # Wait for processes to terminate
        time.sleep(wait_seconds)

        # Check if processes are gone
        return not has_active_processes(window_id)

    except Exception:
        # If error occurs, return False (processes may still be active)
        return False
