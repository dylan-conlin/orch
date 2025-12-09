"""Monitoring commands for orch CLI.

Commands for monitoring agent status and activity.
"""

import click
import json
import time
from pathlib import Path

from orch.registry import AgentRegistry
from orch.tmux_utils import list_windows, find_session, is_tmux_available
from orch.monitor import check_agent_status, get_status_emoji
from orch.logging import OrchLogger
from orch.path_utils import get_git_root, detect_and_display_context
from orch.spawn_context_quality import (
    validate_spawn_context_quality,
    format_quality_for_human,
    format_quality_for_json,
)
from orch.agent_filters import (
    resolve_project_path,
    filter_agents,
    filter_agents_by_status,
)


def _display_context_info(context_info):
    """Helper to display context info."""
    click.echo(f"    Context: {context_info.tokens_used:,}/{context_info.tokens_total:,} ({context_info.percentage:.1f}%)")


def _get_issue_title(beads_id: str, db_path: str = None) -> str | None:
    """Fetch beads issue title for display.

    Args:
        beads_id: Beads issue ID
        db_path: Optional path to beads database

    Returns:
        Issue title or None if issue not found or beads CLI unavailable
    """
    from orch.beads_integration import (
        BeadsIntegration,
        BeadsCLINotFoundError,
        BeadsIssueNotFoundError,
    )

    try:
        beads = BeadsIntegration(db_path=db_path) if db_path else BeadsIntegration()
        issue = beads.get_issue(beads_id)
        return issue.title
    except (BeadsCLINotFoundError, BeadsIssueNotFoundError):
        return None


def _get_issue_convergence(beads_id: str, db_path: str = None) -> dict | None:
    """Fetch child issue convergence stats for a parent issue.

    Args:
        beads_id: Beads issue ID
        db_path: Optional path to beads database

    Returns:
        Convergence dict {total, closed, in_progress, open} or None if no children
    """
    from orch.beads_integration import (
        BeadsIntegration,
        BeadsCLINotFoundError,
        BeadsIssueNotFoundError,
    )

    try:
        beads = BeadsIntegration(db_path=db_path) if db_path else BeadsIntegration()
        return beads.get_child_convergence(beads_id)
    except (BeadsCLINotFoundError, BeadsIssueNotFoundError):
        return None


def _format_convergence(convergence: dict | None) -> str:
    """Format convergence stats for display.

    Args:
        convergence: Convergence dict from _get_issue_convergence

    Returns:
        Formatted string like "3/5 children complete" or empty string
    """
    if not convergence:
        return ""
    closed = convergence.get("closed", 0)
    total = convergence.get("total", 0)
    return f" [{closed}/{total} children complete]"


def _format_agent_not_found_error(agent_id: str, registry: AgentRegistry) -> str:
    """Format a helpful 'agent not found' error message with active agents listed.

    Args:
        agent_id: The agent ID that wasn't found
        registry: The agent registry to get active agents from

    Returns:
        Formatted error message with active agents listed
    """
    active_agents = registry.list_active_agents()
    if active_agents:
        agent_ids = [a['id'] for a in active_agents]
        available_str = ', '.join(agent_ids[:5])
        if len(agent_ids) > 5:
            available_str += f", ... ({len(agent_ids)} total)"
        return (
            f"Agent '{agent_id}' not found.\n"
            f"   Active agents: {available_str}\n"
            f"   Use 'orch status' to see all agents."
        )
    else:
        return f"Agent '{agent_id}' not found (no active agents)."


