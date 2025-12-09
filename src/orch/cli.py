import click
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from orch import __version__
from orch.registry import AgentRegistry
from orch.tmux_utils import list_windows, find_session, is_tmux_available, get_window_by_target
from orch.monitor import check_agent_status, get_status_emoji
from orch.logging import OrchLogger
from orch.complete import verify_agent_work, clean_up_agent
from orch.help import show_help_overview, show_help_topic, show_unknown_topic, HELP_TOPICS
from orch.markdown_utils import extract_tldr

# Import from path_utils to break circular dependencies
# (cli -> complete -> spawn -> cli and cli -> complete -> spawn -> investigations -> cli)
# Re-export for backward compatibility
from orch.path_utils import get_git_root, find_orch_root, detect_and_display_context

# Import command modules for registration
from orch.spawn_commands import register_spawn_commands
from orch.monitoring_commands import register_monitoring_commands
from orch.workspace_commands import register_workspace_commands
from orch.work_commands import register_work_commands
from orch.error_commands import register_error_commands

@click.group()
@click.version_option(version=__version__, prog_name="orch")
def cli():
    """Orchestration monitoring and coordination tools."""
    pass

# Register commands from external modules
register_spawn_commands(cli)
register_monitoring_commands(cli)
register_workspace_commands(cli)
register_work_commands(cli)
register_error_commands(cli)

@cli.command()
@click.argument('topic', required=False)
def help(topic):
    """Show workflow-based help for orch commands.

    \b
    Available topics:
      spawn      - How to spawn and configure agents
      monitor    - How to monitor agent progress
      complete   - How to complete agent work
      maintain   - Maintenance and cleanup workflows

    Run 'orch help' without a topic to see the overview.
    """
    if topic is None:
        show_help_overview()
    elif topic in HELP_TOPICS:
        show_help_topic(topic)
    else:
        show_unknown_topic(topic)

def _is_stale_agent(agent: dict, check_status_func) -> tuple[bool, str | None]:
    """
    Determine if an agent is stale based on age and activity.

    Stale criteria:
    1. Phase: Unknown AND spawned >24 hours ago AND no commits since spawn
    2. OR: No commits since spawn AND spawned >4 hours ago

    An agent with commits is considered actively working and not stale.

    Args:
        agent: Agent dictionary from registry
        check_status_func: Function to check agent workspace status

    Returns:
        Tuple of (is_stale, reason) where reason explains why agent is stale
    """
    from datetime import datetime, timedelta

    status_val = agent.get('status', 'unknown')

    # Only check active agents (already abandoned/terminated agents don't need stale check)
    if status_val != 'active':
        return (False, None)

    # Get spawn time
    spawned_at_str = agent.get('spawned_at')
    if not spawned_at_str:
        return (False, None)

    try:
        spawned_at = datetime.fromisoformat(spawned_at_str)
    except (ValueError, TypeError):
        return (False, None)

    now = datetime.now()
    age = now - spawned_at

    # Get agent status (phase, commits)
    workspace_status = None
    if 'project_dir' in agent and 'workspace' in agent:
        workspace_status = check_status_func(agent, check_git=True)

    phase = workspace_status.phase if workspace_status else 'Unknown'
    commits_since_spawn = workspace_status.commits_since_spawn if workspace_status else 0

    # If agent has commits, it's actively working - not stale
    if commits_since_spawn > 0:
        return (False, None)

    # Criterion 1: Phase Unknown AND >24 hours old AND no commits
    if phase == 'Unknown' and age > timedelta(hours=24):
        return (True, 'Stale: Phase Unknown for >24 hours')

    # Criterion 2: No commits since spawn AND >4 hours old
    if phase == 'Unknown' and age > timedelta(hours=4):
        return (True, 'Stale: No commits for >4 hours')

    return (False, None)


def _should_clean_agent(agent: dict, clean_all: bool, pattern_violations: bool, stale: bool, check_status_func) -> tuple[bool, str | None]:
    """
    Determine whether an agent should be cleaned based on mode.

    Args:
        agent: Agent dictionary from registry
        clean_all: True if --all flag was specified
        pattern_violations: True if --pattern-violations flag was specified
        stale: True if --stale flag was specified
        check_status_func: Function to check agent workspace status (injected for testability)

    Returns:
        Tuple of (should_clean, stale_reason) where stale_reason is set for --stale mode
    """
    status_val = agent.get('status', 'unknown')

    # --stale mode: clean agents that are stuck
    if stale:
        is_stale, reason = _is_stale_agent(agent, check_status_func)
        if is_stale:
            return (True, reason)
        return (False, None)

    # Pattern violations mode: only clean orphaned/malformed agents
    if pattern_violations:
        if status_val in ('terminated', 'abandoned'):
            return (True, None)
        # Check for orphaned agents (no workspace file)
        if 'project_dir' in agent and 'workspace' in agent:
            workspace_status = check_status_func(agent)
            if workspace_status.phase == 'Unknown':
                return (True, None)
        return (False, None)

    # --all mode: clean everything cleanable
    # Note: 'Unknown' phase is NOT included here because:
    # 1. Newly-spawned agents have 'Unknown' phase until workspace is populated
    # 2. Corrupt/unreadable workspaces also show 'Unknown' - safer to not auto-clean
    # Use --pattern-violations to clean orphaned agents with 'Unknown' phase
    if clean_all:
        if status_val in ('abandoned', 'terminated', 'completed', 'completing'):
            return (True, None)
        if 'project_dir' in agent and 'workspace' in agent:
            workspace_status = check_status_func(agent)
            if workspace_status.phase in ('Complete', 'Abandoned'):
                return (True, None)
        return (False, None)

    # Default mode: conservative cleanup
    if status_val in ('abandoned', 'terminated'):
        return (True, None)

    # Check workspace phase for agents with workspace fields
    if 'project_dir' in agent and 'workspace' in agent:
        workspace_status = check_status_func(agent)
        if workspace_status.phase == 'Complete':
            return (True, None)
        if workspace_status.phase == 'Unknown' and status_val == 'completed':
            return (True, None)
        if status_val == 'completed':
            return (True, None)
        return (False, None)

    # Legacy agent without workspace fields
    if status_val == 'completed':
        return (True, None)

    return (False, None)


@cli.command()
@click.option('--all', is_flag=True, help='Clean all completed/terminated agents (not just Phase: Complete)')
@click.option('--pattern-violations', is_flag=True, help='Clean agents with pattern violations (missing workspaces, terminated)')
@click.option('--stale', is_flag=True, help='Clean agents stuck from previous day (Phase: Unknown >24h, or no commits >4h)')
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned without executing')
def clean(all, pattern_violations, stale, dry_run):
    """Remove completed agents and close their tmux windows."""
    from orch.monitor import check_agent_status

    # Initialize logger
    orch_logger = OrchLogger()

    # Start timing
    start_time = time.time()

    # Load registry
    registry = AgentRegistry()

    # Get all agents
    all_agents = registry.list_agents()

    # Filter agents based on flags and collect stale reasons
    agents_to_clean = []
    stale_reasons = {}  # agent_id -> reason
    for agent in all_agents:
        should_clean, stale_reason = _should_clean_agent(agent, all, pattern_violations, stale, check_agent_status)
        if should_clean:
            agents_to_clean.append(agent)
            if stale_reason:
                stale_reasons[agent['id']] = stale_reason

    # Log clean start
    orch_logger.log_command_start("clean", {
        "total_agents": len(all_agents),
        "completed_agents": len(agents_to_clean),
        "mode": "stale" if stale else ("all" if all else ("pattern_violations" if pattern_violations else "default"))
    })

    if not agents_to_clean:
        orch_logger.log_event("clean", "No completed agents to clean", {
            "total_agents": len(all_agents)
        }, level="INFO")
        click.echo("No completed agents to clean.")
        return

    # Dry run: show what would be cleaned
    if dry_run:
        click.echo(f"Would clean {len(agents_to_clean)} agent(s):\n")
        for agent in agents_to_clean:
            workspace = agent.get('workspace', 'N/A')
            status = agent.get('status', 'unknown')
            reason = stale_reasons.get(agent['id'], '')
            click.echo(f"  • {agent['id']}")
            click.echo(f"    Status: {status}")
            click.echo(f"    Workspace: {workspace}")
            if reason:
                click.echo(f"    Reason: {reason}")
            click.echo()
        click.echo(f"Run without --dry-run to execute cleanup.")
        return

    # Close tmux windows and remove from registry
    cleaned_count = 0
    for agent in agents_to_clean:
        # For stale mode: auto-abandon the agent first
        stale_reason = stale_reasons.get(agent['id'])
        if stale and stale_reason:
            registry.abandon_agent(agent['id'], reason=stale_reason)
            orch_logger.log_event("clean", f"Auto-abandoned stale agent: {agent['id']}", {
                "agent_id": agent['id'],
                "reason": stale_reason
            }, level="INFO")

        # Try to close tmux window using stable window ID
        window_id = agent.get('window_id')
        if window_id:
            # Use window ID (stable, never changes)
            try:
                subprocess.run(['tmux', 'kill-window', '-t', window_id],
                             check=False,  # Don't raise if window already closed
                             stderr=subprocess.DEVNULL)
            except Exception:
                # Window might already be closed, continue anyway
                pass
        else:
            # Fallback for old registry entries without window_id
            window = get_window_by_target(agent['window'])
            if window:
                try:
                    window.kill()
                except Exception:
                    pass

        # Remove from registry via public API
        registry.remove(agent['id'])
        cleaned_count += 1

        # Log agent removal
        orch_logger.log_event("clean", f"Removed agent: {agent['id']}", {
            "agent_id": agent['id'],
            "window": agent.get('window', 'unknown'),
            "reason": stale_reason if stale_reason else "completed"
        }, level="INFO")

    # Save registry (skip merge to prevent re-adding removed agents)
    # Bug fix: Merge logic would re-add deleted agents from disk
    # Investigation: .orch/investigations/2025-11-17-investigate-from-roadmap-resume-failure.md
    registry.save(skip_merge=True)

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Log clean complete
    orch_logger.log_command_complete("clean", duration_ms, {
        "removed": cleaned_count,
        "skipped": len(all_agents) - len(agents_to_clean)
    })

    # Show summary
    click.echo(f"✅ Cleaned {cleaned_count} completed agent(s).")


