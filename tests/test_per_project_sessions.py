"""
Tests for per-project workers sessions feature.

Tests the functionality of creating and managing per-project tmux sessions
(e.g., workers-orch-cli, workers-beads) instead of a single global 'workers' session.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, call
import subprocess


class TestSessionNameDerivation:
    """Tests for session name derivation from project name."""

    def test_get_workers_session_name_simple(self):
        """Test deriving session name from simple project name."""
        from orch.spawn import get_workers_session_name

        result = get_workers_session_name("orch-cli")
        assert result == "workers-orch-cli"

    def test_get_workers_session_name_with_dashes(self):
        """Test deriving session name from project with dashes."""
        from orch.spawn import get_workers_session_name

        result = get_workers_session_name("price-watch")
        assert result == "workers-price-watch"

    def test_get_workers_session_name_single_word(self):
        """Test deriving session name from single-word project."""
        from orch.spawn import get_workers_session_name

        result = get_workers_session_name("beads")
        assert result == "workers-beads"


class TestTmuxinatorConfigGeneration:
    """Tests for tmuxinator config file generation."""

    def test_ensure_tmuxinator_config_creates_file(self, tmp_path):
        """Test that ensure_tmuxinator_config creates YAML file if missing."""
        from orch.tmuxinator import ensure_tmuxinator_config

        # Use tmp_path for tmuxinator config directory
        with patch.object(Path, 'home', return_value=tmp_path):
            config_dir = tmp_path / ".tmuxinator"
            config_dir.mkdir(parents=True, exist_ok=True)

            project_dir = tmp_path / "test-project"
            project_dir.mkdir()

            config_path = ensure_tmuxinator_config("orch-cli", project_dir)

            assert config_path.exists()
            assert config_path.name == "workers-orch-cli.yml"

            content = config_path.read_text()
            assert "name: workers-orch-cli" in content
            assert "startup_window: servers" in content
            assert str(project_dir) in content

    def test_ensure_tmuxinator_config_skips_if_exists(self, tmp_path):
        """Test that ensure_tmuxinator_config doesn't overwrite existing file."""
        from orch.tmuxinator import ensure_tmuxinator_config

        with patch.object(Path, 'home', return_value=tmp_path):
            config_dir = tmp_path / ".tmuxinator"
            config_dir.mkdir(parents=True, exist_ok=True)

            existing_config = config_dir / "workers-orch-cli.yml"
            existing_content = "# Custom config - do not overwrite"
            existing_config.write_text(existing_content)

            project_dir = tmp_path / "test-project"
            project_dir.mkdir()

            config_path = ensure_tmuxinator_config("orch-cli", project_dir)

            # Should return existing path without overwriting
            assert config_path == existing_config
            assert config_path.read_text() == existing_content

    def test_ensure_tmuxinator_config_template_has_servers_window(self, tmp_path):
        """Test that generated config includes pinned servers window at position 0."""
        from orch.tmuxinator import ensure_tmuxinator_config

        with patch.object(Path, 'home', return_value=tmp_path):
            config_dir = tmp_path / ".tmuxinator"
            config_dir.mkdir(parents=True, exist_ok=True)

            project_dir = tmp_path / "test-project"
            project_dir.mkdir()

            config_path = ensure_tmuxinator_config("test-project", project_dir)
            content = config_path.read_text()

            # Verify servers window configuration
            assert "- servers:" in content or "servers:" in content
            assert "startup_window: servers" in content


class TestTmuxinatorSessionStart:
    """Tests for starting workers session via tmuxinator."""

    def test_start_workers_session_creates_new_session(self):
        """Test starting a new workers session via tmuxinator."""
        from orch.tmuxinator import start_workers_session

        with patch('orch.tmuxinator.session_exists', return_value=False), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = start_workers_session("orch-cli")

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "tmuxinator" in call_args
            assert "start" in call_args
            assert "workers-orch-cli" in call_args
            assert "-d" in call_args  # Detached mode

    def test_start_workers_session_reuses_existing(self):
        """Test that existing session is reused without starting new one."""
        from orch.tmuxinator import start_workers_session

        with patch('orch.tmuxinator.session_exists', return_value=True), \
             patch('subprocess.run') as mock_run:

            result = start_workers_session("orch-cli")

            assert result is True
            mock_run.assert_not_called()  # Should not call tmuxinator

    def test_start_workers_session_handles_tmuxinator_failure(self):
        """Test handling tmuxinator start failure."""
        from orch.tmuxinator import start_workers_session

        with patch('orch.tmuxinator.session_exists', return_value=False), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")

            result = start_workers_session("orch-cli")

            assert result is False


