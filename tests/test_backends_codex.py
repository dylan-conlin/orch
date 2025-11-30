"""Tests for CodexBackend implementation."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.backends.codex import CodexBackend
from orch.spawn import SpawnConfig


class TestCodexBackendBasics:
    """Test basic CodexBackend properties and simple methods."""

    def test_backend_name_is_codex(self):
        """CodexBackend.name property should return 'codex'."""
        backend = CodexBackend()
        assert backend.name == "codex"

    def test_get_config_dir_returns_codex_directory(self):
        """CodexBackend.get_config_dir() should return ~/.codex."""
        backend = CodexBackend()
        expected = Path.home() / ".codex"
        assert backend.get_config_dir() == expected


class TestCodexBackendBuildCommand:
    """Test CodexBackend.build_command() method."""

    def test_build_command_basic(self):
        """build_command should generate Codex CLI command with prompt."""
        backend = CodexBackend()
        prompt = "Test task"

        command = backend.build_command(prompt)

        # Should contain codex command (NOT claude wrapper)
        assert "codex" in command
        assert "claude" not in command.lower()
        # Should contain the prompt (shell-quoted)
        assert "Test task" in command or "'Test task'" in command

    def test_build_command_with_options(self):
        """build_command should accept and use options parameter."""
        backend = CodexBackend()
        prompt = "Test task"
        options = {"allowed_tools": "Read,Write", "skip_permissions": False}

        # For Phase 3, we're using simple implementation that may ignore options
        # (similar to ClaudeBackend Phase 2 behavior)
        command = backend.build_command(prompt, options)

        # Should still build valid command even with options
        assert "codex" in command


class TestCodexBackendEnvVars:
    """Test CodexBackend.get_env_vars() method."""

    def test_get_env_vars_returns_codex_variables(self):
        """get_env_vars should return CODEX_* environment variables (not CLAUDE_*)."""
        backend = CodexBackend()

        # Create minimal SpawnConfig
        config = MagicMock()
        config.project_dir = Path("/test/project")

        workspace_abs = Path("/test/workspace")
        deliverables_list = "workspace,investigation"

        env_vars = backend.get_env_vars(config, workspace_abs, deliverables_list)

        # Should contain all CODEX_* variables (NOT CLAUDE_*)
        assert "CODEX_CONTEXT" in env_vars
        assert env_vars["CODEX_CONTEXT"] == "worker"

        assert "CODEX_WORKSPACE" in env_vars
        assert env_vars["CODEX_WORKSPACE"] == str(workspace_abs)

        assert "CODEX_PROJECT" in env_vars
        assert env_vars["CODEX_PROJECT"] == str(config.project_dir)

        assert "CODEX_DELIVERABLES" in env_vars
        assert env_vars["CODEX_DELIVERABLES"] == deliverables_list

        # Should NOT contain CLAUDE_* variables
        assert "CLAUDE_CONTEXT" not in env_vars
        assert "CLAUDE_WORKSPACE" not in env_vars

    def test_get_env_vars_returns_strings(self):
        """All env var values must be strings (required for shell export)."""
        backend = CodexBackend()

        config = MagicMock()
        config.project_dir = Path("/test/project")
        workspace_abs = Path("/test/workspace")
        deliverables_list = "workspace"

        env_vars = backend.get_env_vars(config, workspace_abs, deliverables_list)

        # All values must be strings
        for key, value in env_vars.items():
            assert isinstance(value, str), f"{key} value must be string, got {type(value)}"


class TestCodexBackendWaitForReady:
    """Test CodexBackend.wait_for_ready() method."""

    @patch('subprocess.run')
    def test_wait_for_ready_detects_codex_prompt(self, mock_run):
        """wait_for_ready should detect Codex prompt indicators.

        Validated patterns (2025-11-21):
        - "OpenAI Codex" in startup banner
        - "›" (U+203A) as ready prompt
        - "context left" in status bar
        - "/init" in help commands
        """
        backend = CodexBackend()

        # Simulate tmux output with Codex ready indicator (validated pattern)
        # Using actual Codex CLI output pattern
        mock_result = MagicMock()
        mock_result.stdout = "› Explain this codebase\n  100% context left · ? for shortcuts"
        mock_run.return_value = mock_result

        result = backend.wait_for_ready("test:1", timeout=1.0)

        assert result is True
        # Should have called tmux capture-pane
        mock_run.assert_called()

    @patch('subprocess.run')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_wait_for_ready_times_out(self, mock_sleep, mock_run):
        """wait_for_ready should return False if timeout reached."""
        backend = CodexBackend()

        # Always return non-ready output
        mock_result = MagicMock()
        mock_result.stdout = "Loading...\n"
        mock_run.return_value = mock_result

        result = backend.wait_for_ready("test:1", timeout=0.3)

        assert result is False

    @patch.dict(os.environ, {"ORCH_SKIP_CODEX_READY": "1"})
    @patch('time.sleep')
    def test_wait_for_ready_skip_env_var(self, mock_sleep):
        """wait_for_ready should skip polling when ORCH_SKIP_CODEX_READY=1."""
        backend = CodexBackend()

        result = backend.wait_for_ready("test:1", timeout=5.0)

        # Should return True immediately (after grace period)
        assert result is True
        # Should have slept once (grace period)
        mock_sleep.assert_called_once_with(1.0)

    @patch('subprocess.run')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_wait_for_ready_handles_subprocess_error(self, mock_sleep, mock_run):
        """wait_for_ready should handle subprocess errors gracefully."""
        backend = CodexBackend()

        # First call raises error, second call succeeds with validated pattern
        mock_success = MagicMock()
        mock_success.stdout = "OpenAI Codex (v0.59.0)\n› "  # Actual Codex pattern
        mock_run.side_effect = [
            subprocess.SubprocessError("tmux error"),
            mock_success
        ]

        result = backend.wait_for_ready("test:1", timeout=2.0)

        # Should recover from error and detect ready state
        assert result is True


class TestCodexBackendIntegration:
    """Integration tests for CodexBackend."""

    def test_backend_implements_all_required_methods(self):
        """CodexBackend should implement all Backend ABC methods."""
        backend = CodexBackend()

        # Should have all required methods
        assert hasattr(backend, "name")
        assert hasattr(backend, "get_config_dir")
        assert hasattr(backend, "build_command")
        assert hasattr(backend, "wait_for_ready")
        assert hasattr(backend, "get_env_vars")

        # name should be a property
        assert isinstance(type(backend).name, property)

    def test_backend_is_distinct_from_claude(self):
        """CodexBackend should have different configuration from ClaudeBackend."""
        backend = CodexBackend()

        # Config dir should be different from Claude's
        config_dir = backend.get_config_dir()
        assert ".codex" in str(config_dir)
        assert ".claude" not in str(config_dir)

        # Backend name should be different
        assert backend.name != "claude"
        assert backend.name == "codex"
