"""
End-to-end workflow tests for orch CLI.

Tests complete user workflows from spawn to completion, validating that
the orchestration system works as users experience it.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from orch.cli import cli


# cli_runner and e2e_project_dir fixtures are now provided by conftest.py
# Note: e2e_project_dir from conftest.py has slightly different structure,
# so we define a local version for e2e tests that need specific structure


@pytest.fixture
def e2e_project_dir(tmp_path):
    """Create temporary project directory with .orch structure for e2e tests."""
    project = tmp_path / "test-project"
    project.mkdir()

    orch_dir = project / ".orch"
    orch_dir.mkdir()
    (orch_dir / "workspace").mkdir()
    (orch_dir / "agents").mkdir()
    (orch_dir / "active-agents.md").touch()

    return project


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for git and tmux commands."""
    def side_effect(args, **kwargs):
        cmd = args if isinstance(args, list) else [args]

        # Git commands
        if 'git' in str(cmd[0]):
            if 'branch' in cmd:
                return Mock(returncode=0, stdout="master\n", stderr="")
            elif 'status' in cmd:
                if '--porcelain' in cmd:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="nothing to commit, working tree clean\n", stderr="")
            elif 'log' in cmd:
                return Mock(returncode=0, stdout="abc123 Latest commit\n", stderr="")
            return Mock(returncode=0, stdout="", stderr="")

        # Tmux commands
        if 'tmux' in str(cmd[0]):
            if 'capture-pane' in cmd:
                return Mock(returncode=0, stdout="Welcome to Claude Code\nclaude>\n", stderr="")
            elif 'display-message' in cmd:
                if '#I' in str(cmd):
                    return Mock(returncode=0, stdout="10\n", stderr="")
                elif '#P' in str(cmd):
                    return Mock(returncode=0, stdout="0\n", stderr="")
                elif '#S' in str(cmd):
                    return Mock(returncode=0, stdout="orchestrator\n", stderr="")
            elif 'list-windows' in cmd:
                return Mock(returncode=0, stdout="10: test-window* (1 panes)\n", stderr="")
            elif 'new-window' in cmd:
                return Mock(returncode=0, stdout="10:@1008\n", stderr="")
            return Mock(returncode=0, stdout="", stderr="")

        return Mock(returncode=0, stdout="", stderr="")

    return side_effect


class TestSpawnCheckCompleteWorkflow:
    """Test the basic spawn → check → complete workflow."""

    def test_spawn_check_complete_happy_path(self, cli_runner, e2e_project_dir, mock_subprocess):
        """Test full workflow: spawn agent, check status, complete work."""
        with cli_runner.isolated_filesystem(temp_dir=e2e_project_dir.parent):
            # Change to project directory
            import os
            os.chdir(str(e2e_project_dir))

            # Clear worker context env vars to prevent "Cannot spawn from worker context" error
            worker_context_vars = ['CLAUDE_CONTEXT', 'CLAUDE_WORKSPACE', 'CLAUDE_PROJECT', 'CLAUDE_DELIVERABLES']

            # Configure mock registry - used by all modules via orch.registry.AgentRegistry
            mock_registry = Mock()
            mock_registry.list_active_agents.return_value = []
            mock_registry.register.return_value = {'id': 'test-agent-123'}
            mock_registry.find.return_value = None
            mock_registry.save.return_value = None
            mock_registry.remove.return_value = True

            # Mock the backend to return ready immediately
            mock_backend = Mock()
            mock_backend.wait_for_ready.return_value = True
            mock_backend.name = 'claude'
            mock_backend.get_env_vars.return_value = {}
            mock_backend.build_command.return_value = 'claude "test"'

            with patch('subprocess.run', side_effect=mock_subprocess), \
                 patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True), \
                 patch('orch.registry.AgentRegistry', return_value=mock_registry), \
                 patch('orch.cli.AgentRegistry', return_value=mock_registry), \
                 patch('orch.complete.verify_agent_work') as mock_verify, \
                 patch('orch.spawn.get_project_dir', return_value=e2e_project_dir), \
                 patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
                 patch('orch.tmux_utils.get_window_by_target', return_value=True), \
                 patch.dict(os.environ, {var: '' for var in worker_context_vars}, clear=False):

                # Configure verification to pass
                mock_verify.return_value = Mock(
                    passed=True,
                    violations=[],
                    warnings=[]
                )

                # Step 1: Spawn agent (ad-hoc mode)
                spawn_result = cli_runner.invoke(cli, [
                    'spawn',
                    'systematic-debugging',
                    'Test bug description',
                    '--project', 'test-project'
                ])

                # Verify spawn succeeded
                assert spawn_result.exit_code == 0, f"Spawn failed: {spawn_result.output}"
                assert 'Agent spawned' in spawn_result.output or 'spawned' in spawn_result.output.lower()

                # Step 2: Check agent status
                agent_id = "test-agent-123"
                workspace_name = "debug-test-bug-description"

                # Update mock to return our agent for check/complete steps
                mock_registry.list_active_agents.return_value = [{
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'skill': 'systematic-debugging',
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }]
                mock_registry.find.return_value = {
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'skill': 'systematic-debugging',
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }

                check_result = cli_runner.invoke(cli, ['check', agent_id])

                # Verify check shows agent info
                assert check_result.exit_code == 0, f"Check failed: {check_result.output}"
                # Check command may show workspace info or agent metadata

                # Step 3: Complete agent work
                # Create workspace to avoid errors
                workspace_dir = e2e_project_dir / ".orch" / "workspace" / workspace_name
                workspace_dir.mkdir(parents=True, exist_ok=True)
                workspace_file = workspace_dir / "WORKSPACE.md"
                workspace_file.write_text(f"""---
Type: implementation
Status: active
Phase: Complete
Project: test-project
---

# Test Workspace
""")

                complete_result = cli_runner.invoke(cli, ['complete', agent_id])

                # Verify completion succeeded
                assert complete_result.exit_code == 0, f"Complete failed: {complete_result.output}"


