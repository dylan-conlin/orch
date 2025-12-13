"""Tests for focus integration in work daemon.

Tests the focus.json-based prioritization for the work daemon.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.work_daemon import (
    DaemonConfig,
    FocusConfig,
    ReadyIssue,
    load_focus_config,
    prioritize_issues,
    get_focus_path,
    run_daemon_cycle,
)


class TestFocusConfig:
    """Tests for FocusConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FocusConfig()
        assert config.priority_projects == []
        assert config.priority_labels == []
        assert config.priority_issue_types == []
        assert config.enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = FocusConfig(
            priority_projects=["orch-cli", "beads"],
            priority_labels=["P1", "urgent"],
            priority_issue_types=["bug"],
            enabled=True,
        )
        assert config.priority_projects == ["orch-cli", "beads"]
        assert config.priority_labels == ["P1", "urgent"]
        assert config.priority_issue_types == ["bug"]
        assert config.enabled is True


class TestGetFocusPath:
    """Tests for get_focus_path function."""

    def test_returns_orch_focus_path(self):
        """Test focus path is ~/.orch/focus.json."""
        path = get_focus_path()
        assert path == Path.home() / ".orch" / "focus.json"


class TestLoadFocusConfig:
    """Tests for load_focus_config function."""

    def test_no_focus_file_returns_defaults(self, tmp_path):
        """Test missing focus.json returns default config."""
        with patch("orch.work_daemon.get_focus_path", return_value=tmp_path / "focus.json"):
            config = load_focus_config()
            assert config.priority_projects == []
            assert config.enabled is True

    def test_empty_focus_file_returns_defaults(self, tmp_path):
        """Test empty focus.json returns default config."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text("{}")

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.priority_projects == []
            assert config.enabled is True

    def test_loads_priority_projects(self, tmp_path):
        """Test loading priority_projects from focus.json."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text(json.dumps({
            "priority_projects": ["orch-cli", "beads"]
        }))

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.priority_projects == ["orch-cli", "beads"]

    def test_loads_priority_labels(self, tmp_path):
        """Test loading priority_labels from focus.json."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text(json.dumps({
            "priority_labels": ["P1", "urgent", "security"]
        }))

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.priority_labels == ["P1", "urgent", "security"]

    def test_loads_priority_issue_types(self, tmp_path):
        """Test loading priority_issue_types from focus.json."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text(json.dumps({
            "priority_issue_types": ["bug", "security"]
        }))

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.priority_issue_types == ["bug", "security"]

    def test_loads_enabled_flag(self, tmp_path):
        """Test loading enabled flag from focus.json."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text(json.dumps({
            "enabled": False
        }))

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.enabled is False

    def test_invalid_json_returns_defaults(self, tmp_path):
        """Test invalid JSON in focus.json returns default config."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text("not valid json{")

        with patch("orch.work_daemon.get_focus_path", return_value=focus_file):
            config = load_focus_config()
            assert config.priority_projects == []
            assert config.enabled is True


class TestPrioritizeIssues:
    """Tests for prioritize_issues function."""

    @pytest.fixture
    def sample_issues(self, tmp_path):
        """Create sample issues for testing."""
        proj1 = tmp_path / "orch-cli"
        proj2 = tmp_path / "beads"
        proj3 = tmp_path / "other-project"

        return [
            ReadyIssue(
                id="other-1",
                title="Low priority task",
                issue_type="task",
                labels=["triage:ready"],
                project_path=proj3,
            ),
            ReadyIssue(
                id="orch-1",
                title="Critical bug",
                issue_type="bug",
                labels=["triage:ready", "P1"],
                project_path=proj1,
            ),
            ReadyIssue(
                id="beads-1",
                title="Feature request",
                issue_type="feature",
                labels=["triage:ready"],
                project_path=proj2,
            ),
            ReadyIssue(
                id="orch-2",
                title="Regular feature",
                issue_type="feature",
                labels=["triage:ready", "P2"],
                project_path=proj1,
            ),
        ]

    def test_no_focus_config_preserves_order(self, sample_issues):
        """Test that disabled focus config preserves original order."""
        config = FocusConfig(enabled=False)
        result = prioritize_issues(sample_issues, config)
        assert [i.id for i in result] == ["other-1", "orch-1", "beads-1", "orch-2"]

    def test_default_config_preserves_order(self, sample_issues):
        """Test that default config (no priorities) preserves order."""
        config = FocusConfig()
        result = prioritize_issues(sample_issues, config)
        assert [i.id for i in result] == ["other-1", "orch-1", "beads-1", "orch-2"]

    def test_prioritize_by_project(self, sample_issues):
        """Test issues from priority projects come first."""
        config = FocusConfig(priority_projects=["orch-cli"])
        result = prioritize_issues(sample_issues, config)

        # orch-cli issues should be first
        assert result[0].project_path.name == "orch-cli"
        assert result[1].project_path.name == "orch-cli"
        # Other projects after
        assert result[2].project_path.name in ["beads", "other-project"]
        assert result[3].project_path.name in ["beads", "other-project"]

    def test_prioritize_by_label(self, sample_issues):
        """Test issues with priority labels come first."""
        config = FocusConfig(priority_labels=["P1"])
        result = prioritize_issues(sample_issues, config)

        # P1 issue should be first
        assert result[0].id == "orch-1"
        assert "P1" in result[0].labels

    def test_prioritize_by_issue_type(self, sample_issues):
        """Test issues with priority types come first."""
        config = FocusConfig(priority_issue_types=["bug"])
        result = prioritize_issues(sample_issues, config)

        # Bug should be first
        assert result[0].issue_type == "bug"

    def test_combined_priorities(self, sample_issues):
        """Test combined project + label + type priorities."""
        config = FocusConfig(
            priority_projects=["orch-cli"],
            priority_labels=["P1"],
            priority_issue_types=["bug"],
        )
        result = prioritize_issues(sample_issues, config)

        # orch-1 matches all three: orch-cli project, P1 label, bug type
        # It should definitely be first
        assert result[0].id == "orch-1"

    def test_priority_score_ordering(self, sample_issues):
        """Test that higher priority scores come first."""
        config = FocusConfig(
            priority_projects=["orch-cli", "beads"],
            priority_labels=["P1", "P2"],
        )
        result = prioritize_issues(sample_issues, config)

        # orch-1 has: orch-cli (priority project), P1 (priority label) = 2 matches
        # orch-2 has: orch-cli (priority project), P2 (priority label) = 2 matches
        # beads-1 has: beads (priority project) = 1 match
        # other-1 has: no matches = 0 matches

        # Higher scores first
        top_two = {result[0].id, result[1].id}
        assert top_two == {"orch-1", "orch-2"}

    def test_empty_issues_returns_empty(self):
        """Test empty issue list returns empty."""
        config = FocusConfig(priority_projects=["orch-cli"])
        result = prioritize_issues([], config)
        assert result == []

    def test_stable_sort_preserves_relative_order(self, tmp_path):
        """Test that issues with same priority maintain their relative order."""
        proj = tmp_path / "other"
        issues = [
            ReadyIssue(id="a", title="A", issue_type="task", labels=[], project_path=proj),
            ReadyIssue(id="b", title="B", issue_type="task", labels=[], project_path=proj),
            ReadyIssue(id="c", title="C", issue_type="task", labels=[], project_path=proj),
        ]

        config = FocusConfig(priority_projects=["orch-cli"])  # None of these match
        result = prioritize_issues(issues, config)

        # Order should be preserved (stable sort)
        assert [i.id for i in result] == ["a", "b", "c"]


class TestDaemonCycleFocusIntegration:
    """Tests for focus integration in daemon cycle."""

    def test_daemon_cycle_uses_focus_prioritization(self, tmp_path, capsys):
        """Test that daemon cycle applies focus prioritization to spawns."""
        # Create two projects
        proj1 = tmp_path / "priority-project"
        proj1.mkdir()
        (proj1 / ".beads").mkdir()

        proj2 = tmp_path / "other-project"
        proj2.mkdir()
        (proj2 / ".beads").mkdir()

        # Configure focus to prioritize "priority-project"
        focus_config = FocusConfig(priority_projects=["priority-project"])

        # Set up mock issues - other-project issue comes first in bd ready
        mock_issues_proj1 = [{"id": "p1-1", "title": "Priority issue", "issue_type": "bug", "labels": ["triage:ready"]}]
        mock_issues_proj2 = [{"id": "p2-1", "title": "Other issue", "issue_type": "task", "labels": ["triage:ready"]}]

        def mock_run(*args, **kwargs):
            cwd = kwargs.get("cwd", "")
            result = MagicMock()
            result.returncode = 0

            if "priority-project" in cwd:
                result.stdout = json.dumps(mock_issues_proj1)
            elif "other-project" in cwd:
                result.stdout = json.dumps(mock_issues_proj2)
            else:
                result.stdout = "[]"

            return result

        config = DaemonConfig(
            max_concurrent_agents=1,  # Only spawn 1
            dry_run=True,  # Don't actually spawn
            use_focus=True,
        )

        with patch("orch.work_daemon.get_kb_projects", return_value=[proj2, proj1]):  # Other first
            with patch("subprocess.run", side_effect=mock_run):
                with patch("orch.work_daemon.load_focus_config", return_value=focus_config):
                    with patch("orch.registry.AgentRegistry") as mock_registry_class:
                        mock_registry = MagicMock()
                        mock_registry.list_agents.return_value = []  # No active agents
                        mock_registry_class.return_value = mock_registry

                        stats = run_daemon_cycle(config)

        # Should spawn 1 agent
        assert stats["agents_spawned"] == 1

        # The priority-project issue should have been spawned (due to focus)
        captured = capsys.readouterr()
        assert "p1-1" in captured.out

    def test_daemon_cycle_respects_use_focus_false(self, tmp_path, capsys):
        """Test that daemon cycle skips focus when use_focus=False."""
        proj1 = tmp_path / "priority-project"
        proj1.mkdir()
        (proj1 / ".beads").mkdir()

        proj2 = tmp_path / "other-project"
        proj2.mkdir()
        (proj2 / ".beads").mkdir()

        # Issues with other-project first in the list
        mock_issues_proj1 = [{"id": "p1-1", "title": "Priority issue", "issue_type": "bug", "labels": ["triage:ready"]}]
        mock_issues_proj2 = [{"id": "p2-1", "title": "Other issue", "issue_type": "task", "labels": ["triage:ready"]}]

        def mock_run(*args, **kwargs):
            cwd = kwargs.get("cwd", "")
            result = MagicMock()
            result.returncode = 0

            if "priority-project" in cwd:
                result.stdout = json.dumps(mock_issues_proj1)
            elif "other-project" in cwd:
                result.stdout = json.dumps(mock_issues_proj2)
            else:
                result.stdout = "[]"

            return result

        config = DaemonConfig(
            max_concurrent_agents=1,
            dry_run=True,
            use_focus=False,  # Disable focus
        )

        # Projects returned with other-project first
        with patch("orch.work_daemon.get_kb_projects", return_value=[proj2, proj1]):
            with patch("subprocess.run", side_effect=mock_run):
                with patch("orch.registry.AgentRegistry") as mock_registry_class:
                    mock_registry = MagicMock()
                    mock_registry.list_agents.return_value = []
                    mock_registry_class.return_value = mock_registry

                    stats = run_daemon_cycle(config)

        # Should spawn 1 agent
        assert stats["agents_spawned"] == 1

        # Without focus, the first issue (other-project) should be spawned
        captured = capsys.readouterr()
        assert "p2-1" in captured.out
