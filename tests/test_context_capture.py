"""Tests for context capture module."""

import pytest
from pathlib import Path


def test_capture_git_context(tmp_path):
    """Test capturing git status, branch, and recent commits."""
    from orch.context_capture import capture_git_context
    import subprocess

    # Create test git repo
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_dir, check=True, capture_output=True)

    # Create and commit a file
    test_file = project_dir / "test.py"
    test_file.write_text("print('hello')")
    subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=project_dir, check=True, capture_output=True)

    result = capture_git_context(project_dir)

    assert result['branch'] is not None
    assert 'git_status' in result
    assert 'recent_commits' in result
    assert 'modified_files' in result


def test_detect_active_workspace(tmp_path):
    """Test detecting active workspace from current directory."""
    from orch.context_capture import detect_active_workspace

    # Create workspace structure
    project_dir = tmp_path / "test_project"
    workspace_dir = project_dir / ".orch" / "workspace" / "test-workspace"
    workspace_dir.mkdir(parents=True)

    # Create WORKSPACE.md with summary
    workspace_file = workspace_dir / "WORKSPACE.md"
    workspace_file.write_text("""# Workspace: test-workspace

**Phase:** Planning

## Summary (Top 3)

- **Current Goal:** Implement feature X
- **Next Step:** Write tests
- **Blocking Issue:** None
""")

    # Test from within workspace directory
    result = detect_active_workspace(workspace_dir)

    assert result['workspace_path'] is not None
    assert result['workspace_summary'] is not None
    assert 'current_goal' in result['workspace_summary']
    assert result['workspace_summary']['current_goal'] == 'Implement feature X'


def test_capture_full_context(tmp_path):
    """Test capturing complete context for bug flagging."""
    from orch.context_capture import capture_bug_context
    import subprocess

    # Create test project with git
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_dir, check=True, capture_output=True)

    # Create test file and commit
    src_dir = project_dir / "src"
    src_dir.mkdir()
    test_file = src_dir / "main.py"
    test_file.write_text("print('hello')")
    subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=project_dir, check=True, capture_output=True)

    current_dir = src_dir
    description = "Price calculation returns null"

    result = capture_bug_context(
        description=description,
        current_dir=current_dir,
        project_dir=project_dir
    )

    assert result['current_dir'] == str(current_dir)
    assert result['project_dir'] == str(project_dir)
    assert result['description'] == description
    assert 'git_context' in result
    assert 'workspace_context' in result
    assert result['project_name'] == 'test_project'
