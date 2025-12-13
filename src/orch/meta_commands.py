"""Meta orchestration commands for cross-project coordination.

Provides focus, drift, and next commands for strategic alignment.

Data model:
- ~/.orch/focus.json - Focus state and history
- ~/.orch/projects.json - Project registry (used by daemon)

Commands:
- orch focus [DESCRIPTION] - Set or show north star
- orch drift - Check alignment with current focus
- orch next - Suggest next action based on focus
"""

from __future__ import annotations

import json
import click
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FocusState:
    """Represents the current focus/north star."""

    description: str
    set_at: datetime
    aligned_projects: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "description": self.description,
            "set_at": self.set_at.isoformat(),
            "aligned_projects": self.aligned_projects,
            "success_criteria": self.success_criteria,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FocusState":
        """Create from dict (JSON deserialization)."""
        set_at = data.get("set_at")
        if isinstance(set_at, str):
            # Parse ISO format datetime
            set_at = datetime.fromisoformat(set_at.replace("Z", "+00:00"))
        elif set_at is None:
            set_at = datetime.now(timezone.utc)

        return cls(
            description=data.get("description", ""),
            set_at=set_at,
            aligned_projects=data.get("aligned_projects", []),
            success_criteria=data.get("success_criteria", []),
        )


def get_focus_file_path() -> Path:
    """Get path to focus.json file."""
    return Path.home() / ".orch" / "focus.json"


def load_focus() -> Optional[FocusState]:
    """Load current focus from file.

    Returns:
        FocusState if focus is set, None otherwise.
    """
    focus_file = get_focus_file_path()
    if not focus_file.exists():
        return None

    try:
        data = json.loads(focus_file.read_text())
        current = data.get("current")
        if current:
            return FocusState.from_dict(current)
        return None
    except (json.JSONDecodeError, KeyError):
        return None


def save_focus(focus: FocusState) -> None:
    """Save focus to file.

    Preserves history of previous focuses.
    """
    focus_file = get_focus_file_path()

    # Load existing data to preserve history
    existing_data = {}
    if focus_file.exists():
        try:
            existing_data = json.loads(focus_file.read_text())
        except json.JSONDecodeError:
            existing_data = {}

    # Move current to history if it exists
    history = existing_data.get("history", [])
    if "current" in existing_data:
        old_current = existing_data["current"]
        old_current["ended_at"] = datetime.now(timezone.utc).isoformat()
        history.append(old_current)

    # Save new data
    new_data = {
        "current": focus.to_dict(),
        "history": history[-10:],  # Keep last 10 focuses
    }

    # Ensure directory exists
    focus_file.parent.mkdir(parents=True, exist_ok=True)
    focus_file.write_text(json.dumps(new_data, indent=2))


def set_focus(
    description: str,
    aligned_projects: Optional[List[str]] = None,
    success_criteria: Optional[List[str]] = None,
) -> FocusState:
    """Set new focus.

    Args:
        description: The focus description (north star)
        aligned_projects: List of project names that align with this focus
        success_criteria: List of criteria that define success

    Returns:
        The created FocusState
    """
    focus = FocusState(
        description=description,
        set_at=datetime.now(timezone.utc),
        aligned_projects=aligned_projects or [],
        success_criteria=success_criteria or [],
    )
    save_focus(focus)
    return focus


def get_current_focus() -> Optional[FocusState]:
    """Get current focus if set.

    Returns:
        Current FocusState or None if not set.
    """
    return load_focus()


def get_current_project() -> Optional[str]:
    """Get current project name from working directory.

    Returns:
        Project name (directory name with .orch/ or .beads/) or None.
    """
    cwd = Path.cwd()

    # Check if current directory has .orch or .beads
    if (cwd / ".orch").exists() or (cwd / ".beads").exists():
        return cwd.name

    # Walk up to find project root
    for parent in cwd.parents:
        if (parent / ".orch").exists() or (parent / ".beads").exists():
            return parent.name

    return None


