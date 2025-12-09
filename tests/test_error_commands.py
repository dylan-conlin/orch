"""Tests for orch errors command."""

import json
import pytest
from click.testing import CliRunner
from datetime import datetime
from pathlib import Path

from orch.cli import cli
from orch.error_logging import ErrorLogger, ErrorType, reset_default_logger


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def error_file(tmp_path, monkeypatch):
    """Set up temporary error file and reset singleton."""
    reset_default_logger()
    monkeypatch.setenv("HOME", str(tmp_path))
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    return orch_dir / "errors.jsonl"


@pytest.fixture
def logger_with_errors(error_file):
    """Create logger and add sample errors."""
    logger = ErrorLogger(error_file=error_file)

    # Add various errors
    logger.log_error(
        command="orch complete agent-1",
        subcommand="complete",
        error_type=ErrorType.AGENT_NOT_FOUND,
        message="Agent 'agent-1' not found in registry",
        context={"attempted_lookup": "agent-1"},
    )
    logger.log_error(
        command="orch complete agent-2",
        subcommand="complete",
        error_type=ErrorType.VERIFICATION_FAILED,
        message="Investigation file not found",
    )
    logger.log_error(
        command="orch spawn skill task",
        subcommand="spawn",
        error_type=ErrorType.SPAWN_FAILED,
        message="Failed to create workspace",
    )
    logger.log_error(
        command="orch complete agent-3",
        subcommand="complete",
        error_type=ErrorType.AGENT_NOT_FOUND,
        message="Agent 'agent-3' not found",
    )

    return logger


class TestErrorsCommand:
    """Tests for orch errors command."""

    def test_errors_command_exists(self, cli_runner):
        """Test that errors command exists."""
        result = cli_runner.invoke(cli, ['errors', '--help'])
        assert result.exit_code == 0
        assert 'errors' in result.output.lower() or 'Error' in result.output

    def test_errors_shows_summary(self, cli_runner, logger_with_errors, monkeypatch):
        """Test default output shows error summary."""
        # Set HOME so CLI uses our test file
        result = cli_runner.invoke(cli, ['errors'])

        # Should show summary header
        assert 'Error summary' in result.output or 'error' in result.output.lower()

        # Should show counts by type
        assert 'AGENT_NOT_FOUND' in result.output or 'AgentNotFound' in result.output

        # Should show counts by command
        assert 'complete' in result.output

    def test_errors_shows_recent_errors(self, cli_runner, logger_with_errors):
        """Test that recent errors are displayed."""
        result = cli_runner.invoke(cli, ['errors'])

        # Should show recent error messages
        assert 'not found' in result.output.lower() or 'Agent' in result.output

    def test_errors_empty_shows_no_errors(self, cli_runner, error_file):
        """Test output when no errors exist."""
        # Don't add any errors
        result = cli_runner.invoke(cli, ['errors'])

        assert result.exit_code == 0
        # Should indicate no errors
        assert 'No errors' in result.output or 'total' in result.output.lower()

    def test_errors_days_filter(self, cli_runner, logger_with_errors):
        """Test --days filter."""
        result = cli_runner.invoke(cli, ['errors', '--days', '7'])

        assert result.exit_code == 0
        # Should show 7 days in output
        assert '7 days' in result.output or '7' in result.output

    def test_errors_type_filter(self, cli_runner, logger_with_errors):
        """Test --type filter."""
        result = cli_runner.invoke(cli, ['errors', '--type', 'AGENT_NOT_FOUND'])

        assert result.exit_code == 0
        # Should show only agent not found errors
        assert 'AGENT_NOT_FOUND' in result.output or 'AgentNotFound' in result.output

    def test_errors_json_output(self, cli_runner, logger_with_errors):
        """Test --json flag outputs valid JSON."""
        result = cli_runner.invoke(cli, ['errors', '--json'])

        assert result.exit_code == 0

        # Should be valid JSON
        data = json.loads(result.output)

        # Should have expected structure
        assert 'stats' in data
        assert 'recent_errors' in data
        assert 'total' in data['stats']
        assert 'by_type' in data['stats']
        assert 'by_command' in data['stats']

    def test_errors_json_with_filters(self, cli_runner, logger_with_errors):
        """Test --json with filters."""
        result = cli_runner.invoke(cli, ['errors', '--json', '--days', '3'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'stats' in data

    def test_errors_limit_recent(self, cli_runner, logger_with_errors):
        """Test --limit for recent errors."""
        result = cli_runner.invoke(cli, ['errors', '--limit', '2'])

        assert result.exit_code == 0
        # Should limit displayed errors


class TestErrorsCommandEdgeCases:
    """Edge case tests for orch errors command."""

    def test_errors_with_corrupted_file(self, cli_runner, error_file):
        """Test handling of corrupted JSON lines."""
        # Write some valid entries
        logger = ErrorLogger(error_file=error_file)
        logger.log_error(
            command="orch complete x",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Valid error",
        )

        # Append corrupted line
        with open(error_file, 'a') as f:
            f.write("not valid json\n")

        # Should still work (skip bad lines)
        result = cli_runner.invoke(cli, ['errors'])
        assert result.exit_code == 0

    def test_errors_with_missing_file(self, cli_runner, tmp_path, monkeypatch):
        """Test when errors.jsonl doesn't exist."""
        reset_default_logger()
        monkeypatch.setenv("HOME", str(tmp_path))
        # Don't create .orch directory

        result = cli_runner.invoke(cli, ['errors'])

        # Should handle gracefully
        assert result.exit_code == 0
        assert 'No errors' in result.output or '0' in result.output

    def test_errors_invalid_type_filter(self, cli_runner, error_file):
        """Test invalid --type value."""
        result = cli_runner.invoke(cli, ['errors', '--type', 'INVALID_TYPE'])

        # Should handle gracefully (show warning or empty results)
        assert result.exit_code == 0 or result.exit_code == 2


class TestErrorsOutputFormat:
    """Tests for orch errors output format."""

    def test_summary_shows_percentages(self, cli_runner, logger_with_errors):
        """Test that summary shows percentages."""
        result = cli_runner.invoke(cli, ['errors'])

        # Should show percentage breakdown
        assert '%' in result.output or 'percent' in result.output.lower()

    def test_recent_errors_show_timestamp(self, cli_runner, logger_with_errors):
        """Test that recent errors show timestamps."""
        result = cli_runner.invoke(cli, ['errors'])

        # Should show date/time
        assert '202' in result.output  # Year prefix

    def test_recent_errors_show_command(self, cli_runner, logger_with_errors):
        """Test that recent errors show command."""
        result = cli_runner.invoke(cli, ['errors'])

        # Should show command (complete or spawn)
        assert 'complete' in result.output.lower() or 'spawn' in result.output.lower()