class TestSpawnSendCompleteWorkflow:
    """Test spawn → send message → complete workflow (intervention)."""

    def test_spawn_send_complete_with_intervention(self, cli_runner, e2e_project_dir, mock_subprocess):
        """Test workflow with orchestrator intervention via send."""
        with cli_runner.isolated_filesystem(temp_dir=e2e_project_dir.parent):
            import os
            os.chdir(str(e2e_project_dir))

            # Clear worker context env vars to prevent "Cannot spawn from worker context" error
            worker_context_vars = ['CLAUDE_CONTEXT', 'CLAUDE_WORKSPACE', 'CLAUDE_PROJECT', 'CLAUDE_DELIVERABLES']

            agent_id = "test-agent-456"
            workspace_name = "implement-test-feature"

            # Configure mock registry
            mock_registry = Mock()
            mock_registry.list_active_agents.return_value = []
            mock_registry.register.return_value = {'id': agent_id}
            mock_registry.find.return_value = None
            mock_registry.save.return_value = None
            mock_registry.remove.return_value = True

            # Mock the backend to return ready immediately
            mock_backend = Mock()
            mock_backend.wait_for_ready.return_value = True
            mock_backend.name = 'claude'
            mock_backend.get_env_vars.return_value = {}
            mock_backend.build_command.return_value = 'claude "test"'

            # Mock window lookup used by send.py
            mock_window = Mock()
            mock_window.id = '@1008'

            with patch('subprocess.run', side_effect=mock_subprocess), \
                 patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True), \
                 patch('orch.registry.AgentRegistry', return_value=mock_registry), \
                 patch('orch.cli.AgentRegistry', return_value=mock_registry), \
                 patch('orch.monitoring_commands.AgentRegistry', return_value=mock_registry), \
                 patch('orch.complete.verify_agent_work') as mock_verify, \
                 patch('orch.spawn.get_project_dir', return_value=e2e_project_dir), \
                 patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
                 patch('orch.tmux_utils.get_window_by_target', return_value=True), \
                 patch('orch.send.get_window_by_id', return_value=mock_window), \
                 patch.dict(os.environ, {var: '' for var in worker_context_vars}, clear=False):

                mock_verify.return_value = Mock(passed=True, violations=[], warnings=[])

                # Step 1: Spawn agent (use feature-impl instead of deprecated test-driven-development)
                spawn_result = cli_runner.invoke(cli, [
                    'spawn',
                    'feature-impl',
                    'Implement test feature',
                    '--project', 'test-project'
                ])

                assert spawn_result.exit_code == 0, f"Spawn failed: {spawn_result.output}"

                # Step 2: Send intervention message
                # Update mock to return our agent
                mock_registry.list_active_agents.return_value = [{
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }]
                mock_registry.find.return_value = {
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }

                send_result = cli_runner.invoke(cli, [
                    'send',
                    agent_id,
                    'Please add more test cases for edge cases'
                ])

                # Verify message sent
                assert send_result.exit_code == 0, f"Send failed: {send_result.output}"

                # Step 3: Complete work
                workspace_dir = e2e_project_dir / ".orch" / "workspace" / workspace_name
                workspace_dir.mkdir(parents=True, exist_ok=True)
                (workspace_dir / "WORKSPACE.md").write_text("""---
Type: implementation
Phase: Complete
---
""")

                complete_result = cli_runner.invoke(cli, ['complete', agent_id])

                assert complete_result.exit_code == 0, f"Complete failed: {complete_result.output}"


