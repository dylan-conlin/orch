import click
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional
from orch.registry import AgentRegistry
from orch.tmux_utils import list_windows, find_session, is_tmux_available, get_window_by_target
from orch.monitor import check_agent_status, get_status_emoji
from orch.logging import OrchLogger
from orch.complete import verify_agent_work, clean_up_agent
from orch.help import show_help_overview, show_help_topic, show_unknown_topic, HELP_TOPICS
from orch.workspace import is_unmodified_template, extract_tldr

# Import from path_utils to break circular dependencies
# (cli -> complete -> spawn -> cli and cli -> complete -> spawn -> investigations -> cli)
# Re-export for backward compatibility
from orch.path_utils import get_git_root, find_orch_root, detect_and_display_context

# Import command modules for registration
from orch.spawn_commands import register_spawn_commands
from orch.monitoring_commands import register_monitoring_commands
from orch.workspace_commands import register_workspace_commands

@click.group()
def cli():
    """Orchestration monitoring and coordination tools."""
    pass

# Register commands from external modules
register_spawn_commands(cli)
register_monitoring_commands(cli)
register_workspace_commands(cli)

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

@cli.command()
@click.option('--web', is_flag=True, help='Launch web UI instead of TUI')
@click.option('--host', default='127.0.0.1', help='Host to bind to (for --web)')
@click.option('--port', default=8000, type=int, help='Port to bind to (for --web)')
def dashboard(web, host, port):
    """Launch dashboard for agent monitoring.

    By default, launches keyboard-first TUI dashboard.
    Use --web to launch the web UI instead.

    \b
    Examples:
      orch dashboard              # TUI dashboard
      orch dashboard --web        # Web UI on localhost:8000
      orch dashboard --web --port 3000
    """
    if web:
        from orch.serve import start_server
        start_server(host=host, port=port)
    else:
        from orch.dashboard.ui import Dashboard
        dashboard_ui = Dashboard()
        dashboard_ui.run()


def _should_clean_agent(agent: dict, clean_all: bool, pattern_violations: bool, check_status_func) -> bool:
    """
    Determine whether an agent should be cleaned based on mode.

    Args:
        agent: Agent dictionary from registry
        clean_all: True if --all flag was specified
        pattern_violations: True if --pattern-violations flag was specified
        check_status_func: Function to check agent workspace status (injected for testability)

    Returns:
        True if agent should be cleaned, False otherwise
    """
    status_val = agent.get('status', 'unknown')

    # Pattern violations mode: only clean orphaned/malformed agents
    if pattern_violations:
        if status_val in ('terminated', 'abandoned'):
            return True
        # Check for orphaned agents (no workspace file)
        if 'project_dir' in agent and 'workspace' in agent:
            workspace_status = check_status_func(agent)
            if workspace_status.phase == 'Unknown':
                return True
        return False

    # --all mode: clean everything cleanable
    if clean_all:
        if status_val in ('abandoned', 'terminated', 'completed', 'completing'):
            return True
        if 'project_dir' in agent and 'workspace' in agent:
            workspace_status = check_status_func(agent)
            if workspace_status.phase in ('Complete', 'Unknown', 'Abandoned'):
                return True
        return False

    # Default mode: conservative cleanup
    if status_val in ('abandoned', 'terminated'):
        return True

    # Check workspace phase for agents with workspace fields
    if 'project_dir' in agent and 'workspace' in agent:
        workspace_status = check_status_func(agent)
        if workspace_status.phase == 'Complete':
            return True
        if workspace_status.phase == 'Unknown' and status_val == 'completed':
            return True
        if status_val == 'completed':
            return True
        return False

    # Legacy agent without workspace fields
    if status_val == 'completed':
        return True

    return False


@cli.command()
@click.option('--all', is_flag=True, help='Clean all completed/terminated agents (not just Phase: Complete)')
@click.option('--pattern-violations', is_flag=True, help='Clean agents with pattern violations (missing workspaces, terminated)')
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned without executing')
def clean(all, pattern_violations, dry_run):
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

    # Filter agents based on flags
    completed_agents = [
        agent for agent in all_agents
        if _should_clean_agent(agent, all, pattern_violations, check_agent_status)
    ]

    # Log clean start
    orch_logger.log_command_start("clean", {
        "total_agents": len(all_agents),
        "completed_agents": len(completed_agents)
    })

    if not completed_agents:
        orch_logger.log_event("clean", "No completed agents to clean", {
            "total_agents": len(all_agents)
        }, level="INFO")
        click.echo("No completed agents to clean.")
        return

    # Dry run: show what would be cleaned
    if dry_run:
        click.echo(f"Would clean {len(completed_agents)} agent(s):\n")
        for agent in completed_agents:
            workspace = agent.get('workspace', 'N/A')
            status = agent.get('status', 'unknown')
            click.echo(f"  • {agent['id']}")
            click.echo(f"    Status: {status}")
            click.echo(f"    Workspace: {workspace}\n")
        click.echo(f"Run without --dry-run to execute cleanup.")
        return

    # Close tmux windows and remove from registry
    cleaned_count = 0
    for agent in completed_agents:
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
            "reason": "completed"
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
        "skipped": len(all_agents) - len(completed_agents)
    })

    # Show summary
    click.echo(f"✅ Cleaned {cleaned_count} completed agent(s).")


