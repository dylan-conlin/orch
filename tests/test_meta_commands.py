"""Tests for meta orchestration commands (focus, drift, next).

These commands provide cross-project coordination and strategic alignment.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from orch.cli import cli
from orch.meta_commands import (
    FocusState,
    get_focus_file_path,
    load_focus,
    save_focus,
    set_focus,
    get_current_focus,
    check_drift,
    get_next_suggestions,
)


class TestFocusState:
    """Tests for FocusState dataclass."""

    def test_create_focus_state(self):
        """Test creating a FocusState."""
        now = datetime.now(timezone.utc)
        focus = FocusState(
            description="Ship snap MVP",
            set_at=now,
            aligned_projects=["snap"],
            success_criteria=["snap-4x4 closed"],
        )
        assert focus.description == "Ship snap MVP"
        assert focus.set_at == now
        assert "snap" in focus.aligned_projects
        assert "snap-4x4 closed" in focus.success_criteria

    def test_focus_state_to_dict(self):
        """Test converting FocusState to dict for JSON serialization."""
        now = datetime.now(timezone.utc)
        focus = FocusState(
            description="Ship snap MVP",
            set_at=now,
            aligned_projects=["snap"],
            success_criteria=["snap-4x4 closed"],
        )
        data = focus.to_dict()
        assert data["description"] == "Ship snap MVP"
        assert data["set_at"] == now.isoformat()
        assert data["aligned_projects"] == ["snap"]
        assert data["success_criteria"] == ["snap-4x4 closed"]

    def test_focus_state_from_dict(self):
        """Test creating FocusState from dict."""
        now = datetime.now(timezone.utc)
        data = {
            "description": "Ship snap MVP",
            "set_at": now.isoformat(),
            "aligned_projects": ["snap"],
            "success_criteria": ["snap-4x4 closed"],
        }
        focus = FocusState.from_dict(data)
        assert focus.description == "Ship snap MVP"
        assert focus.aligned_projects == ["snap"]
        # Check datetime parsing worked (compare to minute precision)
        assert abs((focus.set_at - now).total_seconds()) < 1


class TestFocusFileOperations:
    """Tests for focus file operations."""

    def test_get_focus_file_path(self):
        """Test getting focus file path."""
        path = get_focus_file_path()
        assert path.name == "focus.json"
        assert ".orch" in str(path)

    def test_save_and_load_focus(self, tmp_path):
        """Test saving and loading focus state."""
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus = FocusState(
            description="Test focus",
            set_at=now,
            aligned_projects=["proj1"],
            success_criteria=["criterion1"],
        )

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            save_focus(focus)
            loaded = load_focus()

        assert loaded is not None
        assert loaded.description == "Test focus"
        assert loaded.aligned_projects == ["proj1"]

    def test_load_focus_no_file(self, tmp_path):
        """Test loading when no focus file exists."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            loaded = load_focus()

        assert loaded is None

    def test_load_focus_invalid_json(self, tmp_path):
        """Test loading with invalid JSON file."""
        focus_file = tmp_path / "focus.json"
        focus_file.write_text("not valid json")

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            loaded = load_focus()

        assert loaded is None


class TestSetFocus:
    """Tests for set_focus function."""

    def test_set_focus_basic(self, tmp_path):
        """Test setting a basic focus."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            focus = set_focus("Ship snap MVP")

        assert focus.description == "Ship snap MVP"
        assert focus.aligned_projects == []  # No projects specified
        assert focus.set_at is not None

    def test_set_focus_with_projects(self, tmp_path):
        """Test setting focus with aligned projects."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            focus = set_focus("Ship snap MVP", aligned_projects=["snap", "orch-cli"])

        assert focus.description == "Ship snap MVP"
        assert "snap" in focus.aligned_projects
        assert "orch-cli" in focus.aligned_projects

    def test_set_focus_with_criteria(self, tmp_path):
        """Test setting focus with success criteria."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            focus = set_focus(
                "Ship snap MVP",
                success_criteria=["snap-4x4 closed", "snap installable"],
            )

        assert "snap-4x4 closed" in focus.success_criteria


class TestGetCurrentFocus:
    """Tests for get_current_focus function."""

    def test_get_current_focus_exists(self, tmp_path):
        """Test getting current focus when it exists."""
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Test focus",
                "set_at": now.isoformat(),
                "aligned_projects": ["proj1"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            focus = get_current_focus()

        assert focus is not None
        assert focus.description == "Test focus"

    def test_get_current_focus_not_set(self, tmp_path):
        """Test getting focus when none is set."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            focus = get_current_focus()

        assert focus is None


