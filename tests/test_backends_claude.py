"""Tests for ClaudeBackend implementation."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.backends.claude import ClaudeBackend
from orch.spawn import SpawnConfig


class TestClaudeBackendBasics:
    """Test basic ClaudeBackend properties and simple methods."""

    def test_backend_name_is_claude(self):
        """ClaudeBackend.name property should return 'claude'."""
        backend = ClaudeBackend()
        assert backend.name == "claude"

    def test_get_config_dir_returns_claude_directory(self):
        """ClaudeBackend.get_config_dir() should return ~/.claude."""
        backend = ClaudeBackend()
        expected = Path.home() / ".claude"
        assert backend.get_config_dir() == expected


class TestClaudeBackendBuildCommand:
    """Test ClaudeBackend.build_command() method."""

    def test_build_command_basic(self):
        """build_command should generate Claude wrapper command with prompt."""
        backend = ClaudeBackend()
        prompt = "Test task"

        command = backend.build_command(prompt)

        # Should contain wrapper script path
        assert "~/.orch/scripts/claude-code-wrapper.sh" in command
        # Should contain the prompt (shell-quoted)
        assert "Test task" in command or "'Test task'" in command
        # Should contain default flags
        assert "--allowed-tools" in command
        # Should NOT contain dangerous permissions flag (removed for security)
        assert "--dangerously-skip-permissions" not in command

    def test_build_command_with_options(self):
        """build_command should accept and use options parameter."""
        backend = ClaudeBackend()
        prompt = "Test task"
        options = {"allowed_tools": "Read,Write", "skip_permissions": False}

        # For Phase 2, we're using simple implementation that ignores options
        # (matches current spawn.py behavior which hardcodes flags)
        command = backend.build_command(prompt, options)

        # Should still build valid command even with options
        assert "~/.orch/scripts/claude-code-wrapper.sh" in command


class TestClaudeBackendEnvVars:
    """Test ClaudeBackend.get_env_vars() method."""

    def test_get_env_vars_returns_claude_variables(self):
        """get_env_vars should return CLAUDE_* environment variables."""
        backend = ClaudeBackend()

        # Create minimal SpawnConfig
        config = MagicMock()
        config.project_dir = Path("/test/project")

        workspace_abs = Path("/test/workspace")
        deliverables_list = "workspace,investigation"

        env_vars = backend.get_env_vars(config, workspace_abs, deliverables_list)

        # Should contain all CLAUDE_* variables
        assert "CLAUDE_CONTEXT" in env_vars
        assert env_vars["CLAUDE_CONTEXT"] == "worker"

        assert "CLAUDE_WORKSPACE" in env_vars
        assert env_vars["CLAUDE_WORKSPACE"] == str(workspace_abs)

        assert "CLAUDE_PROJECT" in env_vars
        assert env_vars["CLAUDE_PROJECT"] == str(config.project_dir)

        assert "CLAUDE_DELIVERABLES" in env_vars
        assert env_vars["CLAUDE_DELIVERABLES"] == deliverables_list

    def test_get_env_vars_returns_strings(self):
        """All env var values must be strings (required for shell export)."""
        backend = ClaudeBackend()

        config = MagicMock()
        config.project_dir = Path("/test/project")
        workspace_abs = Path("/test/workspace")
        deliverables_list = "workspace"

        env_vars = backend.get_env_vars(config, workspace_abs, deliverables_list)

        # All values must be strings
        for key, value in env_vars.items():
            assert isinstance(value, str), f"{key} value must be string, got {type(value)}"


class TestClaudeBackendWaitForReady:
    """Test ClaudeBackend.wait_for_ready() method."""

    @patch('subprocess.run')
    def test_wait_for_ready_detects_claude_prompt(self, mock_run):
        """wait_for_ready should detect Claude prompt indicators."""
        backend = ClaudeBackend()

        # Simulate tmux output with Claude ready indicator
        mock_result = MagicMock()
        mock_result.stdout = "> Try 'refactor ui.py'\n─────\n"
        mock_run.return_value = mock_result

        result = backend.wait_for_ready("test:1", timeout=1.0)

        assert result is True
        # Should have called tmux capture-pane
        mock_run.assert_called()

    @patch('subprocess.run')
    def test_wait_for_ready_skips_sublimating_state(self, mock_run):
        """wait_for_ready should continue polling when Claude is still sublimating."""
        backend = ClaudeBackend()

        # First call: sublimating (not ready)
        # Second call: ready prompt
        sublimating_result = MagicMock()
        sublimating_result.stdout = "✽ Sublimating…\n"

        ready_result = MagicMock()
        ready_result.stdout = "> Try something\n"

        mock_run.side_effect = [sublimating_result, ready_result]

        result = backend.wait_for_ready("test:1", timeout=2.0)

        assert result is True
        # Should have polled multiple times
        assert mock_run.call_count >= 2

    @patch('subprocess.run')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_wait_for_ready_times_out(self, mock_sleep, mock_run):
        """wait_for_ready should return False if timeout reached."""
        backend = ClaudeBackend()

        # Always return non-ready output
        mock_result = MagicMock()
        mock_result.stdout = "Loading...\n"
        mock_run.return_value = mock_result

        result = backend.wait_for_ready("test:1", timeout=0.3)

        assert result is False

    @patch.dict(os.environ, {"ORCH_SKIP_CLAUDE_READY": "1"})
    @patch('time.sleep')
    def test_wait_for_ready_skip_env_var(self, mock_sleep):
        """wait_for_ready should skip polling when ORCH_SKIP_CLAUDE_READY=1."""
        backend = ClaudeBackend()

        result = backend.wait_for_ready("test:1", timeout=5.0)

        # Should return True immediately (well, after 1s grace period)
        assert result is True
        # Should have slept once (grace period)
        mock_sleep.assert_called_once_with(1.0)

    @patch('subprocess.run')
    def test_wait_for_ready_handles_subprocess_error(self, mock_run):
        """wait_for_ready should handle subprocess errors gracefully."""
        backend = ClaudeBackend()

        # First call raises error, second call succeeds
        mock_run.side_effect = [
            subprocess.SubprocessError("tmux error"),
            MagicMock(stdout="> Try something\n")
        ]

        result = backend.wait_for_ready("test:1", timeout=2.0)

        # Should recover from error and detect ready state
        assert result is True


class TestClaudeBackendIntegration:
    """Integration tests for ClaudeBackend."""

    def test_backend_implements_all_required_methods(self):
        """ClaudeBackend should implement all Backend ABC methods."""
        backend = ClaudeBackend()

        # Should have all required methods
        assert hasattr(backend, "name")
        assert hasattr(backend, "get_config_dir")
        assert hasattr(backend, "build_command")
        assert hasattr(backend, "wait_for_ready")
        assert hasattr(backend, "get_env_vars")

        # name should be a property
        assert isinstance(type(backend).name, property)