def check_drift(time_threshold_hours: int = 2) -> Dict[str, Any]:
    """Check if currently drifting from focus.

    Args:
        time_threshold_hours: Hours after which time warning is triggered

    Returns:
        Dict with drift status:
        - drifting: bool - True if actively drifting
        - reason: str - Why drifting (or "no_focus_set")
        - time_warning: bool - True if working too long without progress
        - focus: Optional[FocusState] - Current focus if set
    """
    focus = get_current_focus()

    if focus is None:
        return {
            "drifting": False,
            "reason": "no_focus_set",
            "time_warning": False,
            "focus": None,
        }

    current_project = get_current_project()
    result = {
        "drifting": False,
        "reason": "",
        "time_warning": False,
        "focus": focus,
        "current_project": current_project,
    }

    # Check project alignment
    if focus.aligned_projects:
        if current_project and current_project not in focus.aligned_projects:
            result["drifting"] = True
            result["reason"] = f"Working in {current_project}, focus is on {', '.join(focus.aligned_projects)}"

    # Check time-based drift
    time_since_focus = datetime.now(timezone.utc) - focus.set_at
    if time_since_focus > timedelta(hours=time_threshold_hours):
        result["time_warning"] = True
        hours = time_since_focus.total_seconds() / 3600
        result["time_message"] = f"{hours:.1f} hours since focus set"

    return result


