"""
Complete command functionality for orch tool.

Handles:
- Verification checklist
- Beads issue auto-close (for agents spawned from beads issues)
- Investigation recommendation surfacing
- Git stash restoration
- Agent cleanup

Architecture: This module orchestrates completion workflow, delegating to:
- orch.verification: Agent work verification
- orch.beads_integration: Work tracking via beads
- orch.tmux_utils: Process management
"""

from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime
import re
import click

# Import verification functions - exposed here for backward compatibility
from orch.verification import (
    VerificationResult,
    verify_agent_work,
    _get_skill_deliverables,
    _check_deliverable_exists,
    _has_commits_in_workspace,
    _verify_investigation_artifact,
    _extract_investigation_phase,
    _extract_section,
)
# Import process management functions - exposed here for backward compatibility
from orch.tmux_utils import (
    has_active_processes,
    graceful_shutdown_window,
)
# Import git operations - exposed here for backward compatibility
from orch.git_utils import validate_work_committed

# Import beads integration for auto-close on complete
from orch.beads_integration import (
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)

import subprocess
import shutil


# ============================================================================
# CROSS-REPO WORKSPACE SYNC
# ============================================================================

def sync_workspace_to_origin(
    workspace_name: str,
    project_dir: Path,
    origin_dir: Path | None
) -> bool:
    """
    Sync workspace from project_dir to origin_dir for cross-repo spawns.

    When an agent is spawned with --project (cross-repo spawn), the workspace
    is created in the target repo. This function copies it back to the origin
    repo so the orchestrator has visibility into agent progress.

    Args:
        workspace_name: Name of the workspace directory
        project_dir: Where the agent worked (target repo)
        origin_dir: Where spawn was invoked from (origin repo)

    Returns:
        True if sync succeeded or was not needed, False on failure
    """
    # No-op if origin_dir is None (same-repo spawn)
    if origin_dir is None:
        return True

    # Normalize paths
    project_dir = Path(project_dir).resolve()
    origin_dir = Path(origin_dir).resolve()

    # No-op if same directory (same-repo spawn)
    if project_dir == origin_dir:
        return True

    # Source workspace in project_dir
    source_workspace = project_dir / ".orch" / "workspace" / workspace_name
    if not source_workspace.exists():
        click.echo(f"⚠️  Cross-repo sync: Source workspace not found: {source_workspace}", err=True)
        return False

    # Destination in origin_dir
    dest_workspace_parent = origin_dir / ".orch" / "workspace"
    dest_workspace = dest_workspace_parent / workspace_name

    try:
        # Create destination directory structure if needed
        dest_workspace_parent.mkdir(parents=True, exist_ok=True)

        # Copy workspace files (WORKSPACE.md, SPAWN_CONTEXT.md, etc.)
        if dest_workspace.exists():
            shutil.rmtree(dest_workspace)
        shutil.copytree(source_workspace, dest_workspace)

        # Check if origin_dir is a git repo
        git_check = subprocess.run(
            ['git', '-C', str(origin_dir), 'rev-parse', '--git-dir'],
            capture_output=True, text=True
        )
        if git_check.returncode != 0:
            # Not a git repo - just copy files
            click.echo(f"✓ Cross-repo workspace synced to {dest_workspace}")
            return True

        # Stage and commit the synced workspace in origin repo
        subprocess.run(
            ['git', '-C', str(origin_dir), 'add', str(dest_workspace)],
            check=True, capture_output=True
        )

        # Check if there are changes to commit
        status_result = subprocess.run(
            ['git', '-C', str(origin_dir), 'status', '--porcelain', str(dest_workspace)],
            capture_output=True, text=True
        )
        if status_result.stdout.strip():
            # There are changes to commit
            commit_msg = f"chore: sync cross-repo workspace {workspace_name}"
            subprocess.run(
                ['git', '-C', str(origin_dir), 'commit', '-m', commit_msg],
                check=True, capture_output=True
            )
            click.echo(f"✓ Cross-repo workspace synced and committed to {origin_dir}")
        else:
            click.echo(f"✓ Cross-repo workspace synced to {origin_dir} (no changes)")

        return True

    except subprocess.CalledProcessError as e:
        click.echo(f"⚠️  Cross-repo sync git error: {e.stderr.decode() if e.stderr else str(e)}", err=True)
        return False
    except Exception as e:
        click.echo(f"⚠️  Cross-repo sync error: {e}", err=True)
        return False


