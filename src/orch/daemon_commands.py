"""Daemon commands for orch CLI.

Commands for managing the work daemon.
"""

import click
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from orch.work_daemon import DaemonConfig, run_daemon, run_once


def get_pidfile_path() -> Path:
    """Get path to daemon PID file."""
    return Path.home() / ".orch" / "daemon.pid"


def get_logfile_path() -> Path:
    """Get path to daemon log file."""
    return Path.home() / ".orch" / "daemon.log"


def is_daemon_running() -> tuple[bool, Optional[int]]:
    """Check if daemon is currently running.

    Returns:
        Tuple of (is_running, pid). pid is None if not running.
    """
    pidfile = get_pidfile_path()
    if not pidfile.exists():
        return (False, None)

    try:
        pid = int(pidfile.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)
        return (True, pid)
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file is stale
        pidfile.unlink(missing_ok=True)
        return (False, None)


def register_daemon_commands(cli):
    """Register daemon-related commands with the CLI."""

    @cli.group()
    def daemon():
        """Manage the work daemon for autonomous beads processing.

        The daemon polls `bd ready` across registered projects and spawns
        agents for issues with the `triage:ready` label.

        \b
        Examples:
            orch daemon run              # Run daemon in foreground
            orch daemon run --dry-run    # Preview what would be spawned
            orch daemon once             # Run one polling cycle
            orch daemon status           # Check if daemon is running
        """
        pass

    @daemon.command()
    @click.option("--poll-interval", default=60, help="Seconds between polls (default: 60)")
    @click.option("--max-agents", default=3, help="Max concurrent agents (default: 3)")
    @click.option("--label", default="triage:ready", help="Required label for spawn (default: triage:ready)")
    @click.option("--dry-run", is_flag=True, help="Preview spawns without executing")
    @click.option("--verbose", "-v", is_flag=True, help="Verbose output")
    def run(poll_interval, max_agents, label, dry_run, verbose):
        """Run the work daemon in foreground.

        Polls `bd ready` across all projects registered with kb and spawns
        agents for issues that have the required label (default: triage:ready).

        \b
        Examples:
            orch daemon run                     # Run with defaults
            orch daemon run --dry-run           # Preview spawns
            orch daemon run --poll-interval 30  # Poll every 30 seconds
            orch daemon run --max-agents 5      # Allow 5 concurrent agents
        """
        config = DaemonConfig(
            poll_interval_seconds=poll_interval,
            max_concurrent_agents=max_agents,
            required_label=label,
            dry_run=dry_run,
            verbose=verbose,
        )

        run_daemon(config)

    @daemon.command()
    @click.option("--label", default="triage:ready", help="Required label for spawn (default: triage:ready)")
    @click.option("--max-agents", default=3, help="Max concurrent agents (default: 3)")
    @click.option("--dry-run", is_flag=True, help="Preview spawns without executing")
    @click.option("--verbose", "-v", is_flag=True, help="Verbose output")
    def once(label, max_agents, dry_run, verbose):
        """Run a single polling cycle.

        Useful for testing or one-shot processing.

        \b
        Examples:
            orch daemon once                # Run one cycle
            orch daemon once --dry-run      # Preview what would be spawned
            orch daemon once --verbose      # Show detailed output
        """
        config = DaemonConfig(
            poll_interval_seconds=0,  # Not used for once
            max_concurrent_agents=max_agents,
            required_label=label,
            dry_run=dry_run,
            verbose=verbose,
        )

        stats = run_once(config)

        if not dry_run and not verbose:
            # Always show summary for non-verbose mode
            click.echo(f"Projects polled: {stats['projects_polled']}")
            click.echo(f"Ready issues (with label): {stats['issues_found']}")
            click.echo(f"Agents spawned: {stats['agents_spawned']}")
            if stats['skipped_at_limit'] > 0:
                click.echo(f"Skipped (at limit): {stats['skipped_at_limit']}")

    @daemon.command()
    def status():
        """Check daemon status.

        Shows whether the daemon is running and any relevant stats.
        """
        is_running, pid = is_daemon_running()

        if is_running:
            click.echo(f"Daemon is running (PID: {pid})")
        else:
            click.echo("Daemon is not running")

        # Also show quick stats
        try:
            from orch.registry import AgentRegistry

            registry = AgentRegistry()
            agents = registry.list_agents()
            active = sum(1 for a in agents if a.get("status") == "active")
            click.echo(f"\nActive agents: {active}")
        except Exception:
            pass

        # Show projects count
        try:
            from orch.project_discovery import get_kb_projects

            projects = get_kb_projects(filter_existing=True)
            click.echo(f"Registered projects: {len(projects)}")
        except Exception:
            pass

    @daemon.command()
    @click.option("--label", default="triage:ready", help="Required label filter (default: triage:ready)")
    def preview(label):
        """Preview issues that would be spawned.

        Shows ready issues across all projects that match the label filter,
        without actually spawning any agents.
        """
        from orch.work_daemon import get_kb_projects, get_all_ready_issues

        projects = get_kb_projects()
        if not projects:
            click.echo("No projects found in kb registry")
            return

        ready_issues = get_all_ready_issues(projects, label)

        if not ready_issues:
            click.echo(f"No ready issues with label '{label}'")
            click.echo(f"\nTo mark an issue ready for daemon processing:")
            click.echo(f"  bd label <issue-id> {label}")
            return

        click.echo(f"Ready issues with label '{label}':\n")

        # Group by project
        by_project = {}
        for issue in ready_issues:
            project_name = issue.project_path.name
            if project_name not in by_project:
                by_project[project_name] = []
            by_project[project_name].append(issue)

        for project_name, issues in sorted(by_project.items()):
            click.echo(f"  {project_name}:")
            for issue in issues:
                click.echo(f"    [{issue.issue_type}] {issue.id}: {issue.title[:50]}")
            click.echo()

        click.echo(f"Total: {len(ready_issues)} issue(s) across {len(by_project)} project(s)")
