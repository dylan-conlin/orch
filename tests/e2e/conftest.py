"""
Pytest fixtures for E2E tests.

Provides isolated test environments with tmux sessions, git repositories,
and temporary directories for realistic end-to-end testing.
"""

import pytest
import tempfile
import subprocess
import shutil
from pathlib import Path
import os
import time


@pytest.fixture
def e2e_env(monkeypatch):
    """
    Provide isolated E2E test environment.

    Returns dict with:
        - tmux_session: Name of isolated tmux session
        - project_dir: Path to temporary git repository
        - registry_path: Path to temporary registry file
        - home_dir: Mocked HOME directory
        - env: Dict of environment variables to pass to subprocess

    Automatically cleans up on teardown.
    """
    # Create unique session name for isolation
    session_name = f"e2e-test-{int(time.time() * 1000000) % 1000000}"

    # Create temporary directory for the test
    temp_dir = Path(tempfile.mkdtemp(prefix='orch-e2e-'))

    # Create fake HOME directory for isolation
    home_dir = temp_dir / "home"
    home_dir.mkdir()

    # Create .orch directory in fake HOME
    orch_config_dir = home_dir / '.orch'
    orch_config_dir.mkdir()

    # Create project directory structure
    project_dir = temp_dir / "test-project"
    project_dir.mkdir()

    # Create active-projects.md (required by orch spawn)
    # Format: ## project-name followed by **Path:** `path` (in backticks)
    active_projects_file = orch_config_dir / 'active-projects.md'
    active_projects_file.write_text(f"""# Active Projects

## {project_dir.name}
**Path:** `{project_dir}`
**Description:** E2E test project
""")

    # Create minimal ROADMAP.org (some commands check for it)
    roadmap_file = orch_config_dir / 'ROADMAP.org'
    roadmap_file.write_text("""#+TITLE: E2E Test ROADMAP

* Test Tasks
""")

    # Create config.yaml to point to our files
    config_file = orch_config_dir / 'config.yaml'
    config_file.write_text(f"""# E2E test configuration
tmux_session: {session_name}
active_projects_file: {active_projects_file}
roadmap_paths:
  - {roadmap_file}
""")

    # Copy workspace templates from real ~/.orch/templates to fake HOME
    # This allows spawn to create workspaces
    real_templates_dir = Path.home() / '.orch' / 'templates'
    fake_templates_dir = orch_config_dir / 'templates'
    fake_templates_dir.mkdir()

    # Copy WORKSPACE.md template
    if (real_templates_dir / 'WORKSPACE.md').exists():
        shutil.copy(
            real_templates_dir / 'WORKSPACE.md',
            fake_templates_dir / 'WORKSPACE.md'
        )

    # Initialize as git repository (required by orch commands)
    subprocess.run(
        ['git', 'init'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )

    # Configure git user for commits (required for some operations)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'E2E Test'],
        cwd=project_dir,
        check=True,
        capture_output=True
    )

    # Create .orch directory structure
    orch_dir = project_dir / '.orch'
    orch_dir.mkdir()
    (orch_dir / 'workspace').mkdir()

    # Create initial git commit (some commands require non-empty repo)
    (project_dir / 'README.md').write_text('# Test Project\n')
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

    # Registry will be at ~/.orch/agent-registry.json (in our mocked HOME)
    registry_path = orch_config_dir / 'agent-registry.json'

    # Create isolated tmux session
    subprocess.run(
        ['tmux', 'new-session', '-d', '-s', session_name],
        check=True,
        capture_output=True
    )

    # Create environment dict for subprocess calls
    # This ensures orch commands use our fake HOME
    test_env = os.environ.copy()
    test_env['HOME'] = str(home_dir)

    # Remove worker context variables to ensure clean orchestrator context
    # (tests may run from within spawned agents, inheriting worker env vars)
    for var in ['CLAUDE_CONTEXT', 'CLAUDE_WORKSPACE', 'CLAUDE_PROJECT', 'CLAUDE_DELIVERABLES']:
        test_env.pop(var, None)

    # Package environment for test
    env = {
        'tmux_session': session_name,
        'project_dir': project_dir,
        'registry_path': registry_path,
        'home_dir': home_dir,
        'temp_dir': temp_dir,
        'env': test_env,  # Pass this to subprocess.run(..., env=env['env'])
    }

    # Yield to test
    yield env

    # Cleanup: Kill tmux session
    try:
        subprocess.run(
            ['tmux', 'kill-session', '-t', session_name],
            check=False,  # Don't fail if session already gone
            capture_output=True,
            timeout=5
        )
    except (subprocess.TimeoutExpired, Exception):
        # If kill-session hangs or fails, force it
        pass

    # Cleanup: Remove temporary directory
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        # Best effort cleanup
        pass