def register_monitoring_commands(cli):
    """Register monitoring-related commands with the CLI."""

    @cli.command()
    @click.option('--compact', is_flag=True, help='Show compact view (collapse working agents)')
    @click.option('--session', default=None, help='Tmux session name')
    @click.option('--context', 'check_context', is_flag=True, help='Check agent context usage (slower)')
    @click.option('--format', 'output_format', type=click.Choice(['human', 'json']), default='human', help='Output format')
    @click.option('--json', 'json_flag', is_flag=True, help='Output in JSON format (shorthand for --format json)')
    @click.option('--global', 'global_flag', is_flag=True, help='Show all agents across all projects (skip auto-scoping)')
    @click.option('--project', help='Filter by project directory (exact match or substring)')
    @click.option('--filter', 'workspace_filter', help='Filter by workspace name pattern (e.g., "investigate-*")')
    @click.option('--status', 'status_filter', help='Filter by phase/status (e.g., "Planning", "Complete", "blocked")')
    @click.option('--registry', 'registry_path', type=click.Path(exists=True), hidden=True, help='Registry path (for testing)')
    def status(compact, session, check_context, output_format, json_flag, global_flag, project, workspace_filter, status_filter, registry_path):
        """Quick-glance agent monitoring.

        \b
        AUTO-SCOPING BEHAVIOR:
        By default, 'orch status' shows agents for the current git repository only.
        This allows running the command from any subdirectory within a project.

        \b
        To see all agents across all projects:
          orch status --global

        \b
        To filter to a specific project:
          orch status --project /path/to/project
        """
        from orch.json_output import serialize_agent_status, output_json

        # --json flag overrides --format (shorthand for --format json)
        if json_flag:
            output_format = 'json'

        # Initialize logger
        orch_logger = OrchLogger()

        # Start timing
        start_time = time.time()

        # Log command start with flags
        orch_logger.log_command_start("status", {
            "compact": compact,
            "session": session,
            "check_context": check_context,
            "format": output_format,
            "global": global_flag,
            "project": project,
            "workspace_filter": workspace_filter,
            "status_filter": status_filter
        })

        # Load registry (use custom path for testing)
        if registry_path:
            registry = AgentRegistry(registry_path=Path(registry_path))
        else:
            registry = AgentRegistry()

        # Resolve session default from config if not provided
        if not session:
            try:
                from orch.config import get_tmux_session_default
                session = get_tmux_session_default()
            except Exception:
                session = 'orchestrator'

        # Check tmux availability
        if not is_tmux_available():
            # Only show warnings in human format
            if output_format == 'human':
                click.echo("⚠️  Tmux not available or not running.")
                click.echo("   Cannot reconcile agent state with tmux windows.")
                click.echo("   Showing registry state only (may be stale).\n")
            # Skip reconciliation, continue with registry state
        else:
            # Collect active window IDs from ALL sessions where agents are registered
            # This fixes the bug where agents in workers-* sessions were incorrectly
            # marked as completed when status only checked the orchestrator session

            # Find all unique sessions from registered agents
            agent_sessions = set()
            for agent in registry.list_active_agents():
                # Extract session name from window target (e.g., "workers-price-watch:5" -> "workers-price-watch")
                window_target = agent.get('window') or ''
                if window_target and ':' in window_target:
                    session_name = window_target.split(':')[0]
                    agent_sessions.add(session_name)

            # Also include the default session (for backward compatibility)
            agent_sessions.add(session)

            # Build combined active_window_ids from all relevant sessions
            all_active_window_ids = []
            target_to_id = {}  # For legacy migration

            for sess in agent_sessions:
                session_obj = find_session(sess)
                if session_obj:
                    windows = list_windows(sess)
                    # Add to combined list
                    all_active_window_ids.extend([w['id'] for w in windows])
                    # Build legacy migration map
                    for w in windows:
                        target_to_id[f"{sess}:{w['index']}"] = w['id']

            # Legacy migration: upgrade agents missing window_id (one-time migration)
            migrated_count = 0
            for agent in registry.list_active_agents():
                if not agent.get('window_id') and agent['window'] in target_to_id:
                    agent['window_id'] = target_to_id[agent['window']]
                    migrated_count += 1

            # Save if any migrations occurred
            if migrated_count > 0:
                registry.save()

            # Always reconcile - even if no windows found, this detects agents whose windows closed
            registry.reconcile(all_active_window_ids)

        # Note: reconcile_opencode() removed in lifecycle simplification
        # OpenCode agents tracked via beads, not separate reconciliation

        # Get active agents
        agents = registry.list_active_agents()

        # Phase 2.5: Also get completed agents (for autonomous verification workflow)
        # Completed agents need to be processed via `orch complete`
        completed_agents = [a for a in registry.list_agents() if a.get('status') == 'completed']

        # Automatic project scoping: filter to git root if no filters specified
        # This allows running 'orch status' from subdirectories and seeing project agents
        # Skip auto-scoping when --global flag is set (show all agents across all projects)
        if not global_flag and not project and not workspace_filter and not status_filter:
            git_root = get_git_root()
            if git_root:
                project = git_root

        # Apply early filters (project, workspace pattern) before status checks
        if project or workspace_filter:
            agents = filter_agents(agents, project=project, workspace_pattern=workspace_filter)
            completed_agents = filter_agents(completed_agents, project=project, workspace_pattern=workspace_filter)

        if not agents:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log completion with zero agents
            orch_logger.log_command_complete("status", duration_ms, {
                "total_agents": 0,
                "critical": 0,
                "warnings": 0,
                "working": 0
            })

            # Output based on format
            if output_format == 'json':
                click.echo(output_json({"agents": []}))
            else:
                # Display context indicator (orchestrator/worker/interactive)
                detect_and_display_context()

                # Show helpful message with context about filtering
                if project or workspace_filter or status_filter:
                    click.echo("No agents match the specified filters.")
                    # If auto-scoped to git root, show helpful tip
                    if project and not workspace_filter and not status_filter:
                        git_root = get_git_root()
                        if git_root and project == git_root:
                            click.echo(f"   (Auto-scoped to git root: {project})")
                            click.echo("   💡 Tip: Use '--project .' to see all agents across all projects")
                else:
                    click.echo("No active agents found.")
            return

        # Show progress if checking context (slow operation) - only in human format
        total_agents_to_check = len(agents) + len(completed_agents)
        if check_context and output_format == 'human' and total_agents_to_check > 0:
            click.echo(f"\n⏳ Checking context usage for {total_agents_to_check} agent(s)...\n")

        # Check status of each active agent
        agent_statuses = []
        for agent in agents:
            status_obj = check_agent_status(agent, check_context=check_context)
            agent_statuses.append((agent, status_obj))

        # Phase 2.5: Check status of completed agents too
        completed_statuses = []
        for agent in completed_agents:
            status_obj = check_agent_status(agent, check_context=check_context)
            completed_statuses.append((agent, status_obj))

        # Filter by status/phase if requested
        if status_filter:
            agent_statuses = filter_agents_by_status(agent_statuses, status_filter)

        # Build cache of issue titles and convergence for agents spawned from beads issues
        issue_titles = {}
        issue_convergence = {}
        all_agents_to_display = [a for a, s in agent_statuses] + [a for a, s in completed_statuses]
        for agent in all_agents_to_display:
            beads_id = agent.get('beads_id')
            if beads_id and beads_id not in issue_titles:
                db_path = agent.get('beads_db_path')
                title = _get_issue_title(beads_id, db_path)
                if title:
                    issue_titles[beads_id] = title
                # Also fetch convergence (may be None if no children)
                convergence = _get_issue_convergence(beads_id, db_path)
                if convergence:
                    issue_convergence[beads_id] = convergence

        # Group by priority
        critical = [(a, s) for a, s in agent_statuses if s.priority == 'critical']
        warnings = [(a, s) for a, s in agent_statuses if s.priority == 'warning']
        info = [(a, s) for a, s in agent_statuses if s.priority == 'info']
        working = [(a, s) for a, s in agent_statuses if s.priority == 'ok']

        # Output based on format
        if output_format == 'json':
            # Serialize agent data to JSON
            agents_data = []
            for agent, status_obj in agent_statuses:
                agent_data = {
                    "agent_id": agent['id'],
                    "workspace": agent['workspace'],
                    "project": str(agent['project_dir']),
                    "phase": status_obj.phase,
                    "alerts": status_obj.alerts,
                    "priority": status_obj.priority,
                    "started_at": agent.get('spawned_at', 'unknown'),
                    "window": agent.get('window', 'unknown')
                }

                # Include beads issue info if available
                beads_id = agent.get('beads_id')
                if beads_id:
                    agent_data["beads_id"] = beads_id
                    if beads_id in issue_titles:
                        agent_data["beads_title"] = issue_titles[beads_id]

                # Include context info if requested
                if check_context and status_obj.context_info:
                    from orch.json_output import serialize_context_info
                    agent_data["context_info"] = serialize_context_info(status_obj.context_info)

                agents_data.append(agent_data)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log completion
            orch_logger.log_command_complete("status", duration_ms, {
                "total_agents": len(agents),
                "critical": len(critical),
                "warnings": len(warnings),
                "info": len(info),
                "working": len(working),
                "format": "json"
            })

            # Output JSON
            click.echo(output_json({"agents": agents_data}))
            return

        # Human format display
        # Display context indicator (orchestrator/worker/interactive)
        detect_and_display_context()

        click.echo(f"🎯 Agent Status ({len(agents)} active)")
        click.echo()

        if critical:
            click.echo(f"🔴 NEEDS ATTENTION ({len(critical)})")
            for agent, status_obj in critical:
                beads_id = agent.get('beads_id')
                title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                click.echo(f"  {agent['id']} (window {agent['window'].split(':')[1]}){title_suffix}")
                for alert in status_obj.alerts:
                    click.echo(f"    {alert['type'].upper()}: {alert['message']}")
                if check_context and status_obj.context_info:
                    _display_context_info(status_obj.context_info)
                # Phase 2: Display recommendation if available
                if status_obj.recommendation:
                    click.echo(f"     └─ {status_obj.recommendation}")
            click.echo()

        if warnings:
            click.echo(f"🟡 WARNINGS ({len(warnings)})")
            for agent, status_obj in warnings:
                window_info = f" (window {agent['window'].split(':')[1]})" if agent.get('window') else ""
                beads_id = agent.get('beads_id')
                title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                click.echo(f"  {agent['id']}{window_info}{title_suffix}")
                for alert in status_obj.alerts:
                    click.echo(f"    ⚠️  {alert['message']}")
                if check_context and status_obj.context_info:
                    _display_context_info(status_obj.context_info)
                # Phase 2: Display recommendation if available
                if status_obj.recommendation:
                    click.echo(f"     └─ {status_obj.recommendation}")
            click.echo()

        if info:
            click.echo(f"⏸️  AWAITING VALIDATION ({len(info)})")
            for agent, status_obj in info:
                beads_id = agent.get('beads_id')
                title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                click.echo(f"  {agent['id']} (window {agent['window'].split(':')[1]}){title_suffix} - Phase: {status_obj.phase}")
                for alert in status_obj.alerts:
                    click.echo(f"    ℹ️  {alert['message']}")
                if check_context and status_obj.context_info:
                    _display_context_info(status_obj.context_info)
                # Display recommendation if available
                if status_obj.recommendation:
                    click.echo(f"     └─ {status_obj.recommendation}")
            click.echo()

        if not compact and working:
            click.echo(f"🟢 WORKING ({len(working)})")
            for agent, status_obj in working:
                context_str = ""
                if check_context and status_obj.context_info:
                    ctx = status_obj.context_info
                    context_str = f" - Context: {ctx.percentage:.1f}%"
                beads_id = agent.get('beads_id')
                title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                click.echo(f"  {agent['id']}{title_suffix} - Phase: {status_obj.phase}{context_str}")

                # Phase 2: Display recommendation if available
                if status_obj.recommendation:
                    click.echo(f"     └─ {status_obj.recommendation}")
            click.echo()
        elif working:
            click.echo(f"🟢 WORKING ({len(working)})")
            click.echo(f"    Run 'orch status' without --compact to expand")
            click.echo()

        # Phase 2.5: Display completed agents with session grouping
        if completed_statuses:
            from orch.session import SessionTracker

            # Get session start time
            tracker = SessionTracker()
            session_start = tracker.get_session_start(session)

            # Group completed agents by session
            this_session = []
            previous_sessions = []

            for agent, status_obj in completed_statuses:
                if status_obj.completed_at and status_obj.completed_at > session_start:
                    this_session.append((agent, status_obj))
                else:
                    previous_sessions.append((agent, status_obj))

            # Display completed this session
            if this_session:
                click.echo(f"✅ COMPLETED THIS SESSION ({len(this_session)})")
                for agent, status_obj in this_session:
                    age_str = f" ({status_obj.age_str})" if status_obj.age_str else ""
                    beads_id = agent.get('beads_id')
                    title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                    click.echo(f"  {agent['id']}{title_suffix}{age_str}")
                    if status_obj.recommendation:
                        click.echo(f"     └─ {status_obj.recommendation}")
                click.echo()

            # Display older completed agents (stale)
            if previous_sessions and not compact:
                click.echo(f"⏰ COMPLETED EARLIER ({len(previous_sessions)})")
                for agent, status_obj in previous_sessions:
                    age_str = f" ({status_obj.age_str})" if status_obj.age_str else ""
                    stale_marker = "⏰ " if status_obj.is_stale else ""
                    beads_id = agent.get('beads_id')
                    title_suffix = f' - "{issue_titles[beads_id]}"{_format_convergence(issue_convergence.get(beads_id))}' if beads_id and beads_id in issue_titles else ""
                    click.echo(f"  {stale_marker}{agent['id']}{title_suffix}{age_str}")
                    if status_obj.recommendation:
                        click.echo(f"     └─ {status_obj.recommendation}")
                click.echo()

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log completion with summary
        orch_logger.log_command_complete("status", duration_ms, {
            "total_agents": len(agents),
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(info),
            "working": len(working),
            "completed": len(completed_statuses)
        })

    @cli.command()
    @click.argument('agent_id', required=False)
    @click.option('--issue', 'beads_issue', help='Inspect beads issue directly (bypass registry)')
    @click.option('--format', 'output_format', type=click.Choice(['human', 'json']), default='human', help='Output format')
    @click.option('--registry', 'registry_path', type=click.Path(exists=True), hidden=True, help='Registry path (for testing)')
    def check(agent_id, beads_issue, output_format, registry_path):
        """Detailed inspection of specific agent or beads issue."""
        from orch.json_output import serialize_agent_status, serialize_commit_info, output_json

        # Initialize logger
        orch_logger = OrchLogger()

        # Validate: either agent_id or --issue, but not both
        if agent_id and beads_issue:
            click.echo("Cannot specify both agent_id and --issue. Use one or the other.", err=True)
            raise click.Abort()

        if not agent_id and not beads_issue:
            click.echo("Must specify either agent_id or --issue.", err=True)
            raise click.Abort()

        # Handle --issue flag: inspect beads issue directly (bypass registry)
        if beads_issue:
            from orch.beads_integration import (
                BeadsIntegration,
                BeadsCLINotFoundError,
                BeadsIssueNotFoundError,
            )

            orch_logger.log_command_start("check", {"beads_issue": beads_issue, "format": output_format})

            try:
                beads = BeadsIntegration()
                issue = beads.get_issue(beads_issue)
                phase = beads.get_phase_from_comments(beads_issue)
            except BeadsCLINotFoundError:
                click.echo("bd CLI not found. Install beads or check PATH.", err=True)
                raise click.Abort()
            except BeadsIssueNotFoundError:
                click.echo(f"Beads issue '{beads_issue}' not found.", err=True)
                raise click.Abort()

            # Output based on format
            if output_format == 'json':
                result = {
                    "issue": {
                        "id": issue.id,
                        "title": issue.title,
                        "description": issue.description,
                        "status": issue.status,
                        "priority": issue.priority,
                        "phase": phase,
                        "notes": issue.notes,
                    }
                }
                click.echo(output_json(result))
                return

            # Human format
            click.echo()
            click.echo(f"🔍 Beads Issue: {issue.id}")
            click.echo("=" * 70)
            click.echo()
            click.echo(f"Title: {issue.title}")
            click.echo(f"Status: {issue.status}")
            click.echo(f"Priority: {issue.priority}")
            click.echo(f"Phase: {phase or 'None (no phase comments)'}")
            if issue.description:
                click.echo(f"\nDescription:\n{issue.description}")
            if issue.notes:
                click.echo(f"\nNotes: {issue.notes}")
            click.echo()
            return

        # Log check start
        orch_logger.log_command_start("check", {"agent_id": agent_id, "format": output_format})

        # Load registry (use custom path for testing)
        if registry_path:
            registry = AgentRegistry(registry_path=Path(registry_path))
        else:
            registry = AgentRegistry()

        agent = registry.find(agent_id)

        if not agent:
            orch_logger.log_error("check", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })
            click.echo(_format_agent_not_found_error(agent_id, registry))
            return

        # Check status (with git tracking)
        status_obj = check_agent_status(agent, check_git=True)

        # Output based on format
        if output_format == 'json':
            # Build JSON structure
            agent_data = {
                "id": agent['id'],
                "task": agent['task'],
                "window": agent['window'],
                "project_dir": str(agent['project_dir']),
                "spawned_at": agent['spawned_at'],
                "status": agent['status'],
                "phase": status_obj.phase,
                "priority": status_obj.priority,
                "alerts": status_obj.alerts,
                "violations": [
                    {"severity": v.severity, "message": v.message}
                    for v in status_obj.violations
                ] if status_obj.violations else []
            }

            # Include git info if available
            if status_obj.last_commit:
                agent_data["last_commit"] = serialize_commit_info(status_obj.last_commit)
                agent_data["commits_since_spawn"] = status_obj.commits_since_spawn

            # Include spawn context quality if SPAWN_CONTEXT.md exists
            project_dir = Path(agent['project_dir'])
            spawn_context_file = project_dir / agent['workspace'] / 'SPAWN_CONTEXT.md'
            if spawn_context_file.exists():
                spawn_context_content = spawn_context_file.read_text()
                spawn_quality = validate_spawn_context_quality(spawn_context_content)
                agent_data["spawn_context_quality"] = format_quality_for_json(spawn_quality)

            # Log completion
            orch_logger.log_event("check", f"Agent inspection complete: {agent_id}", {
                "agent_id": agent_id,
                "phase": status_obj.phase,
                "priority": status_obj.priority,
                "alerts_count": len(status_obj.alerts),
                "violations_count": len(status_obj.violations) if status_obj.violations else 0,
                "format": "json"
            }, level="INFO")

            # Output JSON
            click.echo(output_json({"agent": agent_data}))
            return

        # Human format
        click.echo()
        click.echo(f"🔍 Agent: {agent['id']}")
        click.echo("=" * 70)
        click.echo()

        # Basic info
        click.echo(f"Task: {agent['task']}")
        click.echo(f"Window: {agent['window']}")
        click.echo(f"Project: {agent['project_dir']}")
        click.echo(f"Spawned: {agent['spawned_at']}")
        click.echo(f"Status: {agent['status']}")
        click.echo()

        click.echo(f"Priority: {get_status_emoji(status_obj.priority)} {status_obj.priority}")
        project_dir = Path(agent['project_dir'])
        click.echo(f"Phase: {status_obj.phase}")

        # Show git info
        if status_obj.last_commit:
            commit = status_obj.last_commit
            click.echo(f"Last Commit: {commit.short_hash} - {commit.short_message}")
            click.echo(f"             by {commit.author} at {commit.timestamp.strftime('%Y-%m-%d %H:%M')}")
            if status_obj.commits_since_spawn > 0:
                click.echo(f"Commits Since Spawn: {status_obj.commits_since_spawn}")
        else:
            click.echo("Last Commit: None")

        click.echo()

        # Show alerts
        if status_obj.alerts:
            click.echo("🚨 Alerts:")
            for alert in status_obj.alerts:
                click.echo(f"  [{alert['level'].upper()}] {alert['type']}: {alert['message']}")
            click.echo()

        # Show violations
        if status_obj.violations:
            click.echo("⚠️  Pattern Violations:")
            for violation in status_obj.violations:
                click.echo(f"  [{violation.severity.upper()}] {violation.message}")
            click.echo()

        # Show spawn context quality if SPAWN_CONTEXT.md exists
        spawn_context_file = project_dir / agent['workspace'] / 'SPAWN_CONTEXT.md'
        if spawn_context_file.exists():
            spawn_context_content = spawn_context_file.read_text()
            spawn_quality = validate_spawn_context_quality(spawn_context_content)
            click.echo("📋 Spawn Context Quality:")
            click.echo("-" * 70)
            click.echo(format_quality_for_human(spawn_quality))
            click.echo("-" * 70)
            click.echo()

        # WORKSPACE.md no longer used - beads is source of truth for agent state

        # Log completion with inspection results
        orch_logger.log_event("check", f"Agent inspection complete: {agent_id}", {
            "agent_id": agent_id,
            "phase": status_obj.phase,
            "priority": status_obj.priority,
            "alerts_count": len(status_obj.alerts),
            "violations_count": len(status_obj.violations) if status_obj.violations else 0
        }, level="INFO")

        click.echo()

    @cli.command()
    @click.argument('agent_id')
    @click.option('--lines', default=20, help='Number of lines to capture (default: 20)')
    def tail(agent_id, lines):
        """Capture recent output from agent's tmux window."""
        from orch.tail import tail_agent_output

        # Initialize logger
        orch_logger = OrchLogger()

        # Load registry
        registry = AgentRegistry()
        agent = registry.find(agent_id)

        if not agent:
            orch_logger.log_error("tail", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })
            click.echo(f"❌ {_format_agent_not_found_error(agent_id, registry)}", err=True)
            raise click.Abort()

        # Capture output
        try:
            output = tail_agent_output(agent, lines=lines)

            # Log successful tail
            orch_logger.log_event("tail", f"Tail captured for {agent_id}", {
                "agent_id": agent_id,
                "lines_requested": lines,
                "output_length": len(output)
            }, level="INFO")

            click.echo(output)
        except RuntimeError as e:
            orch_logger.log_error("tail", f"Failed to capture tail: {agent_id}", {
                "agent_id": agent_id,
                "reason": str(e)
            })
            click.echo(f"❌ {e}", err=True)
            raise click.Abort()

    @cli.command()
    @click.option('--limit', default=50, help='Number of log entries to show (default: 50)')
    @click.option('--command', 'command_filter', help='Filter by command name (spawn, clean, status, etc.)')
    @click.option('--level', 'level_filter', help='Filter by log level (INFO, ERROR, etc.)')
    def logs(limit, command_filter, level_filter):
        """View orch command logs with optional filtering."""

        orch_logger = OrchLogger()

        # Read logs with filters
        entries = orch_logger.read_logs(
            limit=limit,
            command_filter=command_filter,
            level_filter=level_filter
        )

        if not entries:
            click.echo("No log entries found.")
            return

        # Display entries (most recent first)
        click.echo()
        click.echo(f"📋 Orch Logs (showing {len(entries)} entries)")
        click.echo()

        for entry in reversed(entries):  # Reverse to show most recent last
            # Format: timestamp LEVEL [command] message
            level_emoji = {
                'INFO': '✓',
                'ERROR': '✗',
                'WARNING': '⚠',
                'DEBUG': '·'
            }.get(entry['level'], '·')

            click.echo(f"{level_emoji} {entry['timestamp']} [{entry['command']}] {entry['message']}")

            # Show key data fields (but not all - keep output clean)
            if 'agent_id' in entry['data']:
                click.echo(f"   Agent: {entry['data']['agent_id']}")
            if 'duration_ms' in entry['data']:
                click.echo(f"   Duration: {entry['data']['duration_ms']}ms")

        click.echo()

    @cli.command()
    @click.option('--analytics', is_flag=True, help='Show analytics grouped by task type')
    @click.option('--skills', is_flag=True, help='Show skill usage analytics')
    @click.option('--days', default=30, type=int, help='Number of days to analyze (default: 30)')
    @click.option('--registry', type=click.Path(), help='Path to registry file (for testing)')
    @click.option('--format', 'output_format', type=click.Choice(['human', 'json']), default='human', help='Output format')
    def history(analytics, skills, days, registry, output_format):
        """Show completed agents with durations and analytics."""
        from orch.json_output import output_json

        # Load registry (custom path for testing)
        if registry:
            reg = AgentRegistry(registry_path=Path(registry))
        else:
            reg = AgentRegistry()

        # Skills analytics mode
        if skills:
            from orch.history import analyze_skill_usage, format_skill_analytics, export_skill_analytics_json

            # Determine project directory (current working directory)
            project_dir = Path.cwd()

            # Look for .orch directory to find project root
            check_dir = project_dir
            while check_dir != check_dir.parent:
                if (check_dir / '.orch').exists():
                    project_dir = check_dir
                    break
                check_dir = check_dir.parent

            # Analyze skill usage from workspaces
            skill_analytics = analyze_skill_usage(project_dir, days=days)

            # Output based on format
            if output_format == 'json':
                result = export_skill_analytics_json(skill_analytics)
                click.echo(output_json(result))
                return

            # Human format
            formatted_output = format_skill_analytics(skill_analytics)
            click.echo(formatted_output)

            return

        if analytics:
            # Analytics now delegated to beads
            click.echo("Analytics tracking moved to beads. Use 'bd stats' instead.")
            return

        # Show history view - list completed agents from registry
        completed_agents = [a for a in reg.list_agents() if a.get('status') == 'completed']

        if not completed_agents:
            if output_format == 'json':
                click.echo(output_json({"history": []}))
            else:
                click.echo("No completed agents in history.")
            return

        # Output based on format
        if output_format == 'json':
            click.echo(output_json({"history": completed_agents}))
            return

        # Human format
        click.echo()
        click.echo("📜 Agent History")
        click.echo("=" * 70)
        click.echo()

        for agent in sorted(completed_agents, key=lambda a: a.get('completed_at', ''), reverse=True):
            click.echo(f"{agent['id']}")
            click.echo(f"  Task: {agent['task']}")
            if agent.get('completed_at'):
                click.echo(f"  Completed: {agent['completed_at']}")
            click.echo()

    @cli.command()
    @click.argument('agent_id')
    @click.argument('message')
    def send(agent_id, message):
        """Send a message to a spawned agent.

        AGENT_ID is the agent's unique identifier (e.g., 'fix-tmux-registry-tracking'),
        not the window number. Use 'orch status' to see active agent IDs.

        Example: orch send fix-tmux-registry-tracking "Please provide a status update"
        """
        from orch.send import send_message_to_agent

        # Initialize logger
        orch_logger = OrchLogger()

        # Load registry
        registry = AgentRegistry()
        agent = registry.find(agent_id)

        if not agent:
            # Log error
            orch_logger.log_error("send", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })

            # Check if user provided numeric window ID instead of agent ID
            if agent_id.isdigit():
                # Try to find agent by window number for helpful error message
                from orch.config import get_tmux_session_default
                session_name = get_tmux_session_default()
                session = find_session(session_name)
                if session:
                    for window in session.windows:
                        if window.window_index == agent_id:
                            # Find agent with matching window
                            for a in registry.list_active_agents():
                                if a.get('window') == f"{session_name}:{agent_id}":
                                    click.echo(f"❌ Agent '{agent_id}' not found.", err=True)
                                    click.echo(f"   Did you mean agent ID '{a['id']}'? (currently in window {agent_id})", err=True)
                                    click.echo(f"   Use: orch send {a['id']} \"your message\"", err=True)
                                    raise click.Abort()

                click.echo(f"❌ {_format_agent_not_found_error(agent_id, registry)}", err=True)
                click.echo(f"   Note: Use agent ID (e.g., 'fix-tmux-registry-tracking'), not window number.", err=True)
            else:
                click.echo(f"❌ {_format_agent_not_found_error(agent_id, registry)}", err=True)

            raise click.Abort()

        # Send message
        try:
            send_message_to_agent(agent, message)

            # Log success
            orch_logger.log_event("send", f"Message sent to {agent_id}", {
                "agent_id": agent_id,
                "message_length": len(message),
                "window": agent.get('window', 'unknown')
            }, level="INFO")

            click.echo(f"✅ Message sent to {agent_id}")
        except RuntimeError as e:
            # Log error
            orch_logger.log_error("send", f"Failed to send message to {agent_id}", {
                "agent_id": agent_id,
                "reason": str(e)
            })

            click.echo(f"❌ {e}", err=True)
            raise click.Abort()

    @cli.command()
    @click.argument('agent_id')
    @click.option('--message', '-m', help='Custom continuation message (overrides auto-generated message)')
    @click.option('--dry-run', is_flag=True, help='Show what would be sent without actually sending')
    def resume(agent_id, message, dry_run):
        """Resume a paused agent with workspace-aware continuation.

        Automatically:
        - Reads workspace to get current state
        - Updates resumption timestamps
        - Sends continuation message (auto-generated or custom)

        AGENT_ID is the agent's unique identifier (use 'orch status' to see active agents).

        Examples:
            # Simple resume (auto-generated message from workspace)
            orch resume fix-authentication-bug

            # Resume with specific direction
            orch resume fix-authentication-bug -m "Skip Task 4, jump to Task 5"

            # Check what would be sent (dry-run)
            orch resume fix-authentication-bug --dry-run
        """
        from orch.send import send_message_to_agent

        # Initialize logger
        orch_logger = OrchLogger()

        # Load registry
        registry = AgentRegistry()
        agent = registry.find(agent_id)

        if not agent:
            # Log error
            orch_logger.log_error("resume", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })

            click.echo(f"❌ {_format_agent_not_found_error(agent_id, registry)}", err=True)
            raise click.Abort()

        # Get workspace path from agent
        workspace_rel = agent.get('workspace')
        if not workspace_rel:
            orch_logger.log_error("resume", f"No workspace found for agent {agent_id}", {
                "agent_id": agent_id,
                "reason": "no_workspace"
            })

            click.echo(f"❌ Agent '{agent_id}' has no workspace configured.", err=True)
            click.echo(f"   Resume requires workspace for context.", err=True)
            raise click.Abort()

        # Construct paths (SPAWN_CONTEXT.md is the coordination artifact)
        project_dir = Path(agent.get('project_dir', Path.cwd()))
        spawn_context_path = project_dir / workspace_rel / "SPAWN_CONTEXT.md"

        # Extract workspace name from path for display/messages
        workspace_name = workspace_rel.split('/')[-1] if workspace_rel else ''

        if not spawn_context_path.exists():
            orch_logger.log_error("resume", f"SPAWN_CONTEXT.md not found: {spawn_context_path}", {
                "agent_id": agent_id,
                "workspace": workspace_rel,
                "reason": "spawn_context_missing"
            })

            click.echo(f"❌ SPAWN_CONTEXT.md not found: {spawn_context_path}", err=True)
            click.echo(f"   Agent '{agent_id}' workspace: {workspace_rel}", err=True)
            raise click.Abort()

        # Generate continuation message (simple resume - no workspace parsing needed)
        # Custom message takes priority, otherwise use generic resume prompt
        if message:
            continuation_message = message
        else:
            continuation_message = (
                f"Session resumed. Read your SPAWN_CONTEXT.md at "
                f"{spawn_context_path} and continue your task. "
                f"Report your current phase via `bd comment`."
            )

        # Dry-run mode: show what would be sent
        if dry_run:
            click.echo(f"🔍 Dry-run mode for agent '{agent_id}':\n")
            click.echo(f"Workspace: {workspace_name}")
            click.echo(f"SPAWN_CONTEXT path: {spawn_context_path}\n")
            click.echo(f"Continuation message:")
            click.echo(f"---")
            click.echo(continuation_message)
            click.echo(f"---\n")
            return

        # Send continuation message
        try:
            send_message_to_agent(agent, continuation_message)

            # Log success
            orch_logger.log_event("resume", f"Agent {agent_id} resumed", {
                "agent_id": agent_id,
                "workspace": workspace_name,
                "message_length": len(continuation_message),
                "custom_message": bool(message)
            }, level="INFO")

            click.echo(f"✅ Agent '{agent_id}' resumed successfully")
            click.echo(f"   Workspace: {workspace_name}")
            if message:
                click.echo(f"   Used custom message")

        except RuntimeError as e:
            # Log error
            orch_logger.log_error("resume", f"Failed to send message to {agent_id}", {
                "agent_id": agent_id,
                "workspace": workspace_name,
                "reason": str(e)
            })

            click.echo(f"❌ {e}", err=True)
            raise click.Abort()

    @cli.command()
    @click.argument('agent_id')
    def question(agent_id):
        """Extract pending question from agent's tmux output."""
        import subprocess
        from orch.question import extract_question_from_text

        # Initialize logger
        orch_logger = OrchLogger()

        # Load registry
        registry = AgentRegistry()
        agent = registry.find(agent_id)

        if not agent:
            orch_logger.log_error("question", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })
            click.echo(_format_agent_not_found_error(agent_id, registry))
            return

        # Get tmux window content
        # Prefer stable window_id over window target (window indices change when tmux renumbers)
        window = agent.get('window_id', agent['window'])
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', window, '-p'],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout
        except subprocess.CalledProcessError:
            orch_logger.log_error("question", f"Failed to capture tmux output: {agent_id}", {
                "agent_id": agent_id,
                "window": window,
                "reason": "tmux_capture_failed"
            })
            click.echo(f"Failed to capture tmux output for window {window}")
            return

        # Extract question
        question_text = extract_question_from_text(output)

        if question_text:
            orch_logger.log_event("question", f"Question found for {agent_id}", {
                "agent_id": agent_id,
                "question_length": len(question_text)
            }, level="INFO")
            click.echo(question_text)
        else:
            orch_logger.log_event("question", f"No question found for {agent_id}", {
                "agent_id": agent_id
            }, level="INFO")
            click.echo("No question found in agent output.")

    @cli.command()
    @click.argument('agent_id')
    @click.option('--phase', default='Complete', help='Target phase to wait for (default: Complete)')
    @click.option('--timeout', default='30m', help='Timeout duration (e.g., 30s, 5m, 1h). Default: 30m')
    @click.option('--interval', default=5, type=int, help='Poll interval in seconds (default: 5)')
    @click.option('--quiet', '-q', is_flag=True, help='Suppress progress output')
    def wait(agent_id, phase, timeout, interval, quiet):
        """Block until agent reaches specified phase.

        Waits for an agent to reach a target phase, polling at regular intervals.
        Replaces manual 'sleep X && orch check' loops with cleaner workflow.

        \b
        Examples:
          orch wait fix-auth-bug                    # Wait for Complete (default)
          orch wait fix-auth-bug --phase Complete   # Explicit phase
          orch wait fix-auth-bug --timeout 5m       # 5 minute timeout
          orch wait fix-auth-bug -q                 # Quiet mode (no progress)

        \b
        Exit codes:
          0 - Agent reached target phase
          1 - Timeout reached
          2 - Agent not found

        \b
        Timeout format:
          30s  - 30 seconds
          5m   - 5 minutes
          1h   - 1 hour
          1h30m - 1 hour 30 minutes
        """
        import sys
        import re

        # Initialize logger
        orch_logger = OrchLogger()

        # Start timing
        start_time = time.time()

        # Log command start
        orch_logger.log_command_start("wait", {
            "agent_id": agent_id,
            "target_phase": phase,
            "timeout": timeout,
            "interval": interval
        })

        # Parse timeout duration
        timeout_seconds = _parse_timeout(timeout)
        if timeout_seconds is None:
            click.echo(f"❌ Invalid timeout format: '{timeout}'", err=True)
            click.echo("   Use formats like: 30s, 5m, 1h, 1h30m", err=True)
            sys.exit(2)

        # Load registry
        registry = AgentRegistry()
        agent = registry.find(agent_id)

        if not agent:
            orch_logger.log_error("wait", f"Agent not found: {agent_id}", {
                "agent_id": agent_id,
                "reason": "agent_not_found"
            })
            click.echo(f"❌ {_format_agent_not_found_error(agent_id, registry)}", err=True)
            sys.exit(2)

        # Initial status check
        if not quiet:
            click.echo(f"⏳ Waiting for agent '{agent_id}' to reach phase '{phase}'...")
            click.echo(f"   Timeout: {timeout}, Poll interval: {interval}s")

        # Polling loop
        last_phase = None
        while True:
            # Check agent status
            status_obj = check_agent_status(agent)
            current_phase = status_obj.phase

            # Log phase changes
            if current_phase != last_phase:
                if not quiet:
                    click.echo(f"   Current phase: {current_phase}")
                last_phase = current_phase

            # Check if target phase reached (case-insensitive partial match)
            if current_phase and phase.lower() in current_phase.lower():
                # Success!
                duration_ms = int((time.time() - start_time) * 1000)
                orch_logger.log_command_complete("wait", duration_ms, {
                    "agent_id": agent_id,
                    "target_phase": phase,
                    "final_phase": current_phase,
                    "success": True
                })

                if not quiet:
                    elapsed = time.time() - start_time
                    click.echo(f"✅ Agent '{agent_id}' reached phase '{current_phase}' after {_format_duration(elapsed)}")

                sys.exit(0)

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                # Timeout reached
                duration_ms = int(elapsed * 1000)
                orch_logger.log_error("wait", f"Timeout waiting for agent: {agent_id}", {
                    "agent_id": agent_id,
                    "target_phase": phase,
                    "final_phase": current_phase,
                    "elapsed_seconds": elapsed,
                    "timeout_seconds": timeout_seconds
                })

                if not quiet:
                    click.echo(f"⏰ Timeout after {_format_duration(elapsed)}", err=True)
                    click.echo(f"   Agent '{agent_id}' is still at phase '{current_phase}'", err=True)

                sys.exit(1)

            # Wait before next poll
            time.sleep(interval)

            # Reload agent info (in case registry was updated)
            registry._load()
            agent = registry.find(agent_id)
            if not agent:
                # Agent was removed during wait
                orch_logger.log_error("wait", f"Agent disappeared: {agent_id}", {
                    "agent_id": agent_id,
                    "reason": "agent_removed"
                })
                click.echo(f"❌ Agent '{agent_id}' was removed from registry during wait", err=True)
                sys.exit(2)


def _parse_timeout(timeout_str: str) -> int | None:
    """Parse timeout string like '30s', '5m', '1h', '1h30m' to seconds.

    Args:
        timeout_str: Timeout string (e.g., '30s', '5m', '1h', '1h30m')

    Returns:
        Timeout in seconds, or None if invalid format
    """
    import re

    if not timeout_str:
        return None

    # Try to parse as integer (seconds)
    if timeout_str.isdigit():
        return int(timeout_str)

    # Parse duration components
    total_seconds = 0
    pattern = r'(\d+)([smh])'
    matches = re.findall(pattern, timeout_str.lower())

    if not matches:
        return None

    for value, unit in matches:
        value = int(value)
        if unit == 's':
            total_seconds += value
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 'h':
            total_seconds += value * 3600

    return total_seconds if total_seconds > 0 else None


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration (e.g., '5m 30s', '1h 15m')
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
