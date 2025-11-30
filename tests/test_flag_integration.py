"""Integration tests for orch flag command.

NOTE: Full end-to-end testing with tmux spawning requires a tmux session.
These tests verify the workflow without actually spawning agents.
"""

import pytest
from pathlib import Path


def test_flag_command_integration(tmp_path, monkeypatch, mocker):
    """Test complete flag workflow integration (without actual spawning)."""
    from orch.flag import flag_bug
    from orch.context_capture import capture_bug_context

    # Setup test project with git
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / ".orch" / "workspace").mkdir(parents=True)

    # Initialize git repo
    import subprocess
    subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'],
                   cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'],
                   cwd=project_dir, check=True, capture_output=True)

    # Create test file
    src_dir = project_dir / "src"
    src_dir.mkdir()
    test_file = src_dir / "main.py"
    test_file.write_text("print('hello')\n")

    # Commit
    subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'],
                   cwd=project_dir, check=True, capture_output=True)

    # Mock Path.home() for template (templates expected at ~/.orch/templates/)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    template_dir = fake_home / ".orch" / "templates"
    template_dir.mkdir(parents=True)
    template_file = template_dir / "WORKSPACE.md"
    template_file.write_text("""# Workspace: {{ workspace_name }}

**Owner:** {{ owner }}
**Started:** {{ started }}
**Phase:** {{ phase }}

## Summary (Top 3)
- **Current Goal:** [One sentence]

## Context
[Background needed to understand this work]

---

## External References

""")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Mock spawn_debugging_agent to avoid actual tmux spawning
    mock_spawn = mocker.patch('orch.flag.spawn_debugging_agent', return_value={
        'success': True,
        'output': 'Agent spawned successfully'
    })

    # Test 1: Capture context (real, not mocked)
    current_dir = project_dir / "src"
    bug_context = capture_bug_context(
        description="Test bug in main.py",
        current_dir=current_dir,
        project_dir=project_dir
    )

    # Verify context was captured
    assert bug_context['description'] == "Test bug in main.py"
    assert bug_context['git_context']['branch'] is not None
    assert bug_context['project_name'] == "test_project"

    # Test 2: Run complete flag workflow
    result = flag_bug(
        description="Test bug in main.py",
        project_dir=project_dir
    )

    # Verify success
    assert result['success'] is True
    assert result['workspace_name'].startswith('debug-')
    assert 'test-bug-in-main' in result['workspace_name']

    # Verify workspace was created
    workspace_path = Path(result['workspace_path'])
    assert workspace_path.exists()
    workspace_file = workspace_path / "WORKSPACE.md"
    assert workspace_file.exists()

    # Verify workspace has context
    content = workspace_file.read_text()
    assert 'Test bug in main.py' in content
    assert 'Flagged From:' in content  # Has flagged from field
    assert 'Git Branch:' in content  # Has git context

    # Verify spawn was called
    assert mock_spawn.called


def test_cli_flag_command_with_project(cli_runner, tmp_path, mocker):
    """Test orch flag CLI command with real project context."""
    from orch.cli import cli
    from pathlib import Path

    # Setup project
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / ".orch").mkdir()

    # Mock flag_bug to verify it's called correctly
    mock_flag_bug = mocker.patch('orch.flag.flag_bug', return_value={
        'success': True,
        'workspace_name': 'debug-test-integration',
        'workspace_path': str(project_dir / '.orch' / 'workspace' / 'debug-test-integration'),
        'spawn_output': 'Agent spawned'
    })

    # Run CLI command from project directory
    result = cli_runner.invoke(cli, ['flag', 'Integration test bug'],
                               catch_exceptions=False)

    # Verify command succeeded
    assert result.exit_code == 0
    assert '🐛 Bug flagged' in result.output
    assert 'Integration test bug' in result.output

    # Verify flag_bug was called with correct args
    assert mock_flag_bug.called
    call_args = mock_flag_bug.call_args
    assert call_args[1]['description'] == 'Integration test bug'
    assert isinstance(call_args[1]['project_dir'], Path)


# cli_runner fixture is now provided by conftest.py
