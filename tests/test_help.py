"""Tests for orch help command."""
import pytest
from orch.cli import cli


# cli_runner fixture provided by conftest.py


class TestHelpCommand:
    """Test orch help command behavior."""

    def test_help_shows_overview_when_no_topic(self, cli_runner):
        """Test that 'orch help' shows overview."""
        result = cli_runner.invoke(cli, ['help'])

        assert result.exit_code == 0
        assert 'orch - AI Agent Orchestration CLI' in result.output
        assert 'WORKFLOW-BASED HELP' in result.output
        assert 'orch help spawn' in result.output
        assert 'orch help monitor' in result.output
        assert 'orch help complete' in result.output
        assert 'orch help maintain' in result.output

    def test_help_shows_spawn_topic(self, cli_runner):
        """Test that 'orch help spawn' shows spawn workflow."""
        result = cli_runner.invoke(cli, ['help', 'spawn'])

        assert result.exit_code == 0
        assert 'Spawning Agents and Interactive Sessions' in result.output
        assert '--feature' in result.output
        assert 'SKILL-BASED' in result.output
        assert 'INTERACTIVE' in result.output

    def test_help_shows_monitor_topic(self, cli_runner):
        """Test that 'orch help monitor' shows monitoring workflow."""
        result = cli_runner.invoke(cli, ['help', 'monitor'])

        assert result.exit_code == 0
        assert 'Monitoring Agent Progress' in result.output
        assert 'orch status' in result.output
        assert 'orch check' in result.output
        assert 'Progressive Disclosure' in result.output

    def test_help_shows_complete_topic(self, cli_runner):
        """Test that 'orch help complete' shows completion workflow."""
        result = cli_runner.invoke(cli, ['help', 'complete'])

        assert result.exit_code == 0
        assert 'Completing Agent Work' in result.output
        assert 'orch complete <agent-id>' in result.output
        assert 'FEATURE VS AD-HOC' in result.output
        assert 'auto-detects' in result.output

    def test_help_shows_maintain_topic(self, cli_runner):
        """Test that 'orch help maintain' shows maintenance workflow."""
        result = cli_runner.invoke(cli, ['help', 'maintain'])

        assert result.exit_code == 0
        assert 'Maintenance and Cleanup' in result.output
        assert 'orch clean' in result.output
        assert 'orch logs' in result.output  # Updated: orch archive was removed
        assert 'TIER 3' in result.output

    def test_help_handles_unknown_topic(self, cli_runner):
        """Test that unknown topics show error and overview."""
        result = cli_runner.invoke(cli, ['help', 'nonexistent'])

        assert result.exit_code == 0
        assert 'Unknown help topic: nonexistent' in result.output
        assert 'Available topics:' in result.output

    def test_help_command_registered(self, cli_runner):
        """Test that help command is registered in CLI."""
        result = cli_runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert 'help' in result.output
