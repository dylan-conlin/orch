"""Tests for work daemon module.

Tests the daemon that autonomously processes beads issues.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.work_daemon import (
    DaemonConfig,
    ReadyIssue,
    get_ready_issues_for_project,
    get_all_ready_issues,
    count_active_agents,
    spawn_issue,
    run_daemon_cycle,
)


class TestDaemonConfig:
    """Tests for DaemonConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DaemonConfig()
        assert config.poll_interval_seconds == 60
        assert config.max_concurrent_agents == 3
        assert config.required_label == "triage:ready"
        assert config.dry_run is False
        assert config.verbose is False
        assert config.use_focus is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DaemonConfig(
            poll_interval_seconds=30,
            max_concurrent_agents=5,
            required_label="actionable",
            dry_run=True,
            verbose=True,
            use_focus=False,
        )
        assert config.poll_interval_seconds == 30
        assert config.max_concurrent_agents == 5
        assert config.required_label == "actionable"
        assert config.dry_run is True
        assert config.verbose is True
        assert config.use_focus is False


class TestReadyIssue:
    """Tests for ReadyIssue dataclass."""

    def test_create_ready_issue(self, tmp_path):
        """Test creating a ReadyIssue."""
        issue = ReadyIssue(
            id="proj-abc",
            title="Fix bug",
            issue_type="bug",
            labels=["triage:ready", "P1"],
            project_path=tmp_path,
        )
        assert issue.id == "proj-abc"
        assert issue.title == "Fix bug"
        assert issue.issue_type == "bug"
        assert "triage:ready" in issue.labels
        assert issue.project_path == tmp_path


class TestGetReadyIssuesForProject:
    """Tests for get_ready_issues_for_project."""

    def test_no_beads_dir(self, tmp_path):
        """Test project without .beads directory returns empty."""
        issues = get_ready_issues_for_project(tmp_path)
        assert issues == []

    def test_bd_not_found(self, tmp_path):
        """Test graceful handling when bd CLI not found."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            issues = get_ready_issues_for_project(tmp_path)
            assert issues == []

    def test_bd_returns_issues(self, tmp_path):
        """Test parsing issues from bd ready output."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        mock_issues = [
            {
                "id": "proj-abc",
                "title": "Fix bug",
                "issue_type": "bug",
                "labels": ["triage:ready"],
            },
            {
                "id": "proj-def",
                "title": "Add feature",
                "issue_type": "feature",
                "labels": [],  # No triage:ready label
            },
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_issues)

        with patch("subprocess.run", return_value=mock_result):
            # Without label filter - get all
            issues = get_ready_issues_for_project(tmp_path, required_label=None)
            assert len(issues) == 2

            # With label filter - get only matching
            issues = get_ready_issues_for_project(tmp_path, required_label="triage:ready")
            assert len(issues) == 1
            assert issues[0].id == "proj-abc"

    def test_bd_timeout(self, tmp_path):
        """Test graceful handling of bd timeout."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bd", 30)):
            issues = get_ready_issues_for_project(tmp_path)
            assert issues == []


class TestGetAllReadyIssues:
    """Tests for get_all_ready_issues."""

    def test_multiple_projects(self, tmp_path):
        """Test collecting issues from multiple projects."""
        proj1 = tmp_path / "proj1"
        proj1.mkdir()
        (proj1 / ".beads").mkdir()

        proj2 = tmp_path / "proj2"
        proj2.mkdir()
        (proj2 / ".beads").mkdir()

        def mock_run(*args, **kwargs):
            cwd = kwargs.get("cwd", "")
            result = MagicMock()
            result.returncode = 0

            if "proj1" in cwd:
                result.stdout = json.dumps([{"id": "p1-abc", "title": "Issue 1", "issue_type": "bug", "labels": ["triage:ready"]}])
            elif "proj2" in cwd:
                result.stdout = json.dumps([{"id": "p2-xyz", "title": "Issue 2", "issue_type": "feature", "labels": ["triage:ready"]}])
            else:
                result.stdout = "[]"

            return result

        with patch("subprocess.run", side_effect=mock_run):
            issues = get_all_ready_issues([proj1, proj2], required_label="triage:ready")
            assert len(issues) == 2
            ids = {i.id for i in issues}
            assert "p1-abc" in ids
            assert "p2-xyz" in ids


class TestCountActiveAgents:
    """Tests for count_active_agents."""

    def test_count_active(self):
        """Test counting active agents from registry."""
        mock_agents = [
            {"id": "agent-1", "status": "active"},
            {"id": "agent-2", "status": "active"},
            {"id": "agent-3", "status": "completed"},
            {"id": "agent-4", "status": "abandoned"},
        ]

        with patch("orch.registry.AgentRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.list_agents.return_value = mock_agents
            mock_registry_class.return_value = mock_registry

            count = count_active_agents()
            assert count == 2

    def test_registry_error(self):
        """Test graceful handling of registry errors."""
        with patch("orch.registry.AgentRegistry", side_effect=Exception("Registry error")):
            count = count_active_agents()
            assert count == 0


class TestSpawnIssue:
    """Tests for spawn_issue."""

    def test_dry_run(self, tmp_path, capsys):
        """Test dry run doesn't actually spawn."""
        issue = ReadyIssue(
            id="proj-abc",
            title="Fix bug",
            issue_type="bug",
            labels=["triage:ready"],
            project_path=tmp_path,
        )

        result = spawn_issue(issue, dry_run=True)
        assert result is True

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "proj-abc" in captured.out

    def test_spawn_success(self, tmp_path, capsys):
        """Test successful spawn."""
        issue = ReadyIssue(
            id="proj-abc",
            title="Fix bug",
            issue_type="bug",
            labels=["triage:ready"],
            project_path=tmp_path,
        )

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = spawn_issue(issue, dry_run=False)
            assert result is True

        captured = capsys.readouterr()
        assert "Spawned" in captured.out

    def test_spawn_failure(self, tmp_path, capsys):
        """Test spawn failure handling."""
        issue = ReadyIssue(
            id="proj-abc",
            title="Fix bug",
            issue_type="bug",
            labels=["triage:ready"],
            project_path=tmp_path,
        )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"

        with patch("subprocess.run", return_value=mock_result):
            result = spawn_issue(issue, dry_run=False)
            assert result is False

        captured = capsys.readouterr()
        assert "Failed" in captured.out


