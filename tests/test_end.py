"""Tests for orch end command - clean session exit with knowledge capture gates."""

import json
import os
import pytest
from click.testing import CliRunner
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.cli import cli


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_kn_dir(tmp_path):
    """Create a temporary .kn directory with entries.jsonl."""
    kn_dir = tmp_path / ".kn"
    kn_dir.mkdir()
    return kn_dir


@pytest.fixture
def session_file(tmp_path):
    """Create a temporary session file."""
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    session_file = orch_dir / "current-session.json"
    # Set session start to 1 hour ago
    started_at = (datetime.now() - timedelta(hours=1)).isoformat()
    session_file.write_text(json.dumps({"started_at": started_at}))
    return session_file


class TestEndCommandExists:
    """Test that orch end command exists and has proper help."""

    def test_end_command_exists(self, cli_runner):
        """Test that end command is registered."""
        result = cli_runner.invoke(cli, ['end', '--help'])
        assert result.exit_code == 0
        assert 'end' in result.output.lower() or 'session' in result.output.lower()

    def test_end_command_help_shows_purpose(self, cli_runner):
        """Test that help shows the command purpose."""
        result = cli_runner.invoke(cli, ['end', '--help'])
        assert result.exit_code == 0
        # Should mention knowledge capture or session exit
        assert 'knowledge' in result.output.lower() or 'exit' in result.output.lower()


