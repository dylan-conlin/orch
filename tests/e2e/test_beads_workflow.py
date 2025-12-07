"""
Integration tests for beads workflow in orch ecosystem.

Tests the spawn → beads tracking → complete workflow:
- Spawning with --issue integrates beads tracking
- Phase detection from beads comments
- Complete closes beads issues

Note: These tests mock subprocess for CI environments where beads may not be installed.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from orch.spawn import SpawnConfig
from orch.spawn_prompt import build_spawn_prompt
from orch.beads_integration import (
    BeadsIntegration,
    BeadsIssue,
    BeadsIssueNotFoundError,
    BeadsCLINotFoundError,
)


@pytest.mark.e2e
class TestBeadsSpawnIntegration:
    """
    Test that spawn with --issue creates proper beads context.
    """

    def test_spawn_context_includes_beads_id_when_provided(self, project_dir):
        """Verify spawn context includes beads ID when spawned from issue."""
        beads_id = "orch-cli-abc"

        config = SpawnConfig(
            task="Fix authentication bug",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="fix-auth-bug",
            skill_name="systematic-debugging",
            beads_id=beads_id,
        )

        prompt = build_spawn_prompt(config)

        # Beads ID should be present multiple times for tracking
        assert beads_id in prompt, f"Beads ID {beads_id} not found in spawn context"
        assert "BEADS PROGRESS TRACKING" in prompt, \
            "BEADS PROGRESS TRACKING section not found when beads_id provided"

    def test_spawn_context_includes_bd_comment_instructions(self, project_dir):
        """Verify spawn context includes bd comment instructions for progress tracking."""
        beads_id = "orch-cli-xyz"

        config = SpawnConfig(
            task="Implement feature",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="impl-feature",
            skill_name="feature-impl",
            beads_id=beads_id,
        )

        prompt = build_spawn_prompt(config)

        # Should include bd comment examples with the beads ID
        assert f"bd comment {beads_id}" in prompt, \
            "bd comment instruction with beads ID not found"
        assert "Phase: Planning" in prompt, \
            "Phase: Planning example not found"
        assert "Phase: Complete" in prompt, \
            "Phase: Complete example not found"

    def test_spawn_context_warns_against_bd_close(self, project_dir):
        """Verify spawn context warns workers not to run bd close."""
        beads_id = "orch-cli-def"

        config = SpawnConfig(
            task="Task",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="task",
            skill_name="feature-impl",
            beads_id=beads_id,
        )

        prompt = build_spawn_prompt(config)

        # Should warn against workers closing issues
        assert "NEVER run `bd close`" in prompt or "never run bd close" in prompt.lower(), \
            "Warning against bd close not found in spawn context"


@pytest.mark.e2e
class TestBeadsPhaseDetection:
    """
    Test phase detection from beads comments.
    """

    def test_get_phase_from_comments_planning(self):
        """Verify phase detection finds 'Planning' from comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning - Analyzing codebase"}
                ])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-123")

            assert phase == "Planning", f"Expected 'Planning', got '{phase}'"

    def test_get_phase_from_comments_implementing(self):
        """Verify phase detection finds 'Implementing' from comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning - Analyzing codebase"},
                    {"text": "Phase: Implementing - Writing code"},
                ])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-123")

            # Should return most recent phase
            assert phase == "Implementing", f"Expected 'Implementing', got '{phase}'"

    def test_get_phase_from_comments_complete(self):
        """Verify phase detection finds 'Complete' from comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning - Analyzing codebase"},
                    {"text": "Phase: Implementing - Writing code"},
                    {"text": "Phase: Complete - All tests passing"},
                ])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-123")

            assert phase == "Complete", f"Expected 'Complete', got '{phase}'"

    def test_get_phase_from_comments_no_phase(self):
        """Verify phase detection returns None when no phase in comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Started work on feature"}
                ])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-123")

            assert phase is None, f"Expected None, got '{phase}'"

    def test_get_phase_from_comments_empty_comments(self):
        """Verify phase detection handles no comments gracefully."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments("test-123")

            assert phase is None, f"Expected None, got '{phase}'"


@pytest.mark.e2e
class TestBeadsIssueRetrieval:
    """
    Test beads issue retrieval via BeadsIntegration.
    """

    def test_get_issue_success(self):
        """Verify get_issue returns BeadsIssue when found."""
        mock_issue_data = [{
            "id": "orch-cli-123",
            "title": "Fix authentication flow",
            "description": "Users are getting logged out unexpectedly.",
            "status": "open",
            "priority": 1,
        }]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_issue_data)
            )
            beads = BeadsIntegration()
            issue = beads.get_issue("orch-cli-123")

            assert isinstance(issue, BeadsIssue)
            assert issue.id == "orch-cli-123"
            assert issue.title == "Fix authentication flow"
            assert issue.status == "open"

    def test_get_issue_not_found(self):
        """Verify get_issue raises BeadsIssueNotFoundError when issue not found."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Issue not found")
            beads = BeadsIntegration()

            with pytest.raises(BeadsIssueNotFoundError):
                beads.get_issue("nonexistent-123")

    def test_get_issue_cli_not_found(self):
        """Verify get_issue raises BeadsCLINotFoundError when bd not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bd not found")
            beads = BeadsIntegration()

            with pytest.raises(BeadsCLINotFoundError):
                beads.get_issue("test-123")


