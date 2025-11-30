"""
Utilities for ROADMAP format detection and parser selection.

Supports both org-mode (.org) and Markdown (.md) formats, with automatic detection.
Config-driven format preference: config > auto-detect > org fallback.
"""

from pathlib import Path
from typing import List, Optional

from orch.config import get_roadmap_format
from orch.roadmap import (
    RoadmapItem,
    parse_roadmap_file_cached as parse_org,
    find_roadmap_item_for_workspace as find_item_workspace_org,
    mark_roadmap_item_done as mark_done_org,
)
from orch.roadmap_markdown import (
    parse_roadmap_markdown as parse_md,
    find_roadmap_item_for_workspace as find_item_workspace_md,
    mark_roadmap_item_done as mark_done_md,
)


def detect_roadmap_format(roadmap_path: Path) -> str:
    """
    Detect ROADMAP format from file extension.

    Args:
        roadmap_path: Path to ROADMAP file

    Returns:
        "markdown" if .md extension, "org" if .org extension

    Raises:
        ValueError: If extension is neither .md nor .org
    """
    if roadmap_path.suffix == ".md":
        return "markdown"
    elif roadmap_path.suffix == ".org":
        return "org"
    else:
        raise ValueError(f"Unknown ROADMAP format: {roadmap_path.suffix} (expected .md or .org)")


def parse_roadmap(roadmap_path: Path) -> List[RoadmapItem]:
    """
    Parse ROADMAP file using appropriate parser for format.

    Automatically detects format from extension and uses correct parser.

    Args:
        roadmap_path: Path to ROADMAP.md or ROADMAP.org file

    Returns:
        List of RoadmapItem objects

    Raises:
        ValueError: If format is unknown
        FileNotFoundError: If file doesn't exist
    """
    if not roadmap_path.exists():
        return []

    format_type = detect_roadmap_format(roadmap_path)

    if format_type == "markdown":
        return parse_md(roadmap_path)
    else:  # org
        return parse_org(roadmap_path)


def find_roadmap_file(search_dir: Path) -> Optional[Path]:
    """
    Find ROADMAP file in directory, checking both formats.

    Priority logic (config > auto-detect > org fallback):
    1. Check format from config preference
    2. If preferred format exists, return it
    3. Otherwise, check the other format
    4. Default preference is org-mode

    Args:
        search_dir: Directory to search in

    Returns:
        Path to ROADMAP file if found, None otherwise
    """
    preferred_format = get_roadmap_format()

    if preferred_format == 'markdown':
        # Config prefers Markdown: check .md first, fallback to .org
        md_path = search_dir / "ROADMAP.md"
        if md_path.exists():
            return md_path

        org_path = search_dir / "ROADMAP.org"
        if org_path.exists():
            return org_path
    else:  # preferred_format == 'org' (default)
        # Config prefers org-mode: check .org first, fallback to .md
        org_path = search_dir / "ROADMAP.org"
        if org_path.exists():
            return org_path

        md_path = search_dir / "ROADMAP.md"
        if md_path.exists():
            return md_path

    return None


def detect_project_roadmap() -> Optional[Path]:
    """
    Detect if we're in a project context with its own ROADMAP file.

    Searches current directory and parents for .orch/ROADMAP.{md,org}.

    Returns:
        Path to project ROADMAP if found, None otherwise
    """
    current = Path.cwd()

    # Search current directory and parents (up to 5 levels)
    for _ in range(5):
        orch_dir = current / ".orch"
        if orch_dir.exists():
            roadmap = find_roadmap_file(orch_dir)
            if roadmap:
                return roadmap

        # Stop if we hit root or home
        if current == current.parent or current == Path.home():
            break
        current = current.parent

    return None


def find_roadmap_item_for_workspace(
    workspace_name: str,
    roadmap_path: Optional[Path]
) -> Optional[RoadmapItem]:
    """
    Find ROADMAP item that matches workspace name (format-agnostic).

    Automatically detects format and uses appropriate parser.

    Args:
        workspace_name: Workspace name to search for
        roadmap_path: Path to ROADMAP file (.md or .org), or None if no ROADMAP

    Returns:
        RoadmapItem if found, None otherwise
    """
    if roadmap_path is None or not roadmap_path.exists():
        return None

    format_type = detect_roadmap_format(roadmap_path)

    if format_type == "markdown":
        return find_item_workspace_md(workspace_name, roadmap_path)
    else:  # org
        return find_item_workspace_org(workspace_name, roadmap_path)


def mark_roadmap_item_done(
    roadmap_path: Path,
    task_title: Optional[str] = None,
    workspace_name: Optional[str] = None,
    create_backup: bool = False
) -> bool:
    """
    Mark ROADMAP item as done (format-agnostic).

    Automatically detects format and uses appropriate update function.

    Args:
        roadmap_path: Path to ROADMAP file (.md or .org)
        task_title: Optional task title to find and mark done
        workspace_name: Optional workspace name to find and mark done
        create_backup: If True, create backup file before modifying

    Returns:
        True if item was found and marked done, False otherwise

    Raises:
        ValueError: If neither task_title nor workspace_name provided
    """
    if not task_title and not workspace_name:
        raise ValueError("Must provide either task_title or workspace_name")

    if not roadmap_path.exists():
        return False

    format_type = detect_roadmap_format(roadmap_path)

    if format_type == "markdown":
        return mark_done_md(roadmap_path, task_title, workspace_name, create_backup)
    else:  # org
        return mark_done_org(roadmap_path, task_title, workspace_name, create_backup)
