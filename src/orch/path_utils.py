"""
Path utilities for orch CLI.

Extracted from cli.py to break circular dependencies:
- cli -> complete -> spawn -> cli
- cli -> complete -> spawn -> investigations -> cli

These functions are used by spawn.py and investigations.py to find
the project root without importing cli.py.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


def get_git_root(start_path: Optional[str] = None) -> Optional[str]:
    """Find git repository root from start_path (or cwd).

    Returns git root path or None if not in a git repository.

    Args:
        start_path: Directory to start search from (default: cwd)

    Returns:
        Git root path as string, or None if not in a git repository
    """
    if start_path is None:
        start_path = os.getcwd()

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=start_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def find_orch_root(start_path: Optional[str] = None) -> Optional[str]:
    """Find .orch directory by walking up from start_path (or cwd).

    Walks up the directory tree from start_path looking for a .orch directory.
    This allows context detection to work when running from any subdirectory
    within a project, including from within .orch/ itself.

    IMPORTANT: Stops at git root boundary to prevent detecting ~/.orch/
    (the global config directory) as a project root. If in a git repo,
    only looks within that repo for .orch/.

    Args:
        start_path: Directory to start search from (default: cwd)

    Returns:
        Path to directory containing .orch/, or None if not found
    """
    if start_path is None:
        start_path = os.getcwd()

    current = Path(start_path).resolve()

    # Get git root as upper boundary (if in a git repo)
    git_root = get_git_root(start_path)
    git_root_path = Path(git_root).resolve() if git_root else None

    # Walk up the directory tree
    while current != current.parent:
        if (current / '.orch').is_dir():
            return str(current)

        # Stop at git root - don't look outside the repo
        # This prevents ~/.orch/ from being detected as a project root
        if git_root_path and current == git_root_path:
            return None

        current = current.parent

    return None


def detect_and_display_context():
    """Detect and display current context (orchestrator/worker/interactive).

    This function depends on click for display, so it imports click locally
    to avoid making click a dependency of path_utils.

    Returns:
        Context type: 'orchestrator', 'worker', or 'interactive'.
    """
    import click

    cwd = os.getcwd()

    # Check for worker context (SPAWN_CONTEXT.md exists)
    if os.path.isfile(os.path.join(cwd, 'SPAWN_CONTEXT.md')):
        context = 'worker'
        workspace_name = os.path.basename(cwd)

        # Try to extract project from SPAWN_CONTEXT.md
        project_name = None
        try:
            with open('SPAWN_CONTEXT.md', 'r') as f:
                for line in f:
                    if line.startswith('PROJECT_DIR:'):
                        project_path = line.split(':', 1)[1].strip()
                        project_name = os.path.basename(project_path)
                        break
        except Exception:
            pass

        click.echo("Worker Context")
        click.echo(f"   Workspace: {workspace_name}")
        if project_name:
            click.echo(f"   Project: {project_name}")
        click.echo()
        click.echo("Session start checklist:")
        click.echo("  Read SPAWN_CONTEXT.md for task scope")
        click.echo("  Read WORKSPACE.md for current state")
        click.echo("  Focus on deliverables, respect authority boundaries")
        click.echo()

    # Check for orchestrator context (.orch directory exists in tree)
    orch_root = find_orch_root()
    if orch_root:
        context = 'orchestrator'
        project_name = os.path.basename(orch_root)

        click.echo("Orchestrator Context")
        click.echo(f"   Project: {project_name}")
        click.echo()
        click.echo("Session start checklist:")
        click.echo("  Review .orch/README.md for recent artifacts")
        click.echo("  Check .orch/ROADMAP for next work")
        click.echo("  Default to delegation for non-trivial work")
        click.echo()

    else:
        context = 'interactive'
        click.echo("Interactive Context")
        click.echo("   No formal orchestration structure detected")
        click.echo()
        click.echo("Available modes:")
        click.echo("  Conversational assistance")
        click.echo("  Ad-hoc tasks")
        click.echo("  Exploration and learning")
        click.echo()

    return context
