"""
Tests for orch send functionality.
"""

import pytest
from unittest.mock import Mock, patch, call
from pathlib import Path


# cli_runner fixture provided by conftest.py


class TestSendCommand:
    """Tests for the send command."""

    def test_send_message_to_existing_agent(self, cli_runner):
        """Test sending a message to an existing agent."""
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

            # Mock tmux window
            mock_window = Mock()

            with patch('orch.tmux_utils.get_window_by_target', return_value=mock_window):
                with patch('subprocess.run') as mock_run:
                    result = cli_runner.invoke(cli, ['send', 'test-agent', 'Hello agent'])

        # Test should pass when implementation exists
        assert result.exit_code == 0
        assert 'Message sent' in result.output or 'Sent' in result.output

        # Verify subprocess.run was called twice (message + Enter)
        assert mock_run.call_count == 2

    def test_send_message_agent_not_found(self, cli_runner):
        """Test error when agent doesn't exist in registry."""
        from orch.cli import cli

        # Mock registry to return None (agent not found)
        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = None
            mock_registry.list_active_agents.return_value = []
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['send', 'nonexistent-agent', 'Hello'])

        # Should fail with error message
        assert result.exit_code != 0
        assert 'not found' in result.output.lower()

    def test_send_message_with_auto_enter(self):
        """Test that Enter is automatically appended."""
        from orch.send import send_message_to_agent

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5'
        }

        mock_window = Mock()

        with patch('orch.send.get_window_by_target', return_value=mock_window):
            with patch('subprocess.run') as mock_run:
                send_message_to_agent(mock_agent, 'Test message')

        # Verify subprocess.run was called twice (message + Enter)
        assert mock_run.call_count == 2
        # First call: send message
        assert 'Test message' in str(mock_run.call_args_list[0])
        # Second call: send Enter
        assert 'Enter' in str(mock_run.call_args_list[1])

    def test_send_message_tmux_window_not_found(self):
        """Test error when tmux window doesn't exist."""
        from orch.send import send_message_to_agent

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5'
        }

        # Mock get_window_by_target to return None
        with patch('orch.send.get_window_by_target', return_value=None):
            with pytest.raises(RuntimeError, match='Window.*not found'):
                send_message_to_agent(mock_agent, 'Test message')


class TestSendMessageFunction:
    """Tests for the send_message_to_agent function."""

    def test_basic_message_send(self):
        """Test basic message sending functionality."""
        from orch.send import send_message_to_agent

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_window = Mock()

        with patch('orch.send.get_window_by_target', return_value=mock_window):
            with patch('subprocess.run') as mock_run:
                send_message_to_agent(agent, 'Hello from orchestrator')

        # Verify subprocess.run was called twice
        assert mock_run.call_count == 2
        # Verify message was sent
        first_call = mock_run.call_args_list[0][0][0]
        assert 'Hello from orchestrator' in first_call

    def test_message_with_special_characters(self):
        """Test sending message with special characters."""
        from orch.send import send_message_to_agent

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_window = Mock()
        message = 'Check file: ~/test/path with spaces.txt'

        with patch('orch.send.get_window_by_target', return_value=mock_window):
            with patch('subprocess.run') as mock_run:
                send_message_to_agent(agent, message)

        # Verify message was passed through
        assert mock_run.call_count == 2
        first_call = mock_run.call_args_list[0][0][0]
        assert message in first_call

    def test_multiline_message(self):
        """Test sending multiline message."""
        from orch.send import send_message_to_agent

        agent = {
            'id': 'agent-1',
            'window': 'orchestrator:10'
        }

        mock_window = Mock()
        message = 'Line 1\nLine 2\nLine 3'

        with patch('orch.send.get_window_by_target', return_value=mock_window):
            with patch('subprocess.run') as mock_run:
                send_message_to_agent(agent, message)

        # Verify multiline message was sent
        assert mock_run.call_count == 2
        first_call = mock_run.call_args_list[0][0][0]
        assert message in first_call


class TestSendLogging:
    """Tests for send command logging."""

    def test_send_logs_success(self, cli_runner):
        """Test that send command logs successful message send."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'task': 'Test task'
        }

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_event = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.find.return_value = mock_agent
                MockRegistry.return_value = mock_registry

                # Mock send_message_to_agent function
                with patch('orch.send.send_message_to_agent'):
                    result = cli_runner.invoke(cli, ['send', 'test-agent', 'Hello agent'])

        # Verify logging happened
        assert mock_logger.log_event.called

        # Check logged data
        call_args = mock_logger.log_event.call_args
        command = call_args[0][0]
        message = call_args[0][1]
        data = call_args[0][2]

        assert command == 'send'
        assert 'test-agent' in data['agent_id']
        assert 'message_length' in data
        assert data['message_length'] == len('Hello agent')

    def test_send_logs_failure(self, cli_runner):
        """Test that send command logs failures."""
        from orch.cli import cli

        # Mock OrchLogger
        with patch('orch.monitoring_commands.OrchLogger') as MockLogger:
            mock_logger = Mock()
            mock_logger.log_error = Mock()
            MockLogger.return_value = mock_logger

            # Mock registry to return None (agent not found)
            with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
                mock_registry = Mock()
                mock_registry.find.return_value = None
                MockRegistry.return_value = mock_registry

                result = cli_runner.invoke(cli, ['send', 'nonexistent', 'Hello'])

        # Verify error logging happened
        assert mock_logger.log_error.called

        call_args = mock_logger.log_error.call_args
        command = call_args[0][0]
        message = call_args[0][1]
        data = call_args[0][2]

        assert command == 'send'
        assert 'nonexistent' in data['agent_id']
        assert 'reason' in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
