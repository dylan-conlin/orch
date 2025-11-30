"""Tests for orch attach command."""

import pytest
from orch.cli import cli

# Skip all attach command tests - command not yet implemented
# TODO: Implement orch attach command (see test_attach.py for expected behavior)
pytestmark = pytest.mark.skip(reason="orch attach command not yet implemented")


# cli_runner fixture is now provided by conftest.py


@pytest.fixture
def mock_registry(mocker):
    """Mock AgentRegistry with test agent data."""
    mock_reg = mocker.patch('orch.cli.AgentRegistry')
    instance = mock_reg.return_value

    # Mock agent data
    instance.find.return_value = {
        'id': 'test-agent-123',
        'task': 'Test task',
        'window': 'orchestrator:2',
        'window_id': '@30',
        'project_dir': '/Users/test/project',
        'workspace': '.orch/workspace/test-agent-123',
        'spawned_at': '2025-11-22T10:00:00',
        'status': 'active',
        'is_interactive': False
    }

    return instance


def test_attach_command_exists(cli_runner):
    """Test that orch attach command exists."""
    result = cli_runner.invoke(cli, ['attach', '--help'])

    # Command should exist (not show unknown command error)
    assert result.exit_code == 0
    assert 'attach' in result.output.lower()


def test_attach_requires_agent_id(cli_runner):
    """Test that attach command requires agent_id argument."""
    result = cli_runner.invoke(cli, ['attach'])

    # Should fail with missing argument error
    assert result.exit_code != 0
    assert 'Missing argument' in result.output or 'agent-id' in result.output.lower()


def test_attach_agent_not_found(cli_runner, mock_registry):
    """Test attach with non-existent agent ID."""
    mock_registry.find.return_value = None

    result = cli_runner.invoke(cli, ['attach', 'nonexistent-agent'])

    assert result.exit_code != 0
    assert 'not found' in result.output.lower()


def test_attach_finds_agent_and_switches(cli_runner, mock_registry, mocker):
    """Test attach command finds agent and switches window/session."""
    # Mock the helper functions we'll implement
    mock_find_ghostty_window = mocker.patch(
        'orch.cli.find_ghostty_window_for_session',
        return_value={'id': 29060, 'title': 'Mac ❐ orchestrator ● 2 🔬 worker: ...'}
    )
    mock_activate_window = mocker.patch('orch.cli.activate_ghostty_window', return_value=True)
    mock_switch_tmux = mocker.patch('orch.cli.switch_tmux_session', return_value=True)

    result = cli_runner.invoke(cli, ['attach', 'test-agent-123'])

    # Should succeed
    assert result.exit_code == 0

    # Should have looked up agent
    mock_registry.find.assert_called_once_with('test-agent-123')

    # Should have found Ghostty window for session
    mock_find_ghostty_window.assert_called_once()

    # Should have activated window via yabai
    mock_activate_window.assert_called_once_with(29060)

    # Should have switched tmux session
    mock_switch_tmux.assert_called_once()


def test_attach_graceful_degradation_no_yabai(cli_runner, mock_registry, mocker):
    """Test attach falls back to tmux-only when yabai not available."""
    # Mock yabai as unavailable
    mock_find_ghostty_window = mocker.patch(
        'orch.cli.find_ghostty_window_for_session',
        return_value=None  # yabai not running or can't find window
    )
    mock_switch_tmux = mocker.patch('orch.cli.switch_tmux_session', return_value=True)

    result = cli_runner.invoke(cli, ['attach', 'test-agent-123'])

    # Should still succeed with warning
    assert result.exit_code == 0
    assert 'yabai' in result.output.lower() or 'window' in result.output.lower()

    # Should still switch tmux session
    mock_switch_tmux.assert_called_once()
