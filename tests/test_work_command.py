"""Tests for orch work command - start work on beads issues."""

import json
import os
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from orch.cli import cli


# Helper fixture to run as orchestrator (not worker)
@pytest.fixture(autouse=True)
def reset_claude_context(monkeypatch):
    """Reset CLAUDE_CONTEXT to allow tests to run as orchestrator."""
    monkeypatch.delenv('CLAUDE_CONTEXT', raising=False)
    monkeypatch.delenv('CLAUDE_WORKSPACE', raising=False)


class TestWorkCommandSkillInference:
    """Tests for skill inference from issue type."""

    def test_infer_skill_bug_to_debugging(self):
        """Bug issues should use systematic-debugging skill."""
        from orch.work_commands import infer_skill_from_issue_type
        assert infer_skill_from_issue_type("bug") == "systematic-debugging"

    def test_infer_skill_feature_to_feature_impl(self):
        """Feature issues should use feature-impl skill."""
        from orch.work_commands import infer_skill_from_issue_type
        assert infer_skill_from_issue_type("feature") == "feature-impl"

    def test_infer_skill_task_to_investigation(self):
        """Task issues should use investigation skill."""
        from orch.work_commands import infer_skill_from_issue_type
        assert infer_skill_from_issue_type("task") == "investigation"

    def test_infer_skill_epic_to_architect(self):
        """Epic issues should use architect skill."""
        from orch.work_commands import infer_skill_from_issue_type
        assert infer_skill_from_issue_type("epic") == "architect"

    def test_infer_skill_unknown_defaults_to_feature_impl(self):
        """Unknown issue types should default to feature-impl."""
        from orch.work_commands import infer_skill_from_issue_type
        assert infer_skill_from_issue_type("unknown") == "feature-impl"
        assert infer_skill_from_issue_type(None) == "feature-impl"


class TestWorkCommandBasic:
    """Basic tests for orch work command."""

    def test_work_command_exists(self):
        """Verify orch work command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ['work', '--help'])
        assert result.exit_code == 0
        assert 'Start work on a beads issue' in result.output or 'work' in result.output

    def test_work_with_issue_id_success(self):
        """Test orch work <issue-id> starts work with inferred skill."""
        mock_issue = json.dumps([{
            "id": "orch-cli-abc",
            "title": "Fix the bug",
            "description": "Bug description",
            "status": "open",
            "priority": 1,
            "issue_type": "bug"
        }])

        runner = CliRunner()
        with patch('subprocess.run') as mock_run, \
             patch('orch.spawn.spawn_with_skill') as mock_spawn, \
             patch('orch.project_resolver.detect_project_from_cwd') as mock_detect:
            # Mock bd show
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue,
                stderr=""
            )
            # Mock project detection
            mock_detect.return_value = ('test-project', '/path/to/project')

            result = runner.invoke(cli, ['work', 'orch-cli-abc', '-y'])

            # Should call spawn with systematic-debugging for bug
            assert mock_spawn.called
            call_kwargs = mock_spawn.call_args[1]
            assert call_kwargs.get('skill_name') == 'systematic-debugging'
            assert call_kwargs.get('beads_id') == 'orch-cli-abc'

    def test_work_with_skill_override(self):
        """Test orch work <issue-id> -s <skill> uses specified skill."""
        mock_issue = json.dumps([{
            "id": "orch-cli-abc",
            "title": "Some task",
            "description": "Task description",
            "status": "open",
            "priority": 1,
            "issue_type": "task"  # Would normally use investigation
        }])

        runner = CliRunner()
        with patch('subprocess.run') as mock_run, \
             patch('orch.spawn.spawn_with_skill') as mock_spawn, \
             patch('orch.project_resolver.detect_project_from_cwd') as mock_detect:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue,
                stderr=""
            )
            mock_detect.return_value = ('test-project', '/path/to/project')

            # Override with architect skill
            result = runner.invoke(cli, ['work', 'orch-cli-abc', '-s', 'architect', '-y'])

            assert mock_spawn.called
            call_kwargs = mock_spawn.call_args[1]
            assert call_kwargs.get('skill_name') == 'architect'

    def test_work_issue_not_found(self):
        """Test error when issue doesn't exist."""
        runner = CliRunner()
        with patch('subprocess.run') as mock_run, \
             patch('orch.project_resolver.detect_project_from_cwd') as mock_detect:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue not found"
            )
            mock_detect.return_value = ('test-project', '/path/to/project')

            result = runner.invoke(cli, ['work', 'nonexistent-id'])
            assert result.exit_code != 0
            assert 'not found' in result.output.lower()

    def test_work_refuses_closed_issue(self):
        """Test that work refuses closed issues without --force."""
        mock_issue = json.dumps([{
            "id": "orch-cli-abc",
            "title": "Closed issue",
            "description": "",
            "status": "closed",
            "priority": 1,
            "issue_type": "feature"
        }])

        runner = CliRunner()
        with patch('subprocess.run') as mock_run, \
             patch('orch.project_resolver.detect_project_from_cwd') as mock_detect:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue,
                stderr=""
            )
            mock_detect.return_value = ('test-project', '/path/to/project')

            result = runner.invoke(cli, ['work', 'orch-cli-abc'])
            assert result.exit_code != 0
            assert 'closed' in result.output.lower()


class TestWorkCommandInteractive:
    """Tests for interactive picker mode."""

    def test_work_no_args_shows_picker(self):
        """Test orch work with no args shows interactive picker."""
        mock_ready = json.dumps([
            {
                "id": "orch-cli-abc",
                "title": "Task 1",
                "status": "open",
                "priority": 1,
                "issue_type": "feature"
            },
            {
                "id": "orch-cli-def",
                "title": "Task 2",
                "status": "open",
                "priority": 2,
                "issue_type": "bug"
            }
        ])

        runner = CliRunner()
        with patch('orch.work_commands.get_ready_issues') as mock_ready_fn:
            mock_ready_fn.return_value = [
                {"id": "orch-cli-abc", "title": "Task 1", "status": "open", "priority": 1, "issue_type": "feature"},
                {"id": "orch-cli-def", "title": "Task 2", "status": "open", "priority": 2, "issue_type": "bug"}
            ]

            # Simulate user quitting the picker
            result = runner.invoke(cli, ['work'], input='q\n')

            # Should show available issues
            assert 'orch-cli-abc' in result.output or 'Task 1' in result.output

    def test_work_no_ready_issues(self):
        """Test orch work when no ready issues exist."""
        runner = CliRunner()
        with patch('orch.work_commands.get_ready_issues') as mock_ready:
            mock_ready.return_value = []

            result = runner.invoke(cli, ['work'])
            # Should indicate no ready work
            assert 'no ready issues' in result.output.lower()
