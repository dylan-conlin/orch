"""
Tests for orch tail functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


# cli_runner fixture provided by conftest.py


class TestTailCommand:
    """Tests for the tail command."""

    def test_tail_captures_output_from_agent(self, cli_runner):
        """Test capturing output from an existing agent."""
        from orch.cli import cli

        # Mock registry to return an agent
        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'task': 'Test task',
            'status': 'active'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            # Mock subprocess.run to return captured output
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Line 1\nLine 2\nLine 3"

            with patch('subprocess.run', return_value=mock_result):
                result = cli_runner.invoke(cli, ['tail', 'test-agent'])

        # Should succeed and show output
        assert result.exit_code == 0
        assert 'Line 1' in result.output
        assert 'Line 2' in result.output
        assert 'Line 3' in result.output

    def test_tail_defaults_to_20_lines(self, cli_runner):
        """Test that tail defaults to 20 lines when no --lines specified."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'status': 'active'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                result = cli_runner.invoke(cli, ['tail', 'test-agent'])

        # Verify subprocess.run was called with -S -20 (20 lines from bottom)
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert '-S' in call_args
        assert '-20' in call_args

    def test_tail_respects_lines_option(self, cli_runner):
        """Test that --lines option is respected."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'status': 'active'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                result = cli_runner.invoke(cli, ['tail', 'test-agent', '--lines', '50'])

        # Verify subprocess.run was called with -S -50
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert '-S' in call_args
        assert '-50' in call_args

    def test_tail_agent_not_found(self, cli_runner):
        """Test error when agent doesn't exist in registry."""
        from orch.cli import cli

        # Mock registry to return None (agent not found)
        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = None
            mock_registry.list_active_agents.return_value = []
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['tail', 'nonexistent-agent'])

        # Should fail with error message
        assert result.exit_code != 0
        assert 'not found' in result.output.lower()

    def test_tail_tmux_command_failure(self, cli_runner):
        """Test error handling when tmux command fails."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'status': 'active'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            # Mock subprocess.run to fail
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "tmux error"

            with patch('subprocess.run', return_value=mock_result):
                result = cli_runner.invoke(cli, ['tail', 'test-agent'])

        # Should handle error gracefully
        assert result.exit_code != 0


class TestTailFunction:
    """Tests for the tail_agent_output function."""

    def test_basic_capture(self):
        """Test basic output capture functionality."""
        from orch.tail import tail_agent_output

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Captured output"

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            output = tail_agent_output(agent, lines=20)

        # Verify output returned
        assert output == "Captured output"

        # Verify correct tmux command
        call_args = mock_run.call_args[0][0]
        assert 'tmux' in call_args
        assert 'capture-pane' in call_args
        assert '-t' in call_args
        assert 'orchestrator:10' in call_args
        assert '-p' in call_args  # print to stdout
        assert '-S' in call_args
        assert '-20' in call_args

    def test_custom_line_count(self):
        """Test capturing custom number of lines."""
        from orch.tail import tail_agent_output

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            tail_agent_output(agent, lines=100)

        # Verify -S -100 in command
        call_args = mock_run.call_args[0][0]
        assert '-100' in call_args

    def test_tmux_failure_raises_error(self):
        """Test that tmux command failure raises appropriate error."""
        from orch.tail import tail_agent_output

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "window not found"

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError, match='Failed to capture'):
                tail_agent_output(agent, lines=20)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
