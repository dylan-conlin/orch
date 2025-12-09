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

    def test_beads_issue_with_issue_type(self):
        """Test creating a BeadsIssue with issue_type."""
        issue = BeadsIssue(
            id="test-123",
            title="Title",
            description="Desc",
            status="open",
            priority=1,
            issue_type="feature",
        )
        assert issue.issue_type == "feature"

    def test_beads_issue_issue_type_defaults_to_none(self):
        """Test that issue_type defaults to None when not provided."""
        issue = BeadsIssue(
            id="test-123",
            title="Title",
            description="Desc",
            status="open",
            priority=1,
        )
        assert issue.issue_type is None


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


class TestBeadsIntegrationAddComment:
    """Tests for add_comment() - Phase 1 of registry removal."""

    def test_add_comment_success(self):
        """Test adding a comment to a beads issue."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.add_comment("test-id", "Test comment text")

            # Verify the command was called correctly
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "bd" in cmd
            assert "comment" in cmd
            assert "test-id" in cmd
            assert "Test comment text" in cmd

    def test_add_comment_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError):
                beads.add_comment("test-id", "Test comment")

    def test_add_comment_issue_not_found(self):
        """Test error when issue doesn't exist."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: issue not found",
            )

            beads = BeadsIntegration()
            with pytest.raises(BeadsIssueNotFoundError):
                beads.add_comment("nonexistent-id", "Test comment")


