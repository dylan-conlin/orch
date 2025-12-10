"""
Complete command functionality for orch tool.

Simplified version: thin wrapper around beads verification and close.

Handles:
- Verify Phase: Complete in beads comments
- Close beads issue via bd CLI
- Clean up tmux window
"""

from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import click

# Import beads integration for auto-close on complete
from orch.beads_integration import (
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)

# Import tmux utilities for window cleanup
from orch.tmux_utils import (
    has_active_processes,
    graceful_shutdown_window,
    list_windows,
)

# Re-export verification for backward compatibility
from orch.verification import (
    VerificationResult,
    verify_agent_work,
)


def send_exit_command(window_id: str, timeout_seconds: int = 5) -> bool:
    """
    Send /exit command to a tmux window and wait for processes to terminate.

    Args:
        window_id: Tmux window ID (e.g., '@123')
        timeout_seconds: How long to wait for processes to terminate (default: 5)

    Returns:
        True if processes terminated after /exit, False if still running
    """
    import subprocess
    import time

    try:
        # Send /exit command
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_id, '/exit'],
            check=False,
            stderr=subprocess.DEVNULL
        )

        # Wait a moment for message to be pasted
        time.sleep(0.5)

        # Send Enter to execute the command
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_id, 'Enter'],
            check=False,
            stderr=subprocess.DEVNULL
        )

        # Wait for processes to terminate
        time.sleep(timeout_seconds)

        # Check if processes are gone
        return not has_active_processes(window_id)

    except Exception:
        return False


class BeadsPhaseNotCompleteError(Exception):
    """Raised when trying to close a beads issue without Phase: Complete comment."""

    def __init__(self, beads_id: str, current_phase: str):
        self.beads_id = beads_id
        self.current_phase = current_phase
        super().__init__(
            f"Beads issue '{beads_id}' cannot be closed: "
            f"agent has not reported 'Phase: Complete' (current phase: {current_phase or 'none'})"
        )


def close_beads_issue(beads_id: str, verify_phase: bool = True, db_path: Optional[str] = None) -> bool:
    """
    Close a beads issue via BeadsIntegration.

    By default, verifies that agent has reported "Phase: Complete"
    via beads comments before closing.

    Args:
        beads_id: The beads issue ID to close (e.g., 'orch-cli-xyz')
        verify_phase: If True, verify "Phase: Complete" exists in comments
        db_path: Optional path to beads database (for cross-repo access)

    Returns:
        True if issue was closed successfully, False on failure

    Raises:
        BeadsPhaseNotCompleteError: If verify_phase=True and no "Phase: Complete"
    """
    try:
        beads = BeadsIntegration(db_path=db_path)

        if verify_phase:
            current_phase = beads.get_phase_from_comments(beads_id)
            if not current_phase or current_phase.lower() != "complete":
                raise BeadsPhaseNotCompleteError(beads_id, current_phase)

        beads.close_issue(beads_id, reason='Resolved via orch complete')
        return True
    except BeadsCLINotFoundError:
        return False
    except BeadsIssueNotFoundError:
        return False
    except BeadsPhaseNotCompleteError:
        raise


def get_agent_by_id(agent_id: str) -> dict[str, Any] | None:
    """Get agent from registry by ID."""
    from orch.registry import AgentRegistry
    registry = AgentRegistry()
    return registry.find(agent_id)