class TestTmuxSessionExists:
    """Tests for checking if tmux session exists."""

    def test_session_exists_returns_true_when_found(self):
        """Test session_exists returns True when session is running."""
        from orch.tmuxinator import session_exists

        mock_session = Mock()

        with patch('orch.tmux_utils.find_session', return_value=mock_session):
            result = session_exists("workers-orch-cli")
            assert result is True

    def test_session_exists_returns_false_when_not_found(self):
        """Test session_exists returns False when session not running."""
        from orch.tmuxinator import session_exists

        with patch('orch.tmux_utils.find_session', return_value=None):
            result = session_exists("workers-orch-cli")
            assert result is False


class TestSwitchWorkersClient:
    """Tests for switching workers client to different session."""

    def test_switch_workers_client_finds_and_switches(self):
        """Test switching workers client to new session."""
        from orch.tmuxinator import switch_workers_client

        with patch('subprocess.run') as mock_run:
            # First call: list-clients returns workers client TTY with session name
            # Format: #{client_tty} #{session_name}
            # Second call: switch-client
            mock_run.side_effect = [
                Mock(returncode=0, stdout="/dev/ttys043 workers\n", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            result = switch_workers_client("workers-orch-cli")

            assert result is True
            assert mock_run.call_count == 2

            # Verify list-clients call
            first_call = mock_run.call_args_list[0][0][0]
            assert "list-clients" in first_call

            # Verify switch-client call
            second_call = mock_run.call_args_list[1][0][0]
            assert "switch-client" in second_call
            assert "/dev/ttys043" in second_call
            assert "workers-orch-cli" in second_call

    def test_switch_workers_client_no_client_attached(self):
        """Test graceful handling when no workers client attached."""
        from orch.tmuxinator import switch_workers_client

        with patch('subprocess.run') as mock_run:
            # list-clients returns empty (no workers client)
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = switch_workers_client("workers-orch-cli")

            # Should return False but not error
            assert result is False
            # Should only call list-clients, not switch-client
            assert mock_run.call_count == 1

    def test_switch_workers_client_handles_switch_failure(self):
        """Test handling when switch-client command fails."""
        from orch.tmuxinator import switch_workers_client

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="/dev/ttys043\n", stderr=""),
                Mock(returncode=1, stdout="", stderr="can't switch"),
            ]

            result = switch_workers_client("workers-orch-cli")

            # Should return False on switch failure
            assert result is False


