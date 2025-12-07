"""
Project resolution functionality for orch tool.

Handles:
- Active projects parsing from active-projects.md
- Project directory resolution from name or path
- Project detection from current working directory
- ROADMAP detection for project context

Moved from spawn.py for better module organization.
"""

from pathlib import Path
from typing import Dict, List, Optional
import functools
import os

from orch.roadmap_utils import detect_project_roadmap as detect_roadmap_utils


def detect_project_roadmap() -> Optional[Path]:
    """
    Detect if we're in a project context with its own ROADMAP file.

    Searches current directory and parents for .orch/ROADMAP.{md,org}.
    Delegates to roadmap_utils for format-agnostic detection.

    Returns:
        Path to project ROADMAP if found, None otherwise
    """
    return detect_roadmap_utils()


def _get_active_projects_file() -> Optional[Path]:
    """
    Locate the active-projects.md file.

    Returns:
        Path to active-projects.md if found, None otherwise
    """
    # Prefer default under home (patched in tests)
    active_projects_file = Path.home() / "orch-knowledge" / ".orch" / "active-projects.md"
    if not active_projects_file.exists():
        try:
            from orch.config import get_active_projects_file
            cfg_file = get_active_projects_file()
            if cfg_file.exists():
                active_projects_file = cfg_file
        except Exception:
            pass

    return active_projects_file if active_projects_file.exists() else None


@functools.lru_cache(maxsize=1)
def _parse_active_projects(file_path: str, file_mtime: float) -> Dict[str, Path]:
    """
    Parse active-projects.md and return mapping of project names to paths.

    Args:
        file_path: Path to active-projects.md (as string for cache key)
        file_mtime: Modification time (for cache invalidation)

    Returns:
        Dictionary mapping project name to resolved Path
    """
    projects = {}
    current_project = None

    with open(file_path, 'r') as f:
        for line in f:
            # Project names are headers: ## project-name
            if line.strip().startswith('## '):
                project_name = line.strip()[3:].strip()
                # Skip meta-sections
                if project_name.lower() not in ['instructions', 'inactive projects', 'active projects']:
                    current_project = project_name
            # Extract path for current project
            elif current_project and '**Path:**' in line:
                if '`' in line:
                    path_part = line.split('`')[1].strip()
                    projects[current_project] = Path(path_part).expanduser()
                    current_project = None  # Reset after finding path

    return projects


def get_project_dir(project_name_or_path: str) -> Optional[Path]:
    """
    Get project directory from active-projects.md (cached).

    Accepts either a project name or full path for flexibility with AI agents.

    Args:
        project_name_or_path: Either:
          - Project name (e.g., "price-watch")
          - Full path (e.g., "/Users/.../price-watch")
          - Tilde path (e.g., "~/Documents/.../price-watch")
          - Relative path (e.g., ".", "..", "./subdir")

    Returns:
        Path to project directory or None if not found
    """
    active_projects_file = _get_active_projects_file()
    if not active_projects_file:
        return None

    # Get cached projects (with mtime-based invalidation)
    try:
        mtime = os.path.getmtime(active_projects_file)
    except (OSError, FileNotFoundError):
        return None

    projects = _parse_active_projects(str(active_projects_file), mtime)

    # If input looks like a path (contains / or is . or ..), try to match by resolved path first
    if '/' in project_name_or_path or project_name_or_path in ('.', '..'):
        try:
            input_path = Path(project_name_or_path).expanduser().resolve()
            # Match by resolved path
            for project_name, project_path in projects.items():
                if project_path.resolve() == input_path:
                    return project_path
        except Exception:
            # Invalid path, fall through to name matching
            pass

    # Fall back to name matching (case-insensitive)
    for project_name, project_path in projects.items():
        if project_name.lower() == project_name_or_path.lower():
            return project_path

    # Final fallback: check if cwd matches project name and has .orch/
    # This ensures consistency with detect_project_from_cwd() which allows
    # projects not in active-projects.md if they have .orch/ directory
    try:
        from orch.path_utils import find_orch_root
        orch_root = find_orch_root()
        if orch_root:
            orch_root_path = Path(orch_root)
            # Check if directory name matches requested project name (case-insensitive)
            if orch_root_path.name.lower() == project_name_or_path.lower():
                return orch_root_path
    except Exception:
        # Ignore errors in fallback
        pass

    return None


def list_available_projects() -> List[str]:
    """
    List all available project names from active-projects.md (cached).

    Returns:
        List of project names (empty list if file doesn't exist or has no projects)
    """
    active_projects_file = _get_active_projects_file()
    if not active_projects_file:
        return []

    # Get cached projects (with mtime-based invalidation)
    try:
        mtime = os.path.getmtime(active_projects_file)
    except (OSError, FileNotFoundError):
        return []

    projects = _parse_active_projects(str(active_projects_file), mtime)
    return list(projects.keys())


def format_project_not_found_error(project_name: str, context: str = "") -> str:
    """
    Format a helpful "project not found" error message with available projects.

    Args:
        project_name: The project name that wasn't found
        context: Optional context about where the project was specified (e.g., "--project", "ROADMAP :Project:")

    Returns:
        Formatted error message with available projects listed
    """
    available = list_available_projects()
    if available:
        available_str = ', '.join(available[:10])
        if len(available) > 10:
            available_str += f", ... ({len(available)} total)"
        hint = f"\nAvailable projects: {available_str}"
    else:
        hint = "\nNo projects found in ~/.claude/active-projects.md"

    source = f" (from {context})" if context else ""
    return f"❌ Project '{project_name}' not found{source}.{hint}"


def detect_project_from_cwd() -> Optional[tuple]:
    """
    Auto-detect project from current working directory.

    Walks up directory tree looking for .orch/ directory, then matches
    against active-projects.md to get canonical project name.

    Returns:
        Tuple of (project_name, project_dir) if detected, None otherwise.
        If project has .orch/ but isn't in active-projects.md, returns
        (directory_name, project_dir) as fallback.
    """
    from orch.path_utils import find_orch_root

    # Find project root by looking for .orch/ directory
    project_root = find_orch_root()
    if not project_root:
        return None

    project_dir = Path(project_root)

    # Try to find matching project in active-projects.md
    # get_project_dir accepts paths and matches by resolved path
    matched_dir = get_project_dir(str(project_dir))
    if matched_dir:
        # Found in active-projects.md - get the canonical project name
        active_projects_file = _get_active_projects_file()
        if active_projects_file:
            try:
                mtime = os.path.getmtime(active_projects_file)
                projects = _parse_active_projects(str(active_projects_file), mtime)
                # Find project name by path match
                for name, path in projects.items():
                    if path.resolve() == matched_dir.resolve():
                        return (name, matched_dir)
            except (OSError, FileNotFoundError):
                pass

    # Fallback: project has .orch/ but isn't in active-projects.md
    # Use directory name as project identifier
    return (project_dir.name, project_dir)
