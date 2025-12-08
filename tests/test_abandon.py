"""Tests for orch abandon command."""

import pytest
from unittest.mock import Mock, patch


class TestAbandonCommand:
    """Tests for the abandon command."""

    def test_abandon_with_yes_short_flag_skips_confirmation(self, cli_runner):
        """Test that -y flag skips confirmation prompt."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'window_id': '@1000',
            'task': 'Test task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/test-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger'), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            mock_registry.abandon_agent.return_value = True
            MockRegistry.return_value = mock_registry

            # Run with -y flag - should NOT prompt for confirmation
            result = cli_runner.invoke(cli, ['abandon', 'test-agent', '-y'])

        # Should succeed without prompting
        assert result.exit_code == 0
        assert 'Cancelled' not in result.output

    def test_abandon_with_yes_long_flag_skips_confirmation(self, cli_runner):
        """Test that --yes flag skips confirmation prompt."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'window_id': '@1000',
            'task': 'Test task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/test-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger'), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            mock_registry.abandon_agent.return_value = True
            MockRegistry.return_value = mock_registry

            # Run with --yes flag - should NOT prompt for confirmation
            result = cli_runner.invoke(cli, ['abandon', 'test-agent', '--yes'])

        # Should succeed without prompting
        assert result.exit_code == 0
        assert 'Cancelled' not in result.output

    def test_abandon_without_flag_prompts_for_confirmation(self, cli_runner):
        """Test that without -y flag, confirmation is prompted."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'window_id': '@1000',
            'task': 'Test task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/test-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger'):

            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            # Run without -y flag and provide 'n' to cancel
            result = cli_runner.invoke(cli, ['abandon', 'test-agent'], input='n\n')

        # Should show cancelled because we said no
        assert 'Cancelled' in result.output

    def test_abandon_force_flag_still_works(self, cli_runner):
        """Test that --force flag still works for backward compatibility."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'window_id': '@1000',
            'task': 'Test task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/test-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger'), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            mock_registry.abandon_agent.return_value = True
            MockRegistry.return_value = mock_registry

            # Run with --force flag - should still work
            result = cli_runner.invoke(cli, ['abandon', 'test-agent', '--force'])

        # Should succeed without prompting
        assert result.exit_code == 0
        assert 'Cancelled' not in result.output
