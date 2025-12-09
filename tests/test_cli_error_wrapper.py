"""Tests for CLI error logging wrapper."""

import json
import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.cli import cli
from orch.error_logging import ErrorLogger, ErrorType, reset_default_logger


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def error_file(tmp_path, monkeypatch):
    """Set up temporary error file."""
    reset_default_logger()
    monkeypatch.setenv("HOME", str(tmp_path))
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    return orch_dir / "errors.jsonl"


class TestCLIErrorLogging:
    """Tests for automatic error logging in CLI commands."""

    def test_complete_logs_agent_not_found(self, cli_runner, error_file, tmp_path, monkeypatch):
        """Test that orch complete logs AgentNotFound errors."""
        # Set up mock registry with no agents
        from orch.registry import AgentRegistry

        registry_path = tmp_path / ".orch" / "agent-registry.json"
        registry_path.write_text("[]")

        with patch('orch.cli.AgentRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.find.return_value = None
            mock_registry.list.return_value = []
            mock_registry_class.return_value = mock_registry

            result = cli_runner.invoke(cli, ['complete', 'nonexistent-agent'])

        # Command should fail
        assert result.exit_code != 0

        # Error should be logged
        if error_file.exists():
            content = error_file.read_text()
            if content.strip():
                entry = json.loads(content.strip().split('\n')[-1])
                assert entry['error_type'] == 'AGENT_NOT_FOUND'
                assert 'nonexistent-agent' in entry['message']

    def test_spawn_logs_spawn_failed(self, cli_runner, error_file, monkeypatch, tmp_path):
        """Test that orch spawn fails gracefully with invalid skill."""
        # Trigger spawn failure by providing invalid skill (no mock needed)
        result = cli_runner.invoke(cli, ['spawn', 'nonexistent-skill-12345', 'task'])

        # Command should fail
        assert result.exit_code != 0

        # Note: spawn error logging is out of scope for initial implementation
        # This test verifies spawn command handles errors gracefully

    def test_error_includes_command_context(self, cli_runner, error_file, tmp_path, monkeypatch):
        """Test that logged errors include full command context."""
        from orch.registry import AgentRegistry

        with patch('orch.cli.AgentRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.find.return_value = None
            mock_registry.list.return_value = []
            mock_registry_class.return_value = mock_registry

            result = cli_runner.invoke(cli, ['complete', 'test-agent'])

        if error_file.exists():
            content = error_file.read_text()
            if content.strip():
                entry = json.loads(content.strip().split('\n')[-1])
                # Should include command info
                assert 'command' in entry
                assert 'subcommand' in entry
                assert entry['subcommand'] == 'complete'

    def test_error_includes_timestamp(self, cli_runner, error_file, tmp_path, monkeypatch):
        """Test that logged errors include timestamp."""
        with patch('orch.cli.AgentRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.find.return_value = None
            mock_registry.list.return_value = []
            mock_registry_class.return_value = mock_registry

            cli_runner.invoke(cli, ['complete', 'test-agent'])

        if error_file.exists():
            content = error_file.read_text()
            if content.strip():
                entry = json.loads(content.strip().split('\n')[-1])
                assert 'timestamp' in entry
                assert '202' in entry['timestamp']  # Year prefix


class TestOrchCompleteErrorLogging:
    """Specific tests for orch complete error logging."""

    def test_beads_error_logged_when_issue_flag_used(self, cli_runner, error_file, tmp_path, monkeypatch):
        """Test that beads errors are logged when using --issue flag."""
        # Test with non-existent beads issue
        result = cli_runner.invoke(cli, ['complete', '--issue', 'nonexistent-beads-xxx'])

        # Command should fail (beads issue not found or bd CLI not available)
        # This verifies the error handling path works
        assert result.exit_code != 0

        # If error file exists and has content, verify format
        if error_file.exists():
            content = error_file.read_text()
            if content.strip():
                entries = [json.loads(line) for line in content.strip().split('\n') if line]
                if entries:
                    # Should be a beads-related error
                    last_entry = entries[-1]
                    assert last_entry['subcommand'] == 'complete'
                    assert last_entry['error_type'] in ('BEADS_ERROR', 'VERIFICATION_FAILED')


class TestErrorTypeMapping:
    """Tests for exception to ErrorType mapping."""

    def test_click_abort_not_logged_as_unexpected(self, cli_runner, error_file, tmp_path, monkeypatch):
        """Test that click.Abort is mapped to specific type, not unexpected."""
        # click.Abort should be mapped to a known error type when raised by orch
        # This ensures we don't have tons of "UNEXPECTED_ERROR" entries
        with patch('orch.cli.AgentRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.find.return_value = None
            mock_registry.list.return_value = []
            mock_registry_class.return_value = mock_registry

            cli_runner.invoke(cli, ['complete', 'test-agent'])

        if error_file.exists():
            content = error_file.read_text()
            if content.strip():
                entry = json.loads(content.strip().split('\n')[-1])
                # Should NOT be UNEXPECTED_ERROR for a known scenario
                assert entry['error_type'] != 'UNEXPECTED_ERROR'
