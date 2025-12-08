"""
Tests for spawn command commit check behavior with beads issues.

TDD: These tests verify that:
1. Commit check is SKIPPED for open/in_progress issues (work hasn't completed)
2. Commit check RUNS for closed issues (catches re-spawning completed work)
3. The -y flag suppresses warning OUTPUT (not just the prompt)
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from orch.cli import cli


class TestSpawnCommitCheckStatusFiltering:
    """Tests for skipping commit check based on issue status."""

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.spawn_commands.find_commits_mentioning_issue')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_skips_commit_check_for_open_status(
        self, mock_detect, mock_find_commits, mock_beads_cls, mock_spawn
    ):
        """
        When issue status is 'open', commit check should be skipped entirely.
        Open = work hasn't started, commits found are likely from issue creation.
        """
        # Setup: issue with status='open'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-abc",
            title="Test issue",
            description="",
            status="open",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-abc', '-y'])

        # Commit check should NOT be called for open issues
        mock_find_commits.assert_not_called()

        # Spawn should still proceed
        mock_spawn.assert_called_once()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.spawn_commands.find_commits_mentioning_issue')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_skips_commit_check_for_in_progress_status(
        self, mock_detect, mock_find_commits, mock_beads_cls, mock_spawn
    ):
        """
        When issue status is 'in_progress', commit check should be skipped.
        In_progress = work is ongoing, commits are expected.
        """
        # Setup: issue with status='in_progress'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-def",
            title="Test issue",
            description="",
            status="in_progress",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-def', '-y'])

        # Commit check should NOT be called for in_progress issues
        mock_find_commits.assert_not_called()

        # Spawn should still proceed
        mock_spawn.assert_called_once()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.spawn_commands.find_commits_mentioning_issue')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_runs_commit_check_for_closed_status(
        self, mock_detect, mock_find_commits, mock_beads_cls, mock_spawn
    ):
        """
        When issue status is 'closed', commit check SHOULD run.
        Closed = work supposedly complete, warns about re-spawning.
        """
        # Setup: issue with status='closed'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-xyz",
            title="Test issue",
            description="",
            status="closed",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")
        # No commits found (so spawn proceeds without warning)
        mock_find_commits.return_value = []

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-xyz', '-y'])

        # Commit check SHOULD be called for closed issues
        mock_find_commits.assert_called_once()

        # Spawn should proceed
        mock_spawn.assert_called_once()


class TestSpawnCommitCheckYesFlag:
    """Tests for -y flag suppressing warning OUTPUT (not just prompt)."""

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.spawn_commands.find_commits_mentioning_issue')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_yes_flag_suppresses_warning_output(
        self, mock_detect, mock_find_commits, mock_beads_cls, mock_spawn
    ):
        """
        With -y flag, warning about prior commits should NOT be displayed.
        The -y flag should suppress both the warning text AND the confirmation prompt.
        """
        # Setup: closed issue with prior commits
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-closed",
            title="Completed work",
            description="",
            status="closed",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        # Simulate finding prior commits
        mock_commit = MagicMock()
        mock_commit.short_hash = "abc1234"
        mock_commit.short_message = "feat: implement feature"
        mock_find_commits.return_value = [mock_commit]

        runner = CliRunner(mix_stderr=False, env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed', '-y'])

        # Warning text should NOT appear in output with -y flag
        # Check both stdout and stderr
        combined_output = result.output + (result.stderr or "")
        assert "prior commit(s)" not in combined_output
        assert "Work may already be completed" not in combined_output

        # Spawn should proceed
        mock_spawn.assert_called_once()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.spawn_commands.find_commits_mentioning_issue')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_warning_displayed_without_yes_flag(
        self, mock_detect, mock_find_commits, mock_beads_cls, mock_spawn
    ):
        """
        Without -y flag, warning about prior commits SHOULD be displayed.
        """
        # Setup: closed issue with prior commits
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-closed",
            title="Completed work",
            description="",
            status="closed",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        # Simulate finding prior commits
        mock_commit = MagicMock()
        mock_commit.short_hash = "abc1234"
        mock_commit.short_message = "feat: implement feature"
        mock_find_commits.return_value = [mock_commit]

        runner = CliRunner(mix_stderr=False, env={'CLAUDE_CONTEXT': ''})
        # Without -y, user declines
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed'], input='n\n')

        # Warning text SHOULD appear in stderr
        combined_output = result.output + (result.stderr or "")
        assert "prior commit(s)" in combined_output or "Spawn agent anyway?" in result.output

        # Spawn should NOT be called since user declined
        mock_spawn.assert_not_called()
