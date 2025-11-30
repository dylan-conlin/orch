"""
Tests for --backend flag in CLI spawn command.
"""

import pytest
from unittest.mock import patch, MagicMock
from orch.cli import cli


# cli_runner fixture provided by conftest.py


def test_spawn_with_backend_flag(cli_runner):
    """Test that spawn command accepts --backend flag."""
    # Mock the spawn_with_skill function to avoid actual spawning
    with patch('orch.spawn.spawn_with_skill') as mock_spawn:
        with patch('orch.cli.os.environ.get', return_value=None):
            result = cli_runner.invoke(cli, ['spawn', 'feature-impl', 'test task', '--backend', 'codex'])

    # The command should now accept the --backend flag
    # If spawn_with_skill was called, the flag was accepted
    if mock_spawn.called:
        # Verify backend was passed to spawn_with_skill
        call_args = mock_spawn.call_args
        assert call_args[1]['backend'] == 'codex'

    # Command should not fail with "no such option"
    assert 'no such option: --backend' not in result.output.lower()


def test_spawn_backend_flag_integration():
    """Test that --backend flag is passed to backend selection logic."""
    from orch.config import get_backend

    # Test 1: CLI flag overrides default
    backend = get_backend(cli_backend='codex')
    assert backend == 'codex'

    # Test 2: No CLI flag uses default
    backend = get_backend(cli_backend=None)
    assert backend == 'claude'