class TestSpawnInTmuxPerProjectSession:
    """Tests for spawn_in_tmux using per-project sessions."""

    def test_spawn_uses_per_project_session(self, tmp_path):
        """Test that spawn creates agent in per-project session."""
        from orch.spawn import spawn_in_tmux, SpawnConfig
        from orch.backends import ClaudeBackend

        project_dir = tmp_path / "orch-cli"
        project_dir.mkdir()
        (project_dir / ".orch" / "workspace").mkdir(parents=True)

        config = SpawnConfig(
            task="Test task",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        mock_session = Mock()
        mock_backend = Mock(spec=ClaudeBackend)
        mock_backend.name = "claude"
        mock_backend.wait_for_ready.return_value = True
        mock_backend.get_env_vars.return_value = {"CLAUDE_CONTEXT": "worker"}
        mock_backend.build_command.return_value = "claude 'test'"

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.spawn.ensure_tmuxinator_config') as mock_ensure_config, \
             patch('orch.spawn.start_workers_session', return_value=True), \
             patch('orch.spawn.switch_workers_client', return_value=True), \
             patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
             patch('subprocess.run') as mock_run, \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('pathlib.Path.write_text'):

            # Configure subprocess mock
            def subprocess_side_effect(args, **kwargs):
                if 'new-window' in args:
                    return Mock(returncode=0, stdout="5:@1234\n", stderr="")
                if 'capture-pane' in args:
                    return Mock(returncode=0, stdout="> prompt\n", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            result = spawn_in_tmux(config)

            # Verify per-project session was used
            assert result['window'].startswith("workers-orch-cli:")
            mock_ensure_config.assert_called_once()

    def test_spawn_switches_workers_client_after_spawn(self, tmp_path):
        """Test that workers client is switched after successful spawn."""
        from orch.spawn import spawn_in_tmux, SpawnConfig
        from orch.backends import ClaudeBackend

        project_dir = tmp_path / "orch-cli"
        project_dir.mkdir()
        (project_dir / ".orch" / "workspace").mkdir(parents=True)

        config = SpawnConfig(
            task="Test task",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        mock_session = Mock()
        mock_backend = Mock(spec=ClaudeBackend)
        mock_backend.name = "claude"
        mock_backend.wait_for_ready.return_value = True
        mock_backend.get_env_vars.return_value = {"CLAUDE_CONTEXT": "worker"}
        mock_backend.build_command.return_value = "claude 'test'"

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.spawn.ensure_tmuxinator_config'), \
             patch('orch.spawn.start_workers_session', return_value=True), \
             patch('orch.spawn.switch_workers_client') as mock_switch, \
             patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
             patch('subprocess.run') as mock_run, \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('pathlib.Path.write_text'):

            def subprocess_side_effect(args, **kwargs):
                if 'new-window' in args:
                    return Mock(returncode=0, stdout="5:@1234\n", stderr="")
                if 'capture-pane' in args:
                    return Mock(returncode=0, stdout="> prompt\n", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            spawn_in_tmux(config)

            # Verify switch was called with per-project session
            mock_switch.assert_called_once_with("workers-orch-cli")

    def test_spawn_continues_if_switch_fails(self, tmp_path):
        """Test that spawn completes even if client switch fails."""
        from orch.spawn import spawn_in_tmux, SpawnConfig
        from orch.backends import ClaudeBackend

        project_dir = tmp_path / "orch-cli"
        project_dir.mkdir()
        (project_dir / ".orch" / "workspace").mkdir(parents=True)

        config = SpawnConfig(
            task="Test task",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        mock_session = Mock()
        mock_backend = Mock(spec=ClaudeBackend)
        mock_backend.name = "claude"
        mock_backend.wait_for_ready.return_value = True
        mock_backend.get_env_vars.return_value = {"CLAUDE_CONTEXT": "worker"}
        mock_backend.build_command.return_value = "claude 'test'"

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.spawn.ensure_tmuxinator_config'), \
             patch('orch.spawn.start_workers_session', return_value=True), \
             patch('orch.spawn.switch_workers_client', return_value=False), \
             patch('orch.spawn.ClaudeBackend', return_value=mock_backend), \
             patch('subprocess.run') as mock_run, \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('pathlib.Path.write_text'):

            def subprocess_side_effect(args, **kwargs):
                if 'new-window' in args:
                    return Mock(returncode=0, stdout="5:@1234\n", stderr="")
                if 'capture-pane' in args:
                    return Mock(returncode=0, stdout="> prompt\n", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            # Should not raise even though switch failed
            result = spawn_in_tmux(config)
            assert result is not None
            assert 'window' in result


class TestEdgeCases:
    """Tests for edge cases in per-project session handling."""

    def test_handles_project_name_with_special_chars(self):
        """Test session name derivation with special characters in project name."""
        from orch.spawn import get_workers_session_name

        # Underscores should be preserved
        result = get_workers_session_name("my_project_name")
        assert result == "workers-my_project_name"

    def test_tmuxinator_config_creates_parent_directory(self, tmp_path):
        """Test that ensure_tmuxinator_config creates .tmuxinator if missing."""
        from orch.tmuxinator import ensure_tmuxinator_config

        with patch.object(Path, 'home', return_value=tmp_path):
            # Don't create .tmuxinator directory - it should be created
            project_dir = tmp_path / "test-project"
            project_dir.mkdir()

            config_path = ensure_tmuxinator_config("test-project", project_dir)

            assert config_path.parent.exists()
            assert config_path.parent.name == ".tmuxinator"
