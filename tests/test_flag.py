"""Tests for bug flagging module."""

import pytest
from pathlib import Path


def test_generate_workspace_slug():
    """Test generating workspace slug from bug description."""
    from orch.flag import generate_workspace_slug

    # Test basic slug generation
    assert generate_workspace_slug("Price calculation returns null") == "debug-price-calculation-returns-null"

    # Test with special characters
    assert generate_workspace_slug("User's auth token isn't valid!") == "debug-users-auth-token-isnt-valid"

    # Test truncation
    long_desc = "This is a very long description " * 10
    slug = generate_workspace_slug(long_desc)
    assert len(slug) <= 60  # Reasonable limit (max_length + some buffer)
    assert slug.startswith("debug-")


def test_create_debugging_workspace(tmp_path, monkeypatch):
    """Test creating debugging workspace with pre-filled context."""
    from orch.flag import create_debugging_workspace
    from pathlib import Path

    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create .orch directory structure
    (project_dir / ".orch" / "workspace").mkdir(parents=True)

    # Mock Path.home() for template access (templates expected at ~/.orch/templates/)
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
- **Current Goal:** [One sentence - what you're working on NOW]

## Context
[Background needed to understand this work]

---

## External References
""")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    workspace_name = "debug-test-bug"
    bug_context = {
        'description': 'Test bug',
        'current_dir': str(project_dir / 'src'),
        'git_context': {
            'branch': 'main',
            'git_status': ' M src/file.py',
            'modified_files': ['src/file.py']
        },
        'workspace_context': {
            'workspace_path': '.orch/workspace/feature-work',
            'workspace_summary': {'current_goal': 'Implement feature', 'phase': 'Planning'}
        }
    }

    result = create_debugging_workspace(
        workspace_name=workspace_name,
        project_dir=project_dir,
        bug_context=bug_context
    )

    assert result['workspace_path'] is not None
    assert result['workspace_file'].exists()

    # Check that context was pre-filled
    content = result['workspace_file'].read_text()
    assert 'Test bug' in content
    assert 'main' in content  # Git branch


def test_construct_spawn_prompt():
    """Test constructing spawn prompt for debugging agent."""
    from orch.flag import construct_spawn_prompt

    bug_context = {
        'description': 'Test bug',
        'current_dir': '/tmp/test_project/src',
        'git_context': {
            'branch': 'main',
            'modified_files': ['src/file.py']
        },
        'workspace_context': {
            'workspace_path': '.orch/workspace/feature-work',
            'workspace_summary': {'current_goal': 'Implement feature', 'phase': 'Planning'}
        }
    }
    workspace_path = '.orch/workspace/debug-test-bug'

    prompt = construct_spawn_prompt(bug_context, workspace_path)

    assert 'TASK: Investigate bug' in prompt
    assert 'Test bug' in prompt
    assert 'systematic-debugging' in prompt
    assert workspace_path in prompt
    assert '.orch/workspace/feature-work' in prompt


def test_flag_bug_workflow(tmp_path, monkeypatch, mocker):
    """Test complete flag bug workflow."""
    from orch.flag import flag_bug
    from pathlib import Path

    # Mock subprocess calls for tmux/spawn
    mock_spawn = mocker.patch('orch.flag.spawn_debugging_agent', return_value={
        'success': True,
        'output': 'Agent spawned successfully'
    })

    # Setup test project
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / ".orch" / "workspace").mkdir(parents=True)

    # Mock Path.home() for template access (templates expected at ~/.orch/templates/)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    template_dir = fake_home / ".orch" / "templates"
    template_dir.mkdir(parents=True)
    template_file = template_dir / "WORKSPACE.md"
    template_file.write_text("""# Workspace: {{ workspace_name }}

## Context
[Background needed to understand this work]

---

## External References
""")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Mock capture_bug_context to avoid git/workspace dependencies
    mock_context = {
        'description': 'Test bug description',
        'current_dir': str(project_dir),
        'git_context': {
            'branch': 'main',
            'modified_files': ['test.py']
        },
        'workspace_context': {}
    }
    mocker.patch('orch.flag.capture_bug_context', return_value=mock_context)

    # Run flag_bug
    description = "Test bug description"
    result = flag_bug(
        description=description,
        project_dir=project_dir
    )

    assert result['success'] is True
    assert result['workspace_name'].startswith('debug-')
    assert result['workspace_path'] is not None
    assert mock_spawn.called


def test_flag_without_git(tmp_path, monkeypatch, mocker):
    """Test flagging bug in non-git directory."""
    from orch.flag import flag_bug
    from pathlib import Path

    # Mock spawn to avoid actual spawning
    mocker.patch('orch.flag.spawn_debugging_agent', return_value={
        'success': True,
        'output': 'Agent spawned'
    })

    # Setup non-git project
    project_dir = tmp_path / "test_non_git_project"
    project_dir.mkdir()
    (project_dir / ".orch" / "workspace").mkdir(parents=True)

    # Mock Path.home() for template (templates expected at ~/.orch/templates/)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    template_dir = fake_home / ".orch" / "templates"
    template_dir.mkdir(parents=True)
    template_file = template_dir / "WORKSPACE.md"
    template_file.write_text("""# Workspace: {{ workspace_name }}

## Context
[Background]

---

## External References
""")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Mock capture_bug_context to return context without git
    mock_context = {
        'description': 'Test bug',
        'current_dir': str(project_dir),
        'git_context': {
            'branch': None,
            'git_status': '',
            'modified_files': []
        },
        'workspace_context': {}
    }
    mocker.patch('orch.flag.capture_bug_context', return_value=mock_context)

    result = flag_bug(
        description="Test bug",
        project_dir=project_dir
    )

    # Should still succeed, just without git context
    assert result['success'] is True


def test_flag_outside_workspace(tmp_path, monkeypatch, mocker):
    """Test flagging bug when not in a workspace."""
    from orch.flag import flag_bug
    from pathlib import Path

    # Mock spawn
    mocker.patch('orch.flag.spawn_debugging_agent', return_value={
        'success': True,
        'output': 'Agent spawned'
    })

    # Setup project without workspace
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / ".orch" / "workspace").mkdir(parents=True)

    # Mock Path.home() for template (templates expected at ~/.orch/templates/)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    template_dir = fake_home / ".orch" / "templates"
    template_dir.mkdir(parents=True)
    template_file = template_dir / "WORKSPACE.md"
    template_file.write_text("""# Workspace: {{ workspace_name }}

## Context
[Background]

---

## External References
""")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Mock capture_bug_context with no workspace context
    mock_context = {
        'description': 'Test bug',
        'current_dir': str(project_dir),
        'git_context': {
            'branch': 'main',
            'modified_files': []
        },
        'workspace_context': None  # No workspace
    }
    mocker.patch('orch.flag.capture_bug_context', return_value=mock_context)

    result = flag_bug(
        description="Test bug",
        project_dir=project_dir
    )

    # Should succeed, workspace context will be None
    assert result['success'] is True


def test_slug_edge_cases():
    """Test slug generation with edge cases."""
    from orch.flag import generate_workspace_slug

    # Empty description - should generate timestamp-based slug
    slug = generate_workspace_slug("")
    assert slug.startswith("debug-bug-")

    # Only whitespace
    slug = generate_workspace_slug("   ")
    assert slug.startswith("debug-bug-")

    # Only special characters - should generate timestamp-based slug
    slug = generate_workspace_slug("!!!???")
    assert slug.startswith("debug-bug-") or slug == "debug"

    # Unicode characters should be normalized
    slug = generate_workspace_slug("Fix café menu")
    assert slug == "debug-fix-cafe-menu"


def test_spawn_uses_full_project_path(tmp_path, monkeypatch, mocker):
    """Test that spawn_debugging_agent uses full project path, not just name."""
    from orch.flag import spawn_debugging_agent
    from pathlib import Path

    # Setup project directory
    project_dir = tmp_path / "test_unregistered_project"
    project_dir.mkdir()

    # Mock subprocess.run to capture the command
    mock_run = mocker.patch('subprocess.run', return_value=mocker.Mock(
        returncode=0,
        stdout='Agent spawned',
        stderr=''
    ))

    # Call spawn_debugging_agent
    result = spawn_debugging_agent(
        workspace_name="debug-test",
        workspace_path=str(tmp_path / "workspace"),
        spawn_prompt="Test prompt",
        project_dir=project_dir
    )

    # Verify subprocess.run was called
    assert mock_run.called

    # Get the command that was called
    call_args = mock_run.call_args[0][0]

    # Find the --project argument
    project_arg_index = call_args.index('--project')
    project_value = call_args[project_arg_index + 1]

    # Should be full path, not just "test_unregistered_project"
    assert str(project_dir) in project_value
    assert project_value != "test_unregistered_project"
