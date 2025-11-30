"""
Shared pytest fixtures for orch tests.

This module provides commonly used fixtures to reduce duplication across test files.
Fixtures are automatically discovered by pytest when placed in conftest.py.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
from click.testing import CliRunner


# =============================================================================
# SUBPROCESS MOCK HELPERS
# =============================================================================

def create_subprocess_mock(tmux_output="10:@1008\n"):
    """
    Create a mock for subprocess.run that handles both git and tmux commands.

    Args:
        tmux_output: The output to return for tmux commands (default: window target)

    Returns:
        A side_effect function that returns appropriate mock results based on command.
    """
    def side_effect(args, **kwargs):
        cmd = args if isinstance(args, list) else [args]

        # Git branch check - return 'master' for main branch validation
        if cmd == ['git', 'branch', '--show-current']:
            return Mock(returncode=0, stdout="master\n", stderr="")

        # Git status --porcelain check - return empty string for clean working tree
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status'] and '--porcelain' in cmd:
            return Mock(returncode=0, stdout="", stderr="")

        # Git status (regular) - return clean message
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status']:
            return Mock(returncode=0, stdout="nothing to commit, working tree clean\n", stderr="")

        # Tmux capture-pane - return Claude prompt content for polling
        # Using actual Claude Code output pattern (verified from tmux panes)
        if len(cmd) >= 2 and cmd[:2] == ['tmux', 'capture-pane']:
            return Mock(
                returncode=0,
                stdout="─────────────────────────────────────────\n> Try 'refactor ui.py'\n─────────────────────────────────────────\n",
                stderr=""
            )

        # Tmux commands - return configured output (usually window target)
        if cmd and 'tmux' in str(cmd[0]):
            return Mock(returncode=0, stdout=tmux_output, stderr="")

        # Default for other commands
        return Mock(returncode=0, stdout="", stderr="")

    return side_effect


# =============================================================================
# CLI FIXTURES
# =============================================================================

@pytest.fixture
def cli_runner():
    """
    Provide Click CLI test runner.

    Returns a CliRunner instance for testing CLI commands.

    Usage:
        def test_my_command(cli_runner):
            from orch.cli import cli
            result = cli_runner.invoke(cli, ['my-command', '--flag'])
            assert result.exit_code == 0
    """
    return CliRunner()


# =============================================================================
# REGISTRY FIXTURES
# =============================================================================

@pytest.fixture
def temp_registry_path(tmp_path):
    """
    Create a temporary registry file path for testing.

    Returns a Path object pointing to a temporary registry.json file.
    The file does not exist yet - use this when you need just the path.

    Usage:
        def test_registry(temp_registry_path):
            registry = AgentRegistry(registry_path=temp_registry_path)
    """
    return tmp_path / "test-registry.json"


@pytest.fixture
def temp_registry(tmp_path):
    """
    Create a temporary AgentRegistry instance for testing.

    Returns an AgentRegistry instance with a temporary file path.
    Import AgentRegistry locally to avoid circular imports.

    Usage:
        def test_registry_ops(temp_registry):
            temp_registry.register(agent_id="test", ...)
    """
    from orch.registry import AgentRegistry
    registry_path = tmp_path / "test-registry.json"
    return AgentRegistry(registry_path=registry_path)


# =============================================================================
# WORKSPACE FIXTURES
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """
    Create a temporary workspace directory structure for testing.

    Returns a Path to a WORKSPACE.md file within a properly structured
    .orch/workspace directory.

    Usage:
        def test_workspace(temp_workspace):
            temp_workspace.write_text("**Phase:** Complete")
    """
    workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
    workspace_dir.mkdir(parents=True)
    return workspace_dir / "WORKSPACE.md"


@pytest.fixture
def temp_workspace_with_content(temp_workspace):
    """
    Create a temporary workspace with basic content.

    Returns a Path to a WORKSPACE.md file with minimal valid content.

    Usage:
        def test_with_workspace(temp_workspace_with_content):
            content = temp_workspace_with_content.read_text()
    """
    temp_workspace.write_text("""**TLDR:** Test workspace for unit tests

---

# Workspace: test-workspace