class TestCheckDrift:
    """Tests for drift detection."""

    def test_no_focus_no_drift(self, tmp_path):
        """Test that no focus means no drift."""
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            result = check_drift()

        assert result["drifting"] is False
        assert result["reason"] == "no_focus_set"

    def test_aligned_project_no_drift(self, tmp_path):
        """Test no drift when in aligned project."""
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": now.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        # Simulate being in snap project
        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_current_project", return_value="snap"):
                result = check_drift()

        assert result["drifting"] is False

    def test_misaligned_project_causes_drift(self, tmp_path):
        """Test drift when in non-aligned project."""
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": now.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        # Simulate being in different project
        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_current_project", return_value="kb-cli"):
                result = check_drift()

        assert result["drifting"] is True
        assert "kb-cli" in result["reason"]

    def test_time_based_drift(self, tmp_path):
        """Test drift warning after extended time without progress."""
        focus_file = tmp_path / "focus.json"
        # Set focus 3 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": old_time.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_current_project", return_value="snap"):
                result = check_drift(time_threshold_hours=2)

        assert result["time_warning"] is True


class TestGetNextSuggestions:
    """Tests for next action suggestions."""

    def test_next_with_focus(self, tmp_path):
        """Test getting next suggestions when focus is set."""
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": now.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        # Mock beads ready issues (include project field as get_all_ready_issues adds it)
        mock_issues = [
            {"id": "snap-abc", "title": "Implement CLI", "priority": 1, "project": "snap"},
            {"id": "orch-xyz", "title": "Other work", "priority": 2, "project": "orch-cli"},
        ]

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_all_ready_issues", return_value=mock_issues):
                suggestions = get_next_suggestions()

        # Focus-aligned issues should be prioritized
        assert len(suggestions) > 0
        # First suggestion should be from aligned project (snap)
        assert suggestions[0]["project"] == "snap" or suggestions[0].get("aligned", False)

    def test_next_no_focus(self, tmp_path):
        """Test getting next suggestions when no focus is set."""
        focus_file = tmp_path / "focus.json"

        mock_issues = [
            {"id": "proj-abc", "title": "Some work", "priority": 1},
        ]

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_all_ready_issues", return_value=mock_issues):
                suggestions = get_next_suggestions()

        # Should still return suggestions, just not focus-sorted
        assert len(suggestions) > 0


class TestFocusCLI:
    """Tests for orch focus CLI command."""

    def test_focus_set(self, tmp_path):
        """Test setting focus via CLI."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            result = runner.invoke(cli, ["focus", "Ship snap MVP"])

        assert result.exit_code == 0
        assert "Focus set" in result.output or "Ship snap MVP" in result.output

    def test_focus_show(self, tmp_path):
        """Test showing current focus via CLI."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": now.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            result = runner.invoke(cli, ["focus"])

        assert result.exit_code == 0
        assert "Ship snap MVP" in result.output

    def test_focus_with_projects(self, tmp_path):
        """Test setting focus with aligned projects via CLI."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            result = runner.invoke(cli, ["focus", "Ship snap MVP", "--project", "snap"])

        assert result.exit_code == 0

        # Verify the focus was saved with the project
        saved_data = json.loads(focus_file.read_text())
        assert "snap" in saved_data["current"]["aligned_projects"]


class TestDriftCLI:
    """Tests for orch drift CLI command."""

    def test_drift_no_focus(self, tmp_path):
        """Test drift check when no focus is set."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            result = runner.invoke(cli, ["drift"])

        assert result.exit_code == 0
        assert "No focus set" in result.output or "no focus" in result.output.lower()

    def test_drift_aligned(self, tmp_path):
        """Test drift check when aligned."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"
        now = datetime.now(timezone.utc)
        focus_data = {
            "current": {
                "description": "Ship snap MVP",
                "set_at": now.isoformat(),
                "aligned_projects": ["snap"],
                "success_criteria": [],
            },
            "history": [],
        }
        focus_file.write_text(json.dumps(focus_data))

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_current_project", return_value="snap"):
                result = runner.invoke(cli, ["drift"])

        assert result.exit_code == 0
        # Should not show drift warning
        assert "drifting" not in result.output.lower() or "not drifting" in result.output.lower()


class TestNextCLI:
    """Tests for orch next CLI command."""

    def test_next_shows_suggestions(self, tmp_path):
        """Test next command shows action suggestions."""
        runner = CliRunner()
        focus_file = tmp_path / "focus.json"

        mock_suggestions = [
            {"id": "snap-abc", "title": "Implement CLI", "project": "snap", "aligned": True},
        ]

        with patch("orch.meta_commands.get_focus_file_path", return_value=focus_file):
            with patch("orch.meta_commands.get_next_suggestions", return_value=mock_suggestions):
                result = runner.invoke(cli, ["next"])

        assert result.exit_code == 0
        # Should show the suggestion
        assert "snap-abc" in result.output or "Implement CLI" in result.output
