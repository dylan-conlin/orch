"""Agent filtering utilities for orch CLI.

Extracted from monitoring_commands.py to improve testability and maintainability.
Provides functions for filtering agents by project, workspace pattern, and status.
"""

from fnmatch import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def resolve_project_path(project: str, cwd: Optional[str] = None) -> str:
    """Resolve a project path, handling relative paths and symlinks.

    Args:
        project: Project path or name. Can be '.', '..', absolute path, or substring.
        cwd: Current working directory (defaults to actual cwd if not provided).

    Returns:
        Resolved absolute path, or the original string if it's a substring match.
    """
    # Handle relative paths (. and ..) and paths with slashes
    if project in ('.', '..') or '/' in project:
        try:
            if cwd:
                base = Path(cwd)
                if project in ('.', '..'):
                    resolved = (base / project).resolve()
                else:
                    resolved = Path(project).resolve()
            else:
                resolved = Path(project).resolve()
            return str(resolved)
        except Exception:
            return project

    # For project names (substring match), return as-is
    return project


def filter_agents_by_project(
    agents: List[Dict[str, Any]],
    project: Optional[str]
) -> List[Dict[str, Any]]:
    """Filter agents by project path or substring.

    Args:
        agents: List of agent dictionaries with 'project_dir' key.
        project: Project path or name to filter by. None returns all agents.

    Returns:
        Filtered list of agents matching the project.
    """
    if not project:
        return agents

    # Resolve the project path
    resolved_project = resolve_project_path(project)

    filtered = []
    for agent in agents:
        agent_project = str(agent.get('project_dir', ''))
        if not agent_project:
            continue

        # Resolve agent project path to handle symlinks
        try:
            agent_project_resolved = str(Path(agent_project).resolve())
        except Exception:
            agent_project_resolved = agent_project

        # Check both resolved and unresolved paths (case-insensitive substring match)
        matches = (
            resolved_project.lower() in agent_project.lower() or
            resolved_project.lower() in agent_project_resolved.lower() or
            agent_project.lower() in resolved_project.lower() or
            agent_project_resolved.lower() in resolved_project.lower()
        )

        if matches:
            filtered.append(agent)

    return filtered


def filter_agents_by_workspace(
    agents: List[Dict[str, Any]],
    workspace_pattern: Optional[str]
) -> List[Dict[str, Any]]:
    """Filter agents by workspace name pattern (fnmatch).

    Args:
        agents: List of agent dictionaries with 'workspace' key.
        workspace_pattern: Glob pattern to match workspace names. None returns all agents.

    Returns:
        Filtered list of agents matching the workspace pattern.
    """
    if not workspace_pattern:
        return agents

    filtered = []
    for agent in agents:
        workspace_path = agent.get('workspace', '')
        if not workspace_path:
            continue

        # Extract workspace name from path
        # e.g., ".orch/workspace/my-workspace/" -> "my-workspace"
        workspace_name = workspace_path.rstrip('/').split('/')[-1] if workspace_path else ''

        if fnmatch(workspace_name, workspace_pattern):
            filtered.append(agent)

    return filtered


def filter_agents_by_status(
    agent_statuses: List[Tuple[Dict[str, Any], Any]],
    status_filter: Optional[str]
) -> List[Tuple[Dict[str, Any], Any]]:
    """Filter agents by status/phase.

    Args:
        agent_statuses: List of (agent, status_obj) tuples.
        status_filter: Status/phase to filter by. Can be phase name (e.g., 'Planning'),
                      'blocked' (maps to priority='critical'), or priority name.
                      None returns all agents.

    Returns:
        Filtered list of (agent, status_obj) tuples.
    """
    if not status_filter:
        return agent_statuses

    filtered = []
    status_lower = status_filter.lower()

    for agent, status_obj in agent_statuses:
        # Match against phase (e.g., "Planning", "Implementing", "Complete")
        if status_obj.phase.lower() == status_lower:
            filtered.append((agent, status_obj))
        # Also match against priority for common statuses (e.g., "blocked" -> "critical")
        elif status_lower == 'blocked' and status_obj.priority == 'critical':
            filtered.append((agent, status_obj))
        elif status_lower == status_obj.priority.lower():
            filtered.append((agent, status_obj))

    return filtered


def filter_agents(
    agents: List[Dict[str, Any]],
    project: Optional[str] = None,
    workspace_pattern: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Apply project and workspace filters to agent list.

    Args:
        agents: List of agent dictionaries.
        project: Project path or name to filter by.
        workspace_pattern: Glob pattern to match workspace names.

    Returns:
        Filtered list of agents.
    """
    result = agents

    if project:
        result = filter_agents_by_project(result, project)

    if workspace_pattern:
        result = filter_agents_by_workspace(result, workspace_pattern)

    return result