@cli.command()
@click.argument('agent_ids', nargs=-1, required=True)
@click.option('--reason', help='Reason for abandonment')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
@click.option('--force', is_flag=True, help='Skip confirmation prompt (alias for --yes)')
def abandon(agent_ids, reason, yes, force):
    """
    Abandon stuck or frozen agents.

    Marks agents as abandoned, closes tmux windows, and optionally archives workspaces.
    Use this when agents are stuck and cannot complete normally.

    Examples:
      orch abandon agent-id
      orch abandon agent-id --reason "Timeout: No progress for 30 minutes"
      orch abandon agent-id -y
      orch abandon agent-1 agent-2 agent-3 -y
    """
    # Initialize logger
    orch_logger = OrchLogger()

    # Start timing
    start_time = time.time()

    # Load registry
    registry = AgentRegistry()

    # Verify all agents exist
    not_found = []
    agents_to_abandon = []
    for agent_id in agent_ids:
        agent = registry.find(agent_id)
        if not agent:
            not_found.append(agent_id)
        else:
            agents_to_abandon.append(agent)

    if not_found:
        click.echo(f"❌ Agent(s) not found: {', '.join(not_found)}")
        click.echo()
        click.echo("💡 Tip: Use --reason flag for abandonment reason:")
        click.echo("   orch abandon <agent-id> --reason \"your reason here\"")
        click.echo()
        if not agents_to_abandon:
            click.echo("Aborted!")
            return
        click.echo()

    if not agents_to_abandon:
        click.echo("No agents to abandon.")
        return

    # Show what will be abandoned
    click.echo(f"Will abandon {len(agents_to_abandon)} agent(s):")
    for agent in agents_to_abandon:
        click.echo(f"  • {agent['id']} ({agent.get('window', 'no window')})")
    if reason:
        click.echo(f"\nReason: {reason}")
    click.echo()

    # Confirm unless --yes or --force
    if not (yes or force):
        if not click.confirm('Proceed with abandonment?'):
            click.echo("Cancelled.")
            return

    # Log abandon start
    orch_logger.log_command_start("abandon", {
        "agent_count": len(agents_to_abandon),
        "reason": reason or "no_reason_provided"
    })

    # Abandon each agent
    abandoned_count = 0
    for agent in agents_to_abandon:
        agent_id = agent['id']

        # Try to close tmux window using stable window ID
        window_id = agent.get('window_id')
        if window_id:
            try:
                subprocess.run(['tmux', 'kill-window', '-t', window_id],
                             check=False,  # Don't raise if window already closed
                             stderr=subprocess.DEVNULL)
            except Exception:
                # Window might already be closed, continue anyway
                pass
        else:
            # Fallback for old registry entries without window_id
            window = get_window_by_target(agent['window'])
            if window:
                try:
                    window.kill()
                except Exception:
                    pass

        # Mark as abandoned in registry
        registry.abandon_agent(agent_id, reason=reason)
        abandoned_count += 1

        # Log agent abandonment
        orch_logger.log_event("abandon", f"Abandoned agent: {agent_id}", {
            "agent_id": agent_id,
            "window": agent.get('window', 'unknown'),
            "reason": reason or "no_reason_provided"
        }, level="INFO")

    # Save registry
    registry.save()

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Log abandon complete
    orch_logger.log_command_complete("abandon", duration_ms, {
        "abandoned": abandoned_count,
        "reason": reason or "no_reason_provided"
    })

    # Show summary
    click.echo(f"\n✅ Abandoned {abandoned_count} agent(s).")
    click.echo("\nAbandoned agents remain in registry with status='abandoned'.")
    click.echo("Run 'orch clean' to remove them from the registry.")


@cli.command()
@click.argument('agent_id', required=False)
@click.option('--issue', 'beads_issue', help='Close beads issue directly (bypass registry)')
@click.option('--dry-run', is_flag=True, help='Show what would happen without executing')
@click.option('--all', 'complete_all', is_flag=True, help='Complete all ready agents (READY_COMPLETE or READY_CLEAN scenarios)')
@click.option('--project', help='Filter agents by project directory (used with --all)')
@click.option('--skip-test-check', is_flag=True, help='Skip test verification check (use when pre-existing test failures block completion)')
@click.option('--force', is_flag=True, help='Bypass safety checks (active processes, git state) - use when work complete but session hung')
def complete(agent_id, beads_issue, dry_run, complete_all, project, skip_test_check, force):
    """
    Complete agent work: verify, close beads issue, cleanup.

    Workflow:
    1. Verify agent work (Phase: Complete in beads)
    2. Close beads issue
    3. Clean up agent and close tmux window

    Example:
        orch complete my-agent-workspace
        orch complete investigate-bug-123
        orch complete --issue orch-cli-xyz
    """
    from orch.complete import complete_agent_work
    from orch.monitor import check_agent_status, Scenario

    # Handle --issue flag: close beads issue directly (bypass registry)
    if beads_issue:
        # Validate: --issue is mutually exclusive with agent_id and --all
        if agent_id:
            click.echo("Cannot specify both agent_id and --issue. Use one or the other.", err=True)
            raise click.Abort()
        if complete_all:
            click.echo("Cannot use --issue with --all.", err=True)
            raise click.Abort()

        from orch.beads_integration import (
            BeadsIntegration,
            BeadsCLINotFoundError,
            BeadsIssueNotFoundError,
        )
        from orch.complete import BeadsPhaseNotCompleteError

        try:
            beads = BeadsIntegration()

            # Verify Phase: Complete exists in comments
            phase = beads.get_phase_from_comments(beads_issue)
            if not phase or phase.lower() != "complete":
                click.echo(f"Cannot close beads issue '{beads_issue}': Phase is '{phase or 'none'}', not 'Complete'.", err=True)
                click.echo(f"   Agent must run: bd comment {beads_issue} \"Phase: Complete - <summary>\"", err=True)
                raise click.Abort()

            # Close the issue
            beads.close_issue(beads_issue, reason='Resolved via orch complete --issue')
            click.echo(f"Beads issue '{beads_issue}' closed successfully.")

        except BeadsCLINotFoundError:
            click.echo("bd CLI not found. Install beads or check PATH.", err=True)
            raise click.Abort()
        except BeadsIssueNotFoundError:
            click.echo(f"Beads issue '{beads_issue}' not found.", err=True)
            raise click.Abort()

        return

    # Phase 4.5: Batch completion mode
    if complete_all:
        if agent_id:
            click.echo("❌ Cannot specify both agent_id and --all", err=True)
            raise click.Abort()

        # Load registry
        registry = AgentRegistry()
        agents = registry.list_agents()

        # Filter by project if specified
        if project:
            agents = [a for a in agents if Path(a['project_dir']).name == project or str(a['project_dir']) == project]

        # Filter by scenario (only ready agents)
        ready_agents = []
        for agent_info in agents:
            status = check_agent_status(agent_info)
            if status.scenario in [Scenario.READY_COMPLETE, Scenario.READY_CLEAN]:
                ready_agents.append((agent_info, status))

        if not ready_agents:
            click.echo("No ready agents found.")
            return

        # Show preview
        click.echo(f"Found {len(ready_agents)} ready agent(s):")
        click.echo()
        for agent_info, status in ready_agents:
            click.echo(f"  • {agent_info['id']} - {status.recommendation}")
        click.echo()

        if dry_run:
            click.echo("Dry-run mode: Would complete these agents")
            return

        # Batch complete
        successes = []
        failures = []

        for agent_info, status in ready_agents:
            agent_id_batch = agent_info['id']
            click.echo(f"Completing: {agent_id_batch}")

            try:
                project_dir = Path(agent_info['project_dir'])

                result = complete_agent_work(
                    agent_id=agent_id_batch,
                    project_dir=project_dir,
                    dry_run=False,
                    skip_test_check=skip_test_check
                )

                if result['success']:
                    successes.append(agent_id_batch)
                    click.echo(f"  ✓ {agent_id_batch} completed")
                else:
                    failures.append((agent_id_batch, result['errors']))
                    click.echo(f"  ✗ {agent_id_batch} failed: {result['errors'][0] if result['errors'] else 'Unknown error'}")
            except Exception as e:
                failures.append((agent_id_batch, [str(e)]))
                click.echo(f"  ✗ {agent_id_batch} error: {str(e)}")

            click.echo()

        # Show summary
        click.echo(f"Completed: {len(successes)}/{len(ready_agents)} successful")
        if failures:
            click.echo()
            click.echo("Failures:")
            for agent_id_fail, errors in failures:
                click.echo(f"  • {agent_id_fail}: {errors[0] if errors else 'Unknown error'}")

        # Exit code: 0 if all succeeded, 1 if any failed
        if failures:
            raise click.Abort()

        return

    # Single agent mode (original behavior)
    if not agent_id:
        click.echo("❌ Must specify either agent_id or --all", err=True)
        raise click.Abort()

    # Load registry to get agent info
    registry = AgentRegistry()
    agent = registry.find(agent_id)

    if not agent:
        click.echo(f"❌ Agent '{agent_id}' not found in registry.", err=True)
        raise click.Abort()

    # Get project directory from agent
    project_dir = Path(agent['project_dir'])

    click.echo()
    click.echo(f"🔍 Completing: {agent_id}")
    click.echo(f"   Project: {project_dir}")
    click.echo()

    # Run complete workflow (sync mode only)
    result = complete_agent_work(
        agent_id=agent_id,
        project_dir=project_dir,
        dry_run=dry_run,
        skip_test_check=skip_test_check,
        force=force
    )

    # Display results
    if result['success']:
        if result.get('dry_run'):
            click.echo("✅ Dry-run: Would complete successfully")
            click.echo()
            click.echo("   ✓ Verification passed")
            if result.get('warnings'):
                click.echo()
                click.echo("   ⚠️  Warnings:")
                for warning in result['warnings']:
                    click.echo(f"      {warning}")
        else:
            click.echo("✅ Agent work completed successfully!")
            click.echo()
            click.echo("   ✓ Verification passed")
            click.echo("   ✓ Agent cleaned up")
            if result.get('beads_closed'):
                click.echo("   ✓ Beads issue closed")

            # Show warnings if any
            if result.get('warnings'):
                click.echo()
                click.echo("   ⚠️  Warnings:")
                for warning in result['warnings']:
                    click.echo(f"      {warning}")

        click.echo()
    else:
        click.echo("❌ Completion failed:", err=True)
        click.echo()
        if not result['verified']:
            click.echo("   ✗ Verification failed:", err=True)
            for error in result['errors']:
                click.echo(f"     - {error}", err=True)
        else:
            click.echo("   ✗ Error:", err=True)
            for error in result['errors']:
                click.echo(f"     - {error}", err=True)
        click.echo()
        raise click.Abort()


