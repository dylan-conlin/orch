"""
Complete command functionality for orch tool.

Handles:
- Auto-detecting ROADMAP vs ad-hoc agents
- Finding ROADMAP items from workspace metadata (for ROADMAP agents)
- Marking ROADMAP items as DONE (for ROADMAP agents only)
- Verification checklist
- Git commits (for ROADMAP agents only)
- Agent cleanup (for both agent types)

Architecture: This module orchestrates completion workflow, delegating to:
- orch.verification: Agent work verification
- orch.roadmap_utils: ROADMAP operations
- orch.tmux_utils: Process management
- orch.git_utils: Git operations
"""

from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime
import re
import click

from orch.roadmap import RoadmapItem
from orch.roadmap_utils import (
    find_roadmap_item_for_workspace as roadmap_find_item_for_workspace,
    mark_roadmap_item_done as roadmap_mark_item_done,
)
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
from orch.git_utils import commit_roadmap_update

# Import features operations for backlink automation
from orch.features import (
    get_features_by_context_ref,
    all_features_complete_for_context_ref,
)

# Import beads integration for auto-close on complete
from orch.beads_integration import (
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)


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
    if not context_ref or not is_investigation_ref(context_ref):
        return None

    # Check if all features with this context_ref are complete
    if not all_features_complete_for_context_ref(context_ref, project_dir):
        return None

    # Get count of features
    features = get_features_by_context_ref(context_ref, project_dir)

    return {
        'all_complete': True,
        'investigation_path': context_ref,
        'feature_count': len(features)
    }


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


# Backward compatibility wrapper
def find_roadmap_item_for_workspace(
    workspace_name: str,
    roadmap_path: Path | None
) -> RoadmapItem | None:
    """
    Find ROADMAP item that matches workspace name.

    NOTE: This is a wrapper to orch.roadmap.find_roadmap_item_for_workspace
    for backward compatibility.
    """
    if roadmap_path is None:
        return None
    return roadmap_find_item_for_workspace(workspace_name, roadmap_path)


# Backward compatibility wrapper
def mark_roadmap_item_done(
    workspace_name: str,
    roadmap_path: Path | None
) -> None:
    """
    Mark ROADMAP item as DONE.

    NOTE: This is a wrapper to orch.roadmap.mark_roadmap_item_done
    for backward compatibility.
    """
    if roadmap_path is None:
        raise ValueError("Cannot mark ROADMAP item done: roadmap_path is None")
    success = roadmap_mark_item_done(
        roadmap_path=roadmap_path,
        workspace_name=workspace_name
    )
    if not success:
        raise ValueError(f"Workspace '{workspace_name}' not found in ROADMAP")


# NOTE: ROADMAP operations moved to orch.roadmap_utils module
# Backward compatibility wrappers above delegate to that module

# NOTE: Verification functions moved to orch.verification module
# Imported above for backward compatibility with existing callers

# NOTE: Process management functions (has_active_processes, graceful_shutdown_window)
# moved to orch.tmux_utils module - imported above for backward compatibility

