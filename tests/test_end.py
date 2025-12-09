"""Tests for orch end command - clean session exit with knowledge capture gates."""

import json
import os
import pytest
from click.testing import CliRunner
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.cli import cli


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


class TestEndCommandExists:
    """Test that orch end command exists and has proper help."""

    def test_end_command_exists(self, cli_runner):
        """Test that end command is registered."""
        result = cli_runner.invoke(cli, ['end', '--help'])
        assert result.exit_code == 0
        assert 'end' in result.output.lower() or 'session' in result.output.lower()

    def test_end_command_help_shows_purpose(self, cli_runner):
        """Test that help shows the command purpose."""
        result = cli_runner.invoke(cli, ['end', '--help'])
        assert result.exit_code == 0
        # Should mention knowledge capture or session exit
        assert 'knowledge' in result.output.lower() or 'exit' in result.output.lower()
