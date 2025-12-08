"""
Tests for orch status logging functionality.
"""

import pytest
from unittest.mock import Mock, patch, mock_open, call
import time


# cli_runner fixture provided by conftest.py


class TestStatusLogging:
    """Tests for status command logging."""

    def test_status_logs_start_event(self, cli_runner):
        """Test that status command logs start event with flags."""
        from orch.cli import cli

        mock_log_data = []

        def capture_log_event(command, message, data, level="INFO"):
            """Capture log calls."""
            mock_log_data.append({
                'command': command,
                'message': message,
                'data': data,
                'level': level
            })

        # Mock OrchLogger (now in monitoring_commands module)
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock(side_effect=lambda cmd, data: capture_log_event(cmd, "Starting command", data, "INFO"))
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry and tmux checks (now in monitoring_commands module)
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = []
                MockRegistry.return_value = mock_registry

                result = cli_runner.invoke(cli, ['status', '--compact', '--context'])

        # Verify log_command_start was called
        assert mock_logger.log_command_start.called

        # Check the logged data
        assert len(mock_log_data) > 0
        start_log = mock_log_data[0]
        assert start_log['command'] == 'status'
        assert 'compact' in start_log['data']
        assert start_log['data']['compact'] is True
        assert 'check_context' in start_log['data']
        assert start_log['data']['check_context'] is True

    def test_status_logs_reconciliation_events(self, cli_runner):
        """Test that status command logs reconciliation events."""
        from orch.cli import cli

        mock_log_data = []

        def capture_log_event(command, message, data, level="INFO"):
            """Capture log calls."""
            mock_log_data.append({
                'command': command,
                'message': message,
                'data': data,
                'level': level
            })

        # Mock OrchLogger (now in monitoring_commands module)
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_event = Mock(side_effect=capture_log_event)
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry with reconciliation that adds/removes agents
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = []

                # Simulate reconciliation finding changes
                def mock_reconcile(active_windows):
                    # Simulate logging during reconciliation
                    mock_logger.log_event("status", "Reconciliation: 2 stale agents removed",
                                         {"removed": 2}, level="INFO")

                mock_registry.reconcile = mock_reconcile
                MockRegistry.return_value = mock_registry

                # Mock tmux availability (now in monitoring_commands module)
                with patch('orch.monitoring_commands.is_tmux_available', return_value=True):
                    with patch('orch.monitoring_commands.find_session', return_value=Mock()):
                        with patch('orch.monitoring_commands.list_windows', return_value=[]):
                            result = cli_runner.invoke(cli, ['status'])

        # Check reconciliation was logged
        reconciliation_logs = [log for log in mock_log_data if 'Reconciliation' in log['message']]
        assert len(reconciliation_logs) > 0

    def test_status_logs_complete_with_summary(self, cli_runner):
        """Test that status command logs completion with agent counts."""
        from orch.cli import cli
        import os

        # Mock agents with different priorities
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-2'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-3'}
        ]

        # Mock status objects with different priorities
        mock_statuses = [
            Mock(priority='critical', phase='Planning', alerts=[{'type': 'blocked', 'message': 'Blocked'}], context_info=None, recommendation=None),
            Mock(priority='warning', phase='Implementing', alerts=[{'type': 'warning', 'message': 'Slow'}], context_info=None, recommendation=None),
            Mock(priority='ok', phase='Implementing', alerts=[], context_info=None, recommendation=None)
        ]

        # Mock OrchLogger (now in monitoring_commands module)
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry (now in monitoring_commands module)
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                # Phase 2.5: Also mock list_agents for completed agents
                mock_registry.list_agents.return_value = mock_agents  # No completed agents in this test
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status (now in monitoring_commands module)
                with patch('orch.monitoring_commands.check_agent_status', side_effect=mock_statuses):
                    # Mock os.getcwd() to match agent project_dir
                    with patch('os.getcwd', return_value='/test/project'):
                        result = cli_runner.invoke(cli, ['status'])

        # Verify log_command_complete was called with summary
        assert mock_logger.log_command_complete.called

        # Extract the call arguments
        call_args = mock_logger.log_command_complete.call_args
        command = call_args[0][0]
        duration_ms = call_args[0][1]
        data = call_args[0][2]

        assert command == 'status'
        assert isinstance(duration_ms, int)
        assert duration_ms >= 0

        # Check summary data includes counts
        assert 'total_agents' in data
        assert data['total_agents'] == 3
        assert 'critical' in data
        assert data['critical'] == 1
        assert 'warnings' in data
        assert data['warnings'] == 1
        assert 'working' in data
        assert data['working'] == 1

    def test_status_logs_with_no_agents(self, cli_runner):
        """Test that status command logs correctly when no agents found."""
        from orch.cli import cli

        # Mock OrchLogger (now in monitoring_commands module)
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry with no agents (now in monitoring_commands module)
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = []
                # Phase 2.5: Also mock list_agents for completed agents
                mock_registry.list_agents.return_value = []
                MockRegistry.return_value = mock_registry

                result = cli_runner.invoke(cli, ['status'])

        # Verify logging happened
        assert mock_logger.log_command_start.called
        assert mock_logger.log_command_complete.called

        # Check data shows zero agents
        call_args = mock_logger.log_command_complete.call_args
        data = call_args[0][2]
        assert data['total_agents'] == 0