def clean_up_agent(agent_id: str, force: bool = False) -> None:
    """
    Clean up agent: mark as completed and close tmux window.

    Args:
        agent_id: Agent identifier
        force: Bypass safety checks (active processes)
    """
    from orch.registry import AgentRegistry
    import subprocess

    registry = AgentRegistry()
    agent = registry.find(agent_id)

    if not agent:
        return

    # Mark as completed
    agent['status'] = 'completed'
    agent['completed_at'] = datetime.now().isoformat()
    registry.save()

    # Close tmux window if exists
    window_id = agent.get('window_id')
    if window_id:
        # Check for active processes and attempt graceful shutdown
        if has_active_processes(window_id):
            if not graceful_shutdown_window(window_id):
                # Graceful shutdown (Ctrl+C) didn't work, try /exit command
                click.echo(f"⏳ Sending /exit to agent {agent_id}...")
                if not send_exit_command(window_id):
                    # /exit also didn't work
                    if not force:
                        raise RuntimeError(
                            f"Agent {agent_id} has active processes that did not terminate. "
                            f"Cannot safely kill window {window_id}. "
                            f"Tried /exit but processes still running."
                        )

        try:
            # Get session name from window
            result = subprocess.run(
                ['tmux', 'display-message', '-t', window_id, '-p', '#{session_name}'],
                capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                session_name = result.stdout.strip()
                windows = list_windows(session_name)

                # If this is the last window, create a default window first
                if len(windows) == 1:
                    subprocess.run(
                        ['tmux', 'new-window', '-t', session_name, '-n', 'main'],
                        check=False, stderr=subprocess.DEVNULL
                    )

            # Kill the agent window
            subprocess.run(
                ['tmux', 'kill-window', '-t', window_id],
                check=False, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


def complete_agent_work(
    agent_id: str,
    project_dir: Path,
    dry_run: bool = False,
    skip_test_check: bool = False,
    force: bool = False
) -> dict[str, Any]:
    """
    Complete agent work: verify, close beads issue, cleanup.

    Simplified workflow:
    1. Get agent from registry
    2. Verify work (Phase: Complete check happens in close_beads_issue)
    3. Close beads issue if present
    4. Clean up agent and tmux window

    Args:
        agent_id: Agent identifier
        project_dir: Project directory
        dry_run: Show what would happen without executing
        skip_test_check: Skip test verification (unused, kept for API compat)
        force: Bypass safety checks

    Returns:
        Dictionary with success, verified, errors, warnings
    """
    from orch.logging import OrchLogger
    from orch.git_utils import validate_work_committed

    logger = OrchLogger()
    result: dict[str, Any] = {
        'success': False,
        'verified': False,
        'errors': [],
        'warnings': [],
        'dry_run': dry_run
    }

    logger.log_event("complete", "Starting agent completion", {
        "agent_id": agent_id,
        "project_dir": str(project_dir),
        "dry_run": dry_run
    })

    # Get agent from registry
    agent = get_agent_by_id(agent_id)
    if not agent:
        result['errors'].append(f"Agent '{agent_id}' not found in registry")
        return result

    # Verify agent work
    workspace_rel = agent['workspace']
    workspace_dir = project_dir / workspace_rel

    verification = verify_agent_work(
        workspace_dir, project_dir, agent_info=agent, skip_test_check=skip_test_check
    )
    result['verified'] = verification.passed

    if not verification.passed:
        result['errors'].extend(verification.errors)
        return result

    # Validate work is committed
    # Exclude .beads/ from validation - beads changes are committed separately by bd sync
    # This allows parallel orch complete commands without git validation conflicts
    is_valid, warning_message = validate_work_committed(project_dir, exclude_files=[".beads/"])
    if not is_valid:
        result['errors'].append(f"Git validation error:\n{warning_message}")
        return result

    # Dry-run exits before making changes
    if dry_run:
        result['success'] = True
        return result

    # Close beads issues if agent was spawned from one or more
    # Multi-issue spawns have beads_ids list, single-issue spawns have beads_id
    beads_ids_to_close = agent.get('beads_ids') or ([agent['beads_id']] if agent.get('beads_id') else [])
    beads_db_path = agent.get('beads_db_path')

    # Validate repo consistency for cross-repo beads operations
    # If agent was spawned with a beads_db_path (cross-repo), verify we're in the right project
    if beads_db_path and beads_ids_to_close:
        agent_project_dir = agent.get('project_dir')
        if agent_project_dir:
            agent_project = Path(agent_project_dir).resolve()
            current_project = project_dir.resolve()
            if agent_project != current_project:
                result['errors'].append(
                    f"Repo mismatch: agent was spawned in {agent_project} but orch complete "
                    f"was called in {current_project}. Cannot close cross-repo beads issue.\n"
                    f"Run orch complete from the correct project directory."
                )
                return result

    if beads_ids_to_close:
        closed_count = 0
        for beads_id in beads_ids_to_close:
            try:
                # When force=True, trust commits over phase status - skip phase verification
                # For multi-issue, only verify phase on primary issue (first one)
                verify = not force and (beads_id == beads_ids_to_close[0])
                if close_beads_issue(beads_id, verify_phase=verify, db_path=beads_db_path):
                    closed_count += 1
                    logger.log_event("complete", "Beads issue closed", {
                        "beads_id": beads_id, "agent_id": agent_id
                    })
                else:
                    result['warnings'].append(f"Failed to close beads issue '{beads_id}'")
            except BeadsPhaseNotCompleteError as e:
                result['errors'].append(str(e))
                click.echo(f"⚠️  {e}", err=True)
                click.echo(f"   Agent must run: bd comment {beads_id} \"Phase: Complete - <summary>\"", err=True)
                return result

        if closed_count > 0:
            result['beads_closed'] = True
            if len(beads_ids_to_close) == 1:
                click.echo(f"🎯 Beads issue '{beads_ids_to_close[0]}' closed")
            else:
                click.echo(f"🎯 Closed {closed_count} beads issues: {', '.join(beads_ids_to_close)}")

    # Clean up agent
    clean_up_agent(agent_id, force=force)
    logger.log_event("complete", "Agent cleaned up", {"agent_id": agent_id})

    result['success'] = True
    return result
