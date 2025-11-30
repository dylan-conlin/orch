"""Tests for orch auto autonomous execution command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.features import Feature


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with .orch folder."""
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    return tmp_path


@pytest.fixture
def features_json_with_pending(tmp_project):
    """Create backlog.json with pending features."""
    features_data = {
        "version": "1.0",
        "features": [
            {
                "id": "feature-a",
                "description": "Feature A to implement",
                "skill": "feature-impl",
                "status": "pending",
                "category": "feature",
                "skill_args": {},
                "verification": None,
                "context_ref": None,
                "workspace": None,
                "started_at": None,
                "completed_at": None
            },
            {
                "id": "feature-b",
                "description": "Feature B to implement",
                "skill": "investigation",
                "status": "pending",
                "category": "feature",
                "skill_args": {},
                "verification": None,
                "context_ref": None,
                "workspace": None,
                "started_at": None,
                "completed_at": None
            }
        ]
    }

    # Use backlog.json (renamed from features.json)
    features_path = tmp_project / ".orch" / "backlog.json"
    with features_path.open('w') as f:
        json.dump(features_data, f, indent=2)

    return tmp_project


@pytest.fixture
def features_json_all_complete(tmp_project):
    """Create backlog.json with all features complete."""
    features_data = {
        "version": "1.0",
        "features": [
            {
                "id": "feature-done",
                "description": "Already completed feature",
                "skill": "feature-impl",
                "status": "complete",
                "category": "feature",
                "skill_args": {},
                "verification": None,
                "context_ref": None,
                "workspace": ".orch/workspace/test",
                "started_at": "2025-11-27T10:00:00",
                "completed_at": "2025-11-27T12:00:00"
            }
        ]
    }

    # Use backlog.json (renamed from features.json)
    features_path = tmp_project / ".orch" / "backlog.json"
    with features_path.open('w') as f:
        json.dump(features_data, f, indent=2)

    return tmp_project


@pytest.fixture
def features_json_all_blocked(tmp_project):
    """Create backlog.json with all features blocked."""
    features_data = {
        "version": "1.0",
        "features": [
            {
                "id": "blocked-feature",
                "description": "Blocked feature",
                "skill": "feature-impl",
                "status": "blocked",
                "category": "feature",
                "skill_args": {},
                "verification": None,
                "context_ref": None,
                "workspace": None,
                "started_at": None,
                "completed_at": None
            }
        ]
    }

    # Use backlog.json (renamed from features.json)
    features_path = tmp_project / ".orch" / "backlog.json"
    with features_path.open('w') as f:
        json.dump(features_data, f, indent=2)

    return tmp_project


# ============================================================================
# Command existence tests
# ============================================================================

class TestAutoCommandExists:
    """Tests that orch auto command exists and has expected options."""

    def test_auto_command_exists(self, cli_runner):
        """Test that 'orch auto' command exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert result.exit_code == 0
        assert 'Autonomous feature execution loop' in result.output

    def test_auto_has_project_option(self, cli_runner):
        """Test that --project option exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert '--project' in result.output

    def test_auto_has_max_agents_option(self, cli_runner):
        """Test that --max-agents option exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert '--max-agents' in result.output

    def test_auto_has_dry_run_option(self, cli_runner):
        """Test that --dry-run option exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert '--dry-run' in result.output

    def test_auto_has_once_option(self, cli_runner):
        """Test that --once option exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert '--once' in result.output

    def test_auto_has_interval_option(self, cli_runner):
        """Test that --interval option exists."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['auto', '--help'])
        assert '--interval' in result.output


# ============================================================================
# Error handling tests
# ============================================================================

class TestAutoErrorHandling:
    """Tests for error handling in orch auto."""

    def test_auto_no_features_json(self, cli_runner, tmp_project, monkeypatch):
        """Test orch auto fails gracefully when no backlog.json exists."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_project)

        # Mock detect_project_from_cwd to return the temp project
        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', tmp_project)

            # Mock AgentRegistry to return empty list
            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code != 0
        assert 'No backlog.json found' in result.output

    def test_auto_project_not_found(self, cli_runner, tmp_path, monkeypatch):
        """Test orch auto fails when project not found."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_path)

        # Mock get_project_dir to return None
        with patch('orch.spawn.get_project_dir') as mock_get:
            mock_get.return_value = None

            result = cli_runner.invoke(cli, ['auto', '--project', 'nonexistent'])

        assert result.exit_code != 0
        assert 'not found' in result.output


# ============================================================================
# Dry-run mode tests
# ============================================================================

class TestAutoDryRun:
    """Tests for dry-run mode."""

    def test_auto_dry_run_shows_pending_features(self, cli_runner, features_json_with_pending, monkeypatch):
        """Test dry-run shows pending features without spawning."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_with_pending)

        # Mock project detection
        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_with_pending)

            # Mock AgentRegistry
            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        assert 'feature-a' in result.output
        assert 'Would spawn agent' in result.output

    def test_auto_dry_run_does_not_spawn(self, cli_runner, features_json_with_pending, monkeypatch):
        """Test dry-run does not call spawn_with_skill."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_with_pending)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_with_pending)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                with patch('orch.spawn.spawn_with_skill') as mock_spawn:
                    result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

                    # spawn_with_skill should NOT be called in dry-run
                    mock_spawn.assert_not_called()

        assert result.exit_code == 0


# ============================================================================
# All complete exit condition tests
# ============================================================================

class TestAutoExitConditions:
    """Tests for exit conditions."""

    def test_auto_exits_when_all_complete(self, cli_runner, features_json_all_complete, monkeypatch):
        """Test orch auto exits when all features are complete."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_all_complete)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_all_complete)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code == 0
        assert 'All features complete' in result.output

    def test_auto_reports_blocked_features(self, cli_runner, features_json_all_blocked, monkeypatch):
        """Test orch auto reports blocked features when exiting."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_all_blocked)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_all_blocked)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code == 0
        assert 'blocked' in result.output.lower()


# ============================================================================
# Max agents limit tests
# ============================================================================

class TestAutoMaxAgents:
    """Tests for max-agents limit."""

    def test_auto_respects_max_agents_limit(self, cli_runner, features_json_with_pending, monkeypatch):
        """Test orch auto respects --max-agents limit."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_with_pending)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_with_pending)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                # Simulate 2 running agents
                mock_registry.list_agents.return_value = [
                    {'id': 'agent-1', 'project_dir': str(features_json_with_pending), 'status': 'active'},
                    {'id': 'agent-2', 'project_dir': str(features_json_with_pending), 'status': 'active'}
                ]
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run', '--max-agents', '2'])

        assert result.exit_code == 0
        # Should report at capacity
        assert 'At capacity' in result.output or 'Waiting' in result.output


# ============================================================================
# Output format tests
# ============================================================================

class TestAutoOutput:
    """Tests for output formatting."""

    def test_auto_shows_startup_info(self, cli_runner, features_json_with_pending, monkeypatch):
        """Test orch auto shows startup information."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_with_pending)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_with_pending)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code == 0
        assert 'Autonomous mode' in result.output
        assert 'Max agents' in result.output

    def test_auto_shows_feature_count(self, cli_runner, features_json_with_pending, monkeypatch):
        """Test orch auto shows feature counts."""
        from orch.cli import cli

        monkeypatch.chdir(features_json_with_pending)

        with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
            mock_detect.return_value = ('test-project', features_json_with_pending)

            with patch('orch.cli.AgentRegistry') as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_agents.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = cli_runner.invoke(cli, ['auto', '--once', '--dry-run'])

        assert result.exit_code == 0
        assert 'pending' in result.output.lower()