class TestTmuxDetection:
    """Test tmux context detection."""

    def test_not_in_tmux_shows_error(self, cli_runner):
        """Test that running outside tmux shows error."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TMUX env var to simulate not being in tmux
            env = os.environ.copy()
            env.pop('TMUX', None)
            with patch.dict(os.environ, env, clear=True):
                result = cli_runner.invoke(cli, ['end'])
                # Should show error about tmux
                assert 'tmux' in result.output.lower() or result.exit_code != 0

    def test_in_tmux_proceeds(self, cli_runner):
        """Test that running inside tmux proceeds past tmux check."""
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id') as mock_pane:
                mock_pane.return_value = '%0'
                with patch('orch.end.get_kn_entries_since') as mock_kn:
                    mock_kn.return_value = []
                    with patch('orch.end.send_exit_to_pane') as mock_exit:
                        mock_exit.return_value = True
                        result = cli_runner.invoke(cli, ['end', '-y'])
                        # Should not show tmux error
                        assert 'requires tmux' not in result.output.lower()


class TestSessionTypeDetection:
    """Test session type (orchestrator vs worker) detection."""

    def test_detects_orchestrator_context(self, tmp_path):
        """Test detection of orchestrator session."""
        from orch.end import detect_session_type

        # Create orchestrator context: has .orch but NOT in workspace
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()

        result = detect_session_type(str(tmp_path))
        assert result == "orchestrator"

    def test_detects_worker_context(self, tmp_path):
        """Test detection of worker session."""
        from orch.end import detect_session_type

        # Create worker context: in .orch/workspace/
        workspace_dir = tmp_path / ".orch" / "workspace" / "agent-123"
        workspace_dir.mkdir(parents=True)

        result = detect_session_type(str(workspace_dir))
        assert result == "worker"

    def test_unknown_context_when_no_orch(self, tmp_path):
        """Test unknown context when no .orch directory."""
        from orch.end import detect_session_type

        result = detect_session_type(str(tmp_path))
        assert result == "unknown"


class TestKnEntryChecking:
    """Test knowledge entry checking."""

    def test_no_entries_returns_empty(self, temp_kn_dir):
        """Test that no entries returns empty list."""
        from orch.end import get_kn_entries_since

        entries_file = temp_kn_dir / "entries.jsonl"
        entries_file.write_text("")

        since = datetime.now() - timedelta(hours=1)
        result = get_kn_entries_since(since, str(temp_kn_dir.parent))
        assert result == []

    def test_finds_entries_since_session_start(self, temp_kn_dir):
        """Test that entries since session start are found."""
        from orch.end import get_kn_entries_since

        entries_file = temp_kn_dir / "entries.jsonl"
        # Write entry from 30 mins ago
        entry_time = (datetime.now() - timedelta(minutes=30)).isoformat()
        entry = {"id": "test-1", "type": "decision", "content": "test", "created_at": entry_time}
        entries_file.write_text(json.dumps(entry) + "\n")

        # Session started 1 hour ago
        since = datetime.now() - timedelta(hours=1)
        result = get_kn_entries_since(since, str(temp_kn_dir.parent))
        assert len(result) == 1
        assert result[0]["id"] == "test-1"

    def test_ignores_entries_before_session_start(self, temp_kn_dir):
        """Test that entries before session start are ignored."""
        from orch.end import get_kn_entries_since

        entries_file = temp_kn_dir / "entries.jsonl"
        # Write entry from 2 hours ago
        entry_time = (datetime.now() - timedelta(hours=2)).isoformat()
        entry = {"id": "old-1", "type": "decision", "content": "old", "created_at": entry_time}
        entries_file.write_text(json.dumps(entry) + "\n")

        # Session started 1 hour ago
        since = datetime.now() - timedelta(hours=1)
        result = get_kn_entries_since(since, str(temp_kn_dir.parent))
        assert len(result) == 0

    def test_missing_kn_dir_returns_empty(self, tmp_path):
        """Test that missing .kn directory returns empty list."""
        from orch.end import get_kn_entries_since

        since = datetime.now() - timedelta(hours=1)
        result = get_kn_entries_since(since, str(tmp_path))
        assert result == []


class TestSoftGatePrompt:
    """Test soft gate prompt when no knowledge captured."""

    def test_no_entries_shows_warning(self, cli_runner):
        """Test that no entries shows warning message."""
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id', return_value='%0'):
                with patch('orch.end.get_kn_entries_since', return_value=[]):
                    with patch('orch.end.get_session_start_time', return_value=datetime.now()):
                        with patch('orch.end.send_exit_to_pane', return_value=True):
                            # Without -y flag, should show warning
                            result = cli_runner.invoke(cli, ['end'], input='n\n')
                            # Should show knowledge capture warning
                            assert 'knowledge' in result.output.lower() or 'kn' in result.output.lower()

    def test_has_entries_shows_count(self, cli_runner):
        """Test that having entries shows count."""
        entries = [
            {"id": "1", "type": "decision", "content": "test"},
            {"id": "2", "type": "constraint", "content": "test2"},
        ]
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id', return_value='%0'):
                with patch('orch.end.get_kn_entries_since', return_value=entries):
                    with patch('orch.end.get_session_start_time', return_value=datetime.now()):
                        with patch('orch.end.send_exit_to_pane', return_value=True):
                            result = cli_runner.invoke(cli, ['end', '-y'])
                            # Should show entry count
                            assert '2' in result.output or 'entries' in result.output.lower()

    def test_skip_prompt_flag_bypasses_warning(self, cli_runner):
        """Test that -y flag skips the prompt."""
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id', return_value='%0'):
                with patch('orch.end.get_kn_entries_since', return_value=[]):
                    with patch('orch.end.get_session_start_time', return_value=datetime.now()):
                        with patch('orch.end.send_exit_to_pane', return_value=True):
                            result = cli_runner.invoke(cli, ['end', '-y'])
                            # Should not prompt for confirmation
                            assert 'y/N' not in result.output or result.exit_code == 0


class TestExitInjection:
    """Test /exit command injection via tmux."""

    def test_sends_exit_command(self, cli_runner):
        """Test that /exit is sent via tmux send-keys."""
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id', return_value='%0'):
                with patch('orch.end.get_kn_entries_since', return_value=[]):
                    with patch('orch.end.get_session_start_time', return_value=datetime.now()):
                        with patch('orch.end.send_exit_to_pane') as mock_exit:
                            mock_exit.return_value = True
                            result = cli_runner.invoke(cli, ['end', '-y'])
                            # Should have called send_exit_to_pane
                            mock_exit.assert_called_once()

    def test_reports_exit_sent(self, cli_runner):
        """Test that successful exit sends confirmation."""
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with patch('orch.end.get_current_pane_id', return_value='%0'):
                with patch('orch.end.get_kn_entries_since', return_value=[]):
                    with patch('orch.end.get_session_start_time', return_value=datetime.now()):
                        with patch('orch.end.send_exit_to_pane', return_value=True):
                            result = cli_runner.invoke(cli, ['end', '-y'])
                            # Should confirm /exit was sent
                            assert '/exit' in result.output.lower() or 'sending' in result.output.lower()
