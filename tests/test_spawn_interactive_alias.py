"""
Tests for 'interactive' as alias for -i flag in spawn command.

Users should be able to run:
  orch spawn interactive "task"
which behaves the same as:
  orch spawn -i "task"
"""

import os
import pytest
from unittest.mock import patch, Mock


class TestInteractiveAlias:
    """Tests for treating 'interactive' as an alias for -i flag."""

    @pytest.fixture(autouse=True)
    def clear_worker_context(self, mocker):
        """Clear CLAUDE_CONTEXT env var so spawn commands aren't blocked."""
        mocker.patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)

    def test_spawn_interactive_as_skill_name_triggers_interactive_mode(self, cli_runner, mocker):
        """'orch spawn interactive "task"' should trigger interactive mode, not skill lookup."""
        from orch.cli import cli

        # Mock spawn_interactive to track if it's called
        # Note: spawn_interactive is imported from orch.spawn into spawn_commands
        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Run: orch spawn interactive "explore the codebase"
        result = cli_runner.invoke(cli, ['spawn', 'interactive', 'explore the codebase', '--project', 'test-project'])

        # Should NOT fail with "Skill 'interactive' not found"
        assert "Skill 'interactive' not found" not in result.output
        assert "not found" not in result.output.lower() or "project" in result.output.lower()

        # Should call spawn_interactive (interactive mode)
        mock_spawn_interactive.assert_called_once()

    def test_spawn_interactive_passes_task_as_context(self, cli_runner, mocker):
        """'orch spawn interactive "task"' should pass task as context to spawn_interactive."""
        from orch.cli import cli

        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, ['spawn', 'interactive', 'debug auth flow', '--project', 'test-project'])

        # Should pass the task as context
        mock_spawn_interactive.assert_called_once()
        call_kwargs = mock_spawn_interactive.call_args.kwargs
        assert call_kwargs['context'] == 'debug auth flow'

    def test_spawn_interactive_with_project_flag(self, cli_runner, mocker):
        """'orch spawn interactive "task" --project X' should pass project correctly."""
        from orch.cli import cli

        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, ['spawn', 'interactive', 'test task', '--project', 'my-project'])

        mock_spawn_interactive.assert_called_once()
        call_kwargs = mock_spawn_interactive.call_args.kwargs
        assert call_kwargs['project'] == 'my-project'

    def test_spawn_interactive_without_task(self, cli_runner, mocker):
        """'orch spawn interactive' (no task) should still work as empty context."""
        from orch.cli import cli

        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, ['spawn', 'interactive', '--project', 'test-project'])

        # Should call spawn_interactive with empty context
        mock_spawn_interactive.assert_called_once()
        call_kwargs = mock_spawn_interactive.call_args.kwargs
        assert call_kwargs['context'] == ''

    def test_spawn_interactive_alias_preserves_other_flags(self, cli_runner, mocker):
        """'orch spawn interactive' should preserve --yes, --backend, --model flags."""
        from orch.cli import cli

        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, [
            'spawn', 'interactive', 'task',
            '--project', 'test-project',
            '--yes',
            '--backend', 'codex',
            '--model', 'opus'
        ])

        mock_spawn_interactive.assert_called_once()
        call_kwargs = mock_spawn_interactive.call_args.kwargs
        assert call_kwargs['yes'] is True
        assert call_kwargs['backend'] == 'codex'
        assert call_kwargs['model'] == 'opus'


class TestInteractiveAliasDoesNotInterfere:
    """Tests to ensure the alias doesn't interfere with other spawn modes."""

    @pytest.fixture(autouse=True)
    def clear_worker_context(self, mocker):
        """Clear CLAUDE_CONTEXT env var so spawn commands aren't blocked."""
        mocker.patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)

    def test_actual_interactive_flag_still_works(self, cli_runner, mocker):
        """'orch spawn -i "task"' should still work normally."""
        from orch.cli import cli

        mock_spawn_interactive = mocker.patch(
            'orch.spawn.spawn_interactive',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, ['spawn', '-i', 'explore codebase', '--project', 'test-project'])

        mock_spawn_interactive.assert_called_once()
        call_kwargs = mock_spawn_interactive.call_args.kwargs
        assert call_kwargs['context'] == 'explore codebase'

    def test_skill_with_interactive_flag_still_works(self, cli_runner, tmp_path, mocker):
        """'orch spawn architect "task" -i' (skill + -i) should still work."""
        from orch.cli import cli

        # Create a mock skill
        skills_dir = tmp_path / '.claude' / 'skills' / 'worker' / 'architect'
        skills_dir.mkdir(parents=True)
        skill_file = skills_dir / 'SKILL.md'
        skill_file.write_text("""---
skill: architect
spawnable: true
---
# Architect Skill
""")

        mock_spawn_with_skill = mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        # Mock discover_skills to return our test skill
        mocker.patch('orch.skill_discovery.discover_skills', return_value={
            'architect': Mock(name='architect', triggers=[], deliverables=[], verification=[])
        })

        result = cli_runner.invoke(cli, [
            'spawn', 'architect', 'design auth system', '-i',
            '--project', 'test-project'
        ])

        # Should call spawn_with_skill with interactive=True
        mock_spawn_with_skill.assert_called_once()
        call_kwargs = mock_spawn_with_skill.call_args.kwargs
        assert call_kwargs.get('interactive') is True

    def test_regular_skill_spawn_still_works(self, cli_runner, mocker):
        """'orch spawn feature-impl "task"' should still work normally."""
        from orch.cli import cli

        mock_spawn_with_skill = mocker.patch(
            'orch.spawn.spawn_with_skill',
            return_value={'window': 'workers:1', 'window_name': 'test', 'agent_id': 'test-id'}
        )

        result = cli_runner.invoke(cli, ['spawn', 'feature-impl', 'add feature', '--project', 'test-project'])

        mock_spawn_with_skill.assert_called_once()
        call_kwargs = mock_spawn_with_skill.call_args.kwargs
        assert call_kwargs['skill_name'] == 'feature-impl'