# NOTE: Git operations (commit_roadmap_update) moved to orch.git_utils module
# Imported above for backward compatibility


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
    roadmap_path: Path | None,
    registry_path: Path | None = None
) -> dict[str, Any]:
    """
    Start async agent completion: verify, update ROADMAP, spawn background daemon.

    This function returns immediately after spawning the cleanup daemon.
    The actual cleanup (window killing, etc.) happens in the background.

    Args:
        agent_id: Agent identifier (workspace name)
        project_dir: Project directory
        roadmap_path: Path to ROADMAP.org file, or None for backlog.json-only projects
        registry_path: Optional path to registry (for testing)

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

    # Update feature status if feature_id present (do this before daemon)
    if agent.get('feature_id'):
        from orch.features import complete_feature, FeatureNotFoundError, FeaturesNotFoundError
        feature_id = agent['feature_id']
        try:
            complete_feature(feature_id, project_dir)
            result['feature_updated'] = True
            click.echo(f"📋 Feature '{feature_id}' marked complete")
            logger.log_event("complete", "Feature marked complete", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except FeaturesNotFoundError:
            result['warnings'].append(f"backlog.json not found - cannot update feature status")
            logger.log_event("complete", "Features file not found", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except FeatureNotFoundError:
            result['warnings'].append(f"Feature '{feature_id}' not found in backlog.json")
            logger.log_event("complete", "Feature not found", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except Exception as e:
            result['warnings'].append(f"Failed to update feature status: {e}")
            logger.log_event("complete", "Feature update failed", {
                "feature_id": feature_id,
                "agent_id": agent_id,
                "error": str(e)
            })

    # Close beads issue if agent was spawned from beads issue
    # Must happen BEFORE daemon spawn - click.echo() in daemon goes nowhere
    if agent.get('beads_id'):
        beads_id = agent['beads_id']
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
    roadmap_path: Path | None,
    allow_roadmap_miss: bool = False,
    dry_run: bool = False,
    skip_test_check: bool = False,
    force: bool = False
) -> dict[str, Any]:
    """
    Complete agent work: verify, update ROADMAP, commit, cleanup.

    This is the main orchestration function that ties everything together.

    Args:
        agent_id: Agent identifier (workspace name)
        project_dir: Project directory
        roadmap_path: Path to ROADMAP.org file, or None for backlog.json-only projects
        allow_roadmap_miss: Proceed with cleanup even if ROADMAP item not found
        dry_run: Show what would happen without executing
        skip_test_check: Skip test verification check (use when pre-existing test failures block completion)
        force: Bypass safety checks (active processes, git state) - use when work complete but session hung

    Returns:
        Dictionary with:
        - success: bool (overall success)
        - verified: bool (verification passed)
        - roadmap_updated: bool (ROADMAP marked DONE)
        - committed: bool (git commit successful)
        - errors: List[str] (any errors encountered)
        - warnings: List[str] (any warnings)
    """
    from orch.logging import OrchLogger

    logger = OrchLogger()
    result: dict[str, Any] = {
        'success': False,
        'verified': False,
        'roadmap_updated': False,
        'committed': False,
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
    from orch.git_utils import validate_work_committed
    
    # Define orchestrator working files to exclude from validation
    # These files are frequently modified by the orchestrator during sessions
    # and shouldn't block agent completion.
    orchestrator_files = [
        '.orch/ROADMAP.org',
        '.orch/workspace/coordination/WORKSPACE.md',
        '.orch/CLAUDE.md'
    ]
    
    is_valid, warning_message = validate_work_committed(project_dir, exclude_files=orchestrator_files)
    if not is_valid:
        # Block completion - uncommitted changes must be resolved
        result['errors'].append(f"Git validation error:\n{warning_message}")
        return result

    # Phase 4: Dry-run check - exit before making changes
    if dry_run:
        logger.log_event("complete", "Dry-run mode - would complete successfully", {
            "agent_id": agent_id
        })
        result['success'] = True
        return result

    # Step 2: Auto-detect ROADMAP vs ad-hoc agent
    workspace_name = workspace_dir.name  # Extract workspace name from path
    roadmap_item = find_roadmap_item_for_workspace(workspace_name, roadmap_path)

    if roadmap_item:
        # Check if item is already DONE before trying to mark it
        if roadmap_item.is_done:
            # Item already marked DONE - this is fine, just warn and proceed
            result['warnings'].append(f"ROADMAP item already marked DONE (closed: {roadmap_item.closed_date or 'unknown'})")
            result['roadmap_updated'] = False  # Already done, no update needed
            logger.log_event("complete", "ROADMAP item already DONE", {
                "workspace": workspace_name,
                "closed_date": roadmap_item.closed_date
            })
        else:
            # ROADMAP-based agent: Update ROADMAP
            try:
                mark_roadmap_item_done(workspace_name, roadmap_path)
                result['roadmap_updated'] = True
                logger.log_event("complete", "ROADMAP item marked DONE", {
                    "workspace": workspace_name
                })
            except ValueError as e:
                # Phase 4: Conservative ROADMAP handling
                if not allow_roadmap_miss:
                    # Default: Escalate when ROADMAP item not found
                    result['errors'].append(f"ROADMAP item not found: {str(e)}\nUse --allow-roadmap-miss to proceed with cleanup anyway")
                    logger.log_event("complete", "ROADMAP item not found - escalating", {
                        "workspace": workspace_name,
                        "error": str(e)
                    })
                    return result
                else:
                    # Allow-miss flag: Proceed with warning
                    result['warnings'].append(f"ROADMAP item not found (proceeding with cleanup): {str(e)}")
                    result['roadmap_updated'] = False
                    logger.log_event("complete", "ROADMAP item not found - proceeding (allow-miss)", {
                        "workspace": workspace_name,
                        "error": str(e)
                    })

        # Commit ROADMAP update (only if successfully updated)
        if result['roadmap_updated'] and roadmap_path is not None:
            committed = commit_roadmap_update(roadmap_path, workspace_name, project_dir)
            result['committed'] = committed
            if committed:
                logger.log_event("complete", "ROADMAP update committed", {
                    "workspace": workspace_name
                })
    else:
        # Ad-hoc agent: Skip ROADMAP update (no error)
        result['roadmap_updated'] = False
        result['committed'] = False
        logger.log_event("complete", "Ad-hoc agent - no ROADMAP update", {
            "agent_id": agent_id
        })

    # Step 3: Update feature status if feature_id present
    if agent.get('feature_id'):
        from orch.features import complete_feature, FeatureNotFoundError, FeaturesNotFoundError
        feature_id = agent['feature_id']
        try:
            complete_feature(feature_id, project_dir)
            result['feature_updated'] = True
            click.echo(f"📋 Feature '{feature_id}' marked complete")
            logger.log_event("complete", "Feature marked complete", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except FeaturesNotFoundError:
            result['warnings'].append(f"backlog.json not found - cannot update feature status")
            logger.log_event("complete", "Features file not found", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except FeatureNotFoundError:
            result['warnings'].append(f"Feature '{feature_id}' not found in backlog.json")
            logger.log_event("complete", "Feature not found", {
                "feature_id": feature_id,
                "agent_id": agent_id
            })
        except Exception as e:
            result['warnings'].append(f"Failed to update feature status: {e}")
            logger.log_event("complete", "Feature update failed", {
                "feature_id": feature_id,
                "agent_id": agent_id,
                "error": str(e)
            })

        # Step 3.5: Check investigation backlink
        # If this feature has context_ref to an investigation, check if all
        # features from that investigation are now complete
        try:
            from orch.features import get_feature
            feature = get_feature(feature_id, project_dir)
            if feature and feature.context_ref:
                backlink_info = check_investigation_backlink(
                    context_ref=feature.context_ref,
                    project_dir=project_dir
                )
                if backlink_info:
                    result['investigation_backlink'] = backlink_info
                    logger.log_event("complete", "Investigation backlink detected", {
                        "feature_id": feature_id,
                        "investigation_path": backlink_info['investigation_path'],
                        "feature_count": backlink_info['feature_count']
                    })
        except Exception as e:
            # Don't fail completion if backlink check fails
            logger.log_event("complete", "Investigation backlink check failed", {
                "feature_id": feature_id,
                "error": str(e)
            })

    # Step 3.6: Close beads issue if agent was spawned from beads issue
    if agent.get('beads_id'):
        beads_id = agent['beads_id']
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
        Created issue ID (e.g., 'meta-orchestration-abc') or None on failure
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

        # Parse issue ID from output (format: "Created: meta-orchestration-abc")
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

def close_beads_issue(beads_id: str) -> bool:
    """
    Close a beads issue via BeadsIntegration.

    Called during agent completion when agent has beads_id metadata
    (set when spawned from beads issue via `orch spawn --issue`).

    Args:
        beads_id: The beads issue ID to close (e.g., 'meta-orchestration-xyz')

    Returns:
        True if issue was closed successfully, False on failure
    """
    try:
        beads = BeadsIntegration()
        beads.close_issue(beads_id, reason='Resolved via orch complete')
        return True
    except BeadsCLINotFoundError:
        return False
    except BeadsIssueNotFoundError:
        return False
    except Exception:
        return False
