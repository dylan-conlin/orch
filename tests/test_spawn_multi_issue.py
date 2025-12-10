"""
Tests for --issues flag in spawn command.

The --issues flag allows spawning an agent to work on multiple beads issues
at once, marking them all as in_progress and closing them all on complete.

Usage:
  orch spawn feature-impl "Implement feature" --issues pw-a,pw-b,pw-c

This enables:
  1. All issues marked in_progress on spawn
  2. All issues listed in SPAWN_CONTEXT.md
  3. All issues closed on orch complete
"""

import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path


class TestMultiIssueSpawn:
    """Tests for --issues flag with multiple beads issues."""

    @pytest.fixture
    def mock_beads(self, mocker):
        """Mock BeadsIntegration for testing."""
        mock_beads_instance = MagicMock()

        # Mock get_issue to return different issues based on ID
        def mock_get_issue(issue_id):
            return MagicMock(
                id=issue_id,
                title=f"Task for {issue_id}",
                description=f"Description for {issue_id}",
                status="open",
                priority=2,
                labels=None,
                notes=None
            )
        mock_beads_instance.get_issue.side_effect = mock_get_issue
        mock_beads_instance.get_open_blockers.return_value = []

        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )
        return mock_beads_instance

    def test_issues_flag_parses_comma_separated_list(self, cli_runner, mocker, mock_beads, tmp_path):
        """--issues should parse comma-separated issue IDs."""
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
            'spawn', 'feature-impl', 'Implement features',
            '--issues', 'pw-a,pw-b,pw-c',
            '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should call get_issue for each ID
        assert mock_beads.get_issue.call_count == 3

        # Should call spawn_with_skill with beads_ids list
        mock_spawn_with_skill.assert_called_once()
        call_kwargs = mock_spawn_with_skill.call_args.kwargs
        assert call_kwargs.get('beads_ids') == ['pw-a', 'pw-b', 'pw-c']
        assert call_kwargs.get('beads_id') == 'pw-a'  # Primary issue

    def test_issues_flag_marks_all_in_progress(self, cli_runner, mocker, mock_beads, tmp_path):
        """--issues should mark all issues as in_progress."""
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
            'spawn', 'feature-impl', 'Implement features',
            '--issues', 'pw-a,pw-b,pw-c',
            '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should call update_issue_status for each issue
        assert mock_beads.update_issue_status.call_count == 3
        mock_beads.update_issue_status.assert_any_call('pw-a', 'in_progress')
        mock_beads.update_issue_status.assert_any_call('pw-b', 'in_progress')
        mock_beads.update_issue_status.assert_any_call('pw-c', 'in_progress')

    def test_issues_and_issue_flags_are_mutually_exclusive(self, cli_runner, mocker):
        """--issues and --issue should not be used together."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Do something',
            '--issue', 'pw-single',
            '--issues', 'pw-a,pw-b',
            '--project', 'test-project'
        ], env={'CLAUDE_CONTEXT': ''})

        assert result.exit_code != 0
        assert "cannot" in result.output.lower() or "both" in result.output.lower()

    def test_issues_flag_fails_on_closed_issue(self, cli_runner, mocker, tmp_path):
        """--issues should fail if any issue is closed (without --force)."""
        from orch.cli import cli

        mock_beads_instance = MagicMock()

        def mock_get_issue(issue_id):
            # Second issue is closed
            status = "closed" if issue_id == "pw-b" else "open"
            return MagicMock(
                id=issue_id,
                title=f"Task for {issue_id}",
                description="",
                status=status,
                priority=2,
                labels=None,
                notes=None
            )
        mock_beads_instance.get_issue.side_effect = mock_get_issue
        mock_beads_instance.get_open_blockers.return_value = []

        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Do something',
            '--issues', 'pw-a,pw-b,pw-c',
            '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        assert result.exit_code != 0
        assert "closed" in result.output.lower()

    def test_issues_flag_fails_on_missing_issue(self, cli_runner, mocker, tmp_path):
        """--issues should fail if any issue is not found."""
        from orch.cli import cli
        from orch.beads_integration import BeadsIssueNotFoundError

        mock_beads_instance = MagicMock()

        def mock_get_issue(issue_id):
            if issue_id == "pw-missing":
                raise BeadsIssueNotFoundError("pw-missing")
            return MagicMock(
                id=issue_id,
                title=f"Task for {issue_id}",
                description="",
                status="open",
                priority=2,
                labels=None,
                notes=None
            )
        mock_beads_instance.get_issue.side_effect = mock_get_issue

        mocker.patch(
            'orch.spawn_commands.BeadsIntegration',
            return_value=mock_beads_instance
        )

        # Mock project resolver
        mocker.patch(
            'orch.project_resolver.get_project_dir',
            return_value=str(tmp_path)
        )

        result = cli_runner.invoke(cli, [
            'spawn', 'feature-impl', 'Do something',
            '--issues', 'pw-a,pw-missing,pw-c',
            '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_issues_flag_shows_summary(self, cli_runner, mocker, mock_beads, tmp_path):
        """--issues should show summary of issues being spawned."""
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
            'spawn', 'feature-impl', 'Implement features',
            '--issues', 'pw-a,pw-b',
            '--project', 'test-project', '-y'
        ], env={'CLAUDE_CONTEXT': ''})

        # Should show multi-issue spawn message
        assert "2" in result.output  # Shows count
        assert "pw-a" in result.output and "pw-b" in result.output


class TestMultiIssueComplete:
    """Tests for completing agents spawned with multiple issues."""

    def test_complete_closes_all_issues(self, tmp_path, mocker):
        """Complete should close all issues in beads_ids list."""
        from orch.complete import complete_agent_work

        # Set up workspace
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir()

        # Mock registry to return agent with multiple beads_ids
        mock_agent = {
            'id': 'test-agent',
            'workspace': '.orch/workspace/test-workspace',
            'beads_id': 'pw-a',
            'beads_ids': ['pw-a', 'pw-b', 'pw-c'],
            'beads_db_path': None,
            'status': 'active',
            'window_id': '@1234'
        }

        mocker.patch(
            'orch.complete.get_agent_by_id',
            return_value=mock_agent
        )

        # Mock verification to pass
        mocker.patch(
            'orch.complete.verify_agent_work',
            return_value=MagicMock(passed=True, errors=[])
        )

        # Mock git validation
        mocker.patch(
            'orch.git_utils.validate_work_committed',
            return_value=(True, None)
        )

        # Mock close_beads_issue
        mock_close = mocker.patch(
            'orch.complete.close_beads_issue',
            return_value=True
        )

        # Mock clean_up_agent
        mocker.patch('orch.complete.clean_up_agent')

        result = complete_agent_work(
            agent_id='test-agent',
            project_dir=tmp_path,
            force=True  # Skip phase verification for test
        )

        # Should close all three issues
        assert mock_close.call_count == 3
        assert result['beads_closed'] is True

    def test_complete_closes_single_issue_backward_compat(self, tmp_path, mocker):
        """Complete with only beads_id (no beads_ids) should still work."""
        from orch.complete import complete_agent_work

        # Set up workspace
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir()

        # Mock registry to return agent with single beads_id only
        mock_agent = {
            'id': 'test-agent',
            'workspace': '.orch/workspace/test-workspace',
            'beads_id': 'pw-single',
            # Note: no beads_ids field - backward compat test
            'beads_db_path': None,
            'status': 'active',
            'window_id': '@1234'
        }

        mocker.patch(
            'orch.complete.get_agent_by_id',
            return_value=mock_agent
        )

        mocker.patch(
            'orch.complete.verify_agent_work',
            return_value=MagicMock(passed=True, errors=[])
        )

        mocker.patch(
            'orch.git_utils.validate_work_committed',
            return_value=(True, None)
        )

        mock_close = mocker.patch(
            'orch.complete.close_beads_issue',
            return_value=True
        )

        mocker.patch('orch.complete.clean_up_agent')

        result = complete_agent_work(
            agent_id='test-agent',
            project_dir=tmp_path,
            force=True
        )

        # Should close single issue
        assert mock_close.call_count == 1
        mock_close.assert_called_with('pw-single', verify_phase=False, db_path=None)
        assert result['beads_closed'] is True


class TestRegistryMultiIssue:
    """Tests for registry storing multiple beads IDs."""

    def test_registry_stores_beads_ids(self, tmp_path, mocker):
        """Registry should store beads_ids list."""
        from orch.registry import AgentRegistry

        registry_path = tmp_path / "agent-registry.json"
        registry = AgentRegistry(registry_path=registry_path)

        agent = registry.register(
            agent_id='test-agent',
            task='Test task',
            window='workers:1',
            project_dir=str(tmp_path),
            workspace='.orch/workspace/test',
            beads_id='pw-a',
            beads_ids=['pw-a', 'pw-b', 'pw-c']
        )

        assert agent['beads_id'] == 'pw-a'
        assert agent['beads_ids'] == ['pw-a', 'pw-b', 'pw-c']

        # Verify persisted
        registry2 = AgentRegistry(registry_path=registry_path)
        found = registry2.find('test-agent')
        assert found['beads_ids'] == ['pw-a', 'pw-b', 'pw-c']

    def test_registry_without_beads_ids_backward_compat(self, tmp_path, mocker):
        """Registry should work without beads_ids for backward compatibility."""
        from orch.registry import AgentRegistry

        registry_path = tmp_path / "agent-registry.json"
        registry = AgentRegistry(registry_path=registry_path)

        agent = registry.register(
            agent_id='test-agent',
            task='Test task',
            window='workers:1',
            project_dir=str(tmp_path),
            workspace='.orch/workspace/test',
            beads_id='pw-single'
            # Note: no beads_ids
        )

        assert agent['beads_id'] == 'pw-single'
        assert 'beads_ids' not in agent
