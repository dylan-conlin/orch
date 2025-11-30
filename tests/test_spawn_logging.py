"""
Tests for spawn command logging in orch spawn.

Tests logging functionality including:
- Logging spawn start events
- Logging spawn completion events
- Logging errors (tmux unavailable, session not found)
- Timing and duration measurement
- Agent registration logging
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from orch.spawn import (
    spawn_in_tmux,
    register_agent,
    SpawnConfig,
)


def create_subprocess_mock(tmux_output="10:@1008\n"):
    """
    Create a mock for subprocess.run that handles both git and tmux commands.
    """
    def side_effect(args, **kwargs):
        cmd = args if isinstance(args, list) else [args]
        if cmd == ['git', 'branch', '--show-current']:
            return Mock(returncode=0, stdout="master\n", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status'] and '--porcelain' in cmd:
            return Mock(returncode=0, stdout="", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status']:
            return Mock(returncode=0, stdout="nothing to commit, working tree clean\n", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['tmux', 'capture-pane']:
            return Mock(returncode=0, stdout="─────────────────────────────────────────\n> Try 'refactor ui.py'\n─────────────────────────────────────────\n", stderr="")
        if cmd and 'tmux' in str(cmd[0]):
            return Mock(returncode=0, stdout=tmux_output, stderr="")
        return Mock(returncode=0, stdout="", stderr="")
    return side_effect


class TestSpawnLogging:
    """Tests for spawn command logging."""

    def test_spawn_logs_start_event(self, tmp_path):
        """Test that spawn logs start event with task details."""
        # Set up project directory with required structure
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()
        (project_dir / ".orch" / "workspace").mkdir()

        config = SpawnConfig(
            task="debug cart bug",
            project="test-project",
            project_dir=project_dir,
            workspace_name="debug-cart-bug",
            skill_name="systematic-debugging"
        )

        mock_session = Mock()

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('subprocess.run', side_effect=create_subprocess_mock("10:@1008\n")), \
             patch('time.sleep'), \
             patch('orch.tmux_utils.get_window_by_target', return_value=Mock()), \
             patch('orch.spawn.OrchLogger') as MockLogger, \
             patch('pathlib.Path.write_text'):

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            spawn_in_tmux(config)

            # Verify start logging was called
            assert mock_logger.log_command_start.called
            call_args = mock_logger.log_command_start.call_args
            assert call_args[0][0] == "spawn"  # command name
            assert "debug cart bug" in str(call_args[0][1])  # task in data

    def test_spawn_logs_complete_event(self, tmp_path):
        """Test that spawn logs complete event with timing and result."""
        # Set up project directory with required structure
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()
        (project_dir / ".orch" / "workspace").mkdir()

        config = SpawnConfig(
            task="debug cart bug",
            project="test-project",
            project_dir=project_dir,
            workspace_name="debug-cart-bug"
        )

        mock_session = Mock()

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('subprocess.run', side_effect=create_subprocess_mock("10:@1008\n")), \
             patch('time.sleep'), \
             patch('orch.tmux_utils.get_window_by_target', return_value=Mock()), \
             patch('orch.spawn.OrchLogger') as MockLogger, \
             patch('pathlib.Path.write_text'):

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            result = spawn_in_tmux(config)

            # Verify complete logging was called
            assert mock_logger.log_command_complete.called
            call_args = mock_logger.log_command_complete.call_args
            assert call_args[0][0] == "spawn"  # command name
            assert isinstance(call_args[0][1], int)  # duration_ms
            assert "agent_id" in call_args[0][2]  # data dict

    def test_spawn_logs_error_on_tmux_unavailable(self):
        """Test that spawn logs error when tmux is unavailable."""
        config = SpawnConfig(
            task="test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace"
        )

        with patch('orch.tmux_utils.is_tmux_available', return_value=False), \
             patch('subprocess.run', side_effect=create_subprocess_mock()), \
             patch('orch.spawn.OrchLogger') as MockLogger:

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            with pytest.raises(RuntimeError, match="Tmux not available"):
                spawn_in_tmux(config)

            # Verify error was logged
            assert mock_logger.log_error.called
            call_args = mock_logger.log_error.call_args
            assert call_args[0][0] == "spawn"
            assert "Tmux not available" in call_args[0][1]

    def test_spawn_logs_error_on_session_not_found(self):
        """Test that spawn logs error when tmux session not found."""
        config = SpawnConfig(
            task="test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace"
        )

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=None), \
             patch('subprocess.run', side_effect=create_subprocess_mock()), \
             patch('orch.spawn.OrchLogger') as MockLogger:

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            with pytest.raises(RuntimeError, match="Tmux session.*not found"):
                spawn_in_tmux(config)

            # Verify error was logged
            assert mock_logger.log_error.called

    def test_spawn_logs_duration_timing(self, tmp_path):
        """Test that spawn measures and logs duration correctly."""
        # Set up project directory with required structure
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()
        (project_dir / ".orch" / "workspace").mkdir()

        config = SpawnConfig(
            task="test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        mock_session = Mock()

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('subprocess.run', side_effect=create_subprocess_mock("10:@1008\n")), \
             patch('time.sleep'), \
             patch('orch.tmux_utils.get_window_by_target', return_value=Mock()), \
             patch('orch.spawn.OrchLogger') as MockLogger, \
             patch('pathlib.Path.write_text'):

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            spawn_in_tmux(config)

            # Verify duration was measured and passed to log_command_complete
            assert mock_logger.log_command_complete.called
            duration_ms = mock_logger.log_command_complete.call_args[0][1]
            assert duration_ms >= 0  # Should be non-negative
            assert isinstance(duration_ms, int)

    def test_register_agent_logs_success(self, tmp_path):
        """Test that register_agent logs successful registration to orch logs."""
        with patch('orch.registry.AgentRegistry') as MockRegistry, \
             patch('orch.spawn.OrchLogger') as MockLogger:

            mock_registry = Mock()
            MockRegistry.return_value = mock_registry
            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            register_agent(
                agent_id="test-agent",
                task="Test task",
                window="orchestrator:10",
                window_id="@1008",
                project_dir=Path("/test/project"),
                workspace_name="test-workspace",
                skill_name="feature-impl"
            )

            # Verify successful registration was logged to orch logs
            mock_logger.log_event.assert_called_once()
            call_args = mock_logger.log_event.call_args
            assert call_args[0][0] == "register"  # command name
            assert "Agent registered" in call_args[0][1]  # message
            assert call_args[0][2]["agent_id"] == "test-agent"  # data

    def test_register_agent_logs_failure(self, tmp_path):
        """Test that register_agent logs failed registration to orch logs.

        This test verifies the fix for the spawn logging gap:
        Previously, registration failures only went to stderr, not orch logs.
        Ref: .orch/investigations/systems/2025-11-12-follow-investigation-why-spawn-command-execute-4x.md
        """
        with patch('orch.registry.AgentRegistry') as MockRegistry, \
             patch('orch.spawn.OrchLogger') as MockLogger:

            mock_registry = Mock()
            # Simulate duplicate agent registration failure
            mock_registry.register.side_effect = ValueError("Agent 'test-agent' already registered")
            MockRegistry.return_value = mock_registry
            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            # Should raise ValueError for duplicate registration
            with pytest.raises(ValueError, match="already registered"):
                register_agent(
                    agent_id="test-agent",
                    task="Test task",
                    window="orchestrator:10",
                    project_dir=Path("/test/project"),
                    workspace_name="test-workspace"
                )

            # Verify registration failure was logged to orch logs (fixes logging gap)
            mock_logger.log_error.assert_called_once()
            call_args = mock_logger.log_error.call_args
            assert call_args[0][0] == "register"  # command name
            assert "Registration failed" in call_args[0][1]  # message
            assert call_args[0][2]["agent_id"] == "test-agent"  # data
            assert "already registered" in call_args[0][2]["reason"]
