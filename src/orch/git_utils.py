"""
Git utilities for tracking agent commits.
"""

import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class CommitInfo:
    """Information about a git commit."""
    hash: str
    message: str
    author: str
    timestamp: datetime

    @property
    def short_hash(self) -> str:
        """Get short commit hash (first 7 chars)."""
        return self.hash[:7]

    @property
    def short_message(self) -> str:
        """Get first line of commit message."""
        return self.message.split('\n')[0]


def is_git_repo(directory: Path) -> bool:
    """
    Check if directory is a git repository.

    Args:
        directory: Path to check

    Returns:
        True if directory is a git repo, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=directory,
            capture_output=True,
            check=True
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_last_commit(directory: Path) -> Optional[CommitInfo]:
    """
    Get information about the last commit in a git repository.

    Args:
        directory: Path to git repository

    Returns:
        CommitInfo if commits exist, None otherwise
    """
    if not is_git_repo(directory):
        return None

    try:
        # Get last commit info in format: hash|author|timestamp|full_message
        # Use %B for full message body (not just subject line)
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H|%an|%at|%B'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        if not result.stdout.strip():
            return None

        parts = result.stdout.strip().split('|', 3)
        if len(parts) != 4:
            return None

        commit_hash, author, timestamp_str, message = parts
        timestamp = datetime.fromtimestamp(int(timestamp_str))

        return CommitInfo(
            hash=commit_hash,
            message=message.strip(),  # Strip trailing whitespace from message
            author=author,
            timestamp=timestamp
        )
    except (subprocess.CalledProcessError, ValueError):
        return None


def count_commits_since(directory: Path, since_time: datetime) -> int:
    """
    Count commits made since a specific time.

    Args:
        directory: Path to git repository
        since_time: Count commits after this time

    Returns:
        Number of commits since the given time, 0 if error
    """
    if not is_git_repo(directory):
        return 0

    try:
        # Format time for git (Unix timestamp)
        since_timestamp = int(since_time.timestamp())

        result = subprocess.run(
            ['git', 'rev-list', '--count', f'--after={since_timestamp}', 'HEAD'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def validate_git_state(directory: Path) -> None:
    """
    Validate git state before spawning agent (main-branch-only workflow).

    Ensures:
    - On main branch
    - No uncommitted changes
    - Pulls latest from origin/main

    Args:
        directory: Path to git repository

    Raises:
        RuntimeError: If validation fails (not on main, dirty state, pull fails)
    """
    if not is_git_repo(directory):
        raise RuntimeError(f"Directory {directory} is not a git repository")

    # Check current branch
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = result.stdout.strip()

        # Accept both 'main' and 'master' as valid main branches
        if current_branch not in ('main', 'master'):
            raise RuntimeError(
                f"Not on main branch (currently on '{current_branch}'). "
                f"Main-branch-only workflow requires work to happen on main/master. "
                f"Switch to main: git checkout main (or master)"
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to check current branch: {e}")

    # Check for uncommitted changes
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout.strip():
            # Get list of modified files
            files = [line.strip() for line in result.stdout.strip().split('\n')]
            raise RuntimeError(
                f"Uncommitted changes detected. Commit or stash before spawning:\n" +
                '\n'.join(f"  {f}" for f in files)
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to check git status: {e}")

    # Pull latest from origin (using current branch name)
    try:
        # Use the branch we validated earlier (main or master)
        result = subprocess.run(
            ['git', 'pull', 'origin', current_branch],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False  # Don't raise on non-zero exit (we'll check it)
        )

        # Check if pull failed
        if result.returncode != 0:
            # Common cases for local-only repos (no remote configured)
            acceptable_errors = [
                'no tracking information',
                'does not have any commits yet',
                'does not appear to be a git repository',  # No remote configured
                'could not read from remote repository',   # No remote access
            ]

            # Check if error is acceptable (local-only repo)
            error_lower = result.stderr.lower()
            if any(err in error_lower for err in acceptable_errors):
                # This is okay - local-only repo without remote
                # Skip pull, continue with validation
                pass
            else:
                # Unexpected error - fail validation
                raise RuntimeError(
                    f"Failed to pull from origin/{current_branch}: {result.stderr.strip()}\n"
                    f"Ensure remote 'origin' exists and {current_branch} branch is pushed."
                )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to pull from origin/{current_branch}: {e}")


def validate_work_committed(directory: Path, exclude_files: Optional[list[str]] = None) -> tuple[bool, str]:
    """
    Validate work is committed and pushed (main-branch-only workflow).

    Checks:
    - No uncommitted changes (except excluded files)
    - All commits pushed to remote

    Args:
        directory: Path to git repository
        exclude_files: Optional list of file paths to ignore in status check

    Returns:
        Tuple of (is_valid, message)
        - is_valid: True if validation passes
        - message: Warning message if validation fails, empty if passes
    """
    if not is_git_repo(directory):
        return False, f"Directory {directory} is not a git repository"

    warnings = []

    # Check for uncommitted changes
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout.strip():
            # Get all changed lines
            all_changes = [line.strip() for line in result.stdout.strip().split('\n')]
            
            # Filter out excluded files
            files = []
            for change in all_changes:
                # Check if this change should be excluded
                is_excluded = False
                if exclude_files:
                    # Extract the file/directory path from git status line
                    # Format: "XY path" where XY is 2-char status code
                    # Examples: " M file.py", "?? dir/", "MM file.txt", "M  file.py"
                    # The path starts after the 2-char status + separator (space/tab)
                    # Use split with maxsplit=1 to handle any whitespace after status
                    parts = change.split(maxsplit=1)
                    change_path = parts[1] if len(parts) > 1 else ""

                    if change_path:
                        for excluded in exclude_files:
                            # Check if this change should be excluded:
                            # 1. Exact match: excluded path is the changed file
                            # 2. Directory match: excluded path is inside a changed directory
                            #    (e.g., change="?? .orch/", excluded=".orch/ROADMAP.org")
                            if excluded == change_path or excluded.startswith(change_path):
                                is_excluded = True
                                break

                if not is_excluded:
                    files.append(change)

            if files:
                warnings.append(
                    "⚠️  Uncommitted changes detected:\n" +
                    '\n'.join(f"  {f}" for f in files[:5])  # Show first 5 files
                )
                if len(files) > 5:
                    warnings.append(f"  ... and {len(files) - 5} more")
    except subprocess.CalledProcessError as e:
        warnings.append(f"⚠️  Failed to check git status: {e}")

    # Check for unpushed commits
    try:
        # Determine current branch (main or master)
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = branch_result.stdout.strip()

        # Get local commits not in origin/<branch>
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'origin/{current_branch}..HEAD'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False  # Don't raise on error (might not have origin/<branch>)
        )

        if result.returncode == 0:
            unpushed_count = int(result.stdout.strip())
            if unpushed_count > 0:
                # Get list of unpushed commit messages
                commits_result = subprocess.run(
                    ['git', 'log', '--oneline', f'origin/{current_branch}..HEAD'],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    check=True
                )
                commits = commits_result.stdout.strip().split('\n')

                warnings.append(
                    f"⚠️  {unpushed_count} unpushed commit(s):\n" +
                    '\n'.join(f"  {c}" for c in commits[:5])  # Show first 5
                )
                if unpushed_count > 5:
                    warnings.append(f"  ... and {unpushed_count - 5} more")
        # If command failed, origin/<branch> might not exist - that's okay, skip this check
    except (subprocess.CalledProcessError, ValueError):
        # Ignore errors - this is a warning check, not critical
        pass

    if warnings:
        return False, '\n\n'.join(warnings) + '\n\nRun: git add . && git commit -m "..." && git push origin main'

    return True, ""


def find_commits_mentioning_issue(directory: Path, issue_id: str) -> list[CommitInfo]:
    """
    Search git log for commits mentioning a beads issue ID.

    Useful for detecting if work for an issue has already been done,
    preventing duplicate agent spawns for completed work.

    Args:
        directory: Path to git repository
        issue_id: Beads issue ID to search for (e.g., "meta-orchestration-qrk")

    Returns:
        List of CommitInfo for commits mentioning the issue, empty if none found
    """
    if not is_git_repo(directory):
        return []

    try:
        # Use git log --grep to find commits mentioning the issue ID
        result = subprocess.run(
            ['git', 'log', '--oneline', f'--grep={issue_id}', '--format=%H|%an|%at|%s'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        if not result.stdout.strip():
            return []

        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue

            parts = line.split('|', 3)
            if len(parts) != 4:
                continue

            commit_hash, author, timestamp_str, message = parts
            try:
                timestamp = datetime.fromtimestamp(int(timestamp_str))
                commits.append(CommitInfo(
                    hash=commit_hash,
                    message=message.strip(),
                    author=author,
                    timestamp=timestamp
                ))
            except ValueError:
                continue

        return commits
    except subprocess.CalledProcessError:
        return []


def commit_roadmap_update(roadmap_path: Path, workspace_name: str, project_dir: Path) -> bool:
    """
    Commit ROADMAP update to git.

    Args:
        roadmap_path: Path to ROADMAP.org file
        workspace_name: Workspace name being completed
        project_dir: Project directory (for git operations)

    Returns:
        True if committed successfully, False otherwise
    """
    # Check if git repo exists
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        return False

    try:
        # Make roadmap_path relative to project_dir for git add
        relative_roadmap = roadmap_path.relative_to(project_dir)

        # Git add
        subprocess.run(
            ['git', 'add', str(relative_roadmap)],
            cwd=str(project_dir),
            check=True,
            capture_output=True
        )

        # Git commit
        commit_message = f"Complete: {workspace_name}\n\nMark ROADMAP item as DONE"
        subprocess.run(
            ['git', 'commit', '-m', commit_message],
            cwd=str(project_dir),
            check=True,
            capture_output=True
        )

        return True
    except subprocess.CalledProcessError:
        return False
