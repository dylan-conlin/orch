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
            id="orch-cli-ltv",
            title="Test issue title",
            description="Test description",
            status="open",
            priority=2,
        )
        assert issue.id == "orch-cli-ltv"
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
            "id": "orch-cli-ltv",
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
            issue = beads.get_issue("orch-cli-ltv")

            assert issue.id == "orch-cli-ltv"
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
            assert "orch-cli-ltv" in call_args[0][0]
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


class TestBeadsIntegrationUpdateStatus:
    """Tests for BeadsIntegration.update_issue_status()."""

    def test_update_status_success(self):
        """Test successfully updating issue status to in_progress."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.update_issue_status("test-id", "in_progress")

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "bd" in call_args[0][0]
            assert "update" in call_args[0][0]
            assert "test-id" in call_args[0][0]
            assert "--status" in call_args[0][0]
            assert "in_progress" in call_args[0][0]

    def test_update_status_to_open(self):
        """Test updating issue status back to open."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.update_issue_status("test-id", "open")

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            status_idx = cmd.index("--status") + 1
            status_value = cmd[status_idx]
            assert status_value == "open"

    def test_update_status_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError):
                beads.update_issue_status("test-id", "in_progress")

    def test_update_status_issue_not_found(self):
        """Test error when trying to update nonexistent issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue 'nonexistent' not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.update_issue_status("nonexistent", "in_progress")


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


class TestBeadsIntegrationGetPhaseFromComments:
    """Tests for Phase 3: get_phase_from_comments()."""

    def test_get_phase_from_comments_success(self):
        """Test extracting phase from comments."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Planning - Starting work",
                "created_at": "2025-12-02T10:00:00Z"
            },
            {
                "id": 2,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Implementing - Working on feature X",
                "created_at": "2025-12-02T11:00:00Z"
            },
            {
                "id": 3,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Complete - All tests pass",
                "created_at": "2025-12-02T12:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-id")

            assert phase == "Complete"

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "comments" in call_args[0][0]
            assert "test-id" in call_args[0][0]
            assert "--json" in call_args[0][0]

    def test_get_phase_from_comments_no_phase_comments(self):
        """Test when no phase comments exist."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Just a regular comment",
                "created_at": "2025-12-02T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-id")

            assert phase is None

    def test_get_phase_from_comments_empty_comments(self):
        """Test when no comments exist."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr="",
            )

            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-id")

            assert phase is None

    def test_get_phase_from_comments_issue_not_found(self):
        """Test error when issue doesn't exist."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue 'nonexistent' not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.get_phase_from_comments("nonexistent")


class TestBeadsIntegrationHasPhaseComplete:
    """Tests for Phase 3: has_phase_complete()."""

    def test_has_phase_complete_true(self):
        """Test when Phase: Complete comment exists."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Complete - All done",
                "created_at": "2025-12-02T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            assert beads.has_phase_complete("test-id") is True

    def test_has_phase_complete_false_different_phase(self):
        """Test when phase is not Complete."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Implementing - Still working",
                "created_at": "2025-12-02T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            assert beads.has_phase_complete("test-id") is False

    def test_has_phase_complete_false_no_phase(self):
        """Test when no phase comment exists."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Regular comment",
                "created_at": "2025-12-02T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            assert beads.has_phase_complete("test-id") is False


class TestBeadsIntegrationDbPath:
    """Tests for cross-repo db_path support."""

    def test_build_command_without_db_path(self):
        """Test command building without db_path."""
        beads = BeadsIntegration()
        cmd = beads._build_command("show", "test-id", "--json")
        assert cmd == ["bd", "show", "test-id", "--json"]

    def test_build_command_with_db_path(self):
        """Test command building with db_path includes --db flag."""
        beads = BeadsIntegration(db_path="/path/to/other/repo/.beads/beads.db")
        cmd = beads._build_command("show", "test-id", "--json")
        assert cmd == ["bd", "--db", "/path/to/other/repo/.beads/beads.db", "show", "test-id", "--json"]

    def test_get_issue_with_db_path(self):
        """Test get_issue uses --db flag when db_path is set."""
        mock_output = json.dumps([{
            "id": "other-repo-xyz",
            "title": "Cross-repo issue",
            "description": "Issue from another repo",
            "status": "open",
            "priority": 2,
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration(db_path="/path/to/other/.beads/beads.db")
            issue = beads.get_issue("other-repo-xyz")

            # Verify --db flag was included
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--db" in cmd
            assert "/path/to/other/.beads/beads.db" in cmd
            assert issue.id == "other-repo-xyz"

    def test_close_issue_with_db_path(self):
        """Test close_issue uses --db flag when db_path is set."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration(db_path="/other/repo/.beads/beads.db")
            beads.close_issue("cross-repo-id", "Completed in different repo")

            # Verify --db flag was included
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--db" in cmd
            assert "/other/repo/.beads/beads.db" in cmd
            assert "close" in cmd

    def test_get_phase_from_comments_with_db_path(self):
        """Test get_phase_from_comments uses --db flag when db_path is set."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "cross-repo-id",
                "author": "agent",
                "text": "Phase: Complete - Done",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration(db_path="/other/.beads/beads.db")
            phase = beads.get_phase_from_comments("cross-repo-id")

            # Verify --db flag was included
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--db" in cmd
            assert "/other/.beads/beads.db" in cmd
            assert phase == "Complete"


class TestBeadsIntegrationGetInvestigationPath:
    """Tests for get_investigation_path_from_comments() - extracts investigation_path from beads comments."""

    def test_get_investigation_path_from_comments_success(self):
        """Test extracting investigation_path from comments."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Planning - Starting work",
                "created_at": "2025-12-02T10:00:00Z"
            },
            {
                "id": 2,
                "issue_id": "test-id",
                "author": "agent",
                "text": "investigation_path: /path/to/project/.kb/investigations/2025-12-06-my-investigation.md",
                "created_at": "2025-12-02T11:00:00Z"
            },
            {
                "id": 3,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Complete - All done",
                "created_at": "2025-12-02T12:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_comments("test-id")

            assert path == "/path/to/project/.kb/investigations/2025-12-06-my-investigation.md"

    def test_get_investigation_path_from_comments_no_path(self):
        """Test when no investigation_path comment exists."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Complete - Done",
                "created_at": "2025-12-02T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_comments("test-id")

            assert path is None

    def test_get_investigation_path_from_comments_uses_latest(self):
        """Test that latest investigation_path is returned when multiple exist."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "investigation_path: /old/path/investigation.md",
                "created_at": "2025-12-02T10:00:00Z"
            },
            {
                "id": 2,
                "issue_id": "test-id",
                "author": "agent",
                "text": "investigation_path: /new/path/investigation.md",
                "created_at": "2025-12-02T11:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_comments("test-id")

            # Should return the latest (second) path
            assert path == "/new/path/investigation.md"

    def test_get_investigation_path_with_db_path(self):
        """Test get_investigation_path_from_comments uses --db flag when db_path is set."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "cross-repo-id",
                "author": "agent",
                "text": "investigation_path: /project/.kb/investigations/2025-12-06-test.md",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration(db_path="/other/.beads/beads.db")
            path = beads.get_investigation_path_from_comments("cross-repo-id")

            # Verify --db flag was included
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--db" in cmd
            assert "/other/.beads/beads.db" in cmd
            assert path == "/project/.kb/investigations/2025-12-06-test.md"
