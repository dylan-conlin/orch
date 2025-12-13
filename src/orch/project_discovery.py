"""Project discovery functionality for finding initialized .orch projects.

This module provides two approaches for project discovery:

1. **scan_projects()** - Active scanning of filesystem for .orch/CLAUDE.md files
   - Searches specified directories
   - Creates its own cache at ~/.orch/initialized-projects.json
   - Used by `orch scan-projects` and `orch projects list`

2. **get_kb_projects()** - Reads from kb's project registry
   - Reads ~/.kb/projects.json maintained by `kb` CLI
   - No filesystem scanning - just reads the registry
   - Preferred for cross-project operations like the work daemon
   - Avoids duplication: one source of truth for registered projects
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime, timezone


def get_default_search_dirs() -> List[str]:
    """Get default directories to search for initialized projects."""
    home = Path.home()
    search_dirs = []

    # Orch config directory
    meta_orch = home / 'orch-config'
    if meta_orch.exists():
        search_dirs.append(str(meta_orch.parent))

    # Work projects
    work_dir = home / 'Documents' / 'work' / 'SendCutSend' / 'scs-special-projects'
    if work_dir.exists():
        search_dirs.append(str(work_dir))

    # Personal projects
    personal_dir = home / 'Documents' / 'personal'
    if personal_dir.exists():
        search_dirs.append(str(personal_dir))

    # Documents directory (for dotfiles, etc.)
    docs_dir = home / 'Documents'
    if docs_dir.exists():
        search_dirs.append(str(docs_dir))

    # Special case: .doom.d
    doom_dir = home / '.doom.d'
    if (doom_dir / '.orch' / 'CLAUDE.md').exists():
        search_dirs.append(str(doom_dir.parent))

    return search_dirs


def scan_projects(search_dirs: List[str]) -> List[Path]:
    """
    Scan directories for projects with .orch/CLAUDE.md files.

    Args:
        search_dirs: List of directory paths to search

    Returns:
        List of Path objects for projects with .orch/CLAUDE.md (deduplicated)
    """
    projects = []
    seen = set()

    for search_dir in search_dirs:
        search_path = Path(search_dir)
        if not search_path.exists():
            continue

        # Check direct subdirectories
        for item in search_path.iterdir():
            if not item.is_dir():
                continue

            # Check if this directory has .orch/CLAUDE.md
            claude_md = item / ".orch" / "CLAUDE.md"
            if claude_md.exists():
                # Deduplicate by resolved path
                resolved = item.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    projects.append(item)

    return projects


def write_cache(cache_file: Path, projects: List[Path]) -> None:
    """
    Write discovered projects to cache file.

    Args:
        cache_file: Path to cache file
        projects: List of project paths to cache
    """
    data = {
        "version": "1.0",
        "projects": [str(p) for p in projects],
        "last_scan": datetime.now(timezone.utc).isoformat()
    }

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=2)


def read_cache(cache_file: Path) -> List[Path]:
    """
    Read cached projects from file.

    Args:
        cache_file: Path to cache file

    Returns:
        List of Path objects for cached projects, or empty list if cache doesn't exist
    """
    if not cache_file.exists():
        return []

    with open(cache_file) as f:
        data = json.load(f)

    return [Path(p) for p in data["projects"]]


# ============================================================================
# kb project registry integration
# ============================================================================


def get_kb_projects_path() -> Path:
    """
    Get path to kb's project registry file.

    Returns:
        Path to ~/.kb/projects.json
    """
    return Path.home() / ".kb" / "projects.json"


def get_kb_projects(filter_existing: bool = False) -> List[Path]:
    """
    Read registered projects from kb's project registry.

    This reads from ~/.kb/projects.json which is maintained by the `kb` CLI.
    The registry format is:
    {
        "projects": [
            {"name": "project-name", "path": "/absolute/path/to/project"},
            ...
        ]
    }

    Args:
        filter_existing: If True, only return paths that exist on the filesystem.
                        Useful for handling stale entries in the registry.

    Returns:
        List of Path objects for registered projects.
        Returns empty list if:
        - Registry file doesn't exist
        - File contains invalid JSON
        - File is missing 'projects' key
    """
    projects_file = get_kb_projects_path()

    if not projects_file.exists():
        return []

    try:
        with open(projects_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Invalid JSON or read error - return empty list
        return []

    # Get projects array, handle missing key
    projects_data = data.get("projects", [])
    if not isinstance(projects_data, list):
        return []

    # Extract paths from project entries
    # Each entry is {"name": "...", "path": "..."}
    paths = []
    for entry in projects_data:
        if isinstance(entry, dict) and "path" in entry:
            path = Path(entry["path"])
            if not filter_existing or path.exists():
                paths.append(path)

    return paths