# ============================================================================
# INVESTIGATION BACKLINK AUTOMATION
# ============================================================================

def is_investigation_ref(context_ref: str | None) -> bool:
    """
    Check if a context_ref points to an investigation file.

    Args:
        context_ref: The context_ref value to check

    Returns:
        True if context_ref points to .orch/investigations/
    """
    if not context_ref:
        return False
    return ".orch/investigations/" in context_ref


def check_investigation_backlink(
    context_ref: str | None,
    project_dir: Path
) -> dict[str, Any] | None:
    """
    Check if completing this feature makes all features from an investigation complete.

    This is called when completing a feature with a context_ref pointing to an
    investigation. It checks if all other features referencing the same
    investigation are also complete.

    Args:
        context_ref: The context_ref of the completed feature
        project_dir: Project directory

    Returns:
        Dict with investigation info if all features are complete, None otherwise
        Dict contains:
        - all_complete: True
        - investigation_path: path to investigation file
        - feature_count: number of features referencing this investigation
    """
    # Features system removed - roadmap clearing now managed by beads
    return None


# ============================================================================
# INVESTIGATION RECOMMENDATION SURFACING
# ============================================================================

# Skills that produce investigation documents with recommendations
INVESTIGATION_SKILLS = {'investigation', 'codebase-audit', 'architect', 'systematic-debugging'}


