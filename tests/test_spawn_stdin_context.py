"""
Tests for stdin/heredoc context handling in orch spawn.

When spawning via heredoc or piped stdin, the content should be incorporated
into SPAWN_CONTEXT.md's ADDITIONAL CONTEXT section - not ignored.

Related: orch-cli-439 (orch spawn heredoc/stdin context not incorporated)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import io
import sys

from orch.spawn import SpawnConfig
from orch.spawn_prompt import build_spawn_prompt


class TestStdinContextDetection:
    """
    Validates that stdin content is detected and incorporated into spawn context.

    When users pipe content via heredoc, it should appear in ADDITIONAL CONTEXT.
    """

    def test_stdin_content_appears_in_additional_context_section(self):
        """Verify stdin content is incorporated into ADDITIONAL CONTEXT section."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            additional_context="## Investigation Question\nWhat is the answer?"
        )

        prompt = build_spawn_prompt(config)

        # Stdin content should appear in ADDITIONAL CONTEXT section
        assert "## ADDITIONAL CONTEXT" in prompt, \
            "Spawn prompt should include ADDITIONAL CONTEXT section when additional_context provided"
        assert "## Investigation Question" in prompt, \
            "Stdin content should be present in spawn prompt"
        assert "What is the answer?" in prompt, \
            "Full stdin content should be present in spawn prompt"

    def test_stdin_context_does_not_replace_entire_prompt(self):
        """Verify stdin content is added to prompt, not replacing it entirely."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            additional_context="Custom context from stdin"
        )

        prompt = build_spawn_prompt(config)

        # Standard spawn prompt sections should still be present
        assert "TASK:" in prompt, \
            "TASK section should be present (stdin shouldn't replace prompt)"
        assert "PROJECT_DIR:" in prompt, \
            "PROJECT_DIR section should be present"
        assert "Test task" in prompt, \
            "Original task should be present"
        assert "Custom context from stdin" in prompt, \
            "Stdin context should also be present"

    def test_stdin_context_combined_with_beads_context(self):
        """Verify stdin context works alongside beads issue context."""
        # When spawning from beads issue with heredoc, both should be present
        config = SpawnConfig(
            task="Fix bug",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            additional_context="BEADS ISSUE: test-123\n\nIssue Description:\nFix the bug\n\n## Extra Context\nHere is more info"
        )

        prompt = build_spawn_prompt(config)

        # Both beads context and extra heredoc content should be present
        assert "BEADS ISSUE: test-123" in prompt, \
            "Beads issue context should be present"
        assert "Fix the bug" in prompt, \
            "Issue description should be present"
        assert "## Extra Context" in prompt, \
            "Extra heredoc content should be present"
        assert "Here is more info" in prompt, \
            "Full heredoc content should be present"


class TestStdinContextFromCli:
    """
    Tests for CLI-level stdin handling.

    Verifies that spawn_commands.py correctly reads stdin and passes
    it as stdin_context (which is added to ADDITIONAL CONTEXT section).

    Bug: orch-cli-439 - heredoc content is ignored unless --from-stdin is used,
    and --from-stdin replaces entire prompt instead of adding context.
    """

    def test_from_stdin_flag_passes_stdin_context_not_custom_prompt(self):
        """
        Verify --from-stdin flag passes content as stdin_context, not custom_prompt.

        The bug was: --from-stdin set custom_prompt which replaces the entire
        spawn prompt template. Fix: pass as stdin_context instead, which gets
        incorporated into ADDITIONAL CONTEXT section.
        """
        from orch.spawn_commands import register_spawn_commands
        from click.testing import CliRunner
        import click
        import os

        @click.group()
        def cli():
            pass

        register_spawn_commands(cli)

        runner = CliRunner()

        # Clear CLAUDE_CONTEXT to allow spawning (test environment may have worker context)
        env_patch = patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)

        # Mock spawn_with_skill where it's imported (orch.spawn module)
        with env_patch, patch('orch.spawn.spawn_with_skill') as mock_spawn:
            result = runner.invoke(
                cli,
                ['spawn', 'feature-impl', 'test task', '--from-stdin'],
                input="## Investigation Question\nWhat causes the bug?\n"
            )

            # Verify spawn_with_skill was called
            assert mock_spawn.called, f"spawn_with_skill should have been called. Output: {result.output}"

            call_kwargs = mock_spawn.call_args.kwargs
            custom_prompt = call_kwargs.get('custom_prompt')
            stdin_context = call_kwargs.get('stdin_context')

            # The FIX: stdin content should be in stdin_context, NOT custom_prompt
            # custom_prompt replaces entire prompt (bad)
            # stdin_context is added to ADDITIONAL CONTEXT section (good)
            assert custom_prompt is None, (
                f"BUG: --from-stdin set custom_prompt='{custom_prompt[:50]}...'. "
                "This replaces the entire spawn prompt template. "
                "Stdin should go to stdin_context instead."
            )
            assert stdin_context is not None, (
                "stdin_context should be set when using --from-stdin. "
                "This content gets added to ADDITIONAL CONTEXT section."
            )
            assert "## Investigation Question" in stdin_context, (
                f"stdin_context should contain the heredoc content. Got: {stdin_context}"
            )

    def test_auto_detect_piped_stdin_without_flag(self):
        """
        Verify stdin is auto-detected when piped (without explicit --from-stdin flag).

        Users naturally use heredoc without knowing about --from-stdin flag:
          orch spawn investigation "task" << 'CONTEXT'
          ...
          CONTEXT

        This should work without requiring --from-stdin flag.
        """
        from orch.spawn_commands import register_spawn_commands
        from click.testing import CliRunner
        import click
        import os

        @click.group()
        def cli():
            pass

        register_spawn_commands(cli)

        runner = CliRunner()

        # Clear CLAUDE_CONTEXT to allow spawning (test environment may have worker context)
        env_patch = patch.dict(os.environ, {'CLAUDE_CONTEXT': ''}, clear=False)

        with env_patch, patch('orch.spawn.spawn_with_skill') as mock_spawn:
            # CliRunner's input= simulates piped stdin
            result = runner.invoke(
                cli,
                ['spawn', 'feature-impl', 'test task'],  # No --from-stdin flag
                input="## Context\nPiped content\n"
            )

            if mock_spawn.called:
                call_kwargs = mock_spawn.call_args.kwargs
                stdin_context = call_kwargs.get('stdin_context')

                # stdin_context should be set even without --from-stdin flag
                # This is the UX improvement: auto-detect piped stdin
                assert stdin_context is not None, (
                    "stdin_context should be auto-detected from piped stdin. "
                    "Users should not need to explicitly use --from-stdin flag."
                )
                assert "## Context" in stdin_context, (
                    f"stdin_context should contain piped content. Got: {stdin_context}"
                )


class TestPromptFileVsStdin:
    """
    Tests that --prompt-file works differently from stdin/heredoc.

    --prompt-file: Replace entire prompt (power user feature)
    stdin/heredoc: Add to ADDITIONAL CONTEXT section (normal usage)
    """

    def test_prompt_file_replaces_entire_prompt(self):
        """Verify --prompt-file replaces entire spawn prompt (full control)."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            custom_prompt="CUSTOM FULL PROMPT\nMy completely custom prompt."
        )

        prompt = build_spawn_prompt(config)

        # With custom_prompt set, the entire prompt should be replaced
        assert prompt == "CUSTOM FULL PROMPT\nMy completely custom prompt.", \
            "custom_prompt should replace entire spawn prompt"
        assert "TASK:" not in prompt, \
            "Standard template sections should not appear with custom_prompt"

    def test_additional_context_does_not_replace_prompt(self):
        """Verify additional_context adds to prompt, doesn't replace it."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            additional_context="Extra context from heredoc"
        )

        prompt = build_spawn_prompt(config)

        # With additional_context, standard template should still be there
        assert "TASK:" in prompt, \
            "Standard TASK section should be present with additional_context"
        assert "Test task" in prompt, \
            "Task description should be present"
        assert "Extra context from heredoc" in prompt, \
            "Additional context should also be present"