def _load_orchignore_patterns(base_dir: Path):
    """Load ignore patterns from .orchignore file if it exists.

    Args:
        base_dir: Directory to check for .orchignore file

    Returns:
        Set of pattern strings (glob-style patterns)
    """
    orchignore_file = base_dir / '.orchignore'
    patterns = set()

    if orchignore_file.exists():
        try:
            with open(orchignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and blank lines
                    if line and not line.startswith('#'):
                        patterns.add(line)
        except (PermissionError, OSError):
            # If we can't read .orchignore, continue with default patterns
            pass

    return patterns


def _should_ignore_dir(dirname: str, ignore_patterns: set):
    """Check if a directory should be ignored based on patterns.

    Args:
        dirname: Directory name to check
        ignore_patterns: Set of pattern strings (exact match or glob patterns)

    Returns:
        True if directory should be ignored, False otherwise
    """
    import fnmatch

    # Exact match
    if dirname in ignore_patterns:
        return True

    # Glob pattern match
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(dirname, pattern):
            return True

    return False


def _find_claude_files_with_depth(base_dir: Path, max_depth: int = 4, max_files: int = 1000, max_time: int = 30):
    """Find CLAUDE.md files with depth limit and fail-fast checks.

    Args:
        base_dir: Base directory to start scanning from
        max_depth: Maximum directory depth to descend (default 4)
        max_files: Maximum files to scan before warning (default 1000)
        max_time: Maximum scan time in seconds before aborting (default 30)

    Returns:
        List of Path objects for CLAUDE.md files found

    Raises:
        click.ClickException: If scan exceeds time limit
    """
    import time

    start_time = time.time()
    base_depth = len(base_dir.parts)
    results = []
    files_scanned = 0
    last_warning_threshold = 0  # Track last warning to avoid spam

    # Default ignore patterns (common directories to skip)
    default_patterns = {
        'node_modules', '.git', '.venv', 'venv', '__pycache__',
        '.tox', '.pytest_cache', 'dist', 'build', '.eggs', '.mypy_cache',
        'htmlcov', '.coverage', '.cache', '.npm', '.yarn'
    }

    # Load .orchignore patterns and merge with defaults
    custom_patterns = _load_orchignore_patterns(base_dir)
    ignore_patterns = default_patterns | custom_patterns

    try:
        for root, dirs, files in os.walk(base_dir):
            # Fail-fast: Check time limit
            elapsed = time.time() - start_time
            if elapsed > max_time:
                raise click.ClickException(
                    f"❌ Scan exceeded time limit ({max_time}s) while scanning {base_dir}\n"
                    f"   Scanned {files_scanned} files in {elapsed:.1f}s\n"
                    f"   Tip: Add .orchignore file to exclude large directories"
                )

            current_depth = len(Path(root).parts) - base_depth

            # Filter out ignored directories (in-place modification prevents descent)
            dirs[:] = [d for d in dirs if not _should_ignore_dir(d, ignore_patterns)]

            # Stop descending if we've reached max depth
            if current_depth >= max_depth:
                dirs[:] = []  # Clear dirs to prevent further descent
                continue

            # Count files for progress tracking
            files_scanned += len(files)

            # Fail-fast: Warn if scanning too many files (emit warning at each 1000 file threshold)
            if files_scanned > max_files:
                current_threshold = (files_scanned // 1000) * 1000
                if current_threshold > last_warning_threshold:
                    click.echo(
                        f"⚠️  Warning: Scanned {current_threshold}+ files so far (this may take a while)\n"
                        f"   Consider adding .orchignore to exclude unnecessary directories",
                        err=True
                    )
                    last_warning_threshold = current_threshold

            # Find CLAUDE.md files
            if 'CLAUDE.md' in files:
                results.append(Path(root) / 'CLAUDE.md')

    except (PermissionError, OSError):
        # Skip directories we can't access
        pass

    return results


def _reverse_lint_skills(target_command: str):
    """Find skills that reference a specific CLI command.

    Args:
        target_command: The command to search for (e.g., 'spawn', 'build skills')
    """
    import re
    from pathlib import Path

    # Find skill files
    skills_dir = Path.home() / ".claude" / "skills"

    if not skills_dir.exists():
        click.echo(f"🔍 No skills directory found (~/.claude/skills/)")
        click.echo(f"   Found 0 skills referencing 'orch {target_command}'")
        return

    # Discover skill files (hierarchical structure)
    skill_files = []
    for category_dir in skills_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill_files.append(skill_file)

    if not skill_files:
        click.echo(f"🔍 No skill files found (0 skills scanned)")
        click.echo(f"   Found 0 skills referencing 'orch {target_command}'")
        return

    # Pattern to extract orch commands - matches the target command specifically
    # For "spawn", matches "orch spawn", "orch spawn --flag", etc.
    # For "build skills", matches "orch build skills" specifically
    target_parts = target_command.lower().split()

    if len(target_parts) == 2:
        # Subcommand pattern: "build skills" -> match "orch build skills"
        orch_pattern = re.compile(
            rf'`?orch\s+{re.escape(target_parts[0])}\s+{re.escape(target_parts[1])}[^`]*',
            re.IGNORECASE
        )
    else:
        # Single command pattern: "spawn" -> match "orch spawn" (not followed by another command word)
        orch_pattern = re.compile(
            rf'`?orch\s+{re.escape(target_command)}(?:\s+--[a-z][a-z0-9-]*|\s+[^a-z`]|`|$)',
            re.IGNORECASE
        )

    # Track matches
    results = {}  # skill_name -> list of (line_num, line_content)
    total_refs = 0

    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        try:
            lines = skill_file.read_text().splitlines()
        except Exception:
            continue

        matches = []
        for line_num, line in enumerate(lines, start=1):
            if orch_pattern.search(line):
                matches.append((line_num, line.strip()))
                total_refs += 1

        if matches:
            results[skill_name] = {
                'file': str(skill_file),
                'matches': matches
            }

    # Report results
    click.echo(f"🔍 Skills referencing 'orch {target_command}':")
    click.echo()

    if results:
        for skill_name, data in sorted(results.items()):
            click.echo(f"   📦 {skill_name}:")
            click.echo(f"      {data['file']}")
            for line_num, line_content in data['matches']:
                # Truncate long lines
                display_line = line_content[:80] + "..." if len(line_content) > 80 else line_content
                click.echo(f"      - Line {line_num}: {display_line}")
            click.echo()

        skill_count = len(results)
        click.echo(f"   Found {total_refs} references in {skill_count} skill{'s' if skill_count != 1 else ''}.")
    else:
        click.echo(f"   No skills reference 'orch {target_command}'")
        click.echo()
        click.echo(f"   Found 0 skills referencing 'orch {target_command}'")


def _lint_skills():
    """Validate CLI command references in skill files."""
    import re
    from pathlib import Path
    from orch.doc_check import extract_cli_reference

    # Get valid commands from CLI
    valid_commands = extract_cli_reference(cli)

    # Build set of valid command names (including nested like "build skills")
    valid_cmd_names = set(valid_commands.keys())

    # Build map of command -> valid options
    cmd_options = {}
    for cmd_name, cmd_info in valid_commands.items():
        cmd_options[cmd_name] = set()
        for opt in cmd_info.get('options', []):
            opt_name = opt.get('name', '')
            if opt_name.startswith('--'):
                cmd_options[cmd_name].add(opt_name)
                # Also add without -- prefix
                cmd_options[cmd_name].add(opt_name[2:])

    # Find skill files
    skills_dir = Path.home() / ".claude" / "skills"

    if not skills_dir.exists():
        click.echo("✅ No skills directory found (~/.claude/skills/)")
        return

    # Discover skill files (hierarchical structure)
    skill_files = []
    for category_dir in skills_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill_files.append(skill_file)

    if not skill_files:
        click.echo("✅ No skill files found (0 skills scanned)")
        return

    # Pattern to extract orch commands and flags
    # Match: `orch <command> [subcommand] [--flag] [--flag2]`
    # Examples: "`orch spawn`", "`orch build skills`", "`orch spawn --issue`"
    # Requires backticks to avoid matching prose like "orch overhead"
    orch_pattern = re.compile(
        r'`orch\s+([a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)?)'  # command + optional subcommand
        r'((?:\s+--[a-z][a-z0-9-]*)*)`',  # optional flags, ends with backtick
        re.IGNORECASE
    )

    # Track issues
    issues = []  # List of (skill_name, file_path, issue_description)
    total_commands = 0
    valid_count = 0

    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        try:
            content = skill_file.read_text()
        except Exception:
            continue

        # Find all orch command references
        for match in orch_pattern.finditer(content):
            total_commands += 1
            cmd_part = match.group(1).strip().lower()
            flags_part = match.group(2).strip() if match.group(2) else ""

            # Check if command is valid
            # Try both single command and subcommand format
            cmd_valid = False
            matched_cmd = None

            if cmd_part in valid_cmd_names:
                cmd_valid = True
                matched_cmd = cmd_part
            else:
                # Try splitting into command + subcommand
                parts = cmd_part.split()
                if len(parts) == 2:
                    full_cmd = f"{parts[0]} {parts[1]}"
                    if full_cmd in valid_cmd_names:
                        cmd_valid = True
                        matched_cmd = full_cmd
                    elif parts[0] in valid_cmd_names:
                        # Command exists but subcommand may be invalid
                        cmd_valid = True
                        matched_cmd = parts[0]
                        # Check if this command has subcommands
                        parent_info = valid_commands.get(parts[0], {})
                        if parent_info.get('subcommands'):
                            if parts[1] not in parent_info['subcommands']:
                                issues.append((
                                    skill_name,
                                    str(skill_file),
                                    f"Unknown subcommand: orch {parts[0]} {parts[1]} (valid: {', '.join(parent_info['subcommands'])})"
                                ))
                                continue
                elif len(parts) == 1 and parts[0] in valid_cmd_names:
                    cmd_valid = True
                    matched_cmd = parts[0]

            if not cmd_valid:
                issues.append((
                    skill_name,
                    str(skill_file),
                    f"Unknown command: orch {cmd_part}"
                ))
                continue

            # Check flags if command is valid
            if flags_part and matched_cmd:
                # Extract individual flags
                flag_pattern = re.compile(r'--([a-z][a-z0-9-]*)')
                for flag_match in flag_pattern.finditer(flags_part):
                    flag_name = flag_match.group(1)
                    valid_flags = cmd_options.get(matched_cmd, set())
                    if flag_name not in valid_flags and f"--{flag_name}" not in valid_flags:
                        issues.append((
                            skill_name,
                            str(skill_file),
                            f"Unknown flag: --{flag_name} on 'orch {matched_cmd}'"
                        ))
                        continue

            valid_count += 1

    # Report results
    click.echo(f"🔍 Skill CLI reference check:")
    click.echo(f"   Scanned {len(skill_files)} skill files")
    click.echo(f"   Found {total_commands} orch command references")
    click.echo()

    if issues:
        click.echo(f"⚠️  Found {len(issues)} issues:")
        click.echo()

        # Group by skill
        by_skill = {}
        for skill_name, file_path, issue in issues:
            if skill_name not in by_skill:
                by_skill[skill_name] = []
            by_skill[skill_name].append(issue)

        for skill_name, skill_issues in sorted(by_skill.items()):
            click.echo(f"   📦 {skill_name}:")
            for issue in skill_issues:
                click.echo(f"      • {issue}")
            click.echo()
    else:
        click.echo(f"✅ All {valid_count} command references are valid!")


def _lint_issues():
    """Validate beads issues for common problems.

    Checks:
    1. Deletion issues without migration path section
    2. Hidden blockers in description/notes without bd dependency
    3. Vague scope without enumeration
    4. Stale issues (open >7 days without activity)
    5. Missing acceptance criteria
    """
    import re
    from datetime import datetime, timedelta, timezone
    from orch.beads_integration import BeadsIntegration, BeadsCLINotFoundError

    try:
        beads = BeadsIntegration()
    except Exception as e:
        click.echo(f"❌ Failed to initialize beads integration: {e}", err=True)
        return

    # Get all open issues
    try:
        result = subprocess.run(
            ["bd", "list", "--status=open", "--json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.echo("❌ Failed to list beads issues", err=True)
            return

        issues = json.loads(result.stdout)
    except FileNotFoundError:
        click.echo("❌ bd CLI not found. Install beads or check PATH.", err=True)
        return
    except json.JSONDecodeError:
        click.echo("❌ Failed to parse beads output", err=True)
        return

    if not issues:
        click.echo("✅ No open issues to validate")
        return

    # Get blocked issues for accurate "hidden blocker" check
    blocked_issue_ids = set()
    try:
        blocked_result = subprocess.run(
            ["bd", "blocked", "--json"],
            capture_output=True,
            text=True,
        )
        if blocked_result.returncode == 0:
            blocked_issues = json.loads(blocked_result.stdout)
            blocked_issue_ids = {issue.get("id") for issue in blocked_issues if issue.get("id")}
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # If bd blocked fails, skip this check

    click.echo(f"🔍 Validating {len(issues)} open beads issues...")
    click.echo()

    warnings = []  # List of (issue_id, warning_message, suggestion)
    passed_count = 0

    for issue in issues:
        issue_id = issue.get("id", "unknown")
        title = issue.get("title", "").lower()
        description = issue.get("description", "")
        notes = issue.get("notes", "") or ""
        updated_at_str = issue.get("updated_at", "")
        dependencies = issue.get("dependencies", []) or []

        issue_warnings = []

        # Check 1: Deletion issues without migration path
        deletion_keywords = ["delete", "remove", "eliminate", "deprecate"]
        is_deletion_issue = any(kw in title for kw in deletion_keywords)

        if is_deletion_issue:
            has_migration = any(marker in description.lower() for marker in [
                "## migration", "migration path", "migration plan",
                "migrate to", "migration:", "before deleting"
            ])
            if not has_migration:
                issue_warnings.append((
                    "Deletion issue without migration path",
                    f"Contains '{next(kw for kw in deletion_keywords if kw in title)}' but no '## Migration' section",
                    "Add a ## Migration section explaining what replaces the deleted code"
                ))

        # Check 2: Hidden blockers in description/notes without bd dependency
        # Use bd blocked list to accurately detect issues with blocking dependencies
        blocker_patterns = [
            r"(?i)BLOCKED\s*:", r"(?i)Prerequisite\s*:",
            r"(?i)Depends\s+on\s*:", r"(?i)Requires\s*:",
            r"(?i)Must\s+wait\s+for"
        ]
        combined_text = description + " " + notes

        has_blocker_text = any(re.search(pat, combined_text) for pat in blocker_patterns)
        is_in_blocked_list = issue_id in blocked_issue_ids

        # Also check full dependencies array if provided (from bd show)
        has_blocking_dependency = any(
            dep.get("dependency_type") == "blocks" for dep in dependencies
        ) if dependencies else is_in_blocked_list

        if has_blocker_text and not has_blocking_dependency:
            issue_warnings.append((
                "Hidden blocker in description",
                "Found blocker/prerequisite text but no bd dependency tracked",
                "Run 'bd dep <blocker-id> <this-id>' to track the blocker properly"
            ))

        # Check 3: Vague scope without enumeration
        vague_patterns = [
            r"(?i)all\s+\w+\s+references",
            r"(?i)remove\s+all\s+",
            r"(?i)delete\s+all\s+",
            r"(?i)update\s+every\s+",
            r"(?i)across\s+the\s+codebase",
            r"(?i)throughout\s+the\s+project"
        ]
        is_vague = any(re.search(pat, description) for pat in vague_patterns)

        if is_vague:
            # Check for enumeration markers
            has_enumeration = any(marker in description for marker in [
                "1.", "2.", "- ", "* ", "files:", "locations:",
                " occurrences", " references in ", " files"
            ])
            if not has_enumeration:
                issue_warnings.append((
                    "Vague scope without enumeration",
                    "Contains 'all X' or 'remove Y references' but no specific list",
                    "Add enumeration: list specific files, count occurrences, or scope precisely"
                ))

        # Check 4: Stale issues (open >7 days without activity)
        if updated_at_str:
            try:
                # Parse ISO format with timezone
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_days = (now - updated_at).days

                if age_days > 7:
                    issue_warnings.append((
                        f"Stale issue (no activity for {age_days} days)",
                        f"Last updated {age_days} days ago",
                        "Update status, add comment, or close if no longer needed"
                    ))
            except (ValueError, TypeError):
                pass  # Skip if date parsing fails

        # Check 5: Missing acceptance criteria
        acceptance_patterns = [
            r"(?i)done\s+when\s*:",
            r"(?i)success\s+criteria\s*:",
            r"(?i)acceptance\s+criteria\s*:",
            r"(?i)\[\s*\]",  # Checklist marker
            r"(?i)complete\s+when\s*:",
            r"(?i)definition\s+of\s+done"
        ]
        has_acceptance = any(re.search(pat, description) for pat in acceptance_patterns)

        # Epic issues should have success criteria
        is_epic = issue.get("issue_type") == "epic"

        if is_epic and not has_acceptance:
            issue_warnings.append((
                "Epic missing success criteria",
                "Epic issues should have clear '## Success Criteria' section",
                "Add success criteria or checklist to define 'done'"
            ))

        # Accumulate warnings
        if issue_warnings:
            for warning, detail, suggestion in issue_warnings:
                warnings.append((issue_id, issue.get("title", ""), warning, detail, suggestion))
        else:
            passed_count += 1

    # Display results
    if warnings:
        click.echo(f"⚠️  Found {len(warnings)} issue(s) with problems:\n")

        # Group warnings by issue
        warnings_by_issue = {}
        for issue_id, title, warning, detail, suggestion in warnings:
            if issue_id not in warnings_by_issue:
                warnings_by_issue[issue_id] = {"title": title, "warnings": []}
            warnings_by_issue[issue_id]["warnings"].append((warning, detail, suggestion))

        for issue_id, data in warnings_by_issue.items():
            # Truncate title for display
            title = data["title"]
            display_title = title[:50] + "..." if len(title) > 50 else title
            click.echo(f"⚠️  {issue_id}: {display_title}")

            for warning, detail, suggestion in data["warnings"]:
                click.echo(f"   • {warning}")
                click.echo(f"     {detail}")
                click.echo(f"     💡 {suggestion}")
            click.echo()

        click.echo(f"✅ {passed_count} issue(s) passed validation")
    else:
        click.echo(f"✅ All {len(issues)} issue(s) passed validation")


@cli.command(name='lint')
@click.option('--file', type=click.Path(exists=True), help='Specific CLAUDE.md file to check')
@click.option('--all', 'check_all', is_flag=True, help='Check all known CLAUDE.md files')
@click.option('--skills', is_flag=True, help='Validate CLI command references in skill files')
@click.option('--issues', is_flag=True, help='Validate beads issues for common problems')
@click.option('--reverse', 'reverse_cmd', help='Show skills that reference the given CLI command')
def lint(file, check_all, skills, issues, reverse_cmd):
    """
    Check CLAUDE.md files against token and character size limits.

    Validates that CLAUDE.md files stay within recommended limits:
    - Global (~/.claude/CLAUDE.md): 5,000 tokens, 20,000 chars
    - Project (project/CLAUDE.md): 15,000 tokens, 60,000 chars
    - Orchestrator (project/.orch/CLAUDE.md): 15,000 tokens, 40,000 chars

    Both limits must be satisfied for a file to pass.

    With --skills, validates that skill files reference valid CLI commands and flags.

    With --issues, validates beads issues for common problems:
    - Deletion issues without migration path section
    - Hidden blockers in description without bd dependency
    - Vague scope without enumeration
    - Stale issues (open >7 days without activity)
    - Epics missing success criteria

    With --reverse COMMAND, shows which skills reference the given CLI command.
    This helps understand the impact of CLI changes on skill documentation.

    \b
    Examples:
      orch lint                             # Check CLAUDE.md in current project
      orch lint --file ~/.claude/CLAUDE.md  # Check specific file
      orch lint --all                       # Check all known CLAUDE.md files
      orch lint --skills                    # Validate skill CLI references
      orch lint --issues                    # Validate beads issues
      orch lint --reverse spawn             # Show skills referencing 'orch spawn'
      orch lint --reverse "build skills"    # Show skills referencing 'orch build skills'
    """
    from pathlib import Path

    # Handle --reverse mode (reverse lint)
    if reverse_cmd:
        _reverse_lint_skills(reverse_cmd)
        return

    # Handle --skills mode
    if skills:
        _lint_skills()
        return

    # Handle --issues mode
    if issues:
        _lint_issues()
        return

    import tiktoken

    # Token and character limits
    LIMITS = {
        'global': {'tokens': 5000, 'chars': 20000},
        'project': {'tokens': 15000, 'chars': 60000},
        'orchestrator': {'tokens': 15000, 'chars': 40000},
    }

    # Warning thresholds (show warning when approaching limit)
    WARNING_THRESHOLDS = {
        'orchestrator': {'chars': 36000},  # Warn at 90% of limit
    }

    # Initialize tokenizer (cl100k_base is used by Claude)
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        click.echo(f"❌ Failed to initialize tokenizer: {e}", err=True)
        raise click.Abort()

    def count_metrics(file_path):
        """Count tokens and characters in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tokens = encoding.encode(content)
            return len(tokens), len(content)
        except Exception as e:
            click.echo(f"❌ Error reading {file_path}: {e}", err=True)
            return None, None

    def classify_file(file_path):
        """Determine file type based on path."""
        path = Path(file_path)
        if path.name != 'CLAUDE.md':
            return None, None

        if '.claude' in str(path):
            return 'global', LIMITS['global']
        elif '.orch' in str(path):
            return 'orchestrator', LIMITS['orchestrator']
        else:
            return 'project', LIMITS['project']

    def check_file(file_path):
        """Check a single file and return (path, tokens, chars, limits, file_type, passed)."""
        file_type, limits = classify_file(file_path)
        if file_type is None:
            return None

        token_count, char_count = count_metrics(file_path)
        if token_count is None or char_count is None:
            return None

        # Must pass both limits
        tokens_pass = token_count <= limits['tokens']
        chars_pass = char_count <= limits['chars']
        passed = tokens_pass and chars_pass

        return (file_path, token_count, char_count, limits, file_type, passed, tokens_pass, chars_pass)

    # Collect files to check
    files_to_check = []

    if file:
        # Check specific file
        files_to_check.append(file)
    elif check_all:
        # Find all CLAUDE.md files
        home = Path.home()
        # Global
        global_claude = home / '.claude' / 'CLAUDE.md'
        if global_claude.exists():
            files_to_check.append(str(global_claude))

        # Find projects with bounded depth scanning (prevents catastrophic performance)
        # Scan common project locations with max depth of 4 levels
        for base_dir in [home / 'Documents/work', home / 'Documents/personal', home]:
            if base_dir.exists():
                for claude_file in _find_claude_files_with_depth(base_dir, max_depth=4):
                    if str(claude_file) not in files_to_check:
                        files_to_check.append(str(claude_file))
    else:
        # Check current directory
        cwd = Path.cwd()
        # Try .orch/CLAUDE.md first
        orch_claude = cwd / '.orch' / 'CLAUDE.md'
        if orch_claude.exists():
            files_to_check.append(str(orch_claude))
        # Try CLAUDE.md in current dir
        current_claude = cwd / 'CLAUDE.md'
        if current_claude.exists():
            files_to_check.append(str(current_claude))

        if not files_to_check:
            click.echo("❌ No CLAUDE.md files found in current directory", err=True)
            click.echo("   Use --file to specify a file or --all to check all known files", err=True)
            raise click.Abort()

    # Check all files
    results = []
    for file_path in files_to_check:
        result = check_file(file_path)
        if result:
            results.append(result)

    if not results:
        click.echo("❌ No valid CLAUDE.md files found", err=True)
        raise click.Abort()

    # Display results
    click.echo()
    click.echo(f"📊 CLAUDE.md Limit Check ({len(results)} file{'s' if len(results) > 1 else ''})")
    click.echo()

    all_passed = True
    for file_path, tokens, chars, limits, file_type, passed, tokens_pass, chars_pass in results:
        token_pct = (tokens / limits['tokens']) * 100
        char_pct = (chars / limits['chars']) * 100
        status = "✅" if passed else "❌"

        # Shorten path for display
        display_path = str(file_path).replace(str(Path.home()), '~')

        click.echo(f"{status} {display_path}")

        # Show token metrics
        token_status = "✅" if tokens_pass else "❌"
        click.echo(f"   {token_status} Tokens: {tokens:,} / {limits['tokens']:,} ({token_pct:.1f}%)")

        # Show character metrics
        char_status = "✅" if chars_pass else "❌"
        click.echo(f"   {char_status} Chars:  {chars:,} / {limits['chars']:,} ({char_pct:.1f}%)")

        click.echo(f"   Type: {file_type}")

        # Check warning thresholds
        if file_type in WARNING_THRESHOLDS:
            thresholds = WARNING_THRESHOLDS[file_type]
            if 'chars' in thresholds and chars > thresholds['chars'] and chars_pass:
                warning_pct = (chars / limits['chars']) * 100
                click.echo(f"   ⚠️  Approaching char limit: {chars:,} / {limits['chars']:,} ({warning_pct:.1f}%)")

        if not passed:
            all_passed = False
            if not tokens_pass:
                token_overage = tokens - limits['tokens']
                click.echo(f"   ⚠️  EXCEEDS TOKEN LIMIT by {token_overage:,} tokens")
            if not chars_pass:
                char_overage = chars - limits['chars']
                click.echo(f"   ⚠️  EXCEEDS CHAR LIMIT by {char_overage:,} characters")

        click.echo()

    # Summary
    if all_passed:
        click.echo("✅ All files within limits")
    else:
        failed_count = sum(1 for _, _, _, _, _, passed, _, _ in results if not passed)
        click.echo(f"❌ {failed_count} file{'s' if failed_count > 1 else ''} exceed{'s' if failed_count == 1 else ''} limits")
        raise click.Abort()


def extract_investigation_category(path):
    """
    Extract the category (subdirectory) from an investigation file path.

    Args:
        path: Path object for the investigation file (e.g., Path('investigations/systems/2025-11-20-topic.md'))

    Returns:
        str or None: The category name (e.g., 'systems', 'feasibility', 'audits'),
                     or None if the file is in the root investigations directory.
    """
    from pathlib import Path

    path = Path(path)
    parts = path.parts

    # Find 'investigations' in the path
    try:
        inv_index = parts.index('investigations')
    except ValueError:
        return None

    # Check if there's a subdirectory between 'investigations' and the filename
    # Path structure: .../investigations/[category]/filename.md
    if len(parts) > inv_index + 2:
        # There's a subdirectory - return it as the category
        return parts[inv_index + 1]
    else:
        # File is directly in investigations/ with no subdirectory
        return None


@cli.command(name='build-readme', hidden=True)
@click.option('--dry-run', is_flag=True, help='Preview README without writing')
@click.option('--project', help='Project directory (defaults to current dir)')
def build_readme(dry_run, project):
    """
    Auto-generate .orch/README.md from artifact metadata.

    DEPRECATED: Use 'orch build --readme' instead.

    Scans .orch/ directory and generates index of:
    - Recent Decisions (last 14 days)
    - Recent Investigations (last 7 days)
    - Active Workspaces
    - Statistics

    \b
    Examples:
      orch build-readme                    # Generate README for current project
      orch build-readme --dry-run         # Preview without writing
      orch build-readme --project ~/foo   # Generate for specific project
    """
    import re
    from datetime import datetime, timedelta
    from pathlib import Path

    # Determine project directory
    if project:
        project_dir = Path(project).expanduser().resolve()
    else:
        project_dir = Path.cwd()

    orch_dir = project_dir / '.orch'

    # Validate .orch directory exists
    if not orch_dir.exists():
        click.echo(f"❌ .orch directory not found at {orch_dir}", err=True)
        raise click.Abort()

    # Parse frontmatter from markdown file
    def parse_frontmatter(file_path):
        """Extract **Field:** value pairs from markdown frontmatter."""
        metadata = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Match **Field:** value patterns in first ~50 lines
                lines = content.split('\n')[:50]
                for line in lines:
                    match = re.match(r'^\*\*([^*]+):\*\*\s*(.+)$', line)
                    if match:
                        field, value = match.groups()
                        metadata[field] = value.strip()
        except Exception:
            pass  # Skip files that can't be read
        return metadata

    # Discover artifacts
    def discover_artifacts(artifact_dir, extension='.md'):
        """Find all markdown files in directory with metadata."""
        artifacts = []
        if not artifact_dir.exists():
            return artifacts

        for file_path in artifact_dir.rglob(f'*{extension}'):
            if file_path.is_file():
                # Skip template files (files starting with _ or containing 'template')
                filename = file_path.name.lower()
                if filename.startswith('_') or 'template' in filename:
                    continue

                metadata = parse_frontmatter(file_path)
                artifacts.append({
                    'path': file_path,
                    'name': file_path.stem,
                    'relative_path': file_path.relative_to(orch_dir),
                    'mtime': datetime.fromtimestamp(file_path.stat().st_mtime),
                    'metadata': metadata
                })
        return artifacts

    # Discover all artifact types
    click.echo("📦 Scanning artifacts...")

    decisions = discover_artifacts(orch_dir / 'decisions')
    investigations = discover_artifacts(orch_dir / 'investigations')
    knowledge = discover_artifacts(orch_dir / 'knowledge')

    # Helper to infer workspace status from old v2 format
    def infer_workspace_status(file_path, metadata):
        """Infer status for old workspace formats that lack **Status:** field."""
        # If Status already exists, use it
        if 'Status' in metadata:
            return metadata['Status']

        # Old format: infer from Phase field
        phase = metadata.get('Phase', '').lower()
        if phase == 'complete':
            return 'Complete'
        elif phase == 'planning':
            return 'Planning'
        elif 'implementation' in phase or 'testing' in phase:
            return 'Active'

        # Last resort: check file content for "Blocked:" line
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '**Blocked:**' in content and 'Blocked:** null' not in content:
                    return 'Blocked'
        except Exception:
            pass

        return 'Active'  # Default assumption

    # Workspaces are in subdirectories with WORKSPACE.md files
    workspaces = []
    workspace_dir = orch_dir / 'workspace'
    if workspace_dir.exists():
        for ws_path in workspace_dir.iterdir():
            if ws_path.is_dir():
                workspace_file = ws_path / 'WORKSPACE.md'
                if workspace_file.exists():
                    metadata = parse_frontmatter(workspace_file)
                    # Infer status for old formats
                    metadata['Status'] = infer_workspace_status(workspace_file, metadata)
                    workspaces.append({
                        'path': workspace_file,
                        'name': ws_path.name,
                        'relative_path': workspace_file.relative_to(orch_dir),
                        'mtime': datetime.fromtimestamp(workspace_file.stat().st_mtime),
                        'metadata': metadata
                    })

    # Filter recent artifacts
    now = datetime.now()
    recent_decisions = [d for d in decisions
                       if (now - d['mtime']).days <= 14]
    recent_investigations = [i for i in investigations
                           if (now - i['mtime']).days <= 7]
    active_workspaces = [w for w in workspaces
                        if w['metadata'].get('Status', '').lower() in ['active', 'blocked']
                        or (now - w['mtime']).days <= 1]

    # Sort by modification time (newest first)
    recent_decisions.sort(key=lambda x: x['mtime'], reverse=True)
    recent_investigations.sort(key=lambda x: x['mtime'], reverse=True)
    active_workspaces.sort(key=lambda x: x['mtime'], reverse=True)

    # Helper to truncate long status strings
    def truncate_status(status, max_length=80):
        """Truncate status field to max_length characters."""
        if len(status) <= max_length:
            return status
        # Try to truncate at sentence boundary
        truncated = status[:max_length]
        # Find last period, comma, or dash before max_length
        for delim in ['.', ',', ' -', ';']:
            idx = truncated.rfind(delim)
            if idx > max_length * 0.6:  # At least 60% of max_length
                return truncated[:idx + 1].strip() + '...'
        # No good break point, hard truncate
        return truncated.strip() + '...'

    # Generate README content
    readme_lines = []

    # Header
    readme_lines.append("# .orch/ Artifact Index\n")
    readme_lines.append("\n")
    readme_lines.append("**Purpose:** Quick-reference index for high-value artifacts. Auto-loaded at session start to provide amnesia-resilient context.\n")
    readme_lines.append("\n")
    readme_lines.append("**Philosophy:** Files don't help unless loaded into memory. This index makes recent decisions, investigations, and active work immediately discoverable.\n")
    readme_lines.append("\n")
    readme_lines.append("---\n")
    readme_lines.append("\n")

    # Recent Decisions
    readme_lines.append("## Recent Decisions (Last 14 Days)\n")
    readme_lines.append("\n")
    if recent_decisions:
        for decision in recent_decisions[:20]:  # Limit to 20
            name = decision['name']
            status = truncate_status(decision['metadata'].get('Status', 'Unknown'))
            date = decision['metadata'].get('Date', 'Unknown')
            rel_path = decision['relative_path']
            readme_lines.append(f"- `{rel_path}` - [{status}] {date}\n")

            # Add TLDR/Summary if available
            tldr = extract_tldr(decision['path'])
            if tldr:
                tldr_short = tldr[:120] + '...' if len(tldr) > 120 else tldr
                readme_lines.append(f"  → {tldr_short}\n")
    else:
        readme_lines.append("*No recent decisions*\n")

    readme_lines.append("\n")
    readme_lines.append("**Full list:** `ls -lt decisions/ | head -20`\n")
    readme_lines.append("\n")
    readme_lines.append("---\n")
    readme_lines.append("\n")

    # Recent Investigations
    readme_lines.append("## Recent Investigations (Last 7 Days)\n")
    readme_lines.append("\n")
    if recent_investigations:
        for inv in recent_investigations[:20]:  # Limit to 20
            name = inv['name']
            status = inv['metadata'].get('Status', 'Unknown')
            confidence = inv['metadata'].get('Confidence', '')
            rel_path = inv['relative_path']

            # Extract category from path (e.g., 'systems', 'feasibility', 'audits')
            category = extract_investigation_category(rel_path)
            category_tag = f"[{category}] " if category else ""

            # Combine status and confidence, then truncate
            if confidence:
                combined = f"{status}, {confidence}"
            else:
                combined = status
            status_conf = f"[{truncate_status(combined)}]"
            readme_lines.append(f"- `{rel_path}` - {category_tag}{status_conf}\n")

            # Add TLDR if available (for context continuity)
            tldr = extract_tldr(inv['path'])
            if tldr:
                # Truncate TLDR to ~120 chars for readability
                tldr_short = tldr[:120] + '...' if len(tldr) > 120 else tldr
                readme_lines.append(f"  → {tldr_short}\n")
    else:
        readme_lines.append("*No recent investigations*\n")

    readme_lines.append("\n")
    readme_lines.append("**Full list:** `find investigations/ -name '*.md' -type f | xargs ls -lt 2>/dev/null | head -30`\n")
    readme_lines.append("\n")
    readme_lines.append("---\n")
    readme_lines.append("\n")

    # Active Workspaces
    readme_lines.append("## Active Workspaces\n")
    readme_lines.append("\n")
    if active_workspaces:
        for ws in active_workspaces[:15]:  # Limit to 15
            name = ws['name']
            status = ws['metadata'].get('Status', 'Unknown')
            phase = ws['metadata'].get('Phase', '')
            phase_str = f", {phase}" if phase else ""
            readme_lines.append(f"- `workspace/{name}/` - [{status}{phase_str}]\n")
    else:
        readme_lines.append("*No active workspaces*\n")

    readme_lines.append("\n")
    readme_lines.append("**View all:** `ls -lt workspace/ | head -20`\n")
    readme_lines.append("\n")
    readme_lines.append("**Check status:** `orch status`\n")
    readme_lines.append("\n")
    readme_lines.append("---\n")
    readme_lines.append("\n")

    # Statistics
    readme_lines.append("## Statistics\n")
    readme_lines.append("\n")
    readme_lines.append(f"**Total artifacts:** {len(decisions) + len(investigations) + len(knowledge) + len(workspaces)} files\n")
    readme_lines.append("\n")
    readme_lines.append("**Recent activity:**\n")
    readme_lines.append(f"- Decisions (last 14 days): {len(recent_decisions)}\n")
    readme_lines.append(f"- Investigations (last 7 days): {len(recent_investigations)}\n")
    readme_lines.append(f"- Active workspaces: {len(active_workspaces)}\n")
    readme_lines.append("\n")
    readme_lines.append("**All artifacts by type:**\n")
    readme_lines.append(f"- Decisions (total): {len(decisions)}\n")
    readme_lines.append(f"- Investigations (total): {len(investigations)}\n")
    readme_lines.append(f"- Workspaces (total): {len(workspaces)}\n")
    readme_lines.append(f"- Knowledge (total): {len(knowledge)}\n")
    readme_lines.append("\n")
    readme_lines.append("---\n")
    readme_lines.append("\n")

    # Footer
    now_str = datetime.now().strftime('%Y-%m-%d')
    readme_lines.append(f"**Last updated:** {now_str} (auto-generated)\n")
    readme_lines.append(f"**Command:** `orch build-readme`\n")

    readme_content = ''.join(readme_lines)

    # Output
    if dry_run:
        click.echo("📄 Preview of generated README:\n")
        click.echo(readme_content)
        click.echo(f"\n💡 Remove --dry-run to write to {orch_dir / 'README.md'}")
    else:
        readme_path = orch_dir / 'README.md'
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)

        click.echo(f"✅ README generated at {readme_path}")
        click.echo(f"\n📊 Summary:")
        click.echo(f"  Recent decisions: {len(recent_decisions)}")
        click.echo(f"  Recent investigations: {len(recent_investigations)}")
        click.echo(f"  Active workspaces: {len(active_workspaces)}")


@cli.command(name='scan-projects', hidden=True)
def scan_projects_cmd():
    """
    Scan for initialized .orch projects and update cache (internal command).

    Searches standard project directories for .orch/CLAUDE.md files
    and caches the results in ~/.orch/initialized-projects.json
    """
    from orch.project_discovery import scan_projects, write_cache, get_default_search_dirs
    from orch.config import get_initialized_projects_cache

    # Get search directories
    search_dirs = get_default_search_dirs()

    # Scan for projects
    projects = scan_projects(search_dirs)

    # Get cache file path
    cache_file = get_initialized_projects_cache()

    # Write cache
    write_cache(cache_file, projects)

    # Report results
    click.echo(f"✅ Found {len(projects)} initialized projects")
    click.echo(f"📁 Cache updated: {cache_file}")
    click.echo()

    if projects:
        click.echo("Projects found:")
        for project in projects:
            click.echo(f"  • {project}")
    else:
        click.echo("No initialized projects found in standard locations.")


# ============================================================================
# Build group - hierarchical command structure for build operations
# ============================================================================

@cli.group(invoke_without_command=True)
@click.option('--skills', 'target_skills', is_flag=True, help='Build skill SKILL.md files')
@click.option('--readme', 'target_readme', is_flag=True, help='Auto-generate .orch/README.md from artifact metadata')
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.pass_context
def build(ctx, target_skills, target_readme, dry_run, check):
    """
    Build skills from templates.

    Can be invoked with flags or as subcommands:

    \b
    Subcommand style (preferred):
      orch build skills             # Build skill SKILL.md files
      orch build readme             # Generate .orch/README.md

    \b
    Flag style:
      orch build                    # Build skills (default)
      orch build --skills           # Just SKILL.md files
      orch build --readme           # Generate README
      orch build --check            # Check if any rebuilds needed
      orch build --dry-run          # Preview all changes
    """
    # If a subcommand was invoked, don't run the group logic
    if ctx.invoked_subcommand is not None:
        return
    import re
    from pathlib import Path

    # Check if any specific target is requested
    any_specific = target_skills or target_readme

    if target_readme:
        click.echo("🔨 Building README (--readme)...")
        click.echo()
        ctx.invoke(build_readme, dry_run=dry_run, project=None)
        click.echo()
        if not target_skills:
            return

    # Default to skills if nothing specified
    if not any_specific:
        target_skills = True

    # Build skills
    if target_skills:
        click.echo("🔨 Building skills...")
        click.echo()

        import shutil

        # Source: orch-knowledge/skills/src/
        orch_root = find_orch_root()
        if not orch_root:
            click.echo("❌ Not in an orch-knowledge directory", err=True)
            raise click.Abort()

        skills_src = Path(orch_root) / 'skills' / 'src'
        if not skills_src.exists():
            click.echo(f"❌ Skills source not found: {skills_src}", err=True)
            click.echo("   Expected: orch-knowledge/skills/src/", err=True)
            raise click.Abort()

        # Output locations
        global_skills_dir = Path.home() / '.claude' / 'skills'
        project_skills_dir = Path(orch_root) / '.claude' / 'skills'

        # Categories and their output locations
        # All skill categories deploy to global (~/.claude/skills/)
        global_categories = ['worker', 'shared', 'utilities', 'meta', 'policy']
        project_categories = []  # Reserved for future project-scoped skills

        built_count = 0
        deployed_count = 0
        skipped_count = 0

        # Step 1: Build templated skills (those with src/SKILL.md.template)
        template_files = list(skills_src.glob('*/*/src/SKILL.md.template'))

        if template_files:
            click.echo(f"📦 Building {len(template_files)} templated skill(s)...")
            click.echo()

            for template_file in template_files:
                skill_dir = template_file.parent.parent
                skill_name = skill_dir.name
                category = skill_dir.parent.name

                # Load phase files
                phases_dir = template_file.parent / 'phases'
                phase_templates = {}

                if phases_dir.exists():
                    for phase_file in phases_dir.glob('*.md'):
                        phase_name = phase_file.stem
                        try:
                            with open(phase_file, 'r', encoding='utf-8') as f:
                                phase_templates[phase_name] = f.read()
                        except Exception as e:
                            click.echo(f"⚠️  Warning: Could not load phase {phase_name}: {e}", err=True)

                # Read template
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                except Exception as e:
                    click.echo(f"❌ Error reading {template_file}: {e}", err=True)
                    continue

                # Parse and replace templates
                def replace_template(match):
                    template_name = match.group(1)
                    if template_name not in phase_templates:
                        click.echo(f"⚠️  Warning: Phase '{template_name}' not found for {skill_name}", err=True)
                        return match.group(0)

                    phase_content = phase_templates[template_name]
                    replacement = f'<!-- SKILL-TEMPLATE: {template_name} -->\n'
                    replacement += f'<!-- Auto-generated from src/phases/{template_name}.md -->\n\n'
                    replacement += phase_content.strip()
                    replacement += '\n\n<!-- /SKILL-TEMPLATE -->'
                    return replacement

                pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'
                new_content = re.sub(pattern, replace_template, template_content, flags=re.DOTALL)

                # Insert auto-generated header
                header_comment = (
                    "<!-- AUTO-GENERATED: Do not edit this file directly. "
                    "Source: src/SKILL.md.template + src/phases/*.md. "
                    "Build with: orch build --skills -->"
                )
                header_block = (
                    "> AUTO-GENERATED SKILL FILE\n"
                    "> Source: src/SKILL.md.template + src/phases/*.md\n"
                    "> Build command: orch build --skills\n"
                    "> Do NOT edit this file directly; edit the sources and rebuild."
                )

                if "AUTO-GENERATED SKILL FILE" not in new_content:
                    header = f"{header_comment}\n\n{header_block}\n\n"

                    if new_content.startswith("---"):
                        frontmatter_end = new_content.find("\n---", 3)
                        if frontmatter_end != -1:
                            insert_pos = frontmatter_end + len("\n---")
                            before = new_content[:insert_pos]
                            after = new_content[insert_pos:]
                            new_content = before + "\n\n" + header + after.lstrip("\n")
                        else:
                            new_content = header + new_content
                    else:
                        new_content = header + new_content

                # Output to source directory (will be deployed later)
                output_file = skill_dir / 'SKILL.md'
                display_path = str(output_file).replace(str(orch_root), 'orch-knowledge')

                changed = True
                if output_file.exists():
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            current_content = f.read()
                        changed = new_content != current_content
                    except:
                        pass

                if check:
                    if changed:
                        click.echo(f"⚠️  {display_path} - Needs rebuild")
                        built_count += 1
                    else:
                        skipped_count += 1
                elif dry_run:
                    if changed:
                        click.echo(f"🔨 {display_path} - Would rebuild")
                        built_count += 1
                    else:
                        skipped_count += 1
                else:
                    if changed:
                        try:
                            with open(output_file, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            click.echo(f"✅ Built: {category}/{skill_name}")
                            if phase_templates:
                                click.echo(f"   Phases: {', '.join(sorted(phase_templates.keys()))}")
                            built_count += 1
                        except Exception as e:
                            click.echo(f"❌ Error writing {output_file}: {e}", err=True)
                    else:
                        skipped_count += 1

        # Step 2: Deploy skills to output locations
        click.echo()
        click.echo("📦 Deploying skills to output locations...")
        click.echo()

        def deploy_skill(src_skill_dir: Path, dest_dir: Path, skill_name: str, category: str):
            """Deploy a skill directory to destination, creating symlink for Claude discovery."""
            nonlocal deployed_count, skipped_count

            dest_category_dir = dest_dir / category
            dest_skill_dir = dest_category_dir / skill_name

            # Check if SKILL.md exists in source
            src_skill_md = src_skill_dir / 'SKILL.md'
            if not src_skill_md.exists():
                click.echo(f"⚠️  Skipping {category}/{skill_name} - no SKILL.md", err=True)
                return

            display_dest = str(dest_skill_dir).replace(str(Path.home()), '~')

            if check:
                # Check if destination exists and is current
                dest_skill_md = dest_skill_dir / 'SKILL.md'
                if dest_skill_md.exists():
                    try:
                        with open(src_skill_md, 'r') as s, open(dest_skill_md, 'r') as d:
                            if s.read() == d.read():
                                skipped_count += 1
                                return
                    except:
                        pass
                click.echo(f"⚠️  {display_dest} - Needs update")
                deployed_count += 1
                return

            if dry_run:
                click.echo(f"📦 Would deploy: {category}/{skill_name} -> {display_dest}")
                deployed_count += 1
                return

            # Actually deploy
            try:
                # Ensure category directory exists
                dest_category_dir.mkdir(parents=True, exist_ok=True)

                # Remove existing destination if it exists
                if dest_skill_dir.exists():
                    if dest_skill_dir.is_symlink():
                        dest_skill_dir.unlink()
                    else:
                        shutil.rmtree(dest_skill_dir)

                # Copy skill directory
                shutil.copytree(src_skill_dir, dest_skill_dir, dirs_exist_ok=True)

                # Make SKILL.md read-only to prevent accidental edits to distribution
                # Agents should edit skills/src/, not ~/.claude/skills/
                dest_skill_md = dest_skill_dir / 'SKILL.md'
                if dest_skill_md.exists():
                    dest_skill_md.chmod(0o444)

                # Create top-level symlink for Claude Code discovery
                alias_path = dest_dir / skill_name
                if not alias_path.exists():
                    alias_path.symlink_to(dest_skill_dir.relative_to(dest_dir))

                click.echo(f"✅ Deployed: {category}/{skill_name}")
                deployed_count += 1

            except Exception as e:
                click.echo(f"❌ Error deploying {skill_name}: {e}", err=True)

        # Deploy global skills (worker, shared, utilities, meta)
        for category in global_categories:
            category_dir = skills_src / category
            if not category_dir.exists():
                continue

            for skill_dir in sorted(category_dir.iterdir()):
                if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                    deploy_skill(skill_dir, global_skills_dir, skill_dir.name, category)

        # Deploy project skills (orchestrator)
        for category in project_categories:
            category_dir = skills_src / category
            if not category_dir.exists():
                continue

            for skill_dir in sorted(category_dir.iterdir()):
                if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                    deploy_skill(skill_dir, project_skills_dir, skill_dir.name, category)

        click.echo()

        # Summary
        if check:
            total_needing_update = built_count + deployed_count
            if total_needing_update == 0:
                click.echo("✅ All skills are current")
            else:
                click.echo(f"⚠️  {total_needing_update} skill(s) need updating")
        elif dry_run:
            click.echo(f"📋 Dry-run: {built_count} would build, {deployed_count} would deploy")
        else:
            click.echo(f"✅ Skills: {built_count} built, {deployed_count} deployed")

    # Doc sync check (runs after all builds, not in --check mode)
    if not check and not dry_run:
        orch_root = find_orch_root()
        if orch_root:
            reference_path = Path(orch_root) / '.orch' / 'cli-reference.json'
            if reference_path.exists():
                from orch.doc_check import check_doc_sync
                click.echo()
                click.echo("📖 Checking CLI documentation sync...")
                in_sync, issues = check_doc_sync(cli, reference_path, verbose=False)
                if in_sync:
                    click.echo("✓ CLI documentation is in sync")
                else:
                    click.echo("⚠️  CLI documentation drift detected:")
                    for issue in issues:
                        click.echo(f"   {issue}")
                    click.echo()
                    click.echo("💡 Run 'orch doc-gen' to update the reference")


# ============================================================================
# Build subcommands - hierarchical structure under 'orch build'
# ============================================================================

@build.command(name='skills')
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.pass_context
def build_skills_cmd(ctx, dry_run, check):
    """Build skill SKILL.md files from templates.

    Processes templated skills (those with src/SKILL.md.template) and deploys
    all skills to their output locations (~/.claude/skills/ for global,
    .claude/skills/ for project-scoped).

    \b
    Examples:
      orch build skills               # Build and deploy skills
      orch build skills --dry-run     # Preview changes
      orch build skills --check       # Check if rebuild needed
    """
    # Re-invoke the build function with only skills target
    ctx.invoke(build, target_skills=True, dry_run=dry_run, check=check)


@build.command(name='readme')
@click.option('--dry-run', is_flag=True, help='Preview README without writing')
@click.option('--project', help='Project directory (defaults to current dir)')
@click.pass_context
def build_readme_cmd(ctx, dry_run, project):
    """Auto-generate .orch/README.md from artifact metadata.

    Scans .orch/ directory and generates index of:
    - Recent Decisions (last 14 days)
    - Recent Investigations (last 7 days)
    - Active Workspaces
    - Statistics

    \b
    Examples:
      orch build readme                # Generate README for current project
      orch build readme --dry-run      # Preview without writing
      orch build readme --project ~/foo
    """
    ctx.invoke(build_readme, dry_run=dry_run, project=project)


@build.command(name='global')
@click.option('--dry-run', is_flag=True, help='Show what would be synced without making changes')
@click.pass_context
def build_global_cmd(ctx, dry_run):
    """Sync global templates to ~/.orch/templates/.

    Copies templates from templates-src/ to ~/.orch/templates/, including
    subdirectories like investigations/. This ensures orch create-investigation
    and other template-based commands have access to current templates.

    \b
    Source: {orch-knowledge}/templates-src/
    Target: ~/.orch/templates/

    \b
    Examples:
      orch build global               # Sync templates
      orch build global --dry-run     # Preview changes
    """
    import shutil
    from pathlib import Path

    # Use canonical templates location (global operation → global source)
    templates_src = Path.home() / 'orch-knowledge' / 'templates-src'
    if not templates_src.exists():
        click.echo("❌ Templates source not found: ~/orch-knowledge/templates-src/", err=True)
        click.echo("   This is the canonical location for orchestration templates.", err=True)
        click.echo("   Ensure orch-knowledge repository exists in your home directory.", err=True)
        raise click.Abort()

    templates_dest = Path.home() / '.orch' / 'templates'

    click.echo("🔨 Syncing global templates...")
    click.echo(f"   Source: {templates_src}")
    click.echo(f"   Target: {templates_dest}")
    click.echo()

    # Ensure destination exists
    if not dry_run:
        templates_dest.mkdir(parents=True, exist_ok=True)

    synced_count = 0
    skipped_count = 0

    # Sync all .md files in templates-src/
    for src_file in templates_src.glob('*.md'):
        dest_file = templates_dest / src_file.name

        # Check if sync needed
        if dest_file.exists():
            src_mtime = src_file.stat().st_mtime
            dest_mtime = dest_file.stat().st_mtime
            if dest_mtime >= src_mtime:
                skipped_count += 1
                continue

        if dry_run:
            click.echo(f"  Would copy: {src_file.name}")
        else:
            shutil.copy2(src_file, dest_file)
            click.echo(f"  ✅ Copied: {src_file.name}")
        synced_count += 1

    # Sync subdirectories (e.g., investigations/)
    for src_subdir in templates_src.iterdir():
        if src_subdir.is_dir() and not src_subdir.name.startswith('.'):
            dest_subdir = templates_dest / src_subdir.name

            if not dry_run:
                dest_subdir.mkdir(parents=True, exist_ok=True)

            click.echo(f"  📁 {src_subdir.name}/")

            for src_file in src_subdir.glob('*.md'):
                dest_file = dest_subdir / src_file.name

                # Check if sync needed
                if dest_file.exists():
                    src_mtime = src_file.stat().st_mtime
                    dest_mtime = dest_file.stat().st_mtime
                    if dest_mtime >= src_mtime:
                        skipped_count += 1
                        continue

                if dry_run:
                    click.echo(f"    Would copy: {src_file.name}")
                else:
                    shutil.copy2(src_file, dest_file)
                    click.echo(f"    ✅ Copied: {src_file.name}")
                synced_count += 1

    click.echo()
    if dry_run:
        click.echo(f"📋 Dry-run: {synced_count} file(s) would be synced, {skipped_count} up-to-date")
    else:
        click.echo(f"✅ Templates: {synced_count} synced, {skipped_count} up-to-date")


# ============================================================================
# Projects group - hierarchical structure for project discovery
# ============================================================================

@cli.group()
def projects():
    """Project discovery and management commands.

    \b
    Subcommands:
      scan     Scan for initialized .orch projects
      list     List known initialized projects

    \b
    Examples:
      orch projects scan              # Scan for projects
      orch projects list              # List known projects
    """
    pass


@projects.command(name='scan')
@click.pass_context
def projects_scan(ctx):
    """Scan for initialized .orch projects and update cache.

    Searches standard project directories for .orch/CLAUDE.md files
    and caches the results in ~/.orch/initialized-projects.json

    \b
    Examples:
      orch projects scan              # Scan for projects
    """
    ctx.invoke(scan_projects_cmd)


@projects.command(name='list')
def projects_list():
    """List known initialized projects from cache.

    Shows projects previously found by 'orch projects scan'.

    \b
    Examples:
      orch projects list              # List known projects
    """
    from orch.project_discovery import read_cache
    from orch.config import get_initialized_projects_cache

    cache_file = get_initialized_projects_cache()
    projects = read_cache(cache_file)

    if not projects:
        click.echo("No initialized projects found in cache.")
        click.echo("Run 'orch projects scan' to discover projects.")
        return

    click.echo(f"📁 Initialized projects ({len(projects)}):")
    click.echo()
    for project in projects:
        display_path = str(project).replace(str(Path.home()), '~')
        click.echo(f"  • {display_path}")



# =============================================================================
# Documentation Sync Commands
# =============================================================================

@cli.command('doc-check')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed diff including option changes')
def doc_check(verbose):
    """Check if CLI documentation is in sync with code.

    Compares the current CLI commands and options against the documented
    reference in .orch/cli-reference.json. Warns if there's drift.

    \b
    Use after adding new commands/options to catch documentation gaps.
    Run 'orch doc-gen' to update the reference when drift is detected.
    """
    from orch.doc_check import check_doc_sync

    # Find .orch directory
    orch_root = find_orch_root()
    if not orch_root:
        click.echo("❌ Not in an orchestrated project (no .orch directory found)", err=True)
        raise click.Abort()

    reference_path = Path(orch_root) / '.orch' / 'cli-reference.json'

    if not reference_path.exists():
        click.echo("⚠️  No CLI reference found. Run 'orch doc-gen' to create one.")
        raise click.Abort()

    in_sync, issues = check_doc_sync(cli, reference_path, verbose=verbose)

    if in_sync:
        click.echo("✓ CLI documentation is in sync")
    else:
        click.echo("⚠️  CLI documentation drift detected:")
        for issue in issues:
            click.echo(f"   {issue}")
        click.echo()
        click.echo("Run 'orch doc-gen' to update the reference")
        raise SystemExit(1)


@cli.command('doc-gen')
@click.option('--output', '-o', type=click.Path(), help='Output directory (default: .orch/)')
@click.option('--format', 'formats', multiple=True, type=click.Choice(['json', 'markdown']),
              help='Output format(s). Default: both json and markdown')
def doc_gen(output, formats):
    """Generate CLI reference documentation from code.

    Introspects all orch commands and options, then generates reference
    files that stay in sync with the actual CLI.

    \b
    Generated files:
      cli-reference.json  - Machine-readable for sync checking
      cli-reference.md    - Human-readable for AI context

    \b
    The markdown file can be referenced from CLAUDE.md:
      "For CLI details, see .orch/cli-reference.md"
    """
    from orch.doc_check import generate_reference_files

    # Determine output directory
    if output:
        output_dir = Path(output)
    else:
        orch_root = find_orch_root()
        if orch_root:
            output_dir = Path(orch_root) / '.orch'
        else:
            output_dir = Path.cwd()

    # Determine formats
    if not formats:
        formats = ['json', 'markdown']
    else:
        formats = list(formats)

    generated = generate_reference_files(cli, output_dir, formats)

    click.echo(f"✓ Generated CLI reference:")
    for path in generated:
        click.echo(f"   {path}")



if __name__ == '__main__':
    cli()