**Phase:** Planning
**Status:** Active
**Type:** Implementation
""")
    return temp_workspace


# =============================================================================
# PROJECT FIXTURES
# =============================================================================

@pytest.fixture
def project_dir(tmp_path):
    """
    Create a temporary project directory with .orch structure.

    Returns a Path to a temporary project directory with:
    - .orch/ directory
    - .orch/workspace/ subdirectory
    - Initialized as git repository (optional - see git_project_dir)

    Usage:
        def test_project(project_dir):
            workspace_dir = project_dir / ".orch" / "workspace"
    """
    project = tmp_path / "test-project"
    project.mkdir()
    (project / ".orch").mkdir()
    (project / ".orch" / "workspace").mkdir()
    return project


@pytest.fixture
def git_project_dir(project_dir):
    """
    Create a temporary project directory initialized as a git repository.

    Returns a Path to a project directory that has been git init'd
    with an initial commit.

    Usage:
        def test_git_ops(git_project_dir):
            # git commands will work in this directory
    """
    import subprocess

    subprocess.run(
        ['git', 'init'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )

    # Create initial commit
    readme = project_dir / "README.md"
    readme.write_text("# Test Project\n")
    subprocess.run(
        ['git', 'add', 'README.md'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )

    return project_dir


# =============================================================================
# ROADMAP FIXTURES
# =============================================================================

@pytest.fixture
def sample_roadmap_content():
    """
    Provide sample ROADMAP.org content for testing.

    Returns a string containing valid org-mode ROADMAP content
    with TODO and DONE items.

    Usage:
        def test_roadmap(sample_roadmap_content):
            assert "** TODO First task" in sample_roadmap_content
    """
    return """#+TITLE: Test Roadmap
#+AUTHOR: Test Author

* Phase 1: Testing

** TODO First task :tag1:tag2:
Mode: autonomous
:PROPERTIES:
:Created: 2025-11-16
:Project: test-project
:Workspace: test-workspace
:Skill: test-skill
:Priority: 1
:END:

**Context:** This is a test task for validating ROADMAP parsing.

**Problem:** Need to test parsing functionality.

** DONE Second task :tag3:
CLOSED: [2025-11-15]
Mode: interactive
:PROPERTIES:
:Created: 2025-11-14
:Completed: 2025-11-15
:Project: test-project-2
:Workspace: test-workspace-2
:Skill: test-skill-2
:Priority: 2
:END:

**Context:** This is a completed task.

**Resolution:** Task completed successfully.

** TODO Third task with missing properties
Mode: autonomous

**Context:** This task has no :PROPERTIES: block.
"""


@pytest.fixture
def temp_roadmap_file(tmp_path, sample_roadmap_content):
    """
    Create a temporary ROADMAP.org file for testing.

    Returns a Path to a temporary ROADMAP.org file populated
    with sample content.

    Usage:
        def test_roadmap_parsing(temp_roadmap_file):
            items = parse_roadmap_file(temp_roadmap_file)
    """
    roadmap_file = tmp_path / "ROADMAP.org"
    roadmap_file.write_text(sample_roadmap_content)
    return roadmap_file


# =============================================================================
# MOCK AGENT FIXTURES
# =============================================================================

@pytest.fixture
def mock_agent():
    """
    Provide a standard mock agent dictionary.

    Returns a dict representing a typical agent in the registry.

    Usage:
        def test_with_agent(mock_agent):
            mock_agent['status'] = 'completed'
    """
    return {
        'id': 'test-agent',
        'task': 'Test task description',
        'window': 'orchestrator:1',
        'window_id': '@100',
        'project_dir': '/tmp/test-project',
        'workspace': '.orch/workspace/test-workspace',
        'status': 'active',
        'spawned_at': '2025-11-27T10:00:00',
    }


@pytest.fixture
def mock_agent_completed(mock_agent):
    """
    Provide a completed mock agent dictionary.

    Returns a dict representing a completed agent with completion timestamp.

    Usage:
        def test_completed_agent(mock_agent_completed):
            assert mock_agent_completed['status'] == 'completed'
    """
    mock_agent['status'] = 'completed'
    mock_agent['completed_at'] = '2025-11-27T12:00:00'
    return mock_agent


# =============================================================================
# CONFIG FIXTURES
# =============================================================================

@pytest.fixture
def reset_config_cache():
    """
    Reset the config module cache before and after test.

    This fixture should be used in tests that modify or test
    config loading behavior.

    Usage:
        def test_config(reset_config_cache):
            # Config cache is cleared
            cfg = config.get_config()
    """
    from orch import config
    config._CONFIG_CACHE = None
    yield
    config._CONFIG_CACHE = None
