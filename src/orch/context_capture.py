"""Context capture module for bug flagging."""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict
import subprocess
import re

from orch.git_utils import is_git_repo


@dataclass
class GitContext:
    """Git repository context."""
    branch: Optional[str]
    git_status: str
    recent_commits: List[str]
    modified_files: List[str]


def capture_git_context(project_dir: Path) -> Dict:
    """
    Capture git context from project directory.

    Args:
        project_dir: Path to project directory

    Returns:
        Dict with branch, git_status, recent_commits, modified_files
    """
    if not is_git_repo(project_dir):
        return {
            'branch': None,
            'git_status': '',
            'recent_commits': [],
            'modified_files': []
        }

    # Get current branch
    branch_result = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

    # Get git status
    status_result = subprocess.run(
        ['git', 'status', '--short'],
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    git_status = status_result.stdout.strip() if status_result.returncode == 0 else ''

    # Get recent commits (last 3)
    log_result = subprocess.run(
        ['git', 'log', '-3', '--oneline'],
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    recent_commits = log_result.stdout.strip().split('\n') if log_result.returncode == 0 else []

    # Extract modified files from status
    modified_files = []
    for line in git_status.split('\n'):
        if line.strip():
            # Format: "MM path/to/file" or " M path/to/file"
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                modified_files.append(parts[1])

    return {
        'branch': branch,
        'git_status': git_status,
        'recent_commits': recent_commits,
        'modified_files': modified_files
    }


def detect_active_workspace(current_dir: Path) -> Dict:
    """
    Detect if current directory is within a workspace.

    Note: WORKSPACE.md is no longer used for agent state tracking.
    This function now returns basic workspace path info only.

    Args:
        current_dir: Current working directory

    Returns:
        Dict with workspace_path (or None if not in workspace)
    """
    # Check if current directory is within .orch/workspace/
    workspace_marker = '.orch/workspace'

    # Walk up directory tree looking for workspace
    check_dir = current_dir
    workspace_path = None

    while check_dir != check_dir.parent:
        if workspace_marker in str(check_dir):
            # Found workspace directory
            parts = str(check_dir).split(workspace_marker)
            if len(parts) >= 2:
                # Get workspace root (e.g., .orch/workspace/my-workspace)
                workspace_root_parts = parts[1].strip('/').split('/')
                if workspace_root_parts:
                    workspace_name = workspace_root_parts[0]
                    workspace_path = Path(parts[0]) / workspace_marker / workspace_name
                    if workspace_path.exists():
                        break
            workspace_path = None
        check_dir = check_dir.parent

    if not workspace_path or not workspace_path.exists():
        return {
            'workspace_path': None,
            'workspace_summary': None
        }

    # Return workspace path without WORKSPACE.md parsing
    # Beads is now the source of truth for agent state
    return {
        'workspace_path': str(workspace_path),
        'workspace_summary': None
    }


@dataclass
class BugContext:
    """Complete context for bug flagging."""
    description: str
    current_dir: str
    project_dir: str
    project_name: str
    git_context: Dict
    workspace_context: Dict


def capture_bug_context(
    description: str,
    current_dir: Path,
    project_dir: Path
) -> Dict:
    """
    Capture complete context for bug flagging.

    Args:
        description: Bug description from user
        current_dir: Current working directory where bug was noticed
        project_dir: Project root directory

    Returns:
        Dict with all captured context
    """
    # Capture git context
    git_context = capture_git_context(project_dir)

    # Detect active workspace
    workspace_context = detect_active_workspace(current_dir)

    # Extract project name from directory
    project_name = project_dir.name

    return {
        'description': description,
        'current_dir': str(current_dir),
        'project_dir': str(project_dir),
        'project_name': project_name,
        'git_context': git_context,
        'workspace_context': workspace_context
    }