class TestBeadsIntegrationAgentMetadata:
    """Tests for agent metadata functions - Phase 1 of registry removal."""

    def test_add_agent_metadata_success(self):
        """Test storing agent metadata in beads comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.add_agent_metadata(
                issue_id="test-id",
                agent_id="feat-test-agent-06dec",
                window_id="@123",
                skill="investigation",
                project_dir="/path/to/project"
            )

            # Verify the command was called with JSON metadata
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "comment" in cmd
            comment_text = cmd[-1]  # Last argument is the comment
            assert "agent_metadata:" in comment_text
            assert '"agent_id": "feat-test-agent-06dec"' in comment_text
            assert '"window_id": "@123"' in comment_text
            assert '"skill": "investigation"' in comment_text
            assert '"project_dir": "/path/to/project"' in comment_text

    def test_add_agent_metadata_minimal(self):
        """Test storing minimal agent metadata (only required fields)."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.add_agent_metadata(
                issue_id="test-id",
                agent_id="test-agent",
                window_id="@456"
            )

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            comment_text = cmd[-1]
            assert "agent_metadata:" in comment_text
            assert '"agent_id": "test-agent"' in comment_text
            assert '"window_id": "@456"' in comment_text
            # Optional fields should not be in the output
            assert '"skill"' not in comment_text
            assert '"project_dir"' not in comment_text

    def test_get_agent_metadata_success(self):
        """Test extracting agent metadata from comments."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "orchestrator",
                "text": "agent_metadata: {\"agent_id\": \"feat-test-06dec\", \"window_id\": \"@789\", \"skill\": \"feature-impl\", \"project_dir\": \"/home/user/project\"}",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            metadata = beads.get_agent_metadata("test-id")

            assert metadata is not None
            assert metadata["agent_id"] == "feat-test-06dec"
            assert metadata["window_id"] == "@789"
            assert metadata["skill"] == "feature-impl"
            assert metadata["project_dir"] == "/home/user/project"

    def test_get_agent_metadata_no_metadata(self):
        """Test when no agent_metadata comment exists."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "agent",
                "text": "Phase: Planning - Starting work",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            metadata = beads.get_agent_metadata("test-id")

            assert metadata is None

    def test_get_agent_metadata_uses_latest(self):
        """Test that latest agent_metadata is returned when multiple exist."""
        mock_output = json.dumps([
            {
                "id": 1,
                "issue_id": "test-id",
                "author": "orchestrator",
                "text": "agent_metadata: {\"agent_id\": \"old-agent\", \"window_id\": \"@100\"}",
                "created_at": "2025-12-06T10:00:00Z"
            },
            {
                "id": 2,
                "issue_id": "test-id",
                "author": "orchestrator",
                "text": "agent_metadata: {\"agent_id\": \"new-agent\", \"window_id\": \"@200\"}",
                "created_at": "2025-12-06T11:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            metadata = beads.get_agent_metadata("test-id")

            # Should return the latest (second) metadata
            assert metadata["agent_id"] == "new-agent"
            assert metadata["window_id"] == "@200"


class TestBeadsIntegrationListActiveAgents:
    """Tests for list_active_agents() - Phase 2 of registry removal."""

    def test_list_active_agents_success(self):
        """Test listing active agents from in_progress beads issues."""
        # First call: list issues
        mock_issues = json.dumps([
            {
                "id": "orch-cli-abc",
                "title": "Implement feature X",
                "status": "in_progress"
            },
            {
                "id": "orch-cli-def",
                "title": "Fix bug Y",
                "status": "in_progress"
            },
        ])

        # Subsequent calls: get comments for each issue
        mock_comments_1 = json.dumps([
            {
                "id": 1,
                "issue_id": "orch-cli-abc",
                "author": "orchestrator",
                "text": "agent_metadata: {\"agent_id\": \"feat-x-06dec\", \"window_id\": \"@123\", \"skill\": \"feature-impl\"}",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])
        mock_comments_2 = json.dumps([
            {
                "id": 1,
                "issue_id": "orch-cli-def",
                "author": "orchestrator",
                "text": "agent_metadata: {\"agent_id\": \"fix-y-06dec\", \"window_id\": \"@456\", \"skill\": \"systematic-debugging\"}",
                "created_at": "2025-12-06T10:00:00Z"
            },
        ])

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=mock_issues, stderr=""),
                MagicMock(returncode=0, stdout=mock_comments_1, stderr=""),
                MagicMock(returncode=0, stdout=mock_comments_2, stderr=""),
            ]

            beads = BeadsIntegration()
            agents = beads.list_active_agents()

            assert len(agents) == 2

            # First agent
            assert agents[0]["beads_id"] == "orch-cli-abc"
            assert agents[0]["title"] == "Implement feature X"
            assert agents[0]["agent_id"] == "feat-x-06dec"
            assert agents[0]["window_id"] == "@123"
            assert agents[0]["skill"] == "feature-impl"

            # Second agent
            assert agents[1]["beads_id"] == "orch-cli-def"
            assert agents[1]["title"] == "Fix bug Y"
            assert agents[1]["agent_id"] == "fix-y-06dec"

    def test_list_active_agents_no_agents(self):
        """Test when no active agents exist."""
        mock_output = json.dumps([])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            agents = beads.list_active_agents()

            assert agents == []

    def test_list_active_agents_cli_not_found(self):
        """Test error when bd CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")

            beads = BeadsIntegration()
            with pytest.raises(BeadsCLINotFoundError):
                beads.list_active_agents()


class TestBeadsIntegrationNotesMetadata:
    """Tests for notes-based agent metadata storage (Phase 3 of registry removal).

    This replaces comment-based storage with notes field for real-time UI updates.
    The notes field stores JSON with: phase, skill, agent_id, updated_at, investigation_path.
    """

    def test_update_agent_notes_full(self):
        """Test updating notes with all agent metadata fields."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.update_agent_notes(
                issue_id="test-id",
                agent_id="feat-test-06dec",
                window_id="@123",
                phase="Implementing",
                skill="feature-impl",
                project_dir="/path/to/project",
                investigation_path="/path/to/investigation.md"
            )

            # Verify bd update --notes was called with JSON
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "update" in cmd
            assert "--notes" in cmd
            # Find notes value after --notes flag
            notes_idx = cmd.index("--notes") + 1
            notes_value = cmd[notes_idx]
            notes_json = json.loads(notes_value)

            assert notes_json["agent_id"] == "feat-test-06dec"
            assert notes_json["window_id"] == "@123"
            assert notes_json["phase"] == "Implementing"
            assert notes_json["skill"] == "feature-impl"
            assert notes_json["project_dir"] == "/path/to/project"
            assert notes_json["investigation_path"] == "/path/to/investigation.md"
            # Should include updated_at timestamp
            assert "updated_at" in notes_json

    def test_update_agent_notes_minimal(self):
        """Test updating notes with only required fields."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration()
            beads.update_agent_notes(
                issue_id="test-id",
                agent_id="test-agent",
                window_id="@456"
            )

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            notes_idx = cmd.index("--notes") + 1
            notes_value = cmd[notes_idx]
            notes_json = json.loads(notes_value)

            assert notes_json["agent_id"] == "test-agent"
            assert notes_json["window_id"] == "@456"
            assert "updated_at" in notes_json
            # Optional fields should not be present when not provided
            assert notes_json.get("skill") is None
            assert notes_json.get("phase") is None

    def test_update_agent_notes_preserves_existing(self):
        """Test that updating notes preserves existing fields not being updated."""
        # First call: show to get existing notes
        mock_show = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "test-agent",
                "window_id": "@123",
                "phase": "Planning",
                "skill": "feature-impl"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=mock_show, stderr=""),  # show
                MagicMock(returncode=0, stdout="", stderr=""),  # update
            ]

            beads = BeadsIntegration()
            beads.update_agent_notes(
                issue_id="test-id",
                phase="Implementing"  # Only update phase
            )

            # Should have called update with merged notes
            update_call = mock_run.call_args_list[1]
            cmd = update_call[0][0]
            notes_idx = cmd.index("--notes") + 1
            notes_json = json.loads(cmd[notes_idx])

            # Existing fields preserved
            assert notes_json["agent_id"] == "test-agent"
            assert notes_json["window_id"] == "@123"
            assert notes_json["skill"] == "feature-impl"
            # New field updated
            assert notes_json["phase"] == "Implementing"

    def test_get_agent_notes_success(self):
        """Test reading agent metadata from notes field."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "feat-test-06dec",
                "window_id": "@789",
                "phase": "Complete",
                "skill": "investigation",
                "project_dir": "/home/user/project",
                "updated_at": "2025-12-06T10:00:00Z"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            notes = beads.get_agent_notes("test-id")

            assert notes is not None
            assert notes["agent_id"] == "feat-test-06dec"
            assert notes["window_id"] == "@789"
            assert notes["phase"] == "Complete"
            assert notes["skill"] == "investigation"
            assert notes["project_dir"] == "/home/user/project"

    def test_get_agent_notes_empty(self):
        """Test when notes field is empty or None."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": None
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            notes = beads.get_agent_notes("test-id")

            assert notes is None

    def test_get_agent_notes_not_json(self):
        """Test when notes field contains non-JSON string."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": "workspace: .orch/workspace/old-format"
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            notes = beads.get_agent_notes("test-id")

            # Should return None for non-JSON notes
            assert notes is None

    def test_get_phase_from_notes(self):
        """Test extracting phase from notes field."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "test-agent",
                "phase": "Implementing",
                "updated_at": "2025-12-06T10:00:00Z"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            phase = beads.get_phase_from_notes("test-id")

            assert phase == "Implementing"

    def test_get_phase_from_notes_no_phase(self):
        """Test when notes exists but has no phase field."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "test-agent",
                "window_id": "@123"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            phase = beads.get_phase_from_notes("test-id")

            assert phase is None

    def test_get_investigation_path_from_notes(self):
        """Test extracting investigation_path from notes field."""
        mock_output = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "test-agent",
                "investigation_path": "/path/to/investigation.md",
                "updated_at": "2025-12-06T10:00:00Z"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_notes("test-id")

            assert path == "/path/to/investigation.md"

    def test_update_phase_via_notes(self):
        """Test updating just the phase in notes."""
        # Existing notes
        mock_show = json.dumps([{
            "id": "test-id",
            "title": "Test Issue",
            "description": "",
            "status": "in_progress",
            "priority": 2,
            "notes": json.dumps({
                "agent_id": "test-agent",
                "window_id": "@123",
                "phase": "Planning"
            })
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=mock_show, stderr=""),  # show
                MagicMock(returncode=0, stdout="", stderr=""),  # update
            ]

            beads = BeadsIntegration()
            beads.update_phase("test-id", "Complete")

            # Verify phase was updated in notes
            update_call = mock_run.call_args_list[1]
            cmd = update_call[0][0]
            notes_idx = cmd.index("--notes") + 1
            notes_json = json.loads(cmd[notes_idx])

            assert notes_json["phase"] == "Complete"
            # Other fields preserved
            assert notes_json["agent_id"] == "test-agent"

    def test_update_agent_notes_with_db_path(self):
        """Test that update_agent_notes uses --db flag when db_path is set."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            beads = BeadsIntegration(db_path="/other/repo/.beads")
            beads.update_agent_notes(
                issue_id="cross-repo-id",
                agent_id="test-agent",
                window_id="@123"
            )

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--db" in cmd
            assert "/other/repo/.beads" in cmd


class TestBeadsDependency:
    """Tests for BeadsDependency dataclass."""

    def test_beads_dependency_creation(self):
        """Test creating a BeadsDependency with all fields."""
        from orch.beads_integration import BeadsDependency

        dep = BeadsDependency(
            id="orch-cli-abc",
            title="Blocking issue",
            status="open",
            dependency_type="blocks"
        )
        assert dep.id == "orch-cli-abc"
        assert dep.title == "Blocking issue"
        assert dep.status == "open"
        assert dep.dependency_type == "blocks"

    def test_beads_dependency_parent_child_type(self):
        """Test creating a BeadsDependency with parent-child type."""
        from orch.beads_integration import BeadsDependency

        dep = BeadsDependency(
            id="orch-cli-xyz",
            title="Parent epic",
            status="open",
            dependency_type="parent-child"
        )
        assert dep.dependency_type == "parent-child"


class TestBeadsIssueWithDependencies:
    """Tests for BeadsIssue with dependencies field."""

    def test_beads_issue_with_dependencies(self):
        """Test creating a BeadsIssue with dependencies."""
        from orch.beads_integration import BeadsDependency

        dep1 = BeadsDependency(
            id="orch-cli-abc",
            title="Blocker 1",
            status="open",
            dependency_type="blocks"
        )
        dep2 = BeadsDependency(
            id="orch-cli-def",
            title="Blocker 2",
            status="closed",
            dependency_type="blocks"
        )

        issue = BeadsIssue(
            id="orch-cli-test",
            title="Test issue",
            description="Test",
            status="open",
            priority=2,
            dependencies=[dep1, dep2]
        )

        assert len(issue.dependencies) == 2
        assert issue.dependencies[0].id == "orch-cli-abc"
        assert issue.dependencies[1].id == "orch-cli-def"

    def test_beads_issue_empty_dependencies(self):
        """Test creating a BeadsIssue with empty dependencies list."""
        issue = BeadsIssue(
            id="test",
            title="Test",
            description="",
            status="open",
            priority=1,
            dependencies=[]
        )
        assert issue.dependencies == []

    def test_beads_issue_default_dependencies_is_none(self):
        """Test that dependencies defaults to None when not provided."""
        issue = BeadsIssue(
            id="test",
            title="Test",
            description="",
            status="open",
            priority=1
        )
        assert issue.dependencies is None


class TestBeadsIntegrationGetIssueWithDependencies:
    """Tests for get_issue() parsing dependencies from JSON."""

    def test_get_issue_parses_dependencies(self):
        """Test that get_issue parses dependencies from bd show output."""
        mock_output = json.dumps([{
            "id": "orch-cli-xyz",
            "title": "Feature with blockers",
            "description": "Description",
            "status": "open",
            "priority": 2,
            "dependencies": [
                {
                    "id": "orch-cli-abc",
                    "title": "Blocking issue",
                    "description": "Must be done first",
                    "status": "open",
                    "priority": 1,
                    "issue_type": "feature",
                    "dependency_type": "blocks"
                },
                {
                    "id": "orch-cli-def",
                    "title": "Parent epic",
                    "description": "Epic container",
                    "status": "open",
                    "priority": 1,
                    "issue_type": "epic",
                    "dependency_type": "parent-child"
                }
            ]
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            issue = beads.get_issue("orch-cli-xyz")

            assert issue.id == "orch-cli-xyz"
            assert len(issue.dependencies) == 2
            assert issue.dependencies[0].id == "orch-cli-abc"
            assert issue.dependencies[0].status == "open"
            assert issue.dependencies[0].dependency_type == "blocks"
            assert issue.dependencies[1].id == "orch-cli-def"
            assert issue.dependencies[1].dependency_type == "parent-child"

    def test_get_issue_empty_dependencies(self):
        """Test get_issue with empty dependencies array."""
        mock_output = json.dumps([{
            "id": "orch-cli-xyz",
            "title": "Issue without blockers",
            "description": "",
            "status": "open",
            "priority": 2,
            "dependencies": []
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            issue = beads.get_issue("orch-cli-xyz")

            assert issue.dependencies == []

    def test_get_issue_no_dependencies_key(self):
        """Test get_issue when dependencies key is missing from JSON."""
        mock_output = json.dumps([{
            "id": "orch-cli-xyz",
            "title": "Old format issue",
            "description": "",
            "status": "open",
            "priority": 2
            # No dependencies key
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            issue = beads.get_issue("orch-cli-xyz")

            assert issue.dependencies is None


class TestBeadsIntegrationGetOpenBlockers:
    """Tests for get_open_blockers() helper method."""

    def test_get_open_blockers_returns_only_open_blocks(self):
        """Test that get_open_blockers filters for open status and blocks type."""
        mock_output = json.dumps([{
            "id": "orch-cli-test",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 2,
            "dependencies": [
                {
                    "id": "orch-cli-abc",
                    "title": "Open blocker",
                    "status": "open",
                    "dependency_type": "blocks"
                },
                {
                    "id": "orch-cli-def",
                    "title": "Closed blocker",
                    "status": "closed",
                    "dependency_type": "blocks"
                },
                {
                    "id": "orch-cli-ghi",
                    "title": "Open parent (not a blocker)",
                    "status": "open",
                    "dependency_type": "parent-child"
                }
            ]
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            blockers = beads.get_open_blockers("orch-cli-test")

            # Should only return the one open blocker (blocks type)
            assert len(blockers) == 1
            assert blockers[0].id == "orch-cli-abc"
            assert blockers[0].status == "open"
            assert blockers[0].dependency_type == "blocks"

    def test_get_open_blockers_no_blockers(self):
        """Test get_open_blockers when no open blockers exist."""
        mock_output = json.dumps([{
            "id": "orch-cli-test",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 2,
            "dependencies": [
                {
                    "id": "orch-cli-abc",
                    "title": "Closed blocker",
                    "status": "closed",
                    "dependency_type": "blocks"
                }
            ]
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            blockers = beads.get_open_blockers("orch-cli-test")

            assert blockers == []

    def test_get_open_blockers_no_dependencies(self):
        """Test get_open_blockers when issue has no dependencies."""
        mock_output = json.dumps([{
            "id": "orch-cli-test",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 2
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            blockers = beads.get_open_blockers("orch-cli-test")

            assert blockers == []

    def test_get_open_blockers_multiple_open_blockers(self):
        """Test get_open_blockers with multiple open blockers."""
        mock_output = json.dumps([{
            "id": "orch-cli-test",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 2,
            "dependencies": [
                {
                    "id": "orch-cli-abc",
                    "title": "Blocker 1",
                    "status": "open",
                    "dependency_type": "blocks"
                },
                {
                    "id": "orch-cli-def",
                    "title": "Blocker 2",
                    "status": "open",
                    "dependency_type": "blocks"
                },
                {
                    "id": "orch-cli-ghi",
                    "title": "Blocker 3",
                    "status": "open",
                    "dependency_type": "blocks"
                }
            ]
        }])

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            beads = BeadsIntegration()
            blockers = beads.get_open_blockers("orch-cli-test")

            assert len(blockers) == 3
            assert blockers[0].id == "orch-cli-abc"
            assert blockers[1].id == "orch-cli-def"
            assert blockers[2].id == "orch-cli-ghi"
