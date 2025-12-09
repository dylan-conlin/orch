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
        When issue status is 'closed', commit check SHOULD run (after --force).
        Closed = work supposedly complete, warns about re-spawning.
        Note: --force is needed to bypass closed issue refusal check.
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
        # --force is needed to bypass closed issue refusal, then commit check runs
        result = runner.invoke(cli, ['spawn', '--issue', 'test-xyz', '--force', '-y'])

        # Commit check SHOULD be called for closed issues
        mock_find_commits.assert_called_once()

        # Spawn should proceed
        mock_spawn.assert_called_once()


class TestSpawnCommitCheckYesFlag:
    """Tests for -y flag suppressing warning OUTPUT (not just prompt).

    Note: These tests use --force because closed issues are now refused by default.
    The commit check only runs after --force bypasses the closed issue check.
    """

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
        Note: --force is needed to bypass closed issue refusal.
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
        # --force to bypass closed issue check, -y to suppress commit warning
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed', '--force', '-y'])

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
        Note: --force is needed to bypass closed issue refusal.
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
        # --force to bypass closed issue check, no -y so warning displayed
        # User declines the spawn
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed', '--force'], input='n\n')

        # Warning text SHOULD appear in stderr
        combined_output = result.output + (result.stderr or "")
        assert "prior commit(s)" in combined_output or "Spawn agent anyway?" in result.output

        # Spawn should NOT be called since user declined
        mock_spawn.assert_not_called()


class TestSpawnIssueLabels:
    """Tests for labels being included in spawn context from beads issues."""

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_labels_included_in_additional_context(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        When issue has labels, they should be included in additional_context
        passed to spawn_with_skill.
        """
        # Setup: issue with labels
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-xyz",
            title="Test issue with labels",
            description="A test description",
            status="open",
            notes=None,
            labels=["P2", "beads-integration", "target:orch-cli"],
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-xyz', '-y'])

        # Spawn should be called
        mock_spawn.assert_called_once()

        # Get the additional_context argument passed to spawn_with_skill
        call_kwargs = mock_spawn.call_args.kwargs
        additional_context = call_kwargs.get('additional_context', '')

        # Labels should be included in the context
        assert "Labels:" in additional_context
        assert "P2" in additional_context
        assert "beads-integration" in additional_context
        assert "target:orch-cli" in additional_context

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_no_labels_section_when_labels_empty(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        When issue has no labels, the Labels section should not appear.
        """
        # Setup: issue without labels
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-xyz",
            title="Test issue without labels",
            description="A test description",
            status="open",
            notes=None,
            labels=None,
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-xyz', '-y'])

        # Spawn should be called
        mock_spawn.assert_called_once()

        # Get the additional_context argument passed to spawn_with_skill
        call_kwargs = mock_spawn.call_args.kwargs
        additional_context = call_kwargs.get('additional_context', '')

        # Labels section should NOT be in the context
        assert "Labels:" not in additional_context

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_no_labels_section_when_labels_empty_list(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        When issue has empty labels list, the Labels section should not appear.
        """
        # Setup: issue with empty labels list
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-xyz",
            title="Test issue with empty labels",
            description="A test description",
            status="open",
            notes=None,
            labels=[],
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-xyz', '-y'])

        # Spawn should be called
        mock_spawn.assert_called_once()

        # Get the additional_context argument passed to spawn_with_skill
        call_kwargs = mock_spawn.call_args.kwargs
        additional_context = call_kwargs.get('additional_context', '')

        # Labels section should NOT be in the context (empty list is falsy)
        assert "Labels:" not in additional_context


class TestSpawnClosedIssueRefusal:
    """Tests for refusing to spawn from closed beads issues."""

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_refuses_closed_issue_without_force(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        Spawn should REFUSE closed issues by default with a clear message.
        This prevents wasting time re-spawning for already-completed work.
        """
        # Setup: issue with status='closed'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-closed",
            title="Already completed",
            description="",
            status="closed",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(mix_stderr=False, env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed', '-y'])

        # Should be refused - exit code should be non-zero (Abort)
        assert result.exit_code != 0

        # Should show clear error message
        combined_output = result.output + (result.stderr or "")
        assert "closed" in combined_output.lower()
        assert "test-closed" in combined_output
        assert "--force" in combined_output

        # Spawn should NOT be called
        mock_spawn.assert_not_called()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_allows_closed_issue_with_force_flag(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        With --force flag, closed issues should be allowed.
        This provides an escape hatch for legitimate re-spawns.
        """
        # Setup: issue with status='closed'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-closed",
            title="Already completed",
            description="",
            status="closed",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-closed', '--force', '-y'])

        # Should succeed with --force
        assert result.exit_code == 0

        # Spawn should be called
        mock_spawn.assert_called_once()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_open_issue_allowed_without_force(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        Open issues should spawn normally without --force.
        Only closed issues require the --force flag.
        """
        # Setup: issue with status='open'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-open",
            title="New task",
            description="",
            status="open",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-open', '-y'])

        # Should succeed without --force
        assert result.exit_code == 0

        # Spawn should be called
        mock_spawn.assert_called_once()

    @patch('orch.spawn.spawn_with_skill')
    @patch('orch.spawn_commands.BeadsIntegration')
    @patch('orch.project_resolver.detect_project_from_cwd')
    @patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)
    def test_in_progress_issue_allowed_without_force(
        self, mock_detect, mock_beads_cls, mock_spawn
    ):
        """
        In-progress issues should spawn normally without --force.
        Only closed issues require the --force flag.
        """
        # Setup: issue with status='in_progress'
        mock_beads = MagicMock()
        mock_beads_cls.return_value = mock_beads
        mock_beads.get_issue.return_value = MagicMock(
            id="test-inprogress",
            title="WIP task",
            description="",
            status="in_progress",
            notes=None
        )
        mock_detect.return_value = ("test-project", "/path/to/project")

        runner = CliRunner(env={'CLAUDE_CONTEXT': ''})
        result = runner.invoke(cli, ['spawn', '--issue', 'test-inprogress', '-y'])

        # Should succeed without --force
        assert result.exit_code == 0

        # Spawn should be called
        mock_spawn.assert_called_once()
