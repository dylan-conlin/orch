"""
Tests for orch complete CLI command flag behavior.

Tests the CLI flag semantics:
- Default (no flags) should use async mode
- --sync flag should use synchronous blocking mode
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# cli_runner fixture is now provided by conftest.py


@pytest.fixture
def mock_registry(tmp_path):
    """Mock agent registry with a test agent."""
    with patch('orch.cli.AgentRegistry') as MockRegistry:
        mock_reg = MagicMock()
        mock_agent = {
            'id': 'test-agent',
            'project_dir': str(tmp_path),
            'workspace': str(tmp_path / '.orch' / 'workspace' / 'test-workspace'),
            'status': 'active'
        }
        mock_reg.find.return_value = mock_agent
        mock_reg.list_agents.return_value = [mock_agent]
        MockRegistry.return_value = mock_reg
        yield mock_reg


class TestCompleteDefaultBehavior:
    """Test that default complete behavior (no flags) uses async mode."""

    def test_complete_without_flags_uses_async_mode(self, cli_runner, mock_registry, tmp_path):
        """
        Test: orch complete <agent-id> (no flags) should use async mode by default.

        Expected behavior after flag inversion:
        - No flags = async mode (non-blocking)
        - Calls complete_agent_async() not complete_agent_work()
        """
        from orch.cli import cli

        # Mock complete functions
        with patch('orch.complete.complete_agent_async') as mock_async, \
             patch('orch.complete.complete_agent_work') as mock_sync:

            # Setup mocks
            mock_async.return_value = {
                'success': True,
                'async_mode': True,
                'daemon_pid': 12345,
                'verified': True
            }

            # Execute: Run complete command WITHOUT any flags
            result = cli_runner.invoke(cli, ['complete', 'test-agent'])

            # Assert: Should call async function (not sync)
            assert mock_async.called, "Expected complete_agent_async to be called"
            assert not mock_sync.called, "Expected complete_agent_work NOT to be called"

            # Assert: Output indicates async mode
            assert result.exit_code == 0
            assert 'background' in result.output.lower() or 'daemon' in result.output.lower()

    def test_complete_with_sync_flag_uses_sync_mode(self, cli_runner, mock_registry, tmp_path):
        """
        Test: orch complete --sync <agent-id> should use synchronous blocking mode.

        Expected behavior after flag inversion:
        - --sync flag = sync mode (blocking)
        - Calls complete_agent_work() not complete_agent_async()
        """
        from orch.cli import cli

        # Mock complete functions
        with patch('orch.complete.complete_agent_async') as mock_async, \
             patch('orch.complete.complete_agent_work') as mock_sync:

            # Setup mocks
            mock_sync.return_value = {
                'success': True,
                'async_mode': False,
                'verified': True
            }

            # Execute: Run complete command WITH --sync flag
            result = cli_runner.invoke(cli, ['complete', '--sync', 'test-agent'])

            # Assert: Should call sync function (not async)
            assert mock_sync.called, "Expected complete_agent_work to be called"
            assert not mock_async.called, "Expected complete_agent_async NOT to be called"

            # Assert: Output indicates sync mode (completed, not backgrounded)
            assert result.exit_code == 0
            assert 'completed successfully' in result.output.lower()


class TestBackwardCompatibility:
    """Test backward compatibility with old --async flag."""

    def test_old_async_flag_still_works(self, cli_runner, mock_registry, tmp_path):
        """
        Test: orch complete --async <agent-id> should still work (backward compat).

        The --async flag is deprecated but should still function.
        """
        from orch.cli import cli

        # Mock complete functions
        with patch('orch.complete.complete_agent_async') as mock_async, \
             patch('orch.complete.complete_agent_work') as mock_sync:

            # Setup mocks
            mock_async.return_value = {
                'success': True,
                'async_mode': True,
                'daemon_pid': 12345,
                'verified': True
            }

            # Execute: Run complete command WITH old --async flag
            result = cli_runner.invoke(cli, ['complete', '--async', 'test-agent'])

            # Assert: Should still call async function
            assert mock_async.called, "Expected complete_agent_async to be called (backward compat)"
            assert not mock_sync.called, "Expected complete_agent_work NOT to be called"

            # Assert: Command succeeds (backward compatibility)
            assert result.exit_code == 0


class TestHelpText:
    """Test that help text reflects new default behavior."""

    def test_complete_help_shows_sync_flag(self, cli_runner):
        """Test that --help shows --sync flag option."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['complete', '--help'])

        # Assert: Help text mentions --sync flag
        assert '--sync' in result.output
        assert result.exit_code == 0

    def test_help_text_describes_default_async_behavior(self, cli_runner):
        """Test that help text makes clear that async is the default."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['complete', '--help'])

        # Assert: Help text indicates synchronous is opt-in
        # (The help text for --sync should mention it's for blocking/synchronous behavior)
        assert '--sync' in result.output
        assert 'synchronous' in result.output.lower() or 'blocking' in result.output.lower()
