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


class TestStaleCommand:
    """Tests for orch stale CLI command."""

    def test_stale_no_issues(self, cli_runner, mocker):
        """Test stale command when no stale issues exist."""
        from orch.cli import cli

        mock_get_stale = mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            return_value=[]
        )

        result = cli_runner.invoke(cli, ['stale'])

        assert result.exit_code == 0
        assert 'No stale issues' in result.output or 'stale' in result.output.lower()
        mock_get_stale.assert_called_once()

    def test_stale_with_issues(self, cli_runner, mocker):
        """Test stale command with stale issues."""
        from orch.cli import cli

        mock_issues = [
            {
                "id": "orch-cli-abc",
                "title": "Old forgotten issue",
                "status": "open",
                "priority": 2,
                "updated_at": "2025-11-01T10:00:00Z"
            },
            {
                "id": "orch-cli-def",
                "title": "Stale in-progress work",
                "status": "in_progress",
                "priority": 1,
                "updated_at": "2025-11-05T10:00:00Z"
            },
        ]

        mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            return_value=mock_issues
        )

        result = cli_runner.invoke(cli, ['stale'])

        assert result.exit_code == 0
        assert 'orch-cli-abc' in result.output
        assert 'Old forgotten issue' in result.output
        assert 'orch-cli-def' in result.output

    def test_stale_with_days_option(self, cli_runner, mocker):
        """Test stale command with custom days."""
        from orch.cli import cli

        mock_get_stale = mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            return_value=[]
        )

        result = cli_runner.invoke(cli, ['stale', '--days', '7'])

        assert result.exit_code == 0
        mock_get_stale.assert_called_once_with(days=7, status=None, limit=50)

    def test_stale_with_status_filter(self, cli_runner, mocker):
        """Test stale command with status filter."""
        from orch.cli import cli

        mock_get_stale = mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            return_value=[]
        )

        result = cli_runner.invoke(cli, ['stale', '--status', 'in_progress'])

        assert result.exit_code == 0
        mock_get_stale.assert_called_once_with(days=14, status='in_progress', limit=50)

    def test_stale_json_output(self, cli_runner, mocker):
        """Test stale command with JSON output."""
        from orch.cli import cli
        import json

        mock_issues = [
            {
                "id": "orch-cli-abc",
                "title": "Stale issue",
                "status": "open",
                "priority": 2,
            }
        ]

        mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            return_value=mock_issues
        )

        result = cli_runner.invoke(cli, ['stale', '--json'])

        assert result.exit_code == 0
        # Should be valid JSON
        output = json.loads(result.output)
        assert len(output) == 1
        assert output[0]["id"] == "orch-cli-abc"

    def test_stale_cli_not_found(self, cli_runner, mocker):
        """Test stale command when bd CLI not found."""
        from orch.cli import cli
        from orch.beads_integration import BeadsCLINotFoundError

        mocker.patch(
            'orch.beads_integration.BeadsIntegration.get_stale_issues',
            side_effect=BeadsCLINotFoundError()
        )

        result = cli_runner.invoke(cli, ['stale'])

        assert result.exit_code == 1
        assert 'bd' in result.output.lower() or 'not found' in result.output.lower()
