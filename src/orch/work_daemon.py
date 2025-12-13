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
class FocusConfig:
    """Configuration for focus-based prioritization.

    Read from ~/.orch/focus.json to prioritize certain projects,
    labels, or issue types when the daemon spawns agents.
    """

    priority_projects: list = None  # type: ignore
    priority_labels: list = None  # type: ignore
    priority_issue_types: list = None  # type: ignore
    enabled: bool = True

    def __post_init__(self):
        """Initialize empty lists for None values."""
        if self.priority_projects is None:
            self.priority_projects = []
        if self.priority_labels is None:
            self.priority_labels = []
        if self.priority_issue_types is None:
            self.priority_issue_types = []


@dataclass
class DaemonConfig:
    """Configuration for the work daemon."""

    poll_interval_seconds: int = 60
    max_concurrent_agents: int = 3
    required_label: str = "triage:ready"
    dry_run: bool = False
    verbose: bool = False
    use_focus: bool = True  # Enable focus-based prioritization


@dataclass
class ReadyIssue:
    """An issue ready for autonomous processing."""

    id: str
    title: str
    issue_type: str
    labels: list
    project_path: Path


def get_focus_path() -> Path:
    """Get path to focus configuration file.

    Returns:
        Path to ~/.orch/focus.json
    """
    return Path.home() / ".orch" / "focus.json"


def load_focus_config() -> FocusConfig:
    """Load focus configuration from ~/.orch/focus.json.

    If the file doesn't exist or is invalid, returns default FocusConfig.

    Returns:
        FocusConfig with prioritization settings.
    """
    focus_path = get_focus_path()

    if not focus_path.exists():
        return FocusConfig()

    try:
        data = json.loads(focus_path.read_text())
    except (json.JSONDecodeError, OSError):
        return FocusConfig()

    return FocusConfig(
        priority_projects=data.get("priority_projects", []),
        priority_labels=data.get("priority_labels", []),
        priority_issue_types=data.get("priority_issue_types", []),
        enabled=data.get("enabled", True),
    )


def prioritize_issues(issues: list[ReadyIssue], config: FocusConfig) -> list[ReadyIssue]:
    """Prioritize issues based on focus configuration.

    Issues matching priority criteria are moved to the front of the list.
    Higher priority scores (more matches) come first.

    Args:
        issues: List of ReadyIssue objects to prioritize
        config: FocusConfig with prioritization settings

    Returns:
        Sorted list with focus-aligned issues first.
    """
    if not config.enabled or not issues:
        return issues

    # If no priorities configured, preserve original order
    if not config.priority_projects and not config.priority_labels and not config.priority_issue_types:
        return issues

    def priority_score(issue: ReadyIssue) -> int:
        """Calculate priority score for an issue (higher = more priority)."""
        score = 0

        # Check project priority
        if issue.project_path.name in config.priority_projects:
            score += 1

        # Check label priorities
        for label in config.priority_labels:
            if label in issue.labels:
                score += 1

        # Check issue type priority
        if issue.issue_type in config.priority_issue_types:
            score += 1

        return score

    # Sort by priority score descending (stable sort preserves relative order)
    return sorted(issues, key=priority_score, reverse=True)


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

    # Apply focus-based prioritization if enabled
    if config.use_focus:
        focus_config = load_focus_config()
        ready_issues = prioritize_issues(ready_issues, focus_config)

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
