"""Decision record template management."""

import os
from pathlib import Path
from typing import Optional
from datetime import date


class DecisionError(Exception):
    """Base exception for decision operations."""
    pass


def detect_project_dir(project_dir: Optional[Path] = None) -> Path:
    """
    Detect project directory from CLAUDE_PROJECT env or find_orch_root().

    Args:
        project_dir: Explicit project directory (default: auto-detect)

    Returns:
        Path to project directory containing .orch/

    Raises:
        DecisionError: If no .orch directory found
    """
    # Use explicit project_dir if provided
    if project_dir:
        project_path = project_dir.resolve()
        if not (project_path / '.orch').exists():
            raise DecisionError(f"No .orch directory found in {project_path}")
        return project_path

    # Check CLAUDE_PROJECT environment variable
    if 'CLAUDE_PROJECT' in os.environ:
        project_path = Path(os.environ['CLAUDE_PROJECT']).resolve()
        if not (project_path / '.orch').exists():
            raise DecisionError(f"CLAUDE_PROJECT points to {project_path} but no .orch directory found")
        return project_path

    # Use find_orch_root from path_utils (avoids circular dependency with cli)
    from orch.path_utils import find_orch_root
    orch_root = find_orch_root()

    if not orch_root:
        raise DecisionError(
            "No .orch directory found. Either:\n"
            "  1. Run from within a project directory containing .orch/\n"
            "  2. Set CLAUDE_PROJECT environment variable\n"
            "  3. Use --project flag to specify project path"
        )

    return Path(orch_root)


def create_decision(
    slug: str,
    project_dir: Optional[Path] = None
) -> dict:
    """
    Create decision file from template.

    Args:
        slug: Decision topic in kebab-case
        project_dir: Project directory (default: auto-detect)

    Returns:
        dict with keys: file_path, template_name, date

    Raises:
        DecisionError: If template not found, project invalid, or file exists
    """
    # Validate slug (no path traversal)
    if '..' in slug or slug.startswith('/') or '/' in slug:
        raise DecisionError(f"Invalid slug: {slug} (must be kebab-case filename without slashes)")

    # Detect project directory
    project_path = detect_project_dir(project_dir)

    # Build file path (decisions are flat, no subdirectories)
    today = date.today().strftime('%Y-%m-%d')
    decisions_dir = project_path / '.orch' / 'decisions'
    file_path = decisions_dir / f"{today}-{slug}.md"

    # Check if file already exists
    if file_path.exists():
        raise DecisionError(
            f"File already exists: {file_path}\n"
            f"Choose a different slug or remove the existing file"
        )

    # Get template
    template_name = 'DECISION.md'
    template_path = Path.home() / '.orch' / 'templates' / template_name

    if not template_path.exists():
        raise DecisionError(
            f"Template not found: {template_path}\n"
            f"Ensure orchestration templates are installed at ~/.orch/templates/"
        )

    # Create directory
    decisions_dir.mkdir(parents=True, exist_ok=True)

    # Copy template and substitute placeholders
    content = template_path.read_text()

    # Replace date placeholders in various formats found in templates
    content = content.replace('YYYY-MM-DD', today)
    content = content.replace('[YYYY-MM-DD]', today)

    # Write file
    file_path.write_text(content)

    return {
        'file_path': str(file_path),
        'template_name': template_name,
        'date': today
    }
