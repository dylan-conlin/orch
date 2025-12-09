"""
Tests for orch status --include-completed flag.

By default, orch status should show only active agents.
The --include-completed flag enables showing completed agents.
"""

import pytest
from unittest.mock import Mock, patch


class TestStatusIncludeCompleted:
    """Tests for the --include-completed flag on orch status."""

    def test_status_defaults_to_active_only(self, cli_runner):
        """Test that status command defaults to showing only active agents (no completed)."""
        from orch.cli import cli

        # Mock agents - 2 active, 1 completed
        mock_active_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-1', 'status': 'active'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-2', 'status': 'active'},
        ]
        mock_completed_agents = [
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-3', 'status': 'completed'},
        ]

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_active_agents
                mock_registry.list_agents.return_value = mock_active_agents + mock_completed_agents
                MockRegistry.return_value = mock_registry

                mock_status = Mock(
                    priority='ok',
                    phase='Implementing',
                    alerts=[],
                    context_info=None,
                    recommendation=None,
                    completed_at=None,
                    age_str=None,
                    is_stale=False
                )
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    with patch('orch.monitoring_commands.get_git_root', return_value='/test/project'):
                        result = cli_runner.invoke(cli, ['status'])

        # Should NOT show completed agents by default
        assert result.exit_code == 0
        assert 'agent-1' in result.output
        assert 'agent-2' in result.output
        # Completed agent should NOT appear
        assert 'agent-3' not in result.output
        # Should NOT show "COMPLETED" sections
        assert 'COMPLETED THIS SESSION' not in result.output
        assert 'COMPLETED EARLIER' not in result.output

    def test_status_include_completed_shows_all(self, cli_runner):
        """Test that --include-completed flag shows completed agents."""
        from orch.cli import cli
        from datetime import datetime

        # Mock agents - 2 active, 1 completed
        mock_active_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-1', 'status': 'active'},
        ]
        mock_completed_agents = [
            {'id': 'agent-completed', 'window': 'orchestrator:2', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-2', 'status': 'completed', 'completed_at': '2024-01-01T12:00:00'},
        ]

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_active_agents
                mock_registry.list_agents.return_value = mock_active_agents + mock_completed_agents
                MockRegistry.return_value = mock_registry

                def mock_status_for_agent(agent, **kwargs):
                    if agent.get('status') == 'completed':
                        return Mock(
                            priority='ok',
                            phase='Complete',
                            alerts=[],
                            context_info=None,
                            recommendation='Run: orch complete agent-completed',
                            completed_at=datetime(2024, 1, 1, 12, 0, 0),
                            age_str='5h ago',
                            is_stale=False
                        )
                    return Mock(
                        priority='ok',
                        phase='Implementing',
                        alerts=[],
                        context_info=None,
                        recommendation=None,
                        completed_at=None,
                        age_str=None,
                        is_stale=False
                    )

                with patch('orch.monitoring_commands.check_agent_status', side_effect=mock_status_for_agent):
                    with patch('orch.monitoring_commands.get_git_root', return_value='/test/project'):
                        # Mock session tracker - import happens inside the function from orch.session
                        with patch('orch.session.SessionTracker') as MockTracker:
                            mock_tracker = Mock()
                            mock_tracker.get_session_start.return_value = datetime(2024, 1, 1, 0, 0, 0)
                            MockTracker.return_value = mock_tracker
                            result = cli_runner.invoke(cli, ['status', '--include-completed'])

        # Should show both active and completed agents
        assert result.exit_code == 0
        assert 'agent-1' in result.output
        assert 'agent-completed' in result.output
        # Should show completed section
        assert 'COMPLETED' in result.output

    def test_status_include_completed_with_json(self, cli_runner):
        """Test that --include-completed works with JSON output."""
        from orch.cli import cli
        import json

        # Mock agents
        mock_active_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-1', 'status': 'active', 'spawned_at': '2024-01-01T00:00:00'},
        ]
        mock_completed_agents = [
            {'id': 'agent-completed', 'window': 'orchestrator:2', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-2', 'status': 'completed', 'spawned_at': '2024-01-01T00:00:00'},
        ]

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_active_agents
                mock_registry.list_agents.return_value = mock_active_agents + mock_completed_agents
                MockRegistry.return_value = mock_registry

                mock_status = Mock(priority='ok', phase='Implementing', alerts=[], context_info=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    with patch('orch.monitoring_commands.get_git_root', return_value='/test/project'):
                        # Without --include-completed: only active
                        result_active_only = cli_runner.invoke(cli, ['status', '--json'])
                        # With --include-completed: all
                        result_with_completed = cli_runner.invoke(cli, ['status', '--include-completed', '--json'])

        # Without flag: only 1 agent
        assert result_active_only.exit_code == 0
        output_active = json.loads(result_active_only.output)
        assert len(output_active['agents']) == 1
        assert output_active['agents'][0]['agent_id'] == 'agent-1'

        # With flag: 2 agents
        assert result_with_completed.exit_code == 0
        output_all = json.loads(result_with_completed.output)
        assert len(output_all['agents']) == 2

    def test_status_help_shows_include_completed_option(self, cli_runner):
        """Test that --include-completed option appears in help text."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['status', '--help'])

        assert result.exit_code == 0
        assert '--include-completed' in result.output

    def test_status_no_completed_message_when_empty(self, cli_runner):
        """Test behavior when there are no completed agents to show."""
        from orch.cli import cli

        # Only active agents, no completed
        mock_active_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/test/project', 'workspace': '.orch/workspace/test-1', 'status': 'active'},
        ]

        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_active_agents
                mock_registry.list_agents.return_value = mock_active_agents  # No completed
                MockRegistry.return_value = mock_registry

                mock_status = Mock(
                    priority='ok',
                    phase='Implementing',
                    alerts=[],
                    context_info=None,
                    recommendation=None,
                    completed_at=None,
                    age_str=None,
                    is_stale=False
                )
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    with patch('orch.monitoring_commands.get_git_root', return_value='/test/project'):
                        result = cli_runner.invoke(cli, ['status', '--include-completed'])

        # Should work without errors when no completed agents
        assert result.exit_code == 0
        assert 'agent-1' in result.output
        # Should NOT show empty "COMPLETED" sections
        assert 'COMPLETED THIS SESSION (0)' not in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
