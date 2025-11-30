"""
Tests for orch status --json flag functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch


class TestStatusJsonFlag:
    """Tests for --json shorthand flag on status command."""

    def test_status_json_flag_outputs_json(self, cli_runner):
        """Test that --json flag produces JSON output."""
        from orch.cli import cli

        # Mock agents - using a project path we'll match with get_git_root mock
        mock_agents = [
            {
                'id': 'agent-1',
                'window': 'orchestrator:1',
                'project_dir': '/home/user/project',
                'workspace': '.orch/workspace/test-1',
                'spawned_at': '2024-01-01T00:00:00'
            },
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
                mock_registry.list_agents.return_value = []  # No completed agents
                MockRegistry.return_value = mock_registry

                # Mock check_agent_status
                with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                    # Mock get_git_root to match agent's project_dir (auto-scoping will include agent)
                    with patch('orch.monitoring_commands.get_git_root', return_value='/home/user/project'):
                        result = cli_runner.invoke(cli, ['status', '--json'])

        # Should output valid JSON
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert 'agents' in output
        assert 'schema_version' in output
        assert len(output['agents']) == 1
        assert output['agents'][0]['agent_id'] == 'agent-1'

    def test_status_json_flag_equivalent_to_format_json(self, cli_runner):
        """Test that --json flag produces same output as --format json."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {
                'id': 'agent-1',
                'window': 'orchestrator:1',
                'project_dir': '/home/user/project',
                'workspace': '.orch/workspace/test-1',
                'spawned_at': '2024-01-01T00:00:00'
            },
        ]

        # Mock status
        mock_status = Mock(priority='ok', phase='Planning', alerts=[], context_info=None)

        def run_with_flag(flag_args):
            with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
                mock_logger = Mock()
                mock_logger.log_command_start = Mock()
                mock_logger.log_command_complete = Mock()
                MockLogger.return_value = mock_logger

                with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                    mock_registry = Mock()
                    mock_registry.list_active_agents.return_value = mock_agents
                    mock_registry.list_agents.return_value = []
                    MockRegistry.return_value = mock_registry

                    with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
                        return cli_runner.invoke(cli, ['status'] + flag_args)

        # Run with --json flag
        result_json_flag = run_with_flag(['--json'])

        # Run with --format json
        result_format_json = run_with_flag(['--format', 'json'])

        # Both should produce valid JSON with same structure
        assert result_json_flag.exit_code == 0
        assert result_format_json.exit_code == 0

        output_json_flag = json.loads(result_json_flag.output)
        output_format_json = json.loads(result_format_json.output)

        # Same keys and agent count
        assert output_json_flag.keys() == output_format_json.keys()
        assert len(output_json_flag['agents']) == len(output_format_json['agents'])

    def test_status_json_flag_overrides_format_human(self, cli_runner):
        """Test that --json flag takes precedence over --format human."""
        from orch.cli import cli

        # Mock agents
        mock_agents = [
            {
                'id': 'agent-1',
                'window': 'orchestrator:1',
                'project_dir': '/home/user/project',
                'workspace': '.orch/workspace/test-1',
                'spawned_at': '2024-01-01T00:00:00'
            },
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
                    # Use both --json and --format human - --json should win
                    result = cli_runner.invoke(cli, ['status', '--json', '--format', 'human'])

        # Should still output JSON because --json takes precedence
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert 'agents' in output
        assert 'schema_version' in output

    def test_status_json_flag_no_agents(self, cli_runner):
        """Test --json flag with no agents returns empty agents array."""
        from orch.cli import cli

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_command_start = Mock()
            mock_logger.log_command_complete = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry with no agents
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.list_active_agents.return_value = []
                mock_registry.list_agents.return_value = []
                MockRegistry.return_value = mock_registry

                result = cli_runner.invoke(cli, ['status', '--json'])

        # Should output valid JSON with empty agents array
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert 'agents' in output
        assert output['agents'] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
