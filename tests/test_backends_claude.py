"""Tests for ClaudeBackend implementation."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.backends.claude import (
    ClaudeBackend,
    BUILTIN_MCP_SERVERS,
    resolve_mcp_servers,
)
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
        assert "--dangerously-skip-permissions" in command
        # Should contain -- separator before prompt
        assert " -- " in command

    def test_build_command_separator_before_prompt(self):
        """build_command should include -- separator before prompt to prevent variadic option consumption."""
        backend = ClaudeBackend()
        prompt = "Test task"

        command = backend.build_command(prompt)

        # The -- should come before the prompt in the command
        # This is critical for variadic options like --mcp-config <configs...>
        separator_pos = command.find(" -- ")
        prompt_pos = command.find("Test task")

        assert separator_pos != -1, "Command should contain -- separator"
        assert prompt_pos != -1, "Command should contain prompt"
        assert separator_pos < prompt_pos, "-- separator should come before prompt"

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


class TestResolveMcpServers:
    """Tests for resolve_mcp_servers() function."""

    def test_resolve_builtin_server(self):
        """Should resolve built-in MCP servers like playwright."""
        result = resolve_mcp_servers("playwright")

        assert result is not None
        config = json.loads(result)
        assert "mcpServers" in config
        assert "playwright" in config["mcpServers"]
        assert config["mcpServers"]["playwright"] == BUILTIN_MCP_SERVERS["playwright"]

    def test_resolve_multiple_builtin_servers(self):
        """Should resolve multiple built-in servers."""
        result = resolve_mcp_servers("playwright,browser-use")

        assert result is not None
        config = json.loads(result)
        assert "mcpServers" in config
        assert "playwright" in config["mcpServers"]
        assert "browser-use" in config["mcpServers"]

    def test_resolve_empty_string_returns_none(self):
        """Should return None for empty string."""
        result = resolve_mcp_servers("")
        assert result is None

    def test_resolve_none_returns_none(self):
        """Should return None for None input."""
        result = resolve_mcp_servers(None)
        assert result is None

    def test_resolve_unknown_server_warns(self):
        """Should warn but not fail for unknown servers."""
        # Use a mock to capture the warning output
        import click
        with patch.object(click, 'echo') as mock_echo:
            result = resolve_mcp_servers("unknown-server")

            # Should have printed warning
            mock_echo.assert_called()
            warning_calls = [str(call) for call in mock_echo.call_args_list]
            assert any("Unknown MCP server" in str(call) for call in warning_calls)

            # Should return None since no valid servers
            assert result is None

    def test_resolve_mixed_known_unknown_servers(self):
        """Should resolve known servers and warn about unknown ones."""
        import click
        with patch.object(click, 'echo'):
            result = resolve_mcp_servers("playwright,unknown-server")

        # Should still include the known server
        assert result is not None
        config = json.loads(result)
        assert "playwright" in config["mcpServers"]
        assert "unknown-server" not in config["mcpServers"]

    def test_resolve_user_config_file(self, tmp_path):
        """Should use user-defined config file if it exists."""
        # Create a mock ~/.orch/mcp directory
        mcp_dir = tmp_path / ".orch" / "mcp"
        mcp_dir.mkdir(parents=True)

        # Create user config file
        user_config = {"command": "custom-mcp", "args": ["--custom"]}
        user_config_file = mcp_dir / "custom-server.json"
        user_config_file.write_text(json.dumps(user_config))

        # Patch Path.home() to use tmp_path
        with patch.object(Path, 'home', return_value=tmp_path):
            result = resolve_mcp_servers("custom-server")

        assert result is not None
        config = json.loads(result)
        assert "custom-server" in config["mcpServers"]
        assert config["mcpServers"]["custom-server"]["command"] == "custom-mcp"

    def test_resolve_whitespace_handling(self):
        """Should handle whitespace in comma-separated list."""
        result = resolve_mcp_servers("playwright , browser-use")

        assert result is not None
        config = json.loads(result)
        assert "playwright" in config["mcpServers"]
        assert "browser-use" in config["mcpServers"]


class TestBuildCommandWithMcp:
    """Tests for build_command with MCP server options."""

    def test_build_command_with_mcp_servers(self):
        """build_command should include --mcp-config when mcp_servers provided."""
        backend = ClaudeBackend()
        prompt = "Test task"
        options = {"mcp_servers": "playwright"}

        command = backend.build_command(prompt, options)

        # Should contain --mcp-config flag
        assert "--mcp-config" in command
        # Should contain JSON config (quoted)
        assert "mcpServers" in command

    def test_build_command_without_mcp_servers(self):
        """build_command should NOT include --mcp-config when mcp_servers not provided."""
        backend = ClaudeBackend()
        prompt = "Test task"

        command = backend.build_command(prompt)

        # Should NOT contain --mcp-config flag
        assert "--mcp-config" not in command

    def test_build_command_with_model_and_mcp(self):
        """build_command should handle both model and mcp_servers options."""
        backend = ClaudeBackend()
        prompt = "Test task"
        options = {"model": "opus", "mcp_servers": "playwright"}

        command = backend.build_command(prompt, options)

        # Should contain both flags
        assert "--model" in command
        assert "--mcp-config" in command

    def test_build_command_with_workspace_path_writes_file(self, tmp_path):
        """build_command should write MCP config to file when workspace_path provided."""
        backend = ClaudeBackend()
        prompt = "Test task"
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir(parents=True)

        options = {"mcp_servers": "playwright", "workspace_path": workspace_path}

        command = backend.build_command(prompt, options)

        # Should contain --mcp-config flag with file path
        assert "--mcp-config" in command
        # Should reference the config file path
        expected_config_file = workspace_path / "mcp-config.json"
        assert expected_config_file.exists()

        # Verify file content
        config = json.loads(expected_config_file.read_text())
        assert "mcpServers" in config
        assert "playwright" in config["mcpServers"]


class TestResolveMcpServersWithWorkspacePath:
    """Tests for resolve_mcp_servers() with workspace_path parameter."""

    def test_resolve_with_workspace_path_writes_file(self, tmp_path):
        """Should write config to file when workspace_path provided."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir(parents=True)

        result = resolve_mcp_servers("playwright", workspace_path)

        # Should return file path, not JSON string
        assert result is not None
        assert str(workspace_path) in result
        assert result.endswith("mcp-config.json")

        # File should exist with valid content
        config_file = Path(result)
        assert config_file.exists()

        config = json.loads(config_file.read_text())
        assert "mcpServers" in config
        assert "playwright" in config["mcpServers"]

    def test_resolve_without_workspace_path_returns_json(self):
        """Should return JSON string when workspace_path not provided (backward compat)."""
        result = resolve_mcp_servers("playwright")

        # Should return JSON string
        assert result is not None
        config = json.loads(result)  # Should be valid JSON
        assert "mcpServers" in config

    def test_resolve_writes_formatted_json(self, tmp_path):
        """Config file should be human-readable with indentation."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir(parents=True)

        result = resolve_mcp_servers("playwright,browser-use", workspace_path)

        # Read the file content directly
        config_file = Path(result)
        content = config_file.read_text()

        # Should be indented (multiline)
        assert "\n" in content
        # Should contain proper JSON formatting
        assert '"mcpServers"' in content
