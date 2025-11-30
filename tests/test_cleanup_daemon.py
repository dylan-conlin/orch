"""
Tests for orch cleanup_daemon module.

Tests the background daemon for async agent cleanup, including:
- Process detection
- Graceful shutdown
- Exit command sending
- Force kill
- Ephemeral workspace cleanup
- Main cleanup cascade
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from orch.cleanup_daemon import (
    has_active_processes,
    graceful_shutdown_window,
    send_exit_command,
    force_kill_window,
    cleanup_ephemeral_workspace,
    mark_agent_completed,
    cleanup_agent_async,
    main,
)


class TestHasActiveProcesses:
    """Tests for has_active_processes function."""

    def test_returns_false_when_tmux_list_panes_fails(self):
        """When tmux list-panes command fails, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout='', stderr='error')
            assert has_active_processes('@123') is False

    def test_returns_false_when_no_pid_returned(self):
        """When no PID is returned from tmux, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
            assert has_active_processes('@123') is False

    def test_returns_true_when_child_processes_exist(self):
        """When pgrep finds child processes, should return True."""
        with patch('subprocess.run') as mock_run:
            # First call: tmux list-panes returns PID
            # Second call: pgrep finds children
            mock_run.side_effect = [
                Mock(returncode=0, stdout='12345\n', stderr=''),
                Mock(returncode=0, stdout='12346\n12347\n', stderr=''),
            ]
            assert has_active_processes('@123') is True

    def test_returns_false_when_no_child_processes(self):
        """When pgrep finds no child processes, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout='12345\n', stderr=''),
                Mock(returncode=1, stdout='', stderr=''),  # pgrep returns 1 when no match
            ]
            assert has_active_processes('@123') is False

    def test_returns_false_on_exception(self):
        """When any exception occurs, should return False (fail safe)."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception('Unexpected error')
            assert has_active_processes('@123') is False


class TestGracefulShutdownWindow:
    """Tests for graceful_shutdown_window function."""

    def test_returns_true_immediately_if_no_active_processes(self):
        """If no processes are active, should return True without sending Ctrl+C."""
        with patch('orch.cleanup_daemon.has_active_processes', return_value=False):
            with patch('subprocess.run') as mock_run:
                result = graceful_shutdown_window('@123', wait_seconds=1)
                assert result is True
                # Should not have called subprocess.run for send-keys
                assert not any(
                    'send-keys' in str(call) for call in mock_run.call_args_list
                )

    def test_sends_ctrl_c_and_waits(self):
        """Should send Ctrl+C and wait for processes to terminate."""
        with patch('orch.cleanup_daemon.has_active_processes') as mock_has_active:
            # First check: has processes, after wait: no processes
            mock_has_active.side_effect = [True, False]
            with patch('subprocess.run') as mock_run:
                with patch('time.sleep') as mock_sleep:
                    result = graceful_shutdown_window('@123', wait_seconds=5)
                    assert result is True
                    mock_sleep.assert_called_once_with(5)
                    # Check Ctrl+C was sent
                    mock_run.assert_called()

    def test_returns_false_when_processes_still_active(self):
        """When processes remain after waiting, should return False."""
        with patch('orch.cleanup_daemon.has_active_processes') as mock_has_active:
            mock_has_active.side_effect = [True, True]  # Still active after wait
            with patch('subprocess.run'):
                with patch('time.sleep'):
                    result = graceful_shutdown_window('@123', wait_seconds=1)
                    assert result is False

    def test_returns_false_on_exception(self):
        """On exception, should return False."""
        with patch('orch.cleanup_daemon.has_active_processes', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = Exception('tmux error')
                result = graceful_shutdown_window('@123')
                assert result is False


class TestSendExitCommand:
    """Tests for send_exit_command function."""

    def test_sends_exit_and_waits(self):
        """Should send /exit command and wait."""
        with patch('subprocess.run') as mock_run:
            with patch('time.sleep') as mock_sleep:
                with patch('orch.cleanup_daemon.has_active_processes', return_value=False):
                    result = send_exit_command('@123', wait_seconds=5)
                    assert result is True
                    mock_sleep.assert_called_once_with(5)
                    # Verify /exit was sent
                    call_args = mock_run.call_args_list[0]
                    assert '/exit' in call_args[0][0]
                    assert 'Enter' in call_args[0][0]

    def test_returns_false_when_processes_still_active(self):
        """When processes remain after /exit, should return False."""
        with patch('subprocess.run'):
            with patch('time.sleep'):
                with patch('orch.cleanup_daemon.has_active_processes', return_value=True):
                    result = send_exit_command('@123', wait_seconds=1)
                    assert result is False

    def test_returns_false_on_exception(self):
        """On exception, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception('tmux error')
            result = send_exit_command('@123')
            assert result is False