class TestROADMAPWorkflow:
    """Test ROADMAP-based spawning workflow.

    Note: Completing agents no longer updates ROADMAP (beads is now the work tracker).
    This test verifies spawning from ROADMAP still works.
    """

    def test_roadmap_spawn_complete_workflow(self, cli_runner, e2e_project_dir, mock_subprocess):
        """Test spawning from ROADMAP and completing agent."""
        with cli_runner.isolated_filesystem(temp_dir=e2e_project_dir.parent):
            import os
            os.chdir(str(e2e_project_dir))

            # Clear worker context env vars to prevent "Cannot spawn from worker context" error
            worker_context_vars = ['CLAUDE_CONTEXT', 'CLAUDE_WORKSPACE', 'CLAUDE_PROJECT', 'CLAUDE_DELIVERABLES']

            # Create ROADMAP.org with feature-impl skill (not deprecated test-driven-development)
            roadmap_file = e2e_project_dir / ".orch" / "ROADMAP.org"
            roadmap_file.write_text("""#+TITLE: Test Roadmap

* Phase 1: Testing

** 🚧 NEXT Test ROADMAP Feature
:PROPERTIES:
:Workspace: test-roadmap-feature
:Project: test-project
:Skill: feature-impl
:END:

Implement ROADMAP-based spawning.
""")

            agent_id = "roadmap-agent-789"
            workspace_name = "test-roadmap-feature"

            # Configure mock registry
            mock_registry = Mock()
            mock_registry.list_active_agents.return_value = []
            mock_registry.register.return_value = {'id': agent_id}
            mock_registry.find.return_value = None
            mock_registry.save.return_value = None
            mock_registry.remove.return_value = True

            # Mock the backend to return ready immediately
            mock_backend = Mock()
            mock_backend.wait_for_ready.return_value = True
            mock_backend.name = 'claude'
            mock_backend.get_env_vars.return_value = {}
            mock_backend.build_command.return_value = 'claude "test"'

            with patch('subprocess.run', side_effect=mock_subprocess), \
                 patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True), \
                 patch('orch.registry.AgentRegistry', return_value=mock_registry), \
                 patch('orch.cli.AgentRegistry', return_value=mock_registry), \
                 patch('orch.complete.verify_agent_work') as mock_verify, \
                 patch('orch.config.get_roadmap_paths', return_value=[roadmap_file]), \
                 patch('orch.spawn.get_project_dir', return_value=e2e_project_dir), \
                 patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
                 patch('orch.tmux_utils.get_window_by_target', return_value=True), \
                 patch.dict(os.environ, {var: '' for var in worker_context_vars}, clear=False):

                mock_verify.return_value = Mock(passed=True, violations=[], warnings=[])

                # Step 1: Spawn from ROADMAP
                spawn_result = cli_runner.invoke(cli, [
                    'spawn',
                    '--from-roadmap',
                    'Test ROADMAP Feature'
                ])

                # Verify spawn succeeded
                assert spawn_result.exit_code == 0, f"ROADMAP spawn failed: {spawn_result.output}"

                # Step 2: Complete agent (no longer updates ROADMAP - beads is now the work tracker)
                workspace_dir = e2e_project_dir / ".orch" / "workspace" / workspace_name
                workspace_dir.mkdir(parents=True, exist_ok=True)
                (workspace_dir / "WORKSPACE.md").write_text(f"""---
Type: implementation
Phase: Complete
Project: test-project
---
""")

                # Update mock to return our agent for completion
                mock_registry.list_active_agents.return_value = [{
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }]
                mock_registry.find.return_value = {
                    'id': agent_id,
                    'workspace': f".orch/workspace/{workspace_name}",
                    'project_dir': str(e2e_project_dir),
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }

                complete_result = cli_runner.invoke(cli, ['complete', agent_id])

                assert complete_result.exit_code == 0, f"Complete failed: {complete_result.output}"