@cli.command()
@click.argument('agent_ids', nargs=-1, required=True)
@click.option('--reason', help='Reason for abandonment')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
def abandon(agent_ids, reason, force):
    """
    Abandon stuck or frozen agents.

    Marks agents as abandoned, closes tmux windows, and optionally archives workspaces.
    Use this when agents are stuck and cannot complete normally.

    Examples:
      orch abandon agent-id
      orch abandon agent-id --reason "Timeout: No progress for 30 minutes"
      orch abandon agent-id --force
      orch abandon agent-1 agent-2 agent-3
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

    # Confirm unless --force
    if not force:
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


def _auto_detect_roadmap(project_dir: Path, roadmap: Optional[str] = None) -> Optional[Path]:
    """
    Auto-detect ROADMAP.org path for project.

    Args:
        project_dir: Project directory path
        roadmap: Optional explicit roadmap path

    Returns:
        Path to ROADMAP.org file if found, None otherwise.
        None indicates the project uses backlog.json instead of ROADMAP.org,
        and agents should be treated as ad-hoc (no ROADMAP update on completion).
    """
    if roadmap:
        return Path(roadmap)

    # Search configured roadmap paths first
    from orch.config import get_roadmap_paths
    for candidate in get_roadmap_paths():
        if candidate.exists():
            return candidate

    # Fall back to project-level locations
    candidate = project_dir / "ROADMAP.org"
    if candidate.exists():
        return candidate

    candidate2 = project_dir / "docs" / "ROADMAP.org"
    if candidate2.exists():
        return candidate2

    candidate3 = project_dir / ".orch" / "ROADMAP.org"
    if candidate3.exists():
        return candidate3

    # Return None instead of aborting - allows backlog.json-only projects
    return None


@cli.command()
@click.argument('agent_id', required=False)
@click.option('--roadmap', type=click.Path(exists=True), help='Path to ROADMAP.org (auto-detected if not specified)')
@click.option('--allow-roadmap-miss', is_flag=True, help='Proceed with cleanup even if ROADMAP item not found')
@click.option('--dry-run', is_flag=True, help='Show what would happen without executing')
@click.option('--all', 'complete_all', is_flag=True, help='Complete all ready agents (READY_COMPLETE or READY_CLEAN scenarios)')
@click.option('--project', help='Filter agents by project directory (used with --all)')
@click.option('--skip-test-check', is_flag=True, help='Skip test verification check (use when pre-existing test failures block completion)')
@click.option('--force', is_flag=True, help='Bypass safety checks (active processes, git state) - use when work complete but session hung')
@click.option('--sync', 'sync_mode', is_flag=True, help='Run completion synchronously (blocking, wait for cleanup)')
@click.option('--async', 'async_mode', is_flag=True, hidden=True, help='[DEPRECATED] Async is now the default. This flag has no effect.')
def complete(agent_id, roadmap, allow_roadmap_miss, dry_run, complete_all, project, skip_test_check, force, sync_mode, async_mode):
    """
    Complete agent work: verify, update ROADMAP (if applicable), commit, cleanup.

    Auto-detects whether agent is ROADMAP-based or ad-hoc, then runs appropriate workflow:

    For ROADMAP agents:
    1. Verify agent work (Phase: Complete, deliverables exist)
    2. Update ROADMAP.org (mark DONE, add CLOSED timestamp)
    3. Git commit ROADMAP update
    4. Clean up agent and close tmux window

    For ad-hoc agents:
    1. Verify agent work (Phase: Complete, deliverables exist)
    2. Clean up agent and close tmux window

    Example:
        orch complete my-agent-workspace
        orch complete investigate-bug-123  # Works for both ROADMAP and ad-hoc
    """
    from orch.complete import complete_agent_work
    from orch.monitor import check_agent_status, Scenario

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
                # Auto-detect ROADMAP
                project_dir = Path(agent_info['project_dir'])
                roadmap_path = _auto_detect_roadmap(project_dir, roadmap)

                result = complete_agent_work(
                    agent_id=agent_id_batch,
                    project_dir=project_dir,
                    roadmap_path=roadmap_path,
                    allow_roadmap_miss=allow_roadmap_miss,
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

    # Auto-detect ROADMAP
    roadmap_path = _auto_detect_roadmap(project_dir, roadmap)

    click.echo()
    click.echo(f"🔍 Completing: {agent_id}")
    click.echo(f"   Project: {project_dir}")
    if roadmap_path:
        click.echo(f"   ROADMAP: {roadmap_path}")
    else:
        click.echo("   ROADMAP: (none - using backlog.json)")
    click.echo()

    # Run complete workflow (async by default, sync if --sync flag or --dry-run provided)
    # Note: dry_run forces sync mode because async spawns daemon that ignores dry_run
    if not sync_mode and not dry_run:
        # Default: async mode (non-blocking)
        from orch.complete import complete_agent_async

        result = complete_agent_async(
            agent_id=agent_id,
            project_dir=project_dir,
            roadmap_path=roadmap_path
        )
    else:
        # Opt-in: sync mode (blocking)
        result = complete_agent_work(
            agent_id=agent_id,
            project_dir=project_dir,
            roadmap_path=roadmap_path,
            allow_roadmap_miss=allow_roadmap_miss,
            dry_run=dry_run,
            skip_test_check=skip_test_check,
            force=force
        )

    # Display results
    if result['success']:
        if result.get('async_mode'):
            # Async mode - daemon spawned
            click.echo("✅ Agent marked for completion. Cleanup running in background.")
            click.echo()
            click.echo(f"   ✓ Agent status: completing")
            click.echo(f"   ✓ Daemon PID: {result['daemon_pid']}")
            click.echo()
            click.echo("   Use 'orch status' to monitor completion progress")
        elif result.get('dry_run'):
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
            if result['roadmap_updated']:
                click.echo("   ✓ ROADMAP marked DONE (ROADMAP-based agent)")
                if result['committed']:
                    click.echo("   ✓ Changes committed to git")
            else:
                click.echo("   ✓ Ad-hoc agent (no ROADMAP update)")
            click.echo("   ✓ Agent cleaned up")

            # Handle investigation backlink - prompt to mark investigation resolved
            if result.get('investigation_backlink'):
                backlink = result['investigation_backlink']
                click.echo()
                click.echo(f"   📋 Investigation backlink detected:")
                click.echo(f"      All {backlink['feature_count']} feature(s) from this investigation are complete.")
                click.echo(f"      Investigation: {backlink['investigation_path']}")
                if click.confirm("      Mark investigation as resolved?", default=True):
                    from orch.investigations import mark_investigation_resolved, InvestigationError
                    inv_path = project_dir / backlink['investigation_path']
                    try:
                        mark_investigation_resolved(inv_path)
                        click.echo("   ✓ Investigation marked as Resolved")
                    except InvestigationError as e:
                        click.echo(f"   ⚠️  Could not update investigation: {e}")

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


@cli.command(hidden=True)
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, type=int, help='Port to bind to')
def serve(host, port):
    """Start the orch dashboard web UI.

    DEPRECATED: Use 'orch dashboard --web' instead.

    Starts a web server providing real-time agent monitoring, roadmap
    visualization, and artifact exploration.

    \b
    Requirements:
      - Frontend must be built first: cd web/frontend && npm run build
      - Backend dependencies installed: pip install -r web/backend/requirements.txt

    \b
    Example:
      orch serve                    # Start on http://localhost:8000
      orch serve --port 3000        # Start on custom port
    """
    from orch.serve import start_server

    start_server(host=host, port=port)


@cli.command(name='sync-templates', hidden=True)
@click.option('--check', is_flag=True, help='Check if templates are outdated without syncing')
@click.option('--dry-run', is_flag=True, help='Show what would be synced without making changes')
def sync_templates(check, dry_run):
    """
    Sync workspace templates from package to ~/.orch/templates/

    DEPRECATED: Use 'orch build --sync' instead.

    Copies template files from the meta-orchestration repository to your
    local ~/.orch/templates/ directory. Run this after updating templates
    in the meta-orchestration repo to ensure new projects use the latest
    templates.

    \b
    Examples:
      orch sync-templates              # Sync all templates
      orch sync-templates --check      # Check which templates are outdated
      orch sync-templates --dry-run    # Preview what would be synced
    """
    from pathlib import Path
    import shutil

    # Source: package templates (works with editable install via pip install -e .)
    # Path is: <package>/.orch/templates/
    package_dir = Path(__file__).parent.parent.parent / '.orch' / 'templates'

    # Destination: user's orchestration directory
    dest_dir = Path.home() / '.orch' / 'templates'

    # Validate source exists
    if not package_dir.exists():
        click.echo(f"❌ Template source directory not found: {package_dir}", err=True)
        click.echo("   Expected in meta-orchestration/.orch/templates/", err=True)
        raise click.Abort()

    # Find template files
    template_files = list(package_dir.glob('*.md'))
    if not template_files:
        click.echo(f"⚠️  No template files found in {package_dir}", err=True)
        return

    # Check mode: report status without syncing
    if check:
        click.echo()
        click.echo(f"📋 Template Status ({len(template_files)} templates)")
        click.echo()

        for tmpl in sorted(template_files):
            dest = dest_dir / tmpl.name
            if not dest.exists():
                click.echo(f"❌ Missing:   {tmpl.name}")
            elif dest.stat().st_mtime < tmpl.stat().st_mtime:
                click.echo(f"⚠️  Outdated:  {tmpl.name}")
            else:
                click.echo(f"✅ Current:   {tmpl.name}")
        click.echo()
        return

    # Dry-run mode: show what would be synced
    if dry_run:
        click.echo()
        click.echo(f"🔍 Dry-run: Would sync {len(template_files)} template(s)")
        click.echo(f"   From: {package_dir}")
        click.echo(f"   To:   {dest_dir}")
        click.echo()

        for tmpl in sorted(template_files):
            dest = dest_dir / tmpl.name
            if not dest.exists():
                click.echo(f"   Would create: {tmpl.name}")
            elif dest.stat().st_mtime < tmpl.stat().st_mtime:
                click.echo(f"   Would update: {tmpl.name}")
            else:
                click.echo(f"   Would skip:   {tmpl.name} (already current)")
        click.echo()
        return

    # Sync mode: copy templates
    dest_dir.mkdir(parents=True, exist_ok=True)

    click.echo()
    click.echo(f"📋 Syncing {len(template_files)} template(s)...")
    click.echo(f"   From: {package_dir}")
    click.echo(f"   To:   {dest_dir}")
    click.echo()

    synced_count = 0
    skipped_count = 0

    for tmpl in sorted(template_files):
        dest = dest_dir / tmpl.name

        # Skip if destination is already current
        if dest.exists() and dest.stat().st_mtime >= tmpl.stat().st_mtime:
            click.echo(f"   ⏭️  Skipped: {tmpl.name} (already current)")
            skipped_count += 1
            continue

        # Copy template (preserves metadata with copy2)
        shutil.copy2(tmpl, dest)
        action = "Updated" if dest.exists() else "Created"
        click.echo(f"   ✅ {action}: {tmpl.name}")
        synced_count += 1

    click.echo()
    click.echo(f"✅ Sync complete: {synced_count} synced, {skipped_count} skipped")
    click.echo()


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


@cli.command(name='lint')
@click.option('--file', type=click.Path(exists=True), help='Specific CLAUDE.md file to check')
@click.option('--all', 'check_all', is_flag=True, help='Check all known CLAUDE.md files')
@click.option('--instructions', is_flag=True, help='Check orchestrator instruction drift (missing instructions)')
def lint(file, check_all, instructions):
    """
    Check CLAUDE.md files against token and character size limits, or check instruction drift.

    Default mode validates that CLAUDE.md files stay within recommended limits:
    - Global (~/.claude/CLAUDE.md): 5,000 tokens, 20,000 chars
    - Project (project/CLAUDE.md): 15,000 tokens, 60,000 chars
    - Orchestrator (project/.orch/CLAUDE.md): 15,000 tokens, 40,000 chars

    Both limits must be satisfied for a file to pass.

    With --instructions, checks for missing orchestrator instructions in current project.

    \b
    Examples:
      orch lint                             # Check CLAUDE.md in current project
      orch lint --file ~/.claude/CLAUDE.md  # Check specific file
      orch lint --all                       # Check all known CLAUDE.md files
      orch lint --instructions              # Check for missing instructions
    """
    from pathlib import Path

    # Handle --instructions mode
    if instructions:
        from orch.instructions import get_missing_instructions, get_current_instructions, get_available_instructions

        # Determine project path
        project_path = os.getcwd()
        git_root = get_git_root(project_path)
        if git_root:
            project_path = git_root

        # Check if project has .orch/CLAUDE.md
        claude_md_path = Path(project_path) / '.orch' / 'CLAUDE.md'
        if not claude_md_path.exists():
            click.echo("❌ No .orch/CLAUDE.md found in current project", err=True)
            click.echo(f"   Looked in: {project_path}", err=True)
            raise click.Abort()

        # Get instruction counts
        available = get_available_instructions()
        current = get_current_instructions(project_path)
        missing = get_missing_instructions(project_path)

        available_count = len(available)
        current_count = len(current)
        missing_count = len(missing)
        coverage_pct = int((current_count / available_count) * 100) if available_count > 0 else 0

        # Report
        project_name = Path(project_path).name
        click.echo(f"📋 Instruction drift check for {project_name}:")
        click.echo()
        click.echo(f"   ✅ Has {current_count}/{available_count} instructions ({coverage_pct}% coverage)")

        if missing_count > 0:
            click.echo(f"   ⚠️  Missing {missing_count} available instructions:")
            click.echo()
            for inst in missing:
                name = inst['name']
                description = inst.get('description', '')
                if description:
                    click.echo(f"      • {name}")
                    click.echo(f"        {description}")
                else:
                    click.echo(f"      • {name}")
            click.echo()
            click.echo("💡 To add: orch add-instruction <name>")
            click.echo("   Or list: orch list-instructions --missing")

            # Exit with error if significant drift (less than 70% coverage)
            if coverage_pct < 70:
                click.echo()
                click.echo(f"❌ Instruction coverage below 70% threshold")
                raise click.Abort()
        else:
            click.echo()
            click.echo("✅ No missing instructions - project has all available instructions!")

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


# ============================================================================
# Instruction group - consolidated instruction management commands
# ============================================================================

@cli.group()
def instruction():
    """Manage orchestrator instructions.

    \b
    Subcommands:
      list     List available/current/missing instructions
      add      Add instruction markers to project
      remove   Remove instruction from project
      upgrade  Upgrade all instructions to latest

    \b
    Examples:
      orch instruction list                  # Show all available
      orch instruction list --missing        # Show missing in project
      orch instruction add artifact-organization
      orch instruction remove artifact-organization
      orch instruction upgrade               # Add all missing
    """
    pass


@instruction.command(name='list')
@click.option('--current', is_flag=True, help='Show instructions currently in project CLAUDE.md')
@click.option('--missing', is_flag=True, help='Show instructions available but not in project')
@click.pass_context
def instruction_list(ctx, current, missing):
    """List available orchestrator instructions.

    \b
    Examples:
      orch instruction list           # Show all available
      orch instruction list --current # Show in current project
      orch instruction list --missing # Show missing (discovery)
    """
    ctx.invoke(list_instructions, current=current, missing=missing)


# Legacy command (hidden, for backward compatibility)
@cli.command(name='list-instructions', hidden=True)
@click.option('--current', is_flag=True, help='Show instructions currently in project CLAUDE.md')
@click.option('--missing', is_flag=True, help='Show instructions available but not in project')
def list_instructions(current, missing):
    """
    List available orchestrator instructions.

    By default, shows all available instructions from ~/.orch/templates/orchestrator/.
    Use --current to see which instructions are already in your project.
    Use --missing to see which instructions you don't have yet (key for discovery).

    \b
    Examples:
      orch list-instructions           # Show all available instructions
      orch list-instructions --current # Show instructions in current project
      orch list-instructions --missing # Show missing instructions (discovery)
    """
    from orch.instructions import (
        get_available_instructions,
        get_current_instructions,
        get_missing_instructions,
    )

    # Determine project path (current directory or find git root)
    project_path = os.getcwd()
    git_root = get_git_root(project_path)
    if git_root:
        project_path = git_root

    # Check if project has .orch/CLAUDE.md
    claude_md_path = Path(project_path) / '.orch' / 'CLAUDE.md'
    has_orch_context = claude_md_path.exists()

    if current:
        # Show current instructions in project
        if not has_orch_context:
            click.echo("❌ No .orch/CLAUDE.md found in current project", err=True)
            click.echo(f"   Looked in: {project_path}", err=True)
            raise click.Abort()

        current_instructions = get_current_instructions(project_path)

        if not current_instructions:
            click.echo("No instructions found in .orch/CLAUDE.md")
            click.echo()
            click.echo("💡 To add instructions: orch add-instruction <name>")
            return

        click.echo(f"📋 Current instructions in {Path(project_path).name} ({len(current_instructions)}):")
        click.echo()
        for inst_name in current_instructions:
            click.echo(f"  • {inst_name}")

        click.echo()
        click.echo(f"💡 To see missing instructions: orch list-instructions --missing")

    elif missing:
        # Show missing instructions
        if not has_orch_context:
            click.echo("❌ No .orch/CLAUDE.md found in current project", err=True)
            click.echo(f"   Looked in: {project_path}", err=True)
            raise click.Abort()

        missing_instructions = get_missing_instructions(project_path)

        if not missing_instructions:
            click.echo("✅ No missing instructions - project has all available instructions!")
            return

        click.echo(f"📋 Missing orchestrator instructions ({len(missing_instructions)}):")
        click.echo()

        for inst in missing_instructions:
            name = inst['name']
            description = inst.get('description', '')
            if description:
                click.echo(f"  • {name}")
                click.echo(f"    {description}")
            else:
                click.echo(f"  • {name}")

        click.echo()
        click.echo("💡 To add: orch add-instruction <name>")
        click.echo("   Or see all: orch list-instructions")

    else:
        # Show all available instructions
        available = get_available_instructions()

        if not available:
            click.echo("❌ No instructions found in ~/.orch/templates/orchestrator/", err=True)
            raise click.Abort()

        click.echo(f"📋 Available orchestrator instructions ({len(available)}):")
        click.echo()

        for inst in available:
            name = inst['name']
            description = inst.get('description', '')
            if description:
                click.echo(f"  • {name}")
                click.echo(f"    {description}")
            else:
                click.echo(f"  • {name}")

        click.echo()
        if has_orch_context:
            current_count = len(get_current_instructions(project_path))
            available_count = len(available)
            coverage_pct = int((current_count / available_count) * 100) if available_count > 0 else 0

            click.echo(f"📊 Project coverage: {current_count}/{available_count} instructions ({coverage_pct}%)")
            click.echo()

            if current_count < available_count:
                click.echo("💡 To see what's missing: orch list-instructions --missing")
        else:
            click.echo("💡 To see which are in your project: orch list-instructions --current")


def _run_build_orchestrator_context_for_project(project_path: str) -> None:
    """Helper to run build-orchestrator-context for a single project path."""
    click.echo("🔄 Injecting instruction content...")

    try:
        result = subprocess.run(
            ['orch', 'build-orchestrator-context', '--project', project_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            click.echo(f"✅ Instruction content injected successfully")
            click.echo()
            click.echo("💡 Next steps:")
            click.echo(f"   • Review changes: git diff .orch/")
            click.echo(f"   • Commit when ready: git add .orch/ && git commit")
        else:
            click.echo(f"⚠️  Build completed with warnings:", err=True)
            if result.stderr:
                click.echo(result.stderr, err=True)

    except Exception as e:
        click.echo(f"⚠️  Error running build: {e}", err=True)
        click.echo()
        click.echo("Marker updates applied but content not injected. Run manually:")
        click.echo(f"   orch build-orchestrator-context --project {project_path}")


@instruction.command(name='add')
@click.argument('instruction_name', required=False)
@click.option('--all-missing', is_flag=True, help='Add markers for all missing instructions in this project')
@click.pass_context
def instruction_add(ctx, instruction_name, all_missing):
    """Add instruction markers to project context files.

    \b
    Examples:
      orch instruction add artifact-organization
      orch instruction add --all-missing
    """
    ctx.invoke(add_instruction, instruction_name=instruction_name, all_missing=all_missing)


# Legacy command (hidden, for backward compatibility)
@cli.command(name='add-instruction', hidden=True)
@click.argument('instruction_name', required=False)
@click.option('--all-missing', is_flag=True, help='Add markers for all missing instructions in this project')
def add_instruction(instruction_name, all_missing):
    """
    Add orchestrator instruction markers to project context files.

    Default mode adds a single instruction marker to the project's
    .orch/CLAUDE.md, .orch/GEMINI.md, and .orch/AGENTS.md files (when present).

    With --all-missing, adds markers for all available instructions that are
    not yet present in the project (bulk add).

    This command:
    1. Validates the instruction(s) exist in ~/.orch/templates/orchestrator/
    2. Finds existing context files (CLAUDE.md, GEMINI.md, and/or AGENTS.md)
    3. Inserts marker pairs <!-- ORCH-INSTRUCTION: name --> ... <!-- /ORCH-INSTRUCTION -->
    4. Runs the build system to inject the instruction content

    Insertion priority:
    1. After last existing instruction marker
    2. Before <!-- PROJECT-SPECIFIC-START --> marker
    3. Fallback to a safe end-of-file position when no markers/PROJECT-SPECIFIC-START exist

    \b
    Examples:
      orch add-instruction artifact-organization
      orch add-instruction delegation-thresholds
      orch add-instruction --all-missing
    """
    from orch.instructions import (
        validate_instruction_exists,
        get_available_instructions,
        get_current_instructions,
        get_missing_instructions,
        find_insertion_point,
        get_project_context_files,
        create_empty_instruction_block,
    )

    # Validate argument/flag combination
    if all_missing and instruction_name:
        raise click.UsageError("Cannot use both a specific INSTRUCTION_NAME and --all-missing. Choose one.")
    if not all_missing and not instruction_name:
        raise click.UsageError("Must provide INSTRUCTION_NAME or use --all-missing.")

    # Determine project path
    project_path = os.getcwd()
    git_root = get_git_root(project_path)
    if git_root:
        project_path = git_root

    # Check if project has any context files
    context_files = get_project_context_files(project_path)
    if not context_files:
        click.echo("❌ No .orch/CLAUDE.md, .orch/GEMINI.md, or .orch/AGENTS.md found in current project", err=True)
        click.echo(f"   Looked in: {project_path}/.orch/", err=True)
        raise click.Abort()

    # Decide which instructions to add
    instructions_to_add = []
    if all_missing:
        missing = get_missing_instructions(project_path)
        if not missing:
            click.echo("✅ No missing instructions - project already has all available instructions!")
            return
        instructions_to_add = [inst['name'] for inst in missing]
        click.echo(f"📋 Adding {len(instructions_to_add)} missing instruction(s) to project context files...")
    else:
        # Validate specific instruction exists
        if not validate_instruction_exists(instruction_name):
            click.echo(f"❌ Instruction '{instruction_name}' not found in ~/.orch/templates/orchestrator/", err=True)
            click.echo()
            click.echo("Available instructions:")
            for inst in get_available_instructions():
                click.echo(f"  • {inst['name']}")
            raise click.Abort()

        # Check if instruction already exists (check CLAUDE.md as reference)
        current_instructions = get_current_instructions(project_path)
        if instruction_name in current_instructions:
            click.echo(f"⚠️  Instruction '{instruction_name}' already exists in context files")
            click.echo("   No changes made.")
            return

        instructions_to_add = [instruction_name]

    # Add markers to each context file for each instruction
    files_updated = []
    for name in instructions_to_add:
        marker_block = create_empty_instruction_block(name)

        for file_type, file_path in context_files:
            # Read current content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                click.echo(f"❌ Error reading {file_path}: {e}", err=True)
                raise click.Abort()

            # Find insertion point
            insertion_index, reason = find_insertion_point(content)

            if insertion_index is None:
                click.echo(f"❌ Could not find a safe insertion point in {file_path}", err=True)
                click.echo()
                click.echo("Expected one of:")
                click.echo("  • Existing instruction markers (<!-- ORCH-INSTRUCTION: ... --> or <!-- ORCH-TEMPLATE: ... -->)")
                click.echo("  • Project-specific section marker (<!-- PROJECT-SPECIFIC-START -->)")
                click.echo()
                click.echo(f"Please check your {file_path} file structure.")
                raise click.Abort()

            # Insert the marker block
            new_content = content[:insertion_index] + marker_block + content[insertion_index:]

            # Write back to file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_updated.append((file_type, name, reason))
            except Exception as e:
                click.echo(f"❌ Error writing to {file_path}: {e}", err=True)
                raise click.Abort()

    # Report what was updated
    if not files_updated:
        click.echo("⚠️  No instruction markers were added (nothing to do).")
    else:
        for file_type, name, reason in files_updated:
            click.echo(f"✅ Added instruction marker for '{name}' to .orch/{file_type}")
            click.echo(f"   Insertion location: {reason.replace('_', ' ')}")

    click.echo()
    _run_build_orchestrator_context_for_project(project_path)


@instruction.command(name='upgrade')
@click.pass_context
def instruction_upgrade(ctx):
    """Upgrade all instructions to latest.

    Adds all missing instructions and migrates legacy markers.

    \b
    Examples:
      orch instruction upgrade
    """
    ctx.invoke(upgrade_instructions)


# Legacy command (hidden, for backward compatibility)
@cli.command(name='upgrade-instructions', hidden=True)
def upgrade_instructions():
    """
    Upgrade orchestrator instruction markers in the current project.

    This is a semantic alias for:
      orch add-instruction --all-missing

    Additionally, it migrates legacy <!-- ORCH-TEMPLATE: ... --> markers to
    the newer <!-- ORCH-INSTRUCTION: ... --> form across all project context
    files (.orch/CLAUDE.md, .orch/GEMINI.md, .orch/AGENTS.md).

    Use this after updating global orchestrator templates or when adopting the
    multi-agent context flow to keep instructions consistent.
    """
    from orch.instructions import (
        get_missing_instructions,
        get_project_context_files,
        migrate_markers_to_instruction,
        find_insertion_point,
        create_empty_instruction_block,
    )

    # Determine project path
    project_path = os.getcwd()
    git_root = get_git_root(project_path)
    if git_root:
        project_path = git_root

    # Check if project has any context files
    context_files = get_project_context_files(project_path)
    if not context_files:
        click.echo("❌ No .orch/CLAUDE.md, .orch/GEMINI.md, or .orch/AGENTS.md found in current project", err=True)
        click.echo(f"   Looked in: {project_path}/.orch/", err=True)
        raise click.Abort()

    files_migrated = []

    # First, migrate existing markers from ORCH-TEMPLATE to ORCH-INSTRUCTION
    for file_type, file_path in context_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            click.echo(f"❌ Error reading {file_path}: {e}", err=True)
            raise click.Abort()

        new_content, changed = migrate_markers_to_instruction(content)
        if changed:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_migrated.append(file_type)
            except Exception as e:
                click.echo(f"❌ Error writing to {file_path}: {e}", err=True)
                raise click.Abort()

    if files_migrated:
        unique_types = sorted(set(files_migrated))
        click.echo(f"✅ Migrated legacy ORCH-TEMPLATE markers to ORCH-INSTRUCTION in: {', '.join(unique_types)}")

    # Next, add all missing instructions (bulk add)
    missing = get_missing_instructions(project_path)
    if not missing:
        click.echo("✅ No missing instructions - project already has all available instructions!")
        # Still run build to ensure migrated markers get updated content
        click.echo()
        _run_build_orchestrator_context_for_project(project_path)
        return

    instructions_to_add = [inst['name'] for inst in missing]
    click.echo(f"📋 Adding {len(instructions_to_add)} missing instruction(s) to project context files...")

    files_updated = []
    for name in instructions_to_add:
        marker_block = create_empty_instruction_block(name)

        for file_type, file_path in context_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                click.echo(f"❌ Error reading {file_path}: {e}", err=True)
                raise click.Abort()

            insertion_index, reason = find_insertion_point(content)
            if insertion_index is None:
                click.echo(f"❌ Could not find a safe insertion point in {file_path}", err=True)
                click.echo()
                click.echo("Expected one of:")
                click.echo("  • Existing instruction markers (<!-- ORCH-INSTRUCTION: ... --> or <!-- ORCH-TEMPLATE: ... -->)")
                click.echo("  • Project-specific section marker (<!-- PROJECT-SPECIFIC-START -->)")
                click.echo()
                click.echo(f"Please check your {file_path} file structure.")
                raise click.Abort()

            new_content = content[:insertion_index] + marker_block + content[insertion_index:]

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_updated.append((file_type, name, reason))
            except Exception as e:
                click.echo(f"❌ Error writing to {file_path}: {e}", err=True)
                raise click.Abort()

    for file_type, name, reason in files_updated:
        click.echo(f"✅ Added instruction marker for '{name}' to .orch/{file_type}")
        click.echo(f"   Insertion location: {reason.replace('_', ' ')}")

    click.echo()
    _run_build_orchestrator_context_for_project(project_path)


@instruction.command(name='remove')
@click.argument('instruction_name')
@click.pass_context
def instruction_remove(ctx, instruction_name):
    """Remove instruction from project.

    \b
    Examples:
      orch instruction remove artifact-organization
    """
    ctx.invoke(remove_instruction, instruction_name=instruction_name)


# Legacy command (hidden, for backward compatibility)
@cli.command(name='remove-instruction', hidden=True)
@click.argument('instruction_name')
def remove_instruction(instruction_name):
    """
    Remove an orchestrator instruction marker from project context files.

    Removes the instruction block (marker, content, and trailing separator)
    for the given instruction name across .orch/CLAUDE.md, .orch/GEMINI.md,
    and .orch/AGENTS.md when present, then rebuilds the orchestrator context.

    \b
    Examples:
      orch remove-instruction artifact-organization
    """
    from orch.instructions import (
        get_current_instructions,
        get_project_context_files,
        remove_instruction_from_content,
    )

    # Determine project path
    project_path = os.getcwd()
    git_root = get_git_root(project_path)
    if git_root:
        project_path = git_root

    # Check if project has any context files
    context_files = get_project_context_files(project_path)
    if not context_files:
        click.echo("❌ No .orch/CLAUDE.md, .orch/GEMINI.md, or .orch/AGENTS.md found in current project", err=True)
        click.echo(f"   Looked in: {project_path}/.orch/", err=True)
        raise click.Abort()

    # Verify instruction exists (using CLAUDE.md as reference)
    current_instructions = get_current_instructions(project_path)
    if instruction_name not in current_instructions:
        click.echo(f"⚠️  Instruction '{instruction_name}' not found in project context files")
        click.echo("   No changes made.")
        return

    files_updated = []
    for file_type, file_path in context_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            click.echo(f"❌ Error reading {file_path}: {e}", err=True)
            raise click.Abort()

        new_content, removed = remove_instruction_from_content(content, instruction_name)
        if not removed:
            continue

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            files_updated.append(file_type)
        except Exception as e:
            click.echo(f"❌ Error writing to {file_path}: {e}", err=True)
            raise click.Abort()

    if not files_updated:
        click.echo(f"⚠️  Instruction '{instruction_name}' was not removed from any context files (nothing matched).")
        return

    unique_types = sorted(set(files_updated))
    click.echo(f"✅ Removed instruction '{instruction_name}' from: {', '.join(unique_types)}")
    click.echo()
    _run_build_orchestrator_context_for_project(project_path)


@cli.command(name='build-orchestrator-context', hidden=True)
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.option('--project', type=click.Path(exists=True), help='Specific project directory to build')
@click.option('--rescan', is_flag=True, help='Rescan for projects before building')
def build_orchestrator_context(dry_run, check, project, rescan):
    """
    Build .orch/CLAUDE.md, .orch/GEMINI.md, and .orch/AGENTS.md files from templates.

    DEPRECATED: Use 'orch build context' instead.

    Replaces marked sections in .orch/CLAUDE.md, .orch/GEMINI.md, and .orch/AGENTS.md
    files with content from templates at ~/.orch/templates/orchestrator/. This allows
    sharing common orchestration patterns while keeping files self-contained.

    All three file types use the same templates and marker syntax, supporting multiple
    AI agent backends (Claude Code uses CLAUDE.md, Gemini CLI uses GEMINI.md,
    Codex uses AGENTS.md).

    Marker syntax (both supported, ORCH-INSTRUCTION preferred):
      <!-- ORCH-INSTRUCTION: template-name -->
      [Generated content will be placed here]
      <!-- /ORCH-INSTRUCTION -->

    \b
    Examples:
      orch build context              # Build all projects (new)
      orch build context --dry-run    # Preview changes
      orch build context --check      # Check if rebuild needed
    """
    import tiktoken
    import re
    from pathlib import Path

    # Token and character limits
    LIMITS = {'orchestrator': {'tokens': 15000, 'chars': 40000}}

    # Warning threshold (show warning when approaching limit)
    WARNING_THRESHOLD_CHARS = 36000  # Warn at 90% of limit

    # Initialize tokenizer
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        click.echo(f"❌ Failed to initialize tokenizer: {e}", err=True)
        raise click.Abort()

    def count_metrics(content):
        """Count tokens and characters in content."""
        tokens = encoding.encode(content)
        return len(tokens), len(content)

    # Template directory
    template_dir = Path.home() / '.orch' / 'templates' / 'orchestrator'
    if not template_dir.exists():
        click.echo(f"❌ Template directory not found: {template_dir}", err=True)
        click.echo("   Create templates first at ~/.orch/templates/orchestrator/", err=True)
        raise click.Abort()

    # Load templates
    templates = {}
    for template_file in template_dir.glob('*.md'):
        template_name = template_file.stem
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                templates[template_name] = f.read()
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not load template {template_name}: {e}", err=True)

    if not templates:
        click.echo(f"❌ No templates found in {template_dir}", err=True)
        raise click.Abort()

    # Rescan if requested
    if rescan:
        from orch.project_discovery import scan_projects, write_cache, get_default_search_dirs
        from orch.config import get_initialized_projects_cache

        search_dirs = get_default_search_dirs()
        projects = scan_projects(search_dirs)
        cache_file = get_initialized_projects_cache()
        write_cache(cache_file, projects)

        if not dry_run:
            click.echo(f"🔄 Rescanned and found {len(projects)} projects")

    def find_orch_context_files():
        """Find all .orch/CLAUDE.md, .orch/GEMINI.md, and .orch/AGENTS.md files."""
        from orch.project_discovery import read_cache
        from orch.config import get_initialized_projects_cache

        files = []

        if project:
            # Check specific project
            project_path = Path(project)
            orch_claude = project_path / '.orch' / 'CLAUDE.md'
            orch_gemini = project_path / '.orch' / 'GEMINI.md'
            orch_agents = project_path / '.orch' / 'AGENTS.md'

            # Add all three files if they exist
            if orch_claude.exists():
                files.append(orch_claude)
            if orch_gemini.exists():
                files.append(orch_gemini)
            if orch_agents.exists():
                files.append(orch_agents)

            if not files:
                click.echo(f"❌ No .orch/CLAUDE.md, .orch/GEMINI.md, or .orch/AGENTS.md found in {project}", err=True)
                raise click.Abort()
        else:
            # Read from cache
            cache_file = get_initialized_projects_cache()
            projects = read_cache(cache_file)

            if not projects:
                click.echo(f"❌ No initialized projects found in cache: {cache_file}", err=True)
                click.echo("   Run 'orch scan-projects' first to discover projects", err=True)
                raise click.Abort()

            # Get CLAUDE.md, GEMINI.md, and AGENTS.md files from cached projects
            for project_path in projects:
                orch_claude = project_path / '.orch' / 'CLAUDE.md'
                orch_gemini = project_path / '.orch' / 'GEMINI.md'
                orch_agents = project_path / '.orch' / 'AGENTS.md'

                if orch_claude.exists():
                    files.append(orch_claude)
                if orch_gemini.exists():
                    files.append(orch_gemini)
                if orch_agents.exists():
                    files.append(orch_agents)

        return files

    def get_template_order():
        """Get ordered list of templates to include (matches init.py profile='full')."""
        # Essential Core - required for any orchestrator
        core_templates = [
            "orchestrator-vs-worker-boundaries",
            "delegation-thresholds",
            "orchestrator-autonomy",
            "core-responsibilities",
            "worker-skills",
            "spawning-checklist",
            "verification-checklist",
            "amnesia-resilient-design",
            "pre-response-protocol",
            "artifact-organization",
            "error-recovery-patterns",
            "maintenance-patterns",
            "orch-commands",
            "red-flags-and-decision-trees",
        ]
        return core_templates

    def generate_full_content(file_path):
        """Generate complete file content from templates (full regeneration)."""
        template_order = get_template_order()

        # Header
        content_parts = [
            "<!-- AUTO-GENERATED FILE - DO NOT EDIT -->",
            "<!-- Generated by: orch build --context -->",
            "<!-- To modify: Edit templates in ~/.orch/templates/orchestrator/ then rebuild -->",
            "",
            "# Orchestrator Context",
            "",
            "This file provides orchestration guidance for AI agents managing this project.",
            "For project-specific context, see the root CLAUDE.md file.",
            "",
            "---",
            "",
        ]

        templates_used = []
        for template_name in template_order:
            if template_name in templates:
                template_content = templates[template_name]
                content_parts.append(f"<!-- ORCH-INSTRUCTION: {template_name} -->")
                content_parts.append(f"<!-- Source: meta-orchestration/templates-src/orchestrator/{template_name}.md -->")
                content_parts.append("")
                content_parts.append(template_content.strip())
                content_parts.append("")
                content_parts.append(f"<!-- /ORCH-INSTRUCTION -->")
                content_parts.append("")
                templates_used.append(template_name)

        return "\n".join(content_parts), templates_used

    # Find files to build
    files = find_orch_context_files()

    if not files:
        click.echo("❌ No .orch/CLAUDE.md, .orch/GEMINI.md, or .orch/AGENTS.md files found", err=True)
        raise click.Abort()

    # Process each file
    click.echo()
    click.echo(f"🔨 {'Checking' if check else 'Dry-run' if dry_run else 'Building'} orchestrator context for {len(files)} project(s)...")
    click.echo(f"   Templates: {template_dir}")
    click.echo(f"   Available: {', '.join(sorted(templates.keys()))}")
    click.echo()

    built_count = 0
    skipped_count = 0
    exceeded_count = 0

    for file_path in files:
        # Read current content for comparison
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except Exception as e:
            click.echo(f"❌ Error reading {file_path}: {e}", err=True)
            continue

        # Generate full content (complete regeneration)
        new_content, replacements = generate_full_content(file_path)

        # Check if changed
        changed = new_content != current_content

        # Check token and character limits
        token_count, char_count = count_metrics(new_content)
        limits = LIMITS['orchestrator']
        tokens_pass = token_count <= limits['tokens']
        chars_pass = char_count <= limits['chars']
        within_limit = tokens_pass and chars_pass

        # Codex-specific 32KB limit check (AGENTS.md only)
        CODEX_BYTE_LIMIT = 32768  # 32KB
        codex_bytes = len(new_content.encode('utf-8'))
        codex_warning = (file_path.name == 'AGENTS.md' and codex_bytes > CODEX_BYTE_LIMIT)
        codex_overage = codex_bytes - CODEX_BYTE_LIMIT if codex_warning else 0

        # Shorten path for display
        display_path = str(file_path).replace(str(Path.home()), '~')

        if check:
            # Check mode - report status
            if not changed:
                click.echo(f"✅ {display_path} - Current")
                skipped_count += 1
            else:
                click.echo(f"⚠️  {display_path} - Needs rebuild")
                click.echo(f"   Templates used: {', '.join(replacements)}")
                built_count += 1

                if not within_limit:
                    if not tokens_pass:
                        overage = token_count - limits['tokens']
                        click.echo(f"   ❌ Would exceed token limit: {token_count:,} tokens ({overage:,} over)")
                    if not chars_pass:
                        overage = char_count - limits['chars']
                        click.echo(f"   ❌ Would exceed char limit: {char_count:,} chars ({overage:,} over)")
                    exceeded_count += 1

                # Codex-specific warning
                if codex_warning:
                    click.echo(f"   ⚠️  Codex 32KB limit exceeded: {codex_bytes:,} bytes ({codex_overage:,} over)")
        elif dry_run:
            # Dry-run mode - show what would happen
            if not changed:
                click.echo(f"⏭️  {display_path} - Would skip (no changes)")
                skipped_count += 1
            else:
                click.echo(f"🔨 {display_path} - Would rebuild")
                click.echo(f"   Templates: {', '.join(replacements)}")
                token_pct = (token_count / limits['tokens']) * 100
                char_pct = (char_count / limits['chars']) * 100
                click.echo(f"   Tokens: {token_count:,} / {limits['tokens']:,} ({token_pct:.1f}%)")
                click.echo(f"   Chars:  {char_count:,} / {limits['chars']:,} ({char_pct:.1f}%)")

                # Show warning if approaching limit
                if within_limit and char_count > WARNING_THRESHOLD_CHARS:
                    click.echo(f"   ⚠️  Approaching char limit: {char_count:,} / {limits['chars']:,} ({char_pct:.1f}%)")

                if not within_limit:
                    if not tokens_pass:
                        overage = token_count - limits['tokens']
                        click.echo(f"   ❌ EXCEEDS TOKEN LIMIT by {overage:,} tokens")
                    if not chars_pass:
                        overage = char_count - limits['chars']
                        click.echo(f"   ❌ EXCEEDS CHAR LIMIT by {overage:,} characters")
                    exceeded_count += 1
                else:
                    built_count += 1

                # Codex-specific warning
                if codex_warning:
                    click.echo(f"   ⚠️  Codex 32KB limit exceeded: {codex_bytes:,} bytes ({codex_overage:,} over)")
        else:
            # Build mode - actually write files
            if not changed:
                click.echo(f"⏭️  {display_path} - Skipped (no changes)")
                skipped_count += 1
            elif not within_limit:
                click.echo(f"❌ {display_path} - FAILED")
                if not tokens_pass:
                    overage = token_count - limits['tokens']
                    click.echo(f"   Exceeds token limit: {token_count:,} tokens ({overage:,} over)")
                if not chars_pass:
                    overage = char_count - limits['chars']
                    click.echo(f"   Exceeds char limit: {char_count:,} chars ({overage:,} over)")
                exceeded_count += 1
            else:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    click.echo(f"✅ {display_path} - Built")
                    click.echo(f"   Templates: {', '.join(replacements)}")
                    token_pct = (token_count / limits['tokens']) * 100
                    char_pct = (char_count / limits['chars']) * 100
                    click.echo(f"   Tokens: {token_count:,} / {limits['tokens']:,} ({token_pct:.1f}%)")
                    click.echo(f"   Chars:  {char_count:,} / {limits['chars']:,} ({char_pct:.1f}%)")

                    # Show warning if approaching limit
                    if char_count > WARNING_THRESHOLD_CHARS:
                        click.echo(f"   ⚠️  Approaching char limit: {char_count:,} / {limits['chars']:,} ({char_pct:.1f}%)")

                    # Codex-specific warning
                    if codex_warning:
                        click.echo(f"   ⚠️  Codex 32KB limit exceeded: {codex_bytes:,} bytes ({codex_overage:,} over)")

                    built_count += 1

                    # Copy AGENTS.md to repo root for Codex backend
                    # Codex walks from repo root, not .orch/ directory
                    if file_path.name == 'AGENTS.md' and file_path.parent.name == '.orch':
                        repo_root_agents = file_path.parent.parent / 'AGENTS.md'
                        try:
                            import shutil
                            shutil.copy2(file_path, repo_root_agents)
                            click.echo(f"   📋 Copied to {repo_root_agents.relative_to(Path.cwd())} (for Codex)")
                        except Exception as copy_err:
                            click.echo(f"   ⚠️  Failed to copy to repo root: {copy_err}", err=True)

                    # NOTE: Global sync to ~/.claude/CLAUDE.md REMOVED (2025-11-26)
                    # See: .orch/investigations/simple/2025-11-26-root-cause-analysis-claude-claude.md
                    # Reason: Clobbered user's personal preferences file. Claude Code loads
                    # project context from the project directory, not ~/.claude/

                    import shutil
                    if file_path.name == 'GEMINI.md' and file_path.parent.name == '.orch':
                        global_gemini = Path.home() / '.gemini' / 'GEMINI.md'
                        try:
                            global_gemini.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, global_gemini)
                            click.echo(f"   🔄 Synced to ~/.gemini/GEMINI.md")
                        except Exception as sync_err:
                            click.echo(f"   ⚠️  Failed to sync to global: {sync_err}", err=True)
                    elif file_path.name == 'AGENTS.md' and file_path.parent.name == '.orch':
                        global_agents = Path.home() / '.codex' / 'AGENTS.md'
                        try:
                            global_agents.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, global_agents)
                            click.echo(f"   🔄 Synced to ~/.codex/AGENTS.md")
                        except Exception as sync_err:
                            click.echo(f"   ⚠️  Failed to sync to global: {sync_err}", err=True)
                except Exception as e:
                    click.echo(f"❌ Error writing {file_path}: {e}", err=True)

        click.echo()

    # Summary
    if check:
        if built_count == 0:
            click.echo("✅ All files are current")
        else:
            click.echo(f"⚠️  {built_count} file(s) need rebuilding")
            if exceeded_count > 0:
                click.echo(f"❌ {exceeded_count} file(s) would exceed token limits")
                raise click.Abort()
    elif dry_run:
        click.echo(f"📋 Dry-run complete: {built_count} would be built, {skipped_count} would be skipped")
        if exceeded_count > 0:
            click.echo(f"❌ {exceeded_count} file(s) would exceed token limits")
            raise click.Abort()
    else:
        click.echo(f"✅ Build complete: {built_count} built, {skipped_count} skipped")
        if exceeded_count > 0:
            click.echo(f"❌ {exceeded_count} file(s) exceeded token limits (not built)")
            raise click.Abort()

    # Check for missing instructions in processed projects
    if not check:  # Skip for --check mode (just reporting status)
        from orch.instructions import get_missing_instructions

        # Get unique project directories from processed files
        processed_projects = set()
        for file_path in files:
            # .orch/CLAUDE.md -> project root is parent.parent
            if file_path.parent.name == '.orch':
                processed_projects.add(file_path.parent.parent)

        # Check each project for missing instructions
        projects_with_missing = []
        for project_dir in processed_projects:
            try:
                missing = get_missing_instructions(str(project_dir))
                if missing:
                    projects_with_missing.append((project_dir, missing))
            except Exception:
                # Skip projects that can't be checked (e.g., no CLAUDE.md)
                pass

        if projects_with_missing:
            click.echo()
            click.echo(f"⚠️  {len(projects_with_missing)} project(s) have missing instructions:")
            for project_dir, missing in projects_with_missing:
                display_path = str(project_dir).replace(str(Path.home()), '~')
                click.echo(f"   {display_path}: {len(missing)} missing")
            click.echo()
            click.echo("💡 Run 'orch instruction upgrade' in each project to add missing instructions")


@cli.command(name='build-global', hidden=True)
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
def build_global(dry_run, check):
    """
    Build global orchestration artifacts from source.

    DEPRECATED: Use 'orch build --global' instead.

    Syncs templates from meta-orchestration/templates-src/ to ~/.orch/templates/
    for distribution to all projects. This is the first step in the build pipeline:

      templates-src/ → ~/.orch/templates/ → .orch/CLAUDE.md
      (via build-global)   (via build-orchestrator-context)

    \b
    Examples:
      orch build-global              # Build and sync templates
      orch build-global --dry-run    # Preview changes
      orch build-global --check      # Check if rebuild needed
    """
    import shutil
    from pathlib import Path

    # Source directory (meta-orchestration)
    meta_orch = Path.home() / 'meta-orchestration'
    src_templates = meta_orch / 'templates-src'
    src_patterns = meta_orch / 'patterns-src'

    # Distribution directory (global)
    dst_templates = Path.home() / '.orch' / 'templates'
    dst_patterns = Path.home() / '.orch' / 'patterns'

    # Validate source exists
    if not meta_orch.exists():
        click.echo(f"❌ meta-orchestration not found at {meta_orch}", err=True)
        click.echo("   Expected location: ~/meta-orchestration", err=True)
        raise click.Abort()

    if not src_templates.exists():
        click.echo(f"❌ Source templates not found at {src_templates}", err=True)
        click.echo("   Run: mkdir -p ~/meta-orchestration/templates-src", err=True)
        raise click.Abort()

    # Create destination directories
    if not check and not dry_run:
        dst_templates.mkdir(parents=True, exist_ok=True)
        dst_patterns.mkdir(parents=True, exist_ok=True)

    # Track stats
    template_count = 0
    pattern_count = 0
    updated_count = 0
    skipped_count = 0

    # Sync templates
    click.echo("📦 Building global orchestration artifacts...\n")

    click.echo("Templates (templates-src/ → ~/.orch/templates/):")
    # Use rglob to recursively find all .md files in subdirectories
    for src_file in sorted(src_templates.rglob('*.md')):
        # Preserve directory structure
        relative_path = src_file.relative_to(src_templates)
        dst_file = dst_templates / relative_path
        template_count += 1

        # Create destination subdirectory if needed
        if not check and not dry_run:
            dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if update needed
        needs_update = True
        if dst_file.exists():
            src_content = src_file.read_text()
            dst_content = dst_file.read_text()
            needs_update = src_content != dst_content

        # Show relative path for clarity
        display_path = str(relative_path)

        if check:
            if needs_update:
                click.echo(f"  ⚠️  {display_path} - Needs rebuild")
                updated_count += 1
            else:
                click.echo(f"  ✅ {display_path} - Current")
                skipped_count += 1
        elif dry_run:
            if needs_update:
                click.echo(f"  🔨 {display_path} - Would update")
                updated_count += 1
            else:
                click.echo(f"  ⏭️  {display_path} - Would skip (no changes)")
                skipped_count += 1
        else:
            # Actually copy
            if needs_update:
                shutil.copy2(src_file, dst_file)
                click.echo(f"  ✅ {display_path} - Updated")
                updated_count += 1
            else:
                click.echo(f"  ⏭️  {display_path} - Skipped (no changes)")
                skipped_count += 1

    # Sync patterns (if source exists)
    if src_patterns.exists() and list(src_patterns.rglob('*.md')):
        click.echo("\nPatterns (patterns-src/ → ~/.orch/patterns/):")
        # Use rglob to recursively find all .md files in subdirectories
        for src_file in sorted(src_patterns.rglob('*.md')):
            # Preserve directory structure
            relative_path = src_file.relative_to(src_patterns)
            dst_file = dst_patterns / relative_path
            pattern_count += 1

            # Create destination subdirectory if needed
            if not check and not dry_run:
                dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Check if update needed
            needs_update = True
            if dst_file.exists():
                src_content = src_file.read_text()
                dst_content = dst_file.read_text()
                needs_update = src_content != dst_content

            # Show relative path for clarity
            display_path = str(relative_path)

            if check:
                if needs_update:
                    click.echo(f"  ⚠️  {display_path} - Needs rebuild")
                    updated_count += 1
                else:
                    click.echo(f"  ✅ {display_path} - Current")
                    skipped_count += 1
            elif dry_run:
                if needs_update:
                    click.echo(f"  🔨 {display_path} - Would update")
                    updated_count += 1
                else:
                    click.echo(f"  ⏭️  {display_path} - Would skip (no changes)")
                    skipped_count += 1
            else:
                # Actually copy
                if needs_update:
                    shutil.copy2(src_file, dst_file)
                    click.echo(f"  ✅ {display_path} - Updated")
                    updated_count += 1
                else:
                    click.echo(f"  ⏭️  {display_path} - Skipped (no changes)")
                    skipped_count += 1

    # Summary
    click.echo(f"\n{'=' * 50}")
    if check:
        click.echo(f"Check complete: {template_count + pattern_count} files")
        if updated_count > 0:
            click.echo(f"  ⚠️  {updated_count} need rebuilding")
            click.echo(f"\nRun: orch build-global (without --check)")
            raise SystemExit(1)  # Non-zero exit for pre-commit hook detection
        else:
            click.echo(f"  ✅ All files current")
    elif dry_run:
        click.echo(f"Dry run: {template_count + pattern_count} files")
        click.echo(f"  Would update: {updated_count}")
        click.echo(f"  Would skip: {skipped_count}")
    else:
        click.echo(f"Build complete: {template_count + pattern_count} files")
        click.echo(f"  Updated: {updated_count}")
        click.echo(f"  Skipped: {skipped_count}")
        click.echo(f"\n✅ Global artifacts synced to ~/.orch/")

        if updated_count > 0:
            click.echo(f"\n💡 Next: Run 'orch build-orchestrator-context' to update projects")


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
@click.option('--context', 'target_context', is_flag=True, help='Build only agent context files (CLAUDE.md, GEMINI.md, AGENTS.md)')
@click.option('--orchestrator', 'target_orchestrator', is_flag=True, hidden=True, help='Deprecated: use --context instead')
@click.option('--skills', 'target_skills', is_flag=True, help='Build only skill SKILL.md files')
@click.option('--all', 'target_all', is_flag=True, help='Build all targets (default)')
@click.option('--global', 'target_global', is_flag=True, help='Sync templates from meta-orchestration to ~/.orch/templates/')
@click.option('--readme', 'target_readme', is_flag=True, help='Auto-generate .orch/README.md from artifact metadata')
@click.option('--sync', 'target_sync', is_flag=True, help='Sync workspace templates from package to ~/.orch/templates/')
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.pass_context
def build(ctx, target_context, target_orchestrator, target_skills, target_all, target_global, target_readme, target_sync, dry_run, check):
    """
    Build agent context files and/or skills from templates.

    Can be invoked with flags (legacy) or as subcommands (preferred):

    \b
    Subcommand style (preferred):
      orch build context            # Build agent context files
      orch build skills             # Build skill SKILL.md files
      orch build readme             # Generate .orch/README.md
      orch build global             # Sync templates to ~/.orch/

    \b
    Flag style (legacy, still supported):
      orch build                    # Build everything (default)
      orch build --all              # Same as above (explicit)
      orch build --context          # Just agent context files
      orch build --skills           # Just SKILL.md files
      orch build --check            # Check if any rebuilds needed
      orch build --dry-run          # Preview all changes
    """
    # If a subcommand was invoked, don't run the group logic
    if ctx.invoked_subcommand is not None:
        return
    import re
    from pathlib import Path

    # Handle backwards compatibility: --orchestrator maps to --context
    if target_orchestrator:
        click.echo("⚠️  Warning: --orchestrator is deprecated, use --context instead")
        target_context = True

    # Check if any specific target is requested
    any_specific = target_context or target_skills or target_all or target_global or target_readme or target_sync

    # Handle new consolidated flags first (these are independent operations)
    if target_global:
        click.echo("🔨 Syncing global templates (--global)...")
        click.echo()
        ctx.invoke(build_global, dry_run=dry_run, check=check)
        click.echo()

    if target_readme:
        click.echo("🔨 Building README (--readme)...")
        click.echo()
        ctx.invoke(build_readme, dry_run=dry_run, project=None)
        click.echo()

    if target_sync:
        click.echo("🔨 Syncing workspace templates (--sync)...")
        click.echo()
        ctx.invoke(sync_templates, check=check, dry_run=dry_run)
        click.echo()

    # If only new flags were specified, we're done
    if target_global or target_readme or target_sync:
        if not (target_context or target_skills or target_all):
            return

    # Determine traditional targets
    if not any_specific:
        # Default: build all (context + skills)
        target_context = True
        target_skills = True
    elif target_all:
        target_context = True
        target_skills = True

    # Build agent context files
    if target_context:
        click.echo("🔨 Building agent context files...")
        click.echo()
        ctx.invoke(build_orchestrator_context, dry_run=dry_run, check=check, project=None, rescan=False)
        click.echo()

    # Build skills
    if target_skills:
        click.echo("🔨 Building skills...")
        click.echo()

        import shutil

        # Source: meta-orchestration/skills/src/
        orch_root = find_orch_root()
        if not orch_root:
            click.echo("❌ Not in a meta-orchestration directory", err=True)
            raise click.Abort()

        skills_src = Path(orch_root) / 'skills' / 'src'
        if not skills_src.exists():
            click.echo(f"❌ Skills source not found: {skills_src}", err=True)
            click.echo("   Expected: meta-orchestration/skills/src/", err=True)
            raise click.Abort()

        # Output locations
        global_skills_dir = Path.home() / '.claude' / 'skills'
        project_skills_dir = Path(orch_root) / '.claude' / 'skills'

        # Categories and their output locations
        # worker, shared, utilities, meta -> global (~/.claude/skills/)
        # orchestrator -> project (.claude/skills/)
        global_categories = ['worker', 'shared', 'utilities', 'meta']
        project_categories = ['orchestrator']

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
                display_path = str(output_file).replace(str(orch_root), 'meta-orchestration')

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

@build.command(name='context')
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.option('--project', type=click.Path(exists=True), help='Specific project directory to build')
@click.option('--rescan', is_flag=True, help='Rescan for projects before building')
@click.pass_context
def build_context(ctx, dry_run, check, project, rescan):
    """Build agent context files (CLAUDE.md, GEMINI.md, AGENTS.md).

    Replaces marked sections with content from templates at ~/.orch/templates/orchestrator/.
    This allows sharing common orchestration patterns while keeping files self-contained.

    \b
    Examples:
      orch build context                # Build all projects
      orch build context --dry-run      # Preview changes
      orch build context --check        # Check if rebuild needed
      orch build context --project ~/my-project
    """
    ctx.invoke(build_orchestrator_context, dry_run=dry_run, check=check, project=project, rescan=rescan)


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
@click.option('--dry-run', is_flag=True, help='Show what would be built without making changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
@click.pass_context
def build_global_cmd(ctx, dry_run, check):
    """Sync templates from meta-orchestration to ~/.orch/templates/.

    Syncs templates from meta-orchestration/templates-src/ to ~/.orch/templates/
    for distribution to all projects. This is the first step in the build pipeline:

      templates-src/ -> ~/.orch/templates/ -> .orch/CLAUDE.md

    \b
    Examples:
      orch build global               # Build and sync templates
      orch build global --dry-run     # Preview changes
      orch build global --check       # Check if rebuild needed
    """
    ctx.invoke(build_global, dry_run=dry_run, check=check)


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


# ============================================================================
# Features group - enumerable task tracking for autonomous execution
# ============================================================================

@cli.group(invoke_without_command=True)
@click.option('--pending', 'status_filter', flag_value='pending', help='Show only pending features')
@click.option('--in-progress', 'status_filter', flag_value='in_progress', help='Show only in-progress features')
@click.option('--complete', 'status_filter', flag_value='complete', help='Show only complete features')
@click.option('--blocked', 'status_filter', flag_value='blocked', help='Show only blocked features')
@click.option('--category', 'category_filter', help='Filter by category (feature, bug, infrastructure)')
@click.option('--format', 'output_format', type=click.Choice(['human', 'json']), default='human', help='Output format')
@click.pass_context
def features(ctx, status_filter, category_filter, output_format):
    """Feature list management for autonomous execution.

    \b
    Without subcommands, lists all features with optional filtering.

    \b
    Subcommands:
      add      Add a new feature
      edit     Open feature in editor

    \b
    Filter options:
      --pending       Show pending features only
      --in-progress   Show in-progress features only
      --complete      Show completed features only
      --blocked       Show blocked features only
      --category      Filter by category

    \b
    Examples:
      orch features                      # List all features
      orch features --pending            # List pending only
      orch features --category bug       # List bugs only
      orch features add "description"    # Add new feature
      orch features edit rate-limiting   # Edit feature
    """
    # Store filters in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['status_filter'] = status_filter
    ctx.obj['category_filter'] = category_filter
    ctx.obj['output_format'] = output_format

    # If no subcommand, list features
    if ctx.invoked_subcommand is None:
        _features_list(status_filter, category_filter, output_format)


def _features_list(status_filter, category_filter, output_format):
    """Internal function to list features."""
    from orch.features import (
        list_features, load_features_safe, FeaturesNotFoundError,
        get_features_path
    )

    features_path = get_features_path()

    # Load features
    feature_list = load_features_safe()

    if not feature_list and not features_path.exists():
        click.echo("📋 No backlog.json found.")
        click.echo("   Run 'orch features add \"description\"' to create one.")
        return

    # Apply filters
    if status_filter:
        feature_list = [f for f in feature_list if f.status == status_filter]
    if category_filter:
        feature_list = [f for f in feature_list if f.category == category_filter]

    # Output
    if output_format == 'json':
        import json
        data = {
            "features": [f.to_dict() for f in feature_list],
            "total": len(feature_list)
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Human-readable output
    if not feature_list:
        if status_filter or category_filter:
            click.echo("📋 No features match the filters.")
        else:
            click.echo("📋 No features defined.")
        return

    # Group by status for display
    status_order = ['in_progress', 'pending', 'blocked', 'complete']
    status_emoji = {
        'pending': '⏳',
        'in_progress': '🔄',
        'complete': '✅',
        'blocked': '🚫'
    }

    # Display header
    filter_desc = []
    if status_filter:
        filter_desc.append(f"status={status_filter}")
    if category_filter:
        filter_desc.append(f"category={category_filter}")
    filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""

    click.echo(f"📋 Features ({len(feature_list)}){filter_str}:")
    click.echo()

    # Group and display
    for status in status_order:
        status_features = [f for f in feature_list if f.status == status]
        if not status_features:
            continue

        emoji = status_emoji.get(status, '•')
        click.echo(f"  {emoji} {status.replace('_', ' ').title()} ({len(status_features)}):")

        for feature in status_features:
            cat_str = f" [{feature.category}]" if feature.category else ""
            click.echo(f"     {feature.id}{cat_str}")
            click.echo(f"       {feature.description}")
            if feature.workspace:
                click.echo(f"       workspace: {feature.workspace}")
        click.echo()


@features.command(name='add')
@click.argument('description')
@click.option('--skill', default='feature-impl', help='Skill to use (default: feature-impl)')
@click.option('--category', help='Category (feature, bug, infrastructure)')
@click.option('--id', 'feature_id', help='Custom ID (auto-generated if not provided)')
@click.option('--context-ref', help='Reference to context (e.g., ROADMAP.org#section)')
@click.option('--verification', multiple=True, help='Custom verification criteria (can be repeated)')
def features_add(description, skill, category, feature_id, context_ref, verification):
    """Add a new feature to the feature list.

    \b
    Examples:
      orch features add "Add rate limiting to API"
      orch features add "Fix auth bug" --category bug
      orch features add "Add caching" --id add-redis-cache
      orch features add "Migration" --verification "runs forward" --verification "rollback works"
    """
    from orch.features import (
        add_feature, DuplicateFeatureError, FeaturesValidationError
    )

    try:
        verification_list = list(verification) if verification else None
        feature = add_feature(
            description=description,
            skill=skill,
            category=category,
            feature_id=feature_id,
            context_ref=context_ref,
            verification=verification_list,
        )

        click.echo(f"✅ Feature added: {feature.id}")
        click.echo(f"   Description: {feature.description}")
        click.echo(f"   Skill: {feature.skill}")
        if category:
            click.echo(f"   Category: {feature.category}")
        if context_ref:
            click.echo(f"   Context: {context_ref}")
        if verification_list:
            click.echo(f"   Verification: {', '.join(verification_list)}")

    except DuplicateFeatureError as e:
        click.echo(f"❌ {e}", err=True)
        raise SystemExit(1)
    except FeaturesValidationError as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        raise SystemExit(1)


@features.command(name='edit')
@click.argument('feature_id')
def features_edit(feature_id):
    """Open a feature in your default editor.

    Opens the backlog.json file at the specified feature for editing.

    \b
    Examples:
      orch features edit rate-limiting
    """
    import subprocess
    import os
    from orch.features import get_features_path, get_feature, FeatureNotFoundError

    features_path = get_features_path()

    if not features_path.exists():
        click.echo("❌ No backlog.json found.", err=True)
        raise SystemExit(1)

    # Verify feature exists
    try:
        get_feature(feature_id)
    except FeatureNotFoundError:
        click.echo(f"❌ Feature '{feature_id}' not found.", err=True)
        raise SystemExit(1)

    # Get editor
    editor = os.environ.get('EDITOR', os.environ.get('VISUAL', 'vi'))

    # Open file in editor
    click.echo(f"Opening {features_path} in {editor}...")
    try:
        subprocess.run([editor, str(features_path)])
    except FileNotFoundError:
        click.echo(f"❌ Editor '{editor}' not found. Set EDITOR environment variable.", err=True)
        raise SystemExit(1)


@features.command(name='show')
@click.argument('feature_id')
def features_show(feature_id):
    """Show details of a specific feature.

    \b
    Examples:
      orch features show rate-limiting
    """
    from orch.features import get_feature, FeatureNotFoundError
    import json

    try:
        feature = get_feature(feature_id)
    except FeatureNotFoundError:
        click.echo(f"❌ Feature '{feature_id}' not found.", err=True)
        raise SystemExit(1)

    status_emoji = {
        'pending': '⏳',
        'in_progress': '🔄',
        'complete': '✅',
        'blocked': '🚫'
    }

    emoji = status_emoji.get(feature.status, '•')
    click.echo(f"\n{emoji} {feature.id}")
    click.echo(f"   Description: {feature.description}")
    click.echo(f"   Status: {feature.status}")
    click.echo(f"   Skill: {feature.skill}")
    if feature.category:
        click.echo(f"   Category: {feature.category}")
    if feature.skill_args:
        click.echo(f"   Skill Args: {json.dumps(feature.skill_args)}")
    if feature.verification:
        click.echo(f"   Verification: {', '.join(feature.verification)}")
    if feature.context_ref:
        click.echo(f"   Context: {feature.context_ref}")
    if feature.workspace:
        click.echo(f"   Workspace: {feature.workspace}")
    if feature.started_at:
        click.echo(f"   Started: {feature.started_at}")
    if feature.completed_at:
        click.echo(f"   Completed: {feature.completed_at}")
    click.echo()


@cli.command()
def skills():
    """List available worker skills.

    Shows all spawnable worker skills from ~/.claude/skills/worker/ with
    their descriptions and categories.
    """
    import yaml
    from pathlib import Path

    skills_dir = Path.home() / ".claude" / "skills" / "worker"

    if not skills_dir.exists():
        click.echo("❌ Worker skills directory not found: ~/.claude/skills/worker/")
        return

    # Collect all skills
    skills_list = []

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir():
            continue

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            continue

        # Parse YAML frontmatter
        try:
            content = skill_md.read_text()
            if content.startswith('---'):
                # Extract frontmatter
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    if frontmatter and frontmatter.get('spawnable', False):
                        skills_list.append({
                            'name': frontmatter.get('name', skill_path.name),
                            'description': frontmatter.get('description', ''),
                            'category': frontmatter.get('category', 'unknown')
                        })
        except Exception as e:
            # Skip skills with parsing errors
            continue

    if not skills_list:
        click.echo("No spawnable worker skills found.")
        return

    # Display skills
    click.echo("Available Worker Skills:\n")
    for skill in skills_list:
        click.echo(f"  {skill['name']}")
        click.echo(f"    Category: {skill['category']}")
        click.echo(f"    {skill['description']}")
        click.echo()


@cli.command()
@click.option('--fix', is_flag=True, help='Auto-fix fixable issues')
@click.option('--ci', is_flag=True, help='Run in CI mode (exit non-zero on failures)')
def doctor(fix, ci):
    """
    Check system health and detect drift.

    Performs automated health checks to detect drift and issues:
      • OAuth token permissions
      • Documentation drift (CLI commands vs documented)
      • Template drift (workspaces missing fields)
      • Config file validity
      • Git status
      • Test coverage
      • Registry integrity
      • tmux availability

    Examples:
      orch doctor              # Check health
      orch doctor --fix        # Auto-fix fixable issues
      orch doctor --ci         # CI mode (exit non-zero on failures)
    """
    import yaml
    from pathlib import Path
    import stat

    checks_passed = 0
    checks_warned = 0
    checks_failed = 0

    click.echo("🏥 Running system health checks...")
    click.echo()

    # Check 1: OAuth token permissions
    oauth_token_path = Path.home() / '.orch' / 'oauth_token.json'
    if oauth_token_path.exists():
        current_perms = oauth_token_path.stat().st_mode & 0o777
        if current_perms == 0o600:
            click.echo("✓ OAuth token permissions: 600 (secure)")
            checks_passed += 1
        else:
            if fix:
                oauth_token_path.chmod(0o600)
                click.echo(f"✓ OAuth token permissions: Fixed (was {oct(current_perms)}, now 600)")
                checks_passed += 1
            else:
                click.echo(f"✗ OAuth token permissions: {oct(current_perms)} (should be 600)")
                click.echo(f"   Fix: chmod 600 {oauth_token_path}")
                checks_failed += 1
    else:
        click.echo("⚠  OAuth token: Not found (may not be configured)")
        checks_warned += 1

    # Check 2: tmux availability
    if is_tmux_available():
        click.echo("✓ tmux: Available")
        checks_passed += 1
    else:
        click.echo("✗ tmux: Not available (required for agent spawning)")
        click.echo("   Fix: Install tmux")
        checks_failed += 1

    # Check 3: Config file validity
    orch_root = find_orch_root()
    if orch_root:
        config_path = Path(orch_root) / '.orch' / 'config.yaml'
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                click.echo("✓ Config file: Valid YAML")
                checks_passed += 1
            except yaml.YAMLError as e:
                click.echo(f"✗ Config file: Invalid YAML")
                click.echo(f"   Error: {e}")
                click.echo(f"   Fix: Check {config_path} for syntax errors")
                checks_failed += 1
        else:
            click.echo("⚠  Config file: Not found (using defaults)")
            checks_warned += 1

    # Check 4: Git status (uncommitted files warning)
    git_root = get_git_root()
    if git_root:
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                uncommitted_count = len(result.stdout.strip().split('\n'))
                click.echo(f"⚠  Git status: {uncommitted_count} uncommitted changes")
                click.echo(f"   Review: git status")
                checks_warned += 1
            else:
                click.echo("✓ Git status: Clean working tree")
                checks_passed += 1
        except subprocess.CalledProcessError:
            click.echo("⚠  Git status: Could not check")
            checks_warned += 1

    # Check 5: Registry integrity
    try:
        registry = AgentRegistry()
        agents = registry.list_agents()
        click.echo(f"✓ Registry: {len(agents)} agents registered")
        checks_passed += 1
    except Exception as e:
        click.echo(f"✗ Registry: Could not load")
        click.echo(f"   Error: {e}")
        checks_failed += 1

    # Check 6: Documentation drift (CLI commands vs documented)
    # This is complex - for now just check if orch-commands.md exists
    if orch_root:
        orch_commands_path = Path(orch_root) / '.orch' / 'templates' / 'orchestrator' / 'orch-commands.md'
        global_orch_commands = Path.home() / '.orch' / 'templates' / 'orchestrator' / 'orch-commands.md'

        if orch_commands_path.exists() or global_orch_commands.exists():
            click.echo("✓ Documentation: orch-commands.md exists")
            checks_passed += 1
            # TODO: Deep check - compare actual CLI commands vs documented
            # This would require parsing the documented commands and comparing
            # with the actual @cli.command() definitions
        else:
            click.echo("⚠  Documentation: orch-commands.md not found")
            checks_warned += 1

    # Check 7: Template drift (workspaces missing fields)
    if orch_root:
        workspace_dir = Path(orch_root) / '.orch' / 'workspace'
        if workspace_dir.exists():
            workspaces = list(workspace_dir.glob('*/WORKSPACE.md'))
            missing_template_version = 0
            missing_session_scope = 0

            for workspace_file in workspaces[:10]:  # Sample first 10
                try:
                    content = workspace_file.read_text()
                    if 'Template-Version:' not in content:
                        missing_template_version += 1
                    if 'Session Scope:' not in content:
                        missing_session_scope += 1
                except Exception:
                    pass

            if missing_template_version > 0 or missing_session_scope > 0:
                click.echo(f"⚠  Template drift: Workspaces missing template fields")
                if missing_template_version > 0:
                    click.echo(f"   {missing_template_version}/10 sampled missing Template-Version")
                if missing_session_scope > 0:
                    click.echo(f"   {missing_session_scope}/10 sampled missing Session Scope")
                click.echo(f"   Fix: Run workspace migration script (ROADMAP item)")
                checks_warned += 1
            else:
                click.echo("✓ Template drift: Sampled workspaces have required fields")
                checks_passed += 1

    # Check 8: Test coverage (basic check - tests directory exists)
    if git_root:
        tests_dir = Path(git_root) / 'tests'
        if tests_dir.exists():
            test_files = list(tests_dir.glob('test_*.py'))
            click.echo(f"✓ Test coverage: {len(test_files)} test files found")
            checks_passed += 1
        else:
            click.echo("⚠  Test coverage: tests/ directory not found")
            checks_warned += 1

    # Summary
    click.echo()
    click.echo("=" * 50)
    click.echo(f"Health check complete:")
    click.echo(f"  ✓ {checks_passed} passed")
    if checks_warned > 0:
        click.echo(f"  ⚠  {checks_warned} warnings")
    if checks_failed > 0:
        click.echo(f"  ✗ {checks_failed} failed")
    click.echo()

    if checks_failed == 0 and checks_warned == 0:
        click.echo("✅ All checks passed - system healthy")
        exit_code = 0
    elif checks_failed == 0:
        click.echo("⚠️  Some warnings detected - review recommended")
        exit_code = 0
    else:
        click.echo("❌ Some checks failed - action required")
        exit_code = 1

    if ci and exit_code != 0:
        raise click.Abort()


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


# ============================================================================
# Autonomous execution loop
# ============================================================================

@cli.command()
@click.option('--project', help='Project to process (auto-detected if not specified)')
@click.option('--max-agents', default=1, type=int, help='Maximum parallel agents (default: 1)')
@click.option('--interval', default=30, type=int, help='Poll interval in seconds (default: 30)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.option('--once', is_flag=True, help='Run once: complete ready agents, spawn one pending, exit')
@click.option('--no-complete', is_flag=True, help='Skip auto-completing agents (spawn only)')
@click.option('-y', '--yes', is_flag=True, help='Skip confirmations')
def auto(project, max_agents, interval, dry_run, once, no_complete, yes):
    """
    Autonomous feature execution loop.

    Continuously monitors backlog.json and agents:
    1. Complete any agents at Phase: Complete
    2. Spawn pending features up to --max-agents limit
    3. Wait and repeat until no pending features remain

    \b
    Exit conditions:
    - No pending features and no active agents → success
    - All remaining features are blocked → exit with status
    - User interrupt (Ctrl+C) → graceful shutdown

    \b
    Examples:
      orch auto                    # Run loop in current project
      orch auto --dry-run          # Show what would happen
      orch auto --once             # Single iteration then exit
      orch auto --max-agents 3     # Run up to 3 agents in parallel
      orch auto --interval 60      # Check every 60 seconds
    """
    from orch.features import list_features, get_features_path
    from orch.spawn import spawn_with_skill, detect_project_from_cwd, get_project_dir
    from orch.complete import complete_agent_work
    from orch.monitor import check_agent_status, Scenario
    import signal
    import sys

    # Signal handling for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            click.echo("\n⚠️  Force quitting...")
            sys.exit(1)
        shutdown_requested = True
        click.echo("\n⏹️  Shutdown requested. Completing current iteration...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Determine project directory
    project_dir = None
    project_name = project

    if project:
        project_dir = get_project_dir(project)
        if not project_dir:
            click.echo(f"❌ Project '{project}' not found", err=True)
            raise click.Abort()
    else:
        # Try auto-detection
        detected = detect_project_from_cwd()
        if detected:
            project_name, project_dir = detected
        else:
            click.echo("❌ Could not auto-detect project. Use --project to specify.", err=True)
            raise click.Abort()

    click.echo(f"🤖 Autonomous mode: {project_name}")
    click.echo(f"   Project: {project_dir}")
    click.echo(f"   Max agents: {max_agents}")
    click.echo(f"   Poll interval: {interval}s")
    if dry_run:
        click.echo(f"   Mode: DRY RUN")
    if once:
        click.echo(f"   Mode: SINGLE ITERATION")
    click.echo()

    # Load registry
    registry = AgentRegistry()

    iteration = 0
    while not shutdown_requested:
        iteration += 1
        if not once:
            click.echo(f"─── Iteration {iteration} ───")

        # Step 1: Complete ready agents
        if not no_complete:
            agents = registry.list_agents()
            # Filter to this project
            project_agents = [
                a for a in agents
                if str(a.get('project_dir', '')) == str(project_dir)
            ]

            ready_agents = []
            for agent_info in project_agents:
                try:
                    status = check_agent_status(agent_info)
                    if status.scenario in [Scenario.READY_COMPLETE, Scenario.READY_CLEAN]:
                        ready_agents.append((agent_info, status))
                except Exception:
                    pass  # Skip agents we can't check

            if ready_agents:
                click.echo(f"✅ Found {len(ready_agents)} agent(s) ready to complete")
                for agent_info, status in ready_agents:
                    agent_id = agent_info['id']
                    if dry_run:
                        click.echo(f"   [DRY RUN] Would complete: {agent_id}")
                    else:
                        click.echo(f"   Completing: {agent_id}")
                        try:
                            result = complete_agent_work(
                                agent_id=agent_id,
                                project_dir=project_dir,
                                roadmap_path=None,  # Auto-detect
                                allow_roadmap_miss=True,
                                dry_run=False
                            )
                            if result['success']:
                                click.echo(f"   ✓ {agent_id} completed")
                            else:
                                click.echo(f"   ✗ {agent_id} failed: {result.get('errors', ['Unknown'])[0]}")
                        except Exception as e:
                            click.echo(f"   ✗ {agent_id} error: {e}")

        # Refresh agent list after completions
        agents = registry.list_agents()
        active_agents = [
            a for a in agents
            if str(a.get('project_dir', '')) == str(project_dir)
            and a.get('status') not in ('completed', 'terminated', 'abandoned')
        ]

        # Step 2: Check pending features
        features_path = get_features_path(project_dir)
        if not features_path.exists():
            click.echo(f"❌ No backlog.json found at {features_path}. Nothing to process.", err=True)
            raise click.Abort()

        pending_features = list_features(project_dir=project_dir, status='pending')

        blocked_features = list_features(project_dir=project_dir, status='blocked')

        click.echo(f"📋 Features: {len(pending_features)} pending, {len(blocked_features)} blocked, {len(active_agents)} agent(s) running")

        # Exit condition: no pending and no active
        if not pending_features and not active_agents:
            if blocked_features:
                click.echo(f"\n⚠️  All features are either complete or blocked ({len(blocked_features)} blocked)")
                for f in blocked_features[:5]:
                    click.echo(f"   - {f.id}: {f.description[:50]}...")
            else:
                click.echo("\n🎉 All features complete!")
            break

        # Step 3: Spawn if capacity available
        slots_available = max_agents - len(active_agents)
        if slots_available > 0 and pending_features:
            features_to_spawn = pending_features[:slots_available]

            for feature in features_to_spawn:
                click.echo(f"🚀 Spawning: {feature.id}")
                click.echo(f"   Skill: {feature.skill}")
                click.echo(f"   Task: {feature.description[:60]}{'...' if len(feature.description) > 60 else ''}")

                if dry_run:
                    click.echo(f"   [DRY RUN] Would spawn agent for {feature.id}")
                else:
                    try:
                        # Extract skill args
                        phases = feature.skill_args.get('phases')
                        mode = feature.skill_args.get('mode')
                        validation = feature.skill_args.get('validation')

                        spawn_with_skill(
                            skill_name=feature.skill,
                            task=feature.description,
                            project=project_name,
                            workspace_name=None,  # Auto-generate
                            yes=True,  # Always auto-confirm in auto mode
                            resume=False,
                            custom_prompt=None,
                            phases=phases,
                            mode=mode,
                            validation=validation,
                            phase_id=None,
                            depends_on=None,
                            investigation_type='simple',
                            backend=None,
                            model=None,
                            stash=False,
                            allow_dirty=True,  # Allow dirty in auto mode
                            feature_id=feature.id
                        )
                        click.echo(f"   ✓ Spawned: {feature.id}")
                    except Exception as e:
                        click.echo(f"   ✗ Spawn failed: {e}")

        elif slots_available <= 0 and pending_features:
            click.echo(f"⏳ At capacity ({max_agents} agents). Waiting for completions...")

        # Exit if --once
        if once:
            click.echo("\n✓ Single iteration complete.")
            break

        # Wait for next iteration
        if not shutdown_requested:
            click.echo(f"💤 Waiting {interval}s before next check...")
            # Use short sleeps to be responsive to signals
            for _ in range(interval):
                if shutdown_requested:
                    break
                time.sleep(1)

        click.echo()

    if shutdown_requested:
        click.echo("\n👋 Autonomous mode stopped.")


if __name__ == '__main__':
    cli()
