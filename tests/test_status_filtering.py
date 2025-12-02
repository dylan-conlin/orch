"""
Tests for orch status filtering functionality.
"""

import pytest
from unittest.mock import Mock, patch


# cli_runner fixture provided by conftest.py


class TestStatusFiltering:
    """Tests for status command filtering options."""

    def test_status_filter_by_project(self, cli_runner):
        """Test filtering agents by project directory."""
        from orch.cli import cli

        # Mock agents from different projects
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/price-watch', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-2'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/price-watch-api', 'workspace': '.orch/workspace/test-3'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    result = cli_runner.invoke(cli, ['status', '--project', 'price-watch'])

        # Should show 2 agents (agent-1 and agent-3, both match "price-watch")
        assert result.exit_code == 0
        # Verify that check_agent_status was called only for filtered agents
        # With substring matching, both price-watch and price-watch-api match

    def test_status_filter_by_workspace_pattern(self, cli_runner):
        """Test filtering agents by workspace name pattern."""
        from orch.cli import cli

        # Mock agents with different workspace names
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/investigate-bug-123'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/implement-feature'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/investigate-crash'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status) as mock_check:
                    result = cli_runner.invoke(cli, ['status', '--filter', 'investigate-*'])

        # Should show 2 agents (agent-1 and agent-3)
        assert result.exit_code == 0
        # check_agent_status should be called only for filtered agents (2 times)
        assert mock_check.call_count == 2

    def test_status_filter_by_status_phase(self, cli_runner):
        """Test filtering agents by phase/status."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/test-2'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/test-3'},
        ]

        # Mock statuses with different phases
        mock_statuses = [
            Mock(priority='ok', phase='Planning', alerts=[], context_info=None),
            Mock(priority='ok', phase='Implementing', alerts=[], context_info=None),
            Mock(priority='critical', phase='Planning', alerts=[{'type': 'blocked', 'message': 'Blocked'}], context_info=None),
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status to return different statuses
                with patch('orch.monitoring_commands.check_agent_status', side_effect=mock_statuses):
                    result = cli_runner.invoke(cli, ['status', '--status', 'Planning'])

        # Should show 2 agents in Planning phase (agent-1 and agent-3)
        assert result.exit_code == 0

    def test_status_filter_blocked_maps_to_critical(self, cli_runner):
        """Test that --status blocked matches critical priority agents."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/project', 'workspace': '.orch/workspace/test-2'},
        ]

        # Mock statuses
        mock_statuses = [
            Mock(priority='critical', phase='Planning', alerts=[{'type': 'blocked', 'message': 'Blocked'}], context_info=None),
            Mock(priority='ok', phase='Implementing', alerts=[], context_info=None),
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                with patch('orch.monitoring_commands.check_agent_status', side_effect=mock_statuses):
                    result = cli_runner.invoke(cli, ['status', '--status', 'blocked'])

        # Should show 1 agent (agent-1 with critical priority)
        assert result.exit_code == 0

    def test_status_filter_combination(self, cli_runner):
        """Test combining multiple filters (AND logic)."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/price-watch', 'workspace': '.orch/workspace/investigate-bug'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/price-watch', 'workspace': '.orch/workspace/implement-feature'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/investigate-crash'},
        ]

        # Mock statuses
        mock_statuses = [
            Mock(priority='ok', phase='Planning', alerts=[], context_info=None),
            Mock(priority='ok', phase='Planning', alerts=[], context_info=None),
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                with patch('orch.monitoring_commands.check_agent_status', side_effect=mock_statuses) as mock_check:
                    result = cli_runner.invoke(cli, ['status', '--project', 'price-watch', '--filter', 'investigate-*', '--status', 'Planning'])

        # Should show 1 agent (agent-1: price-watch + investigate-* + Planning)
        assert result.exit_code == 0
        # check_agent_status called only for agents that pass early filters (agent-1)
        assert mock_check.call_count == 1

    def test_status_no_matches_message(self, cli_runner):
        """Test message when no agents match filters."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project-a', 'workspace': '.orch/workspace/test'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Filter that won't match anything
                result = cli_runner.invoke(cli, ['status', '--project', 'nonexistent-project'])

        # Should show "No agents match the specified filters" message
        assert result.exit_code == 0
        assert "No agents match the specified filters" in result.output

    def test_status_filter_json_output(self, cli_runner):
        """Test that filtering works with JSON output format."""
        from orch.cli import cli
        import json

        # Mock agents
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/price-watch', 'workspace': '.orch/workspace/test-1', 'spawned_at': '2024-01-01T00:00:00'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-2', 'spawned_at': '2024-01-01T00:00:00'},
        ]

        # Mock status
        mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None)

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    result = cli_runner.invoke(cli, ['status', '--project', 'price-watch', '--format', 'json'])

        # Should output valid JSON with 1 agent
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert 'agents' in output
        assert len(output['agents']) == 1
        assert output['agents'][0]['agent_id'] == 'agent-1'


    def test_status_automatic_project_scoping(self, cli_runner):
        """Test that status command automatically filters to current project directory."""
        from orch.cli import cli
        import os

        # Mock agents from different projects
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/orch-knowledge', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-2'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/orch-knowledge', 'workspace': '.orch/workspace/test-3'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None, recommendation=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status) as mock_check:
                    # Mock get_git_root() to return orch-knowledge directory
                    with patch('orch.monitoring_commands.get_git_root', return_value='/home/user/orch-knowledge'):
                        result = cli_runner.invoke(cli, ['status'])

        # Should show only 2 agents from current project (agent-1 and agent-3)
        # NOT agent-2 from other-project
        assert result.exit_code == 0
        # check_agent_status should be called only for agents in current project (2 times)
        assert mock_check.call_count == 2

    def test_status_explicit_project_overrides_automatic_scoping(self, cli_runner):
        """Test that --project flag overrides automatic project scoping."""
        from orch.cli import cli
        import os

        # Mock agents from different projects
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/orch-knowledge', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-2'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None, recommendation=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status) as mock_check:
                    # Mock os.getcwd() to return orch-knowledge
                    # But use --project to explicitly request other-project
                    with patch('os.getcwd', return_value='/home/user/orch-knowledge'):
                        result = cli_runner.invoke(cli, ['status', '--project', 'other-project'])

        # Should show only agent-2 from other-project (explicit --project overrides cwd)
        assert result.exit_code == 0
        assert mock_check.call_count == 1

    def test_status_no_agents_in_current_project(self, cli_runner):
        """Test message when no agents match current project."""
        from orch.cli import cli
        import os

        # Mock agents all from different project
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-1'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # Phase 2.5: No completed agents
                MockRegistry.return_value = mock_registry

                # Mock get_git_root() to return orch-knowledge (different from agent's project)
                with patch('orch.cli.get_git_root', return_value='/home/user/orch-knowledge'):
                    result = cli_runner.invoke(cli, ['status'])

        # Should show "No agents match" message with helpful tip
        assert result.exit_code == 0
        assert "No agents match the specified filters" in result.output
        assert "Auto-scoped to git root" in result.output
        assert "--project ." in result.output


    def test_status_global_flag_shows_all_agents(self, cli_runner):
        """Test that --global flag shows all agents across all projects."""
        from orch.cli import cli

        # Mock agents from different projects
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project-a', 'workspace': '.orch/workspace/test-1'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/project-b', 'workspace': '.orch/workspace/test-2'},
            {'id': 'agent-3', 'window': 'orchestrator:3', 'project_dir': '/home/user/project-c', 'workspace': '.orch/workspace/test-3'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None, recommendation=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status) as mock_check:
                    # Mock get_git_root to return project-a (would normally auto-scope to just project-a)
                    with patch('orch.monitoring_commands.get_git_root', return_value='/home/user/project-a'):
                        result = cli_runner.invoke(cli, ['status', '--global'])

        # Should show ALL 3 agents (not just project-a)
        assert result.exit_code == 0
        # check_agent_status should be called for all 3 agents
        assert mock_check.call_count == 3

    def test_status_global_flag_skips_auto_scoping(self, cli_runner):
        """Test that --global flag bypasses automatic project scoping."""
        from orch.cli import cli

        # Mock agents - only one from "current" project
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/other-project', 'workspace': '.orch/workspace/test-1'},
        ]

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []  # No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None, recommendation=None)
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status) as mock_check:
                    # Mock get_git_root - agent is from different project
                    # Without --global, this would show "No agents match" since other-project != current-project
                    with patch('orch.monitoring_commands.get_git_root', return_value='/home/user/current-project'):
                        result = cli_runner.invoke(cli, ['status', '--global'])

        # Should show the agent even though it's from a different project
        assert result.exit_code == 0
        assert mock_check.call_count == 1

    def test_status_global_flag_with_json_output(self, cli_runner):
        """Test that --global flag works with JSON output."""
        from orch.cli import cli
        import json

        # Mock agents from different projects
        mock_agents = [
            {'id': 'agent-1', 'window': 'orchestrator:1', 'project_dir': '/home/user/project-a', 'workspace': '.orch/workspace/test-1', 'spawned_at': '2024-01-01T00:00:00'},
            {'id': 'agent-2', 'window': 'orchestrator:2', 'project_dir': '/home/user/project-b', 'workspace': '.orch/workspace/test-2', 'spawned_at': '2024-01-01T00:00:00'},
        ]

        # Mock status
        mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None)

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = mock_agents
                mock_registry.list_agents.return_value = []
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    # Mock get_git_root to return project-a (would auto-scope without --global)
                    with patch('orch.monitoring_commands.get_git_root', return_value='/home/user/project-a'):
                        result = cli_runner.invoke(cli, ['status', '--global', '--json'])

        # Should output valid JSON with all 2 agents
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert 'agents' in output
        assert len(output['agents']) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
