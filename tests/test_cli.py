"""Tests for CLI commands."""

import pytest
import subprocess
from pathlib import Path


# cli_runner fixture is now provided by conftest.py


def test_flag_command(cli_runner, tmp_path, mocker):
    """Test orch flag CLI command."""
    from orch.cli import cli

    # Mock flag_bug to avoid actual spawning
    mock_flag_bug = mocker.patch('orch.flag.flag_bug', return_value={
        'success': True,
        'workspace_name': 'debug-test-bug-description',
        'workspace_path': str(tmp_path / '.orch' / 'workspace' / 'debug-test-bug-description'),
        'spawn_output': 'Agent spawned successfully'
    })

    # Run flag command
    result = cli_runner.invoke(cli, ['flag', 'Test bug description'])

    # Verify command succeeded
    assert result.exit_code == 0

    # Verify output messages
    assert '🐛 Bug flagged' in result.output
    assert 'Test bug description' in result.output
    assert 'debug-test-bug-description' in result.output
    assert '✅ Agent spawned' in result.output

    # Verify flag_bug was called
    assert mock_flag_bug.called