class TestForceKillWindow:
    """Tests for force_kill_window function."""

    def test_kills_window_successfully(self):
        """Should kill tmux window and return True."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout='orchestrator\n', stderr=''),  # display-message
                Mock(returncode=0, stdout='@1\n@2\n', stderr=''),  # list-windows
                Mock(returncode=0, stdout='', stderr=''),  # kill-window
            ]
            result = force_kill_window('@123')
            assert result is True

    def test_creates_new_window_if_last_window(self):
        """If killing last window, should create new window first."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout='orchestrator\n', stderr=''),  # display-message
                Mock(returncode=0, stdout='@1\n', stderr=''),  # list-windows (only 1)
                Mock(returncode=0, stdout='', stderr=''),  # new-window
                Mock(returncode=0, stdout='', stderr=''),  # kill-window
            ]
            result = force_kill_window('@123')
            assert result is True
            # Verify new-window was called
            calls = [str(c) for c in mock_run.call_args_list]
            assert any('new-window' in c for c in calls)

    def test_returns_false_on_kill_failure(self):
        """When kill-window fails, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout='orchestrator\n', stderr=''),
                Mock(returncode=0, stdout='@1\n@2\n', stderr=''),
                Mock(returncode=1, stdout='', stderr='error'),  # kill-window fails
            ]
            result = force_kill_window('@123')
            assert result is False

    def test_returns_false_on_exception(self):
        """On exception, should return False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception('tmux error')
            result = force_kill_window('@123')
            assert result is False


class TestCleanupEphemeralWorkspace:
    """Tests for cleanup_ephemeral_workspace function."""

    def test_deletes_investigation_workspace(self, tmp_path):
        """Should delete workspace for investigation skill."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-investigation"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("test content")
        (workspace_dir / "SPAWN_CONTEXT.md").write_text("test context")

        agent = {
            'skill': 'investigation',
            'workspace': '.orch/workspace/test-investigation',
            'project_dir': str(tmp_path),
        }

        result = cleanup_ephemeral_workspace(agent)
        assert result is True
        assert not workspace_dir.exists()

    def test_keeps_non_ephemeral_workspace(self, tmp_path):
        """Should not delete workspace for feature-impl skill."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-feature"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("test content")

        agent = {
            'skill': 'feature-impl',
            'workspace': '.orch/workspace/test-feature',
            'project_dir': str(tmp_path),
        }

        result = cleanup_ephemeral_workspace(agent)
        assert result is False
        assert workspace_dir.exists()

    def test_returns_false_when_no_workspace(self):
        """Should return False when no workspace specified."""
        agent = {'skill': 'investigation', 'project_dir': '/tmp'}
        result = cleanup_ephemeral_workspace(agent)
        assert result is False

    def test_returns_false_when_workspace_not_exists(self, tmp_path):
        """Should return False when workspace directory doesn't exist."""
        agent = {
            'skill': 'investigation',
            'workspace': '.orch/workspace/nonexistent',
            'project_dir': str(tmp_path),
        }
        result = cleanup_ephemeral_workspace(agent)
        assert result is False

    def test_handles_skill_name_field(self, tmp_path):
        """Should check both 'skill' and 'skill_name' fields."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-investigation"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("test content")

        agent = {
            'skill_name': 'investigation',  # Using skill_name instead of skill
            'workspace': '.orch/workspace/test-investigation',
            'project_dir': str(tmp_path),
        }

        result = cleanup_ephemeral_workspace(agent)
        assert result is True
        assert not workspace_dir.exists()


class TestMarkAgentCompleted:
    """Tests for mark_agent_completed function."""

    def test_marks_agent_completed_with_timestamp(self):
        """Should update status and add completion timestamp."""
        mock_registry = Mock()
        agent = {'id': 'test-agent', 'status': 'active'}

        mark_agent_completed(agent, mock_registry)

        assert agent['status'] == 'completed'
        assert 'completion' in agent
        assert 'completed_at' in agent['completion']
        assert 'updated_at' in agent
        mock_registry.save.assert_called_once()

    def test_preserves_existing_completion_data(self):
        """Should preserve existing completion dict data."""
        mock_registry = Mock()
        agent = {
            'id': 'test-agent',
            'status': 'active',
            'completion': {'notes': 'previous notes'},
        }

        mark_agent_completed(agent, mock_registry)

        assert agent['completion']['notes'] == 'previous notes'
        assert 'completed_at' in agent['completion']

    def test_cleans_ephemeral_workspace(self, tmp_path):
        """Should clean ephemeral workspace and set flag."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-investigation"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("test")

        mock_registry = Mock()
        agent = {
            'id': 'test-agent',
            'status': 'active',
            'skill': 'investigation',
            'workspace': '.orch/workspace/test-investigation',
            'project_dir': str(tmp_path),
        }

        mark_agent_completed(agent, mock_registry)

        assert agent['completion']['workspace_cleaned'] is True
        assert not workspace_dir.exists()