@pytest.mark.e2e
class TestBeadsCompleteIntegration:
    """
    Test that orch complete properly interacts with beads.
    """

    def test_close_issue_success(self):
        """Verify close_issue calls bd close with correct arguments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Issue closed")
            beads = BeadsIntegration()
            beads.close_issue("orch-cli-123", reason="Completed by agent")

            # Verify bd close was called
            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert "close" in call_args
            assert "orch-cli-123" in call_args
            assert "--reason" in call_args

    def test_close_issue_without_reason_uses_default(self):
        """Verify close_issue uses default reason when not provided."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Issue closed")
            beads = BeadsIntegration()
            beads.close_issue("orch-cli-456")

            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert "--reason" in call_args
            # Default reason should be present
            assert "Resolved via orch complete" in ' '.join(call_args)


@pytest.mark.e2e
class TestBeadsInvestigationPath:
    """
    Test investigation_path extraction from beads comments.
    """

    def test_get_investigation_path_found(self):
        """Verify investigation path is extracted from comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning"},
                    {"text": "investigation_path: /project/.kb/investigations/simple/2025-12-06-auth-flow.md"},
                    {"text": "Phase: Complete"},
                ])
            )
            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_comments("test-123")

            assert path == "/project/.kb/investigations/simple/2025-12-06-auth-flow.md", \
                f"Expected investigation path, got '{path}'"

    def test_get_investigation_path_not_found(self):
        """Verify None returned when no investigation path in comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning"},
                    {"text": "Phase: Complete"},
                ])
            )
            beads = BeadsIntegration()
            path = beads.get_investigation_path_from_comments("test-123")

            assert path is None, f"Expected None, got '{path}'"


@pytest.mark.e2e
class TestBeadsHasPhaseComplete:
    """
    Test has_phase_complete helper method.
    """

    def test_has_phase_complete_true(self):
        """Verify has_phase_complete returns True when Phase: Complete exists."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Complete - All done"},
                ])
            )
            beads = BeadsIntegration()
            result = beads.has_phase_complete("test-123")

            assert result is True

    def test_has_phase_complete_false_no_complete(self):
        """Verify has_phase_complete returns False when no Phase: Complete."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Implementing"},
                ])
            )
            beads = BeadsIntegration()
            result = beads.has_phase_complete("test-123")

            assert result is False

    def test_has_phase_complete_false_no_comments(self):
        """Verify has_phase_complete returns False when no comments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([])
            )
            beads = BeadsIntegration()
            result = beads.has_phase_complete("test-123")

            assert result is False


@pytest.mark.e2e
class TestBeadsWorkflowEndToEnd:
    """
    Test complete beads workflow from spawn to complete.
    """

    def test_spawn_complete_workflow_with_beads(self, project_dir):
        """Verify spawn → beads tracking → complete workflow."""
        beads_id = "orch-cli-workflow-test"

        # Step 1: Create spawn config with beads tracking
        config = SpawnConfig(
            task="Implement feature X",
            project="orch-cli",
            project_dir=project_dir,
            workspace_name="impl-feature-x",
            skill_name="feature-impl",
            beads_id=beads_id,
        )

        # Step 2: Verify spawn context includes beads tracking
        prompt = build_spawn_prompt(config)

        assert beads_id in prompt, "Beads ID not in spawn context"
        assert "BEADS PROGRESS TRACKING" in prompt, "Beads tracking section not found"
        assert "Phase: Complete" in prompt, "Completion guidance not found"

        # Step 3: Simulate agent completing and verify phase detection
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Planning - Started feature implementation"},
                    {"text": "Phase: Complete - All tests passing, ready for review"},
                ])
            )
            beads = BeadsIntegration()
            phase = beads.get_phase_from_comments(beads_id)

            assert phase == "Complete", f"Expected 'Complete', got '{phase}'"

        # Step 4: Verify has_phase_complete
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([
                    {"text": "Phase: Complete - All tests passing"},
                ])
            )
            beads = BeadsIntegration()
            assert beads.has_phase_complete(beads_id) is True

        # Step 5: Verify issue can be closed
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Issue closed")
            beads = BeadsIntegration()
            # Should not raise
            beads.close_issue(beads_id, reason="Completed via orch complete")

    def test_spawn_context_no_beads_id(self, project_dir):
        """Verify spawn context works without beads ID (ad-hoc spawn)."""
        config = SpawnConfig(
            task="Quick fix",
            project="test-project",
            project_dir=project_dir,
            workspace_name="quick-fix",
            skill_name="systematic-debugging",
            beads_id=None,  # No beads tracking
        )

        prompt = build_spawn_prompt(config)

        # Should still work, but without beads-specific tracking
        assert "Quick fix" in prompt, "Task not in spawn context"
        # Should NOT have beads-specific section when no beads_id
        assert "BEADS PROGRESS TRACKING" not in prompt, \
            "BEADS PROGRESS TRACKING should not appear when beads_id is None"
