"""
Tests for --auto-track flag in spawn command.

The --auto-track flag automatically creates a beads issue from the task
description and spawns with that issue, enabling automatic lifecycle tracking.

Usage:
  orch spawn feature-impl "Add rate limiting" --auto-track
  orch spawn investigation "Why is auth slow" --auto-track

This is equivalent to:
  1. bd create "Add rate limiting" --type task
  2. orch spawn feature-impl --issue <created-id>
"""

import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path


class TestAutoTrackFlag:
    """Tests for --auto-track flag creating beads issue on spawn."""

    @pytest.fixture
    def mock_beads(self, mocker):
        """Mock BeadsIntegration for testing."""
        mock_beads_instance = MagicMock()
        mock_beads_instance.create_issue.return_value = "orch-cli-abc"
        mock_beads_instance.get_issue.return_value = MagicMock(
            id="orch-cli-abc",
            title="Add rate limiting",
            description="",
            status="open",
            priority=2,
            notes=None
        )
        mock_beads_instance.get_open_blockers.return_value = []

        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )
        return mock_beads_instance

    def test_auto_track_creates_beads_issue(self, cli_runner, mocker, mock_beads, tmp_path):
        """--auto-track should create a beads issue from the task description."""
        from orch.cli import cli

        mock_spawn_with_skill = mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        # Mock cwd to have .beads directory
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Add rate limiting',
            '--auto-track', '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should call create_issue with task as title
        mock_beads.create_issue.assert_called_once_with("Add rate limiting", issue_type="task")

        # Should then spawn with the created beads_id
        mock_spawn_with_skill.assert_called_once()
        call_kwargs = mock_spawn_with_skill.call_args.kwargs
        assert call_kwargs.get('beads_id') == "orch-cli-abc"

    def test_auto_track_marks_issue_in_progress(self, cli_runner, mocker, mock_beads, tmp_path):
        """--auto-track should mark the created issue as in_progress."""
        from orch.cli import cli

        mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        # Mock cwd to have .beads directory
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Fix bug',
            '--auto-track', '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should mark issue as in_progress
        mock_beads.update_issue_status.assert_called_once_with("orch-cli-abc", "in_progress")

    def test_auto_track_requires_task(self, cli_runner, mocker):
        """--auto-track without task description should fail."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl',
            '--auto-track', '--project', 'test-project'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should fail because task is required for issue creation
        assert result.exit_code != 0

    def test_auto_track_with_issue_is_error(self, cli_runner, mocker):
        """--auto-track and --issue together should be an error."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Add feature',
            '--auto-track', '--issue', 'orch-cli-xyz',
            '--project', 'test-project'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should error - can't use both flags
        assert result.exit_code != 0
        assert "auto-track" in result.output.lower() or "issue" in result.output.lower()

    def test_auto_track_prints_created_issue_id(self, cli_runner, mocker, mock_beads, tmp_path):
        """--auto-track should print the created issue ID."""
        from orch.cli import cli

        mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        # Mock cwd to have .beads directory
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Add feature',
            '--auto-track', '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should show the created issue ID
        assert "orch-cli-abc" in result.output

    def test_auto_track_handles_create_failure(self, cli_runner, mocker, tmp_path):
        """--auto-track should handle beads issue creation failure gracefully."""
        from orch.cli import cli

        mock_beads_instance = MagicMock()
        mock_beads_instance.create_issue.side_effect = RuntimeError("Failed to create issue")
        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        # Mock cwd to have .beads directory
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Add feature',
            '--auto-track', '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should fail with error
        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()


class TestAutoTrackWithDifferentSkills:
    """Tests for --auto-track working with different skill types."""

    @pytest.fixture
    def mock_beads(self, mocker):
        """Mock BeadsIntegration for testing."""
        mock_beads_instance = MagicMock()
        mock_beads_instance.create_issue.return_value = "orch-cli-abc"
        mock_beads_instance.get_issue.return_value = MagicMock(
            id="orch-cli-abc",
            title="Test task",
            description="",
            status="open",
            priority=2,
            notes=None
        )
        mock_beads_instance.get_open_blockers.return_value = []

        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )
        return mock_beads_instance

    def test_auto_track_with_investigation_skill(self, cli_runner, mocker, mock_beads, tmp_path):
        """--auto-track should work with investigation skill."""
        from orch.cli import cli

        mock_spawn_with_skill = mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'investigation', 'Why is auth slow',
            '--auto-track', '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        mock_beads.create_issue.assert_called_once_with("Why is auth slow", issue_type="task")
        mock_spawn_with_skill.assert_called_once()

    def test_auto_track_preserves_other_options(self, cli_runner, mocker, mock_beads, tmp_path):
        """--auto-track should preserve other spawn options."""
        from orch.cli import cli

        mock_spawn_with_skill = mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "beads.db").touch()
        mocker.patch.object(Path, 'cwd', return_value=tmp_path)

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Add feature',
            '--auto-track', '--project', 'test-project',
            '--phases', 'implementation,validation',
            '--mode', 'tdd',
            '--validation', 'tests',
            '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        mock_spawn_with_skill.assert_called_once()
        call_kwargs = mock_spawn_with_skill.call_args.kwargs
        assert call_kwargs.get('phases') == 'implementation,validation'
        assert call_kwargs.get('mode') == 'tdd'
        assert call_kwargs.get('validation') == 'tests'