class TestCleanupAgentAsync:
    """Tests for cleanup_agent_async function - main cleanup cascade."""

    def test_returns_false_when_agent_not_found(self, tmp_path):
        """When agent doesn't exist in registry, should return False."""
        registry_path = tmp_path / "registry.json"

        # AgentRegistry is imported inside cleanup_agent_async, so patch it there
        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.find.return_value = None

            result = cleanup_agent_async('nonexistent', registry_path)
            assert result is False

    def test_completes_immediately_without_window(self, tmp_path):
        """When agent has no window, should mark completed immediately."""
        registry_path = tmp_path / "registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'status': 'active',
                # No window_id
            }

            result = cleanup_agent_async('test-agent', registry_path)
            assert result is True
            mock_registry.save.assert_called()

    def test_uses_graceful_shutdown_first(self, tmp_path):
        """Should try graceful shutdown first."""
        registry_path = tmp_path / "registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'status': 'active',
                'window_id': '@123',
            }

            with patch('orch.cleanup_daemon.graceful_shutdown_window', return_value=True) as mock_graceful:
                result = cleanup_agent_async('test-agent', registry_path)
                assert result is True
                mock_graceful.assert_called_once_with('@123', wait_seconds=30)

    def test_tries_exit_command_after_graceful_fails(self, tmp_path):
        """When graceful shutdown fails, should try /exit."""
        registry_path = tmp_path / "registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'status': 'active',
                'window_id': '@123',
            }

            with patch('orch.cleanup_daemon.graceful_shutdown_window', return_value=False):
                with patch('orch.cleanup_daemon.send_exit_command', return_value=True) as mock_exit:
                    result = cleanup_agent_async('test-agent', registry_path)
                    assert result is True
                    mock_exit.assert_called_once_with('@123', wait_seconds=30)

    def test_tries_force_kill_after_exit_fails(self, tmp_path):
        """When /exit fails, should try force kill."""
        registry_path = tmp_path / "registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'status': 'active',
                'window_id': '@123',
            }

            with patch('orch.cleanup_daemon.graceful_shutdown_window', return_value=False):
                with patch('orch.cleanup_daemon.send_exit_command', return_value=False):
                    with patch('orch.cleanup_daemon.force_kill_window', return_value=True) as mock_kill:
                        result = cleanup_agent_async('test-agent', registry_path)
                        assert result is True
                        mock_kill.assert_called_once_with('@123')

    def test_marks_failed_when_all_strategies_fail(self, tmp_path):
        """When all strategies fail, should mark agent as failed."""
        registry_path = tmp_path / "registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            agent = {
                'id': 'test-agent',
                'status': 'active',
                'window_id': '@123',
            }
            mock_registry.find.return_value = agent

            with patch('orch.cleanup_daemon.graceful_shutdown_window', return_value=False):
                with patch('orch.cleanup_daemon.send_exit_command', return_value=False):
                    with patch('orch.cleanup_daemon.force_kill_window', return_value=False):
                        result = cleanup_agent_async('test-agent', registry_path)
                        assert result is False
                        assert agent['status'] == 'failed'
                        assert 'error' in agent['completion']


class TestMain:
    """Tests for main function (CLI entry point)."""

    def test_exits_with_code_2_on_wrong_args(self):
        """Should exit with code 2 when called with wrong number of args."""
        with patch('sys.argv', ['cleanup_daemon.py']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_exits_with_code_0_on_success(self, tmp_path):
        """Should exit with code 0 on successful cleanup."""
        registry_path = tmp_path / "registry.json"

        with patch('sys.argv', ['cleanup_daemon.py', 'test-agent', str(registry_path)]):
            with patch('orch.cleanup_daemon.cleanup_agent_async', return_value=True):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_exits_with_code_1_on_failure(self, tmp_path):
        """Should exit with code 1 on cleanup failure."""
        registry_path = tmp_path / "registry.json"

        with patch('sys.argv', ['cleanup_daemon.py', 'test-agent', str(registry_path)]):
            with patch('orch.cleanup_daemon.cleanup_agent_async', return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