class TestCrossSessionReconciliation:
    """Tests for cross-session reconciliation (bug fix for orch-cli-iej).

    Agents are spawned in workers-* sessions but status was only checking
    the orchestrator session, causing agents to be incorrectly marked as completed.
    """

    def test_reconcile_checks_all_agent_sessions(self, cli_runner):
        """Test that status reconciles across all sessions where agents exist."""
        from orch.cli import cli

        # Agent in workers-price-watch session (not orchestrator)
        mock_agents = [
            {
                'id': 'feat-scraper-08dec',
                'window': 'workers-price-watch:5',
                'window_id': '@1234',  # This window ID should be found
                'project_dir': '/test/project',
                'workspace': '.orch/workspace/feat-scraper-08dec',
                'status': 'active'
            }
        ]

        reconcile_calls = []

        def mock_reconcile(active_windows):
            """Capture what windows are passed to reconcile."""
            reconcile_calls.append(list(active_windows))

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = mock_agents
                mock_registry.reconcile = mock_reconcile
                mock_registry.reconcile_opencode = Mock()
                MockRegistry.return_value = mock_registry

                with patch('orch.monitoring_commands.is_tmux_available', return_value=True):
                    # Mock session default to 'orchestrator'
                    with patch('orch.config.get_tmux_session_default', return_value='orchestrator'):
                        # Mock find_session to return sessions for both orchestrator and workers-price-watch
                        def mock_find_session(session_name):
                            return Mock()  # Session exists

                        # Mock list_windows to return windows for each session
                        def mock_list_windows(session_name):
                            if session_name == 'workers-price-watch':
                                return [{'index': '5', 'name': 'feat-scraper-08dec', 'id': '@1234'}]
                            elif session_name == 'orchestrator':
                                return [{'index': '1', 'name': 'main', 'id': '@100'}]
                            return []

                        with patch('orch.monitoring_commands.find_session', side_effect=mock_find_session):
                            with patch('orch.monitoring_commands.list_windows', side_effect=mock_list_windows):
                                with patch('orch.monitoring_commands.check_agent_status') as mock_check:
                                    mock_check.return_value = Mock(
                                        priority='ok',
                                        phase='Implementing',
                                        alerts=[],
                                        context_info=None,
                                        recommendation=None,
                                        completed_at=None,
                                        age_str=None,
                                        is_stale=False
                                    )
                                    result = cli_runner.invoke(cli, ['status'])

        # Verify reconcile was called with window IDs from BOTH sessions
        assert len(reconcile_calls) == 1
        active_windows = reconcile_calls[0]
        # Should include @1234 from workers-price-watch AND @100 from orchestrator
        assert '@1234' in active_windows, "Should include worker session window"
        assert '@100' in active_windows, "Should include orchestrator session window"

    def test_agent_in_different_session_not_marked_completed(self, cli_runner):
        """Test that an agent in workers-* session stays active when its window exists."""
        from orch.cli import cli

        # Agent in workers-price-watch session
        mock_agents = [
            {
                'id': 'feat-scraper-08dec',
                'window': 'workers-price-watch:5',
                'window_id': '@1234',
                'project_dir': '/test/project',
                'workspace': '.orch/workspace/feat-scraper-08dec',
                'status': 'active'
            }
        ]

        agents_marked_completed = []

        def mock_reconcile(active_windows):
            """Simulate reconcile - if @1234 is in active_windows, agent stays active."""
            if '@1234' not in active_windows:
                agents_marked_completed.append('feat-scraper-08dec')

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = mock_agents
                mock_registry.reconcile = mock_reconcile
                mock_registry.reconcile_opencode = Mock()
                MockRegistry.return_value = mock_registry

                with patch('orch.monitoring_commands.is_tmux_available', return_value=True):
                    def mock_find_session(session_name):
                        return Mock()

                    def mock_list_windows(session_name):
                        if session_name == 'workers-price-watch':
                            # Window @1234 EXISTS in workers-price-watch
                            return [{'index': '5', 'name': 'feat-scraper-08dec', 'id': '@1234'}]
                        return []

                    with patch('orch.monitoring_commands.find_session', side_effect=mock_find_session):
                        with patch('orch.monitoring_commands.list_windows', side_effect=mock_list_windows):
                            with patch('orch.monitoring_commands.check_agent_status') as mock_check:
                                mock_check.return_value = Mock(
                                    priority='ok',
                                    phase='Implementing',
                                    alerts=[],
                                    context_info=None,
                                    recommendation=None,
                                    completed_at=None,
                                    age_str=None,
                                    is_stale=False
                                )
                                result = cli_runner.invoke(cli, ['status'])

        # Agent should NOT be marked as completed since its window exists
        assert len(agents_marked_completed) == 0, "Agent should not be marked completed when its window exists"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
