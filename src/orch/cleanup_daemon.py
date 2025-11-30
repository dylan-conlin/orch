#!/usr/bin/env python3
"""
Background daemon for async agent cleanup.

This script runs as a detached background process to handle agent cleanup
without blocking the CLI. It implements a timeout cascade strategy:

1. Graceful shutdown (Ctrl+C, 30s)
2. Claude Code exit (/exit command, 30s)
3. Force kill tmux window (5s)
4. Mark as failed if still stuck

Usage:
    cleanup_daemon.py <agent_id> <registry_path>

Exit codes:
    0 - Cleanup successful
    1 - Cleanup failed (agent marked as failed in registry)
"""

import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime


def has_active_processes(window_id: str) -> bool:
    """
    Check if a tmux window has active child processes.

    Args:
        window_id: Tmux window ID (e.g., '@123')

    Returns:
        True if window has running child processes, False otherwise
    """
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


def graceful_shutdown_window(window_id: str, wait_seconds: int = 30) -> bool:
    """
    Attempt graceful shutdown of tmux window by sending Ctrl+C and waiting.

    Args:
        window_id: Tmux window ID (e.g., '@123')
        wait_seconds: How long to wait for processes to terminate (default: 30)

    Returns:
        True if shutdown successful (no processes remain), False if processes still active
    """
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


def send_exit_command(window_id: str, wait_seconds: int = 30) -> bool:
    """
    Send /exit command to Claude Code and wait.

    Args:
        window_id: Tmux window ID (e.g., '@123')
        wait_seconds: How long to wait for exit to complete (default: 30)

    Returns:
        True if exit successful (no processes remain), False otherwise
    """
    try:
        # Send /exit command
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_id, '/exit', 'Enter'],
            check=False,
            stderr=subprocess.DEVNULL
        )

        # Wait for exit to complete
        time.sleep(wait_seconds)

        # Check if processes are gone
        return not has_active_processes(window_id)

    except Exception:
        return False


def force_kill_window(window_id: str) -> bool:
    """
    Force kill tmux window.

    Args:
        window_id: Tmux window ID (e.g., '@123')

    Returns:
        True if window killed successfully, False otherwise
    """
    try:
        # Get session name from window first
        result = subprocess.run(
            ['tmux', 'display-message', '-t', window_id, '-p', '#{session_name}'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            session_name = result.stdout.strip()

            # Count windows in session
            windows_result = subprocess.run(
                ['tmux', 'list-windows', '-t', session_name, '-F', '#{window_id}'],
                capture_output=True,
                text=True,
                check=False
            )

            if windows_result.returncode == 0:
                windows = windows_result.stdout.strip().split('\n')

                # If this is the last window, create a default window first
                if len(windows) == 1:
                    subprocess.run(
                        ['tmux', 'new-window', '-t', session_name, '-n', 'main'],
                        check=False,
                        stderr=subprocess.DEVNULL
                    )

        # Now safe to kill the agent window
        result = subprocess.run(
            ['tmux', 'kill-window', '-t', window_id],
            check=False,
            stderr=subprocess.DEVNULL
        )

        return result.returncode == 0

    except Exception:
        return False


def cleanup_ephemeral_workspace(agent: dict) -> bool:
    """
    Delete workspace directory if the skill doesn't use it as a deliverable.

    Investigation skill creates workspace for SPAWN_CONTEXT.md but the deliverable
    is the investigation file, not the workspace. Delete to prevent accumulation.

    Args:
        agent: Agent record from registry

    Returns:
        True if deleted, False if kept or error
    """
    import shutil

    # Skills where workspace is ephemeral (not a deliverable)
    EPHEMERAL_WORKSPACE_SKILLS = {'investigation'}

    skill_name = agent.get('skill') or agent.get('skill_name', '')
    if skill_name not in EPHEMERAL_WORKSPACE_SKILLS:
        return False

    workspace = agent.get('workspace')
    project_dir = agent.get('project_dir')

    if not workspace or not project_dir:
        return False

    workspace_path = Path(project_dir) / workspace

    if not workspace_path.exists():
        return False

    try:
        shutil.rmtree(workspace_path)
        return True
    except Exception:
        # Don't fail completion if workspace cleanup fails
        return False


def mark_agent_completed(agent: dict, registry) -> None:
    """Mark agent as completed in registry and cleanup ephemeral workspace."""
    now = datetime.now().isoformat()
    agent['status'] = 'completed'
    agent['updated_at'] = now  # For timestamp-based merge conflict resolution
    if 'completion' not in agent:
        agent['completion'] = {}
    agent['completion']['completed_at'] = now

    # Clean up ephemeral workspace before saving
    if cleanup_ephemeral_workspace(agent):
        agent['completion']['workspace_cleaned'] = True

    registry.save()


def cleanup_agent_async(agent_id: str, registry_path: Path) -> bool:
    """
    Attempt async cleanup of agent with timeout cascade.

    Timeout cascade:
    1. Graceful shutdown (Ctrl+C, 30s)
    2. /exit command (30s)
    3. Force kill window (5s)
    4. Mark as failed if all fail

    Args:
        agent_id: Agent identifier
        registry_path: Path to agent registry file

    Returns:
        True if successful, False if failed
    """
    # Import here to avoid circular dependencies
    from orch.registry import AgentRegistry

    registry = AgentRegistry(registry_path)
    agent = registry.find(agent_id)

    if not agent:
        # Agent not found - nothing to clean up
        return False

    window_id = agent.get('window_id')
    if not window_id:
        # No window to clean up - mark as completed
        mark_agent_completed(agent, registry)
        return True

    # Strategy 1: Graceful shutdown (Ctrl+C, 30s)
    if graceful_shutdown_window(window_id, wait_seconds=30):
        mark_agent_completed(agent, registry)
        return True

    # Strategy 2: Try /exit command (30s)
    if send_exit_command(window_id, wait_seconds=30):
        mark_agent_completed(agent, registry)
        return True

    # Strategy 3: Force kill window
    if force_kill_window(window_id):
        mark_agent_completed(agent, registry)
        return True

    # All strategies failed - mark as failed
    now = datetime.now().isoformat()
    agent['status'] = 'failed'
    agent['updated_at'] = now  # For timestamp-based merge conflict resolution
    if 'completion' not in agent:
        agent['completion'] = {}
    agent['completion']['completed_at'] = now
    agent['completion']['error'] = 'Cleanup failed after all strategies (graceful, /exit, force kill)'
    registry.save()
    return False


def main():
    """Main entry point for cleanup daemon."""
    if len(sys.argv) != 3:
        print("Usage: cleanup_daemon.py <agent_id> <registry_path>", file=sys.stderr)
        sys.exit(2)

    agent_id = sys.argv[1]
    registry_path = Path(sys.argv[2])

    # Perform cleanup
    success = cleanup_agent_async(agent_id, registry_path)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