class TestMultipleAgentsWorkflow:
    """Test running multiple concurrent agents."""

    def test_multiple_concurrent_agents(self, cli_runner, e2e_project_dir, mock_subprocess):
        """Test spawning and managing multiple agents simultaneously."""
        with cli_runner.isolated_filesystem(temp_dir=e2e_project_dir.parent):
            import os
            os.chdir(str(e2e_project_dir))

            # Clear worker context env vars to prevent "Cannot spawn from worker context" error
            worker_context_vars = ['CLAUDE_CONTEXT', 'CLAUDE_WORKSPACE', 'CLAUDE_PROJECT', 'CLAUDE_DELIVERABLES']

            # Configure mock registry
            mock_registry = Mock()
            mock_registry.list_active_agents.return_value = []
            mock_registry.register.return_value = {'id': 'agent-1'}
            mock_registry.find.return_value = None
            mock_registry.save.return_value = None
            mock_registry.remove.return_value = True

            # Mock the backend to return ready immediately
            mock_backend = Mock()
            mock_backend.wait_for_ready.return_value = True
            mock_backend.name = 'claude'
            mock_backend.get_env_vars.return_value = {}
            mock_backend.build_command.return_value = 'claude "test"'

            with patch('subprocess.run', side_effect=mock_subprocess), \
                 patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True), \
                 patch('orch.registry.AgentRegistry', return_value=mock_registry), \
                 patch('orch.cli.AgentRegistry', return_value=mock_registry), \
                 patch('orch.complete.verify_agent_work') as mock_verify, \
                 patch('orch.spawn.get_project_dir', return_value=e2e_project_dir), \
                 patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
                 patch('orch.tmux_utils.get_window_by_target', return_value=True), \
                 patch.dict(os.environ, {var: '' for var in worker_context_vars}, clear=False):

                mock_verify.return_value = Mock(passed=True, violations=[], warnings=[])

                # Spawn first agent
                spawn1_result = cli_runner.invoke(cli, [
                    'spawn',
                    'systematic-debugging',
                    'Bug 1',
                    '--project', 'test-project'
                ])
                assert spawn1_result.exit_code == 0, f"Spawn 1 failed: {spawn1_result.output}"

                # Update mock - first agent now active
                mock_registry.list_active_agents.return_value = [{
                    'id': 'agent-1',
                    'workspace': '.orch/workspace/debug-bug-1',
                    'project_dir': str(e2e_project_dir),
                    'window_id': '@1008',
                    'window': 'workers:10',
                    'status': 'active'
                }]

                # Spawn second agent (first still active)
                spawn2_result = cli_runner.invoke(cli, [
                    'spawn',
                    'systematic-debugging',
                    'Bug 2',
                    '--project', 'test-project'
                ])
                assert spawn2_result.exit_code == 0, f"Spawn 2 failed: {spawn2_result.output}"

                # Update mock - both agents now active
                mock_registry.list_active_agents.return_value = [
                    {'id': 'agent-1', 'workspace': '.orch/workspace/debug-bug-1', 'project_dir': str(e2e_project_dir), 'window_id': '@1008', 'window': 'workers:10', 'status': 'active'},
                    {'id': 'agent-2', 'workspace': '.orch/workspace/debug-bug-2', 'project_dir': str(e2e_project_dir), 'window_id': '@1009', 'window': 'workers:11', 'status': 'active'}
                ]

                # Check status shows both agents
                status_result = cli_runner.invoke(cli, ['status'])

                assert status_result.exit_code == 0, f"Status failed: {status_result.output}"
                # Status should show multiple agents
