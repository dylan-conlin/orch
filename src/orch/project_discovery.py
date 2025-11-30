"""Project discovery functionality for finding initialized .orch projects."""

import json
from pathlib import Path
from typing import List
from datetime import datetime, timezone


def get_default_search_dirs() -> List[str]:
    """Get default directories to search for initialized projects."""
    home = Path.home()
    search_dirs = []

    # Meta-orchestration itself
    meta_orch = home / 'meta-orchestration'
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