def get_all_ready_issues() -> List[Dict[str, Any]]:
    """Get all ready issues across registered projects.

    Returns:
        List of issue dicts with project info.
    """
    # Import here to avoid circular imports
    from orch.project_discovery import get_kb_projects

    issues = []

    try:
        projects = get_kb_projects(filter_existing=True)
    except Exception:
        projects = []

    for project_path in projects:
        project_name = project_path.name

        # Try to get ready issues from beads
        try:
            import subprocess

            result = subprocess.run(
                ["bd", "ready", "--json"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                project_issues = json.loads(result.stdout)
                for issue in project_issues:
                    issue["project"] = project_name
                    issue["project_path"] = str(project_path)
                    issues.append(issue)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            continue

    return issues


def get_next_suggestions(limit: int = 5) -> List[Dict[str, Any]]:
    """Get next action suggestions based on focus.

    Prioritizes:
    1. Issues from aligned projects
    2. Higher priority issues
    3. Issues with fewer blockers

    Args:
        limit: Maximum number of suggestions to return

    Returns:
        List of suggested issues with alignment info.
    """
    focus = get_current_focus()
    issues = get_all_ready_issues()

    if not issues:
        return []

    aligned_projects = focus.aligned_projects if focus else []

    # Add alignment info to each issue
    for issue in issues:
        project = issue.get("project", "")
        issue["aligned"] = project in aligned_projects if aligned_projects else False
        # Calculate priority score (lower is better)
        # Aligned issues get priority boost
        base_priority = issue.get("priority", 3)
        issue["score"] = base_priority - (2 if issue["aligned"] else 0)

    # Sort by score (lower first), then by aligned status
    sorted_issues = sorted(
        issues,
        key=lambda x: (x["score"], not x["aligned"], x.get("title", "")),
    )

    return sorted_issues[:limit]


def register_meta_commands(cli):
    """Register meta orchestration commands with the CLI."""

    @cli.command()
    @click.argument("description", required=False)
    @click.option("--project", "-p", multiple=True, help="Aligned project (can specify multiple)")
    @click.option("--criteria", "-c", multiple=True, help="Success criterion (can specify multiple)")
    @click.option("--clear", is_flag=True, help="Clear current focus")
    def focus(description, project, criteria, clear):
        """Set or show the current focus (north star).

        Sets a focus to guide cross-project prioritization. When focus is set,
        drift detection warns when working on non-aligned projects.

        \b
        Examples:
            orch focus "Ship snap MVP"
            orch focus "Ship snap MVP" -p snap -p orch-cli
            orch focus "Ship snap MVP" -c "snap-4x4 closed"
            orch focus                   # Show current focus
            orch focus --clear           # Clear focus
        """
        if clear:
            focus_file = get_focus_file_path()
            if focus_file.exists():
                # Load and clear current, move to history
                data = json.loads(focus_file.read_text())
                if "current" in data:
                    history = data.get("history", [])
                    data["current"]["ended_at"] = datetime.now(timezone.utc).isoformat()
                    history.append(data["current"])
                    data["current"] = None
                    data["history"] = history[-10:]
                    focus_file.write_text(json.dumps(data, indent=2))
                    click.echo("Focus cleared")
                else:
                    click.echo("No focus to clear")
            else:
                click.echo("No focus to clear")
            return

        if description:
            # Set new focus
            projects_list = list(project) if project else []
            criteria_list = list(criteria) if criteria else []

            new_focus = set_focus(
                description=description,
                aligned_projects=projects_list,
                success_criteria=criteria_list,
            )

            click.echo(f"🎯 Focus set: {new_focus.description}")
            if projects_list:
                click.echo(f"   Aligned projects: {', '.join(projects_list)}")
            if criteria_list:
                click.echo(f"   Success criteria:")
                for c in criteria_list:
                    click.echo(f"     - {c}")
        else:
            # Show current focus
            current = get_current_focus()
            if current:
                time_ago = datetime.now(timezone.utc) - current.set_at
                hours = time_ago.total_seconds() / 3600

                click.echo(f"🎯 Current Focus")
                click.echo(f"   {current.description}")
                click.echo(f"   Set {hours:.1f} hours ago")

                if current.aligned_projects:
                    click.echo(f"   Aligned projects: {', '.join(current.aligned_projects)}")

                if current.success_criteria:
                    click.echo(f"   Success criteria:")
                    for c in current.success_criteria:
                        click.echo(f"     - {c}")
            else:
                click.echo("No focus set")
                click.echo("")
                click.echo("Set a focus with: orch focus \"Your north star\"")

    @cli.command()
    @click.option("--quiet", "-q", is_flag=True, help="Only output if drifting")
    def drift(quiet):
        """Check alignment with current focus.

        Detects drift based on:
        - Current project vs aligned projects
        - Time since focus was set
        - Progress on success criteria

        \b
        Examples:
            orch drift              # Full drift check
            orch drift --quiet      # Only warn if drifting
        """
        result = check_drift()

        if result["reason"] == "no_focus_set":
            if not quiet:
                click.echo("No focus set - set one with: orch focus \"Your goal\"")
            return

        focus = result.get("focus")
        current_project = result.get("current_project", "unknown")

        if result["drifting"]:
            click.echo(f"⚠️  Drifting!")
            click.echo(f"   {result['reason']}")
            click.echo(f"   Focus: {focus.description}")
            return

        if result.get("time_warning"):
            if not quiet:
                click.echo(f"⏰ Time check: {result.get('time_message', 'Extended session')}")
                click.echo(f"   Focus: {focus.description}")
            return

        if not quiet:
            click.echo(f"✅ On track")
            click.echo(f"   Focus: {focus.description}")
            click.echo(f"   Current project: {current_project}")

    @cli.command()
    @click.option("--limit", "-n", default=5, help="Number of suggestions (default: 5)")
    @click.option("--all-projects", is_flag=True, help="Show issues from all projects, not just aligned")
    def next(limit, all_projects):
        """Suggest next action based on focus.

        Prioritizes issues from focus-aligned projects, then by priority.
        Shows ready issues that can be worked on immediately.

        \b
        Examples:
            orch next              # Top 5 suggestions
            orch next -n 10        # Top 10 suggestions
            orch next --all-projects  # Include all projects
        """
        focus = get_current_focus()
        suggestions = get_next_suggestions(limit=limit if not all_projects else limit * 2)

        if not suggestions:
            click.echo("No ready issues found across registered projects")
            click.echo("")
            click.echo("Tips:")
            click.echo("  - Ensure projects are registered: orch projects list")
            click.echo("  - Check for ready issues: bd ready")
            return

        # Filter to aligned projects unless --all-projects
        if focus and focus.aligned_projects and not all_projects:
            aligned_suggestions = [s for s in suggestions if s.get("aligned")]
            other_suggestions = [s for s in suggestions if not s.get("aligned")]

            if aligned_suggestions:
                click.echo(f"🎯 Focus-aligned ({focus.description}):")
                click.echo("")
                for s in aligned_suggestions[:limit]:
                    _print_suggestion(s)

                if other_suggestions and len(aligned_suggestions) < limit:
                    click.echo("")
                    click.echo("Other ready issues:")
                    for s in other_suggestions[: limit - len(aligned_suggestions)]:
                        _print_suggestion(s)
            else:
                click.echo(f"No ready issues in aligned projects ({', '.join(focus.aligned_projects)})")
                click.echo("")
                click.echo("Other ready issues:")
                for s in other_suggestions[:limit]:
                    _print_suggestion(s)
        else:
            if focus:
                click.echo(f"Focus: {focus.description}")
                click.echo("")

            click.echo("Ready issues:")
            click.echo("")
            for s in suggestions[:limit]:
                _print_suggestion(s)


def _print_suggestion(suggestion: Dict[str, Any]) -> None:
    """Print a single suggestion in a formatted way."""
    issue_id = suggestion.get("id", "unknown")
    title = suggestion.get("title", "No title")
    project = suggestion.get("project", "unknown")
    priority = suggestion.get("priority", "?")
    aligned = suggestion.get("aligned", False)

    # Truncate long titles
    if len(title) > 50:
        title = title[:47] + "..."

    aligned_marker = "★" if aligned else " "
    click.echo(f"  {aligned_marker} [{project}] {issue_id}: {title} (P{priority})")
