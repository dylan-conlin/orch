"""Work daemon for autonomous beads processing.

This module implements a background daemon that:
1. Polls `bd ready` across multiple projects registered with kb
2. Filters for issues with `triage:ready` label
3. Spawns agents autonomously using `orch work`
4. Respects concurrency limits

Architecture decision: kn-5a82d1 - Daemon + Interactive split for orchestration
Design reference: .kb/investigations/2025-12-12-inv-design-issue-refinement-stage-draft.md
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class DaemonConfig:
    """Configuration for the work daemon."""

    poll_interval_seconds: int = 60
    max_concurrent_agents: int = 3
    required_label: str = "triage:ready"
    dry_run: bool = False
    verbose: bool = False


@dataclass
class ReadyIssue:
    """An issue ready for autonomous processing."""

    id: str
    title: str
    issue_type: str
    labels: list
    project_path: Path


def get_kb_projects() -> list[Path]:
    """Get registered projects from kb's project registry.

    Uses 'kb projects list --json' to get projects.
    Falls back to empty list if kb is not available.

    Returns:
        List of Path objects for registered projects.
    """
    from orch.project_discovery import get_kb_projects as _get_kb_projects

    return _get_kb_projects(filter_existing=True)


def get_ready_issues_for_project(
    project_path: Path,
    required_label: Optional[str] = None,
) -> list[ReadyIssue]:
    """Get ready issues for a single project.

    Args:
        project_path: Path to the project directory
        required_label: Optional label filter (e.g., "triage:ready")

    Returns:
        List of ReadyIssue objects for this project.
    """
    beads_dir = project_path / ".beads"
    if not beads_dir.exists():
        return []

    try:
        result = subprocess.run(
            ["bd", "ready", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_path),
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    ready_issues = []
    for issue in issues:
        issue_labels = issue.get("labels") or []

        # Filter by required label if specified
        if required_label and required_label not in issue_labels:
            continue

        ready_issues.append(
            ReadyIssue(
                id=issue.get("id", ""),
                title=issue.get("title", ""),
                issue_type=issue.get("issue_type", "task"),
                labels=issue_labels,
                project_path=project_path,
            )
        )

    return ready_issues


def get_all_ready_issues(
    projects: list[Path],
    required_label: Optional[str] = None,
) -> list[ReadyIssue]:
    """Get all ready issues across multiple projects.

    Args:
        projects: List of project paths to poll
        required_label: Optional label filter (e.g., "triage:ready")

    Returns:
        List of ReadyIssue objects from all projects.
    """
    all_issues = []
    for project_path in projects:
        issues = get_ready_issues_for_project(project_path, required_label)
        all_issues.extend(issues)
    return all_issues


def count_active_agents() -> int:
    """Count currently active agents from registry.

    Returns:
        Number of active agents.
    """
    try:
        from orch.registry import AgentRegistry

        registry = AgentRegistry()
        agents = registry.list_agents()
        return sum(1 for a in agents if a.get("status") == "active")
    except Exception:
        return 0


def spawn_issue(issue: ReadyIssue, dry_run: bool = False) -> bool:
    """Spawn an agent for an issue using orch work.

    Args:
        issue: The ReadyIssue to spawn
        dry_run: If True, print what would happen but don't spawn

    Returns:
        True if spawn succeeded (or dry_run), False on failure.
    """
    project_name = issue.project_path.name

    if dry_run:
        print(f"  [DRY RUN] Would spawn: {issue.id} ({project_name})")
        print(f"    Title: {issue.title[:60]}...")
        print(f"    Type: {issue.issue_type}")
        return True

    try:
        # Use orch work to spawn with skill inference
        result = subprocess.run(
            ["orch", "work", issue.id, "--yes", "--project", project_name],
            capture_output=True,
            text=True,
            cwd=str(issue.project_path),
            timeout=120,
            env={**os.environ, "ORCH_AUTO_CONFIRM": "1"},
        )

        if result.returncode == 0:
            print(f"  ✓ Spawned: {issue.id} ({project_name})")
            return True
        else:
            print(f"  ✗ Failed to spawn {issue.id}: {result.stderr[:100]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout spawning {issue.id}")
        return False
    except Exception as e:
        print(f"  ✗ Error spawning {issue.id}: {e}")
        return False


def run_daemon_cycle(config: DaemonConfig) -> dict:
    """Run a single daemon polling cycle.

    Args:
        config: DaemonConfig with polling parameters

    Returns:
        Dict with cycle stats: {projects_polled, issues_found, agents_spawned}
    """
    stats = {
        "projects_polled": 0,
        "issues_found": 0,
        "agents_spawned": 0,
        "skipped_at_limit": 0,
    }

    # Get registered projects
    projects = get_kb_projects()
    stats["projects_polled"] = len(projects)

    if not projects:
        if config.verbose:
            print("No projects found in kb registry")
        return stats

    # Get ready issues with label filter
    ready_issues = get_all_ready_issues(projects, config.required_label)
    stats["issues_found"] = len(ready_issues)

    if not ready_issues:
        if config.verbose:
            print(f"No ready issues with label '{config.required_label}'")
        return stats

    # Check concurrency limit
    active_count = count_active_agents()
    slots_available = max(0, config.max_concurrent_agents - active_count)

    if slots_available == 0:
        stats["skipped_at_limit"] = len(ready_issues)
        if config.verbose:
            print(f"At agent limit ({config.max_concurrent_agents}), skipping spawn")
        return stats

    # Spawn agents up to limit
    for issue in ready_issues[:slots_available]:
        if spawn_issue(issue, dry_run=config.dry_run):
            stats["agents_spawned"] += 1

    stats["skipped_at_limit"] = max(0, len(ready_issues) - slots_available)
    return stats


def run_daemon(config: DaemonConfig) -> None:
    """Run the daemon polling loop.

    Args:
        config: DaemonConfig with polling parameters

    This function runs indefinitely until interrupted.
    """
    print(f"Work daemon started")
    print(f"  Poll interval: {config.poll_interval_seconds}s")
    print(f"  Max concurrent: {config.max_concurrent_agents}")
    print(f"  Required label: {config.required_label}")
    print(f"  Dry run: {config.dry_run}")
    print()

    try:
        while True:
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{timestamp}] Polling...")

            stats = run_daemon_cycle(config)

            if config.verbose or stats["agents_spawned"] > 0:
                print(f"  Projects: {stats['projects_polled']}")
                print(f"  Ready issues: {stats['issues_found']}")
                print(f"  Spawned: {stats['agents_spawned']}")
                if stats["skipped_at_limit"] > 0:
                    print(f"  Skipped (at limit): {stats['skipped_at_limit']}")

            time.sleep(config.poll_interval_seconds)

    except KeyboardInterrupt:
        print("\nDaemon stopped")


def run_once(config: DaemonConfig) -> dict:
    """Run a single daemon cycle (for testing or one-shot use).

    Args:
        config: DaemonConfig with polling parameters

    Returns:
        Dict with cycle stats
    """
    return run_daemon_cycle(config)
