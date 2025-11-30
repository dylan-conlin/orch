"""Tests for beads integration module."""

import json
import pytest
from unittest.mock import patch, MagicMock
import subprocess

from orch.beads_integration import (
    BeadsIssue,
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)


class TestBeadsIssue:
    """Tests for BeadsIssue dataclass."""

    def test_beads_issue_creation(self):
        """Test creating a BeadsIssue from basic fields."""
        issue = BeadsIssue(
            id="meta-orchestration-ltv",
            title="Test issue title",
            description="Test description",
            status="open",
            priority=2,
        )
        assert issue.id == "meta-orchestration-ltv"
        assert issue.title == "Test issue title"
        assert issue.description == "Test description"
        assert issue.status == "open"
        assert issue.priority == 2
        assert issue.notes is None

    def test_beads_issue_with_notes(self):
        """Test creating a BeadsIssue with notes."""
        issue = BeadsIssue(
            id="test-123",
            title="Title",
            description="Desc",
            status="open",
            priority=1,
            notes="Some notes here",
        )
        assert issue.notes == "Some notes here"


class TestBeadsIntegrationGetIssue:
    """Tests for BeadsIntegration.get_issue()."""

    def test_get_issue_success(self):
        """Test successfully getting an issue."""
        mock_output = json.dumps([{
            "id": "meta-orchestration-ltv",
            "title": "Integrate orch spawn with beads",
            "description": "Detailed description here",
            "status": "open",
            "priority": 2,
            "notes": "workspace: /path/to/workspace",
            "issue_type": "task",
            "created_at": "2025-11-29T17:22:47.507853-08:00",
            "updated_at": "2025-11-29T17:22:47.507853-08:00",
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            issue = beads.get_issue("meta-orchestration-ltv")

            assert issue.id == "meta-orchestration-ltv"
            assert issue.title == "Integrate orch spawn with beads"
            assert issue.description == "Detailed description here"
            assert issue.status == "open"
            assert issue.priority == 2
            assert issue.notes == "workspace: /path/to/workspace"

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "bd" in call_args[0][0]
            assert "show" in call_args[0][0]
            assert "meta-orchestration-ltv" in call_args[0][0]
            assert "--json" in call_args[0][0]

    def test_get_issue_not_found(self):
        """Test error when issue doesn't exist."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue 'nonexistent-id' not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError) as exc_info:
                beads.get_issue("nonexistent-id")

            assert "nonexistent-id" in str(exc_info.value)

    def test_get_issue_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError) as exc_info:
                beads.get_issue("test-id")

            assert "bd" in str(exc_info.value).lower()

    def test_get_issue_empty_result(self):
        """Test error when bd show returns empty array."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr="",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.get_issue("empty-result-id")


class TestBeadsIntegrationUpdateNotes:
    """Tests for BeadsIntegration.update_issue_notes()."""

    def test_update_notes_success(self):
        """Test successfully updating issue notes."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.update_issue_notes(
                "test-id",
                "workspace: .orch/workspace/test-workspace/"
            )

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "bd" in call_args[0][0]
            assert "update" in call_args[0][0]
            assert "test-id" in call_args[0][0]
            assert "--notes" in call_args[0][0]

    def test_update_notes_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError):
                beads.update_issue_notes("test-id", "notes")

    def test_update_notes_issue_not_found(self):
        """Test error when trying to update nonexistent issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue 'nonexistent' not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.update_issue_notes("nonexistent", "notes")


class TestBeadsIntegrationAddWorkspaceLink:
    """Tests for BeadsIntegration.add_workspace_link()."""

    def test_add_workspace_link(self):
        """Test adding a workspace link to an issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.add_workspace_link(
                "test-id",
                ".orch/workspace/2025-11-29-test-workspace/"
            )

            # Verify the notes contain workspace path
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            notes_idx = cmd.index("--notes") + 1
            notes_value = cmd[notes_idx]
            assert "workspace:" in notes_value
            assert ".orch/workspace/2025-11-29-test-workspace/" in notes_value


class TestBeadsIntegrationCloseIssue:
    """Tests for BeadsIntegration.close_issue()."""

    def test_close_issue_success(self):
        """Test successfully closing an issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.close_issue("test-id")

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "bd" in call_args[0][0]
            assert "close" in call_args[0][0]
            assert "test-id" in call_args[0][0]
            assert "--reason" in call_args[0][0]

    def test_close_issue_with_reason(self):
        """Test closing an issue with a custom reason."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.close_issue("test-id", "Custom reason")

            # Verify the reason was passed
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            reason_idx = cmd.index("--reason") + 1
            reason_value = cmd[reason_idx]
            assert reason_value == "Custom reason"

    def test_close_issue_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError):
                beads.close_issue("test-id")

    def test_close_issue_not_found(self):
        """Test error when trying to close nonexistent issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue 'nonexistent' not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.close_issue("nonexistent")


class TestBeadsIntegrationCLIPath:
    """Tests for custom CLI path support."""

    def test_custom_cli_path(self):
        """Test using a custom bd CLI path."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test",
            "description": "",
            "status": "open",
            "priority": 1,
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration(cli_path="/custom/path/to/bd")
            beads.get_issue("test-id")

            # Verify custom path was used
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "/custom/path/to/bd"