class TestRunDaemonCycle:
    """Tests for run_daemon_cycle."""

    def test_no_projects(self):
        """Test cycle with no projects."""
        config = DaemonConfig(verbose=True)

        with patch("orch.work_daemon.get_kb_projects", return_value=[]):
            stats = run_daemon_cycle(config)
            assert stats["projects_polled"] == 0
            assert stats["issues_found"] == 0
            assert stats["agents_spawned"] == 0

    def test_no_ready_issues(self, tmp_path):
        """Test cycle with projects but no ready issues."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".beads").mkdir()

        config = DaemonConfig(verbose=True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"

        with patch("orch.work_daemon.get_kb_projects", return_value=[proj]):
            with patch("subprocess.run", return_value=mock_result):
                stats = run_daemon_cycle(config)
                assert stats["projects_polled"] == 1
                assert stats["issues_found"] == 0
                assert stats["agents_spawned"] == 0

    def test_respects_concurrency_limit(self, tmp_path):
        """Test that daemon respects max concurrent agents."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".beads").mkdir()

        config = DaemonConfig(max_concurrent_agents=1, dry_run=True)

        mock_issues = [
            {"id": "p-1", "title": "Issue 1", "issue_type": "bug", "labels": ["triage:ready"]},
            {"id": "p-2", "title": "Issue 2", "issue_type": "feature", "labels": ["triage:ready"]},
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_issues)

        # 1 active agent, max is 1, so 0 slots available
        mock_agents = [{"id": "agent-1", "status": "active"}]

        with patch("orch.work_daemon.get_kb_projects", return_value=[proj]):
            with patch("subprocess.run", return_value=mock_result):
                with patch("orch.registry.AgentRegistry") as mock_registry_class:
                    mock_registry = MagicMock()
                    mock_registry.list_agents.return_value = mock_agents
                    mock_registry_class.return_value = mock_registry

                    stats = run_daemon_cycle(config)
                    assert stats["issues_found"] == 2
                    assert stats["agents_spawned"] == 0
                    assert stats["skipped_at_limit"] == 2

    def test_spawns_up_to_limit(self, tmp_path, capsys):
        """Test that daemon spawns up to available slots."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".beads").mkdir()

        config = DaemonConfig(max_concurrent_agents=2, dry_run=True)

        mock_issues = [
            {"id": "p-1", "title": "Issue 1", "issue_type": "bug", "labels": ["triage:ready"]},
            {"id": "p-2", "title": "Issue 2", "issue_type": "feature", "labels": ["triage:ready"]},
            {"id": "p-3", "title": "Issue 3", "issue_type": "task", "labels": ["triage:ready"]},
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_issues)

        # 0 active agents, max is 2
        mock_agents = []

        with patch("orch.work_daemon.get_kb_projects", return_value=[proj]):
            with patch("subprocess.run", return_value=mock_result):
                with patch("orch.registry.AgentRegistry") as mock_registry_class:
                    mock_registry = MagicMock()
                    mock_registry.list_agents.return_value = mock_agents
                    mock_registry_class.return_value = mock_registry

                    stats = run_daemon_cycle(config)
                    assert stats["issues_found"] == 3
                    assert stats["agents_spawned"] == 2  # Limited to 2 slots
                    assert stats["skipped_at_limit"] == 1