def extract_recommendations_section(investigation_path: Path) -> str | None:
    """
    Extract Recommendations section from investigation file.

    Looks for sections with headers:
    - ## Recommendations
    - ## Next Steps
    - ## Implementation Recommendations

    Args:
        investigation_path: Path to investigation markdown file

    Returns:
        Section content as string, or None if not found or file missing
    """
    if not investigation_path.exists():
        return None

    try:
        content = investigation_path.read_text()
    except Exception:
        return None

    # Look for ## Recommendations, ## Next Steps, or ## Implementation Recommendations
    # Extract content until next ## header or end of file
    patterns = [
        r'## Recommendations\n(.*?)(?=\n## |\Z)',
        r'## Next Steps\n(.*?)(?=\n## |\Z)',
        r'## Implementation Recommendations\n(.*?)(?=\n## |\Z)',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def find_investigation_file(
    workspace_name: str,
    project_dir: Path
) -> Path | None:
    """
    Find investigation file for a workspace.

    Searches in:
    - .orch/investigations/simple/
    - .orch/investigations/design/

    Looks for files matching workspace name (workspace name typically matches
    investigation file name without .md extension).

    Args:
        workspace_name: Name of the workspace (e.g., "2025-11-29-test-feature")
        project_dir: Project directory

    Returns:
        Path to investigation file, or None if not found
    """
    investigations_dir = project_dir / ".orch" / "investigations"

    if not investigations_dir.exists():
        return None

    # Search in subdirectories: simple, design, etc.
    for subdir in investigations_dir.iterdir():
        if not subdir.is_dir():
            continue

        # Look for exact match first
        exact_match = subdir / f"{workspace_name}.md"
        if exact_match.exists():
            return exact_match

    return None


def surface_investigation_recommendations(
    agent: dict[str, Any],
    project_dir: Path
) -> dict[str, Any] | None:
    """
    Surface recommendations from investigation if applicable.

    Called during agent completion to extract and display recommendations
    from investigation files for investigation-category skills.

    Args:
        agent: Agent info dictionary (must have 'skill' and 'workspace' keys)
        project_dir: Project directory

    Returns:
        Dict with recommendations info, or None if not applicable
    """
    skill = agent.get('skill')

    # Only surface for investigation-category skills
    if skill not in INVESTIGATION_SKILLS:
        return None

    # Try primary_artifact first (most reliable - exact path from spawn)
    inv_path = None
    primary_artifact = agent.get('primary_artifact')
    if primary_artifact:
        # primary_artifact is absolute path
        inv_path = Path(primary_artifact).expanduser()
        if not inv_path.is_absolute():
            # Handle relative paths (unlikely but defensive)
            inv_path = (project_dir / inv_path).resolve()

        # Verify file exists
        if not inv_path.exists():
            inv_path = None

    # Fall back to name-based matching if primary_artifact not available or doesn't exist
    if not inv_path:
        workspace_rel = agent.get('workspace', '')
        workspace_name = Path(workspace_rel).name
        inv_path = find_investigation_file(workspace_name, project_dir)

    # Second fallback: search by date and task keywords
    if not inv_path:
        # Extract date from workspace name (e.g., "2025-11-29-inv-quick-test-...")
        workspace_rel = agent.get('workspace', '')
        workspace_name = Path(workspace_rel).name
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', workspace_name)
        if date_match:
            date_prefix = date_match.group(1)
            # Search investigations for files with same date
            investigations_dir = project_dir / ".orch" / "investigations"
            if investigations_dir.exists():
                for subdir in investigations_dir.iterdir():
                    if not subdir.is_dir():
                        continue
                    for f in subdir.glob(f"{date_prefix}*.md"):
                        # Check if file contains task-related keywords
                        # Use the most recently modified file matching the date
                        if inv_path is None or f.stat().st_mtime > inv_path.stat().st_mtime:
                            inv_path = f

    if not inv_path:
        return None

    # Extract recommendations
    recommendations = extract_recommendations_section(inv_path)
    if not recommendations:
        return None

    return {
        'investigation_path': str(inv_path),
        'recommendations': recommendations
    }


# NOTE: Verification functions moved to orch.verification module
# Imported above for backward compatibility with existing callers

# NOTE: Process management functions (has_active_processes, graceful_shutdown_window)
# moved to orch.tmux_utils module - imported above for backward compatibility


def get_agent_by_id(agent_id: str) -> dict[str, Any] | None:
    """
    Get agent from registry by ID.

    Args:
        agent_id: Agent identifier

    Returns:
        Agent dict or None if not found
    """
    from orch.registry import AgentRegistry

    registry = AgentRegistry()
    return registry.find(agent_id)


def clean_up_agent(agent_id: str, force: bool = False) -> None:
    """
    Clean up agent: mark as completed and close tmux window.

    Args:
        agent_id: Agent identifier
        force: Bypass safety checks (active processes) - use when work complete but session hung
    """
    from orch.registry import AgentRegistry
    from orch.tmux_utils import get_window_by_id, list_windows
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
            # Attempt graceful shutdown (Ctrl+C, wait 5 seconds)
            if not graceful_shutdown_window(window_id):
                # Graceful shutdown failed, processes still active
                if not force:
                    raise RuntimeError(
                        f"Agent {agent_id} has active processes that did not terminate after graceful shutdown. "
                        f"Cannot safely kill window {window_id} while processes are active. "
                        f"Wait for processes to complete or investigate why agent has not finished cleanly.\n\n"
                        f"💡 Tip: Try 'orch send {agent_id} \"/exit\"' to gracefully exit Claude Code before forcing completion."
                    )
                else:
                    # Force mode: proceed with kill despite active processes
                    print(f"⚠️  Warning: Force mode enabled, killing window {window_id} despite active processes")

        try:
            # Get session name from window
            # First, try to get the window to determine session
            result = subprocess.run(
                ['tmux', 'display-message', '-t', window_id, '-p', '#{session_name}'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                session_name = result.stdout.strip()

                # Count windows in session
                windows = list_windows(session_name)

                # If this is the last window, create a default window first
                if len(windows) == 1:
                    subprocess.run(
                        ['tmux', 'new-window', '-t', session_name, '-n', 'main'],
                        check=False,
                        stderr=subprocess.DEVNULL
                    )

            # Now safe to kill the agent window
            subprocess.run(['tmux', 'kill-window', '-t', window_id],
                         check=False,
                         stderr=subprocess.DEVNULL)
        except Exception:
            pass


def complete_agent_async(
    agent_id: str,
    project_dir: Path,
    registry_path: Path | None = None,
    skip_test_check: bool = False
) -> dict[str, Any]:
    """
    Start async agent completion: verify, spawn background daemon.

    This function returns immediately after spawning the cleanup daemon.
    The actual cleanup (window killing, etc.) happens in the background.

    Args:
        agent_id: Agent identifier (workspace name)
        project_dir: Project directory
        registry_path: Optional path to registry (for testing)
        skip_test_check: Skip test verification check

    Returns:
        Dictionary with:
        - success: bool (always True if daemon spawned)
        - async_mode: True
        - daemon_pid: int (PID of background daemon)
    """
    import subprocess
    import os
    from orch.logging import OrchLogger

    logger = OrchLogger()
    result: dict[str, Any] = {
        'success': False,
        'async_mode': True,
        'daemon_pid': None,
        'errors': [],
        'warnings': []
    }

    # Mark agent as 'completing'
    from orch.registry import AgentRegistry
    actual_registry_path: Path
    if registry_path is None:
        actual_registry_path = Path.home() / '.orch' / 'agent-registry.json'
    else:
        actual_registry_path = registry_path

    registry = AgentRegistry(actual_registry_path)
    agent = registry.find(agent_id)

    if not agent:
        result['errors'].append(f"Agent '{agent_id}' not found in registry")
        return result

    # Step 1: Verify agent work BEFORE closing beads issue
    # This prevents closing issues when work wasn't actually done
    workspace_rel = agent['workspace']  # e.g., ".orch/workspace/test-workspace"
    workspace_dir = project_dir / workspace_rel

    verification = verify_agent_work(workspace_dir, project_dir, agent_info=agent, skip_test_check=skip_test_check)
    result['verified'] = verification.passed

    if not verification.passed:
        result['errors'].extend(verification.errors)
        result['warnings'].extend(verification.warnings)
        click.echo("❌ Verification failed:", err=True)
        for error in verification.errors:
            click.echo(f"   • {error}", err=True)
        logger.log_event("complete", "Async verification failed", {
            "agent_id": agent_id,
            "errors": verification.errors
        })
        return result

    now = datetime.now().isoformat()
    agent['status'] = 'completing'
    agent['updated_at'] = now  # For timestamp-based merge conflict resolution
    agent['completion'] = {
        'mode': 'async',
        'daemon_pid': None,  # Will be set after spawn
        'started_at': now,
        'completed_at': None,
        'error': None
    }
    registry.save()

    # Auto-unstash git changes if stashed during spawn (do this before daemon)
    if agent.get('stashed'):
        from orch.spawn import git_stash_pop
        project_dir = Path(agent.get('project_dir', '.'))
        click.echo("📦 Restoring stashed git changes...")
        if git_stash_pop(project_dir):
            click.echo("✓ Stashed changes restored")
            result['stash_restored'] = True
            logger.log_event("complete", "Stashed changes restored", {
                "agent_id": agent_id
            })
        else:
            result['warnings'].append("Failed to restore stashed changes - check git stash list")
            logger.log_event("complete", "Failed to restore stash", {
                "agent_id": agent_id
            })

    # Close beads issue if agent was spawned from beads issue
    # Must happen BEFORE daemon spawn - click.echo() in daemon goes nowhere
    # Note: Verification already passed above, so we can safely close the issue
    if agent.get('beads_id'):
        beads_id = agent['beads_id']
        try:
            if close_beads_issue(beads_id):
                result['beads_closed'] = True
                click.echo(f"🎯 Beads issue '{beads_id}' closed")
                logger.log_event("complete", "Beads issue closed", {
                    "beads_id": beads_id,
                    "agent_id": agent_id
                })
            else:
                result['warnings'].append(f"Failed to close beads issue '{beads_id}'")
                logger.log_event("complete", "Beads issue close failed", {
                    "beads_id": beads_id,
                    "agent_id": agent_id
                })
        except BeadsPhaseNotCompleteError as e:
            # Agent hasn't reported Phase: Complete via beads comment
            result['errors'].append(str(e))
            click.echo(f"⚠️  {e}", err=True)
            click.echo(f"   Agent must run: bd comment {beads_id} \"Phase: Complete - <summary>\"", err=True)
            logger.log_event("complete", "Beads phase not complete", {
                "beads_id": beads_id,
                "agent_id": agent_id,
                "current_phase": e.current_phase
            })

    # Surface investigation recommendations (if applicable)
    # Must happen BEFORE daemon spawn - click.echo() in daemon goes nowhere
    rec_info = surface_investigation_recommendations(agent, project_dir)
    if rec_info:
        result['recommendations'] = rec_info
        click.echo("\n📋 Recommendations from investigation:")
        click.echo(rec_info['recommendations'])
        click.echo(f"\nConsider: `orch backlog add \"description\" --type feature`")
        logger.log_event("complete", "Investigation recommendations surfaced", {
            "agent_id": agent_id,
            "investigation_path": rec_info['investigation_path']
        })

    # Spawn background daemon
    daemon_script = Path(__file__).parent / 'cleanup_daemon.py'

    try:
        # Spawn detached process
        process = subprocess.Popen(
            [
                'python3',
                str(daemon_script),
                agent_id,
                str(actual_registry_path)
            ],
            start_new_session=True,  # Detach from parent
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        # Update registry with daemon PID
        agent['completion']['daemon_pid'] = process.pid
        agent['updated_at'] = datetime.now().isoformat()  # For timestamp-based merge
        registry.save()

        result['success'] = True
        result['daemon_pid'] = process.pid

        logger.log_event("complete", "Async cleanup started", {
            "agent_id": agent_id,
            "daemon_pid": process.pid
        })

    except Exception as e:
        # Failed to spawn daemon
        agent['status'] = 'failed'
        agent['updated_at'] = datetime.now().isoformat()  # For timestamp-based merge
        agent['completion']['error'] = f"Failed to spawn cleanup daemon: {str(e)}"
        registry.save()

        result['errors'].append(f"Failed to spawn cleanup daemon: {str(e)}")

        logger.log_event("complete", "Async cleanup spawn failed", {
            "agent_id": agent_id,
            "error": str(e)
        })

    return result


def complete_agent_work(
    agent_id: str,
    project_dir: Path,
    dry_run: bool = False,
    skip_test_check: bool = False,
    force: bool = False
) -> dict[str, Any]:
    """
    Complete agent work: verify, close beads issue, cleanup.

    This is the main orchestration function that ties everything together.

    Args:
        agent_id: Agent identifier (workspace name)
        project_dir: Project directory
        dry_run: Show what would happen without executing
        skip_test_check: Skip test verification check (use when pre-existing test failures block completion)
        force: Bypass safety checks (active processes, git state) - use when work complete but session hung

    Returns:
        Dictionary with:
        - success: bool (overall success)
        - verified: bool (verification passed)
        - beads_closed: bool (beads issue closed)
        - errors: List[str] (any errors encountered)
        - warnings: List[str] (any warnings)
    """
    from orch.logging import OrchLogger

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

    # Extract workspace path from agent
    workspace_rel = agent['workspace']  # e.g., ".orch/workspace/test-workspace"
    workspace_dir = project_dir / workspace_rel

    # Step 1: Verify agent work
    verification = verify_agent_work(workspace_dir, project_dir, agent_info=agent, skip_test_check=skip_test_check)
    result['verified'] = verification.passed

    if not verification.passed:
        result['errors'].extend(verification.errors)
        return result

    # Step 1.5: Validate work is committed and pushed (main-branch workflow)
    # Define orchestrator working files to exclude from validation
    # These files are frequently modified by the orchestrator during sessions
    # and shouldn't block agent completion.
    orchestrator_files = [
        '.orch/workspace/coordination/WORKSPACE.md',
        '.orch/CLAUDE.md'
    ]

    is_valid, warning_message = validate_work_committed(project_dir, exclude_files=orchestrator_files)
    if not is_valid:
        # Block completion - uncommitted changes must be resolved
        result['errors'].append(f"Git validation error:\n{warning_message}")
        return result

    # Step 2: Dry-run check - exit before making changes
    if dry_run:
        logger.log_event("complete", "Dry-run mode - would complete successfully", {
            "agent_id": agent_id
        })
        result['success'] = True
        return result

    # Step 3: Close beads issue if agent was spawned from beads issue
    if agent.get('beads_id'):
        beads_id = agent['beads_id']
        try:
            if close_beads_issue(beads_id):
                result['beads_closed'] = True
                click.echo(f"🎯 Beads issue '{beads_id}' closed")
                logger.log_event("complete", "Beads issue closed", {
                    "beads_id": beads_id,
                    "agent_id": agent_id
                })
            else:
                result['warnings'].append(f"Failed to close beads issue '{beads_id}'")
                logger.log_event("complete", "Beads issue close failed", {
                    "beads_id": beads_id,
                    "agent_id": agent_id
                })
        except BeadsPhaseNotCompleteError as e:
            # Agent hasn't reported Phase: Complete via beads comment
            result['errors'].append(str(e))
            click.echo(f"⚠️  {e}", err=True)
            click.echo(f"   Agent must run: bd comment {beads_id} \"Phase: Complete - <summary>\"", err=True)
            logger.log_event("complete", "Beads phase not complete", {
                "beads_id": beads_id,
                "agent_id": agent_id,
                "current_phase": e.current_phase
            })

    # Step 4: Auto-unstash git changes if stashed during spawn
    if agent.get('stashed'):
        from orch.spawn import git_stash_pop
        click.echo("📦 Restoring stashed git changes...")
        if git_stash_pop(project_dir):
            click.echo("✓ Stashed changes restored")
            result['stash_restored'] = True
            logger.log_event("complete", "Stashed changes restored", {
                "agent_id": agent_id
            })
        else:
            result['warnings'].append("Failed to restore stashed changes - check git stash list")
            logger.log_event("complete", "Failed to restore stash", {
                "agent_id": agent_id
            })

    # Step 4.5: Surface investigation recommendations (if applicable)
    rec_info = surface_investigation_recommendations(agent, project_dir)
    if rec_info:
        result['recommendations'] = rec_info
        click.echo("\n📋 Recommendations from investigation:")
        click.echo(rec_info['recommendations'])
        click.echo(f"\nConsider: `orch backlog add \"description\" --type feature`")
        logger.log_event("complete", "Investigation recommendations surfaced", {
            "agent_id": agent_id,
            "investigation_path": rec_info['investigation_path']
        })

    # Step 4.6: Sync workspace to origin repo for cross-repo spawns
    if agent.get('origin_dir'):
        workspace_name = Path(agent['workspace']).name
        origin_dir = Path(agent['origin_dir'])
        agent_project_dir = Path(agent['project_dir'])
        if sync_workspace_to_origin(workspace_name, agent_project_dir, origin_dir):
            result['cross_repo_synced'] = True
            logger.log_event("complete", "Cross-repo workspace synced", {
                "agent_id": agent_id,
                "workspace_name": workspace_name,
                "origin_dir": str(origin_dir)
            })
        else:
            result['warnings'].append("Failed to sync workspace to origin repo")
            logger.log_event("complete", "Cross-repo sync failed", {
                "agent_id": agent_id,
                "origin_dir": str(origin_dir)
            })

    # Step 5: Clean up agent
    clean_up_agent(agent_id, force=force)
    logger.log_event("complete", "Agent cleaned up", {
        "agent_id": agent_id
    })

    # Overall success
    result['success'] = True
    return result


# ============================================================================
# DISCOVERY CAPTURE (VC PATTERN ADOPTION)
# ============================================================================
# Reference: .orch/investigations/systems/2025-11-29-vc-vs-orch-philosophical-comparison.md
# Patterns adopted: Post-completion analysis + Discovery linking

def prompt_for_discoveries() -> List[str]:
    """
    Interactive prompt for discovered/punted work items.

    Prompts user to enter work items discovered during agent execution
    that should be tracked for future work.

    Returns:
        List of item descriptions (empty if user skips)
    """
    items = []

    click.echo("\n📋 Discovered/punted work capture")
    click.echo("   Enter items discovered during this work (empty line to finish):")

    while True:
        try:
            item = click.prompt("   Item", default='', show_default=False)
            if not item.strip():
                break
            items.append(item.strip())
        except click.Abort:
            break

    return items


def create_beads_issue(
    title: str,
    discovered_from: str | None = None
) -> str | None:
    """
    Create a beads issue via bd CLI.

    Args:
        title: Issue title/description
        discovered_from: Parent issue ID to link with --discovered-from

    Returns:
        Created issue ID (e.g., 'orch-cli-abc') or None on failure
    """
    import subprocess

    cmd = ['bd', 'create', title, '--type', 'task']

    if discovered_from:
        cmd.extend(['--discovered-from', discovered_from])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            click.echo(f"   ⚠️  Failed to create issue: {result.stderr.strip()}", err=True)
            return None

        # Parse issue ID from output (format: "Created: orch-cli-abc")
        output = result.stdout.strip()
        if 'Created:' in output:
            # Extract ID after "Created: "
            parts = output.split('Created:')
            if len(parts) > 1:
                return parts[1].strip().split()[0]

        # Fallback: return first word that looks like an issue ID
        for word in output.split():
            if '-' in word and len(word) > 3:
                return word

        return output.split()[0] if output else None

    except subprocess.TimeoutExpired:
        click.echo("   ⚠️  bd create timed out", err=True)
        return None
    except Exception as e:
        click.echo(f"   ⚠️  Error creating issue: {e}", err=True)
        return None


def get_discovery_parent_id(agent: Dict[str, Any]) -> str | None:
    """
    Extract parent beads ID from agent if available.

    Checks agent metadata for beads_id field (set when spawned from beads issue).

    Args:
        agent: Agent info dictionary

    Returns:
        Parent beads issue ID or None
    """
    return agent.get('beads_id')


def process_discoveries(
    items: List[str],
    discovered_from: str | None = None
) -> List[Dict[str, Any]]:
    """
    Process all discovered items and create beads issues.

    Args:
        items: List of item descriptions
        discovered_from: Parent issue ID for --discovered-from links

    Returns:
        List of result dicts with 'item', 'issue_id', and optionally 'error'
    """
    results = []

    for item in items:
        issue_id = create_beads_issue(title=item, discovered_from=discovered_from)

        result = {
            'item': item,
            'issue_id': issue_id
        }

        if issue_id is None:
            result['error'] = 'Failed to create issue'

        results.append(result)

    return results


def format_discovery_summary(results: List[Dict[str, Any]]) -> str:
    """
    Format summary of created discovery issues.

    Args:
        results: List of result dicts from process_discoveries

    Returns:
        Formatted summary string
    """
    lines = ["\n📋 Discovery Summary:"]

    successful = [r for r in results if r.get('issue_id')]
    failed = [r for r in results if not r.get('issue_id')]

    if successful:
        lines.append(f"\n   Created {len(successful)} issue(s):")
        for r in successful:
            lines.append(f"   ✓ {r['issue_id']}: {r['item'][:50]}...")

    if failed:
        lines.append(f"\n   ⚠️  {len(failed)} item(s) failed:")
        for r in failed:
            lines.append(f"   ✗ {r['item'][:50]}... - {r.get('error', 'Unknown error')}")

    return '\n'.join(lines)


# ============================================================================
# BEADS AUTO-CLOSE ON COMPLETE
# ============================================================================
# When agent was spawned from beads issue (beads_id in metadata),
# automatically close the issue on successful completion.

class BeadsPhaseNotCompleteError(Exception):
    """Raised when trying to close a beads issue without Phase: Complete comment."""

    def __init__(self, beads_id: str, current_phase: str):
        self.beads_id = beads_id
        self.current_phase = current_phase
        super().__init__(
            f"Beads issue '{beads_id}' cannot be closed: "
            f"agent has not reported 'Phase: Complete' (current phase: {current_phase or 'none'})"
        )


def close_beads_issue(beads_id: str, verify_phase: bool = True) -> bool:
    """
    Close a beads issue via BeadsIntegration.

    Called during agent completion when agent has beads_id metadata
    (set when spawned from beads issue via `orch spawn --issue`).

    Phase 3: By default, verifies that agent has reported "Phase: Complete"
    via beads comments before closing. This ensures agents explicitly
    report completion rather than relying on workspace files.

    Args:
        beads_id: The beads issue ID to close (e.g., 'orch-cli-xyz')
        verify_phase: If True, verify "Phase: Complete" exists in comments
                     before closing. Set to False for backwards compat.

    Returns:
        True if issue was closed successfully, False on failure

    Raises:
        BeadsPhaseNotCompleteError: If verify_phase=True and no "Phase: Complete"
                                   comment exists (raised so caller can handle)
    """
    try:
        beads = BeadsIntegration()

        # Phase 3: Verify agent reported completion before closing
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
        raise  # Re-raise so caller can handle
    except Exception:
        return False
