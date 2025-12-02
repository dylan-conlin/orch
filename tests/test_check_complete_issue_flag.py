"""
Tests for --issue flag on orch check and orch complete commands.

Beads-first workflow: allows inspecting and closing beads issues directly
without requiring the agent to be in the registry.

Reference: beads issue orch-cli-nvl
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner


class TestCheckIssueFlag:
    """Tests for orch check --issue <beads-id>."""

    def test_check_issue_shows_issue_details(self):
        """Test that orch check --issue displays beads issue details."""
        from orch.cli import cli

        runner = CliRunner()

        mock_issue_data = [{
            "id": "orch-cli-xyz",
            "title": "Fix authentication bug",
            "description": "Users can't login after password reset",
            "status": "in_progress",
            "priority": 2,
        }]

        mock_comments = [
            {"text": "Phase: Planning - Starting work", "created_at": "2025-12-02T10:00:00Z"},
            {"text": "Phase: Implementing - Working on fix", "created_at": "2025-12-02T11:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'show' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_issue_data), stderr="")
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            result = runner.invoke(cli, ['check', '--issue', 'orch-cli-xyz'])

            # Should show issue details
            assert result.exit_code == 0
            assert 'orch-cli-xyz' in result.output
            assert 'Fix authentication bug' in result.output
            assert 'Implementing' in result.output  # Latest phase

    def test_check_issue_shows_phase_from_comments(self):
        """Test that orch check --issue extracts phase from beads comments."""
        from orch.cli import cli

        runner = CliRunner()

        mock_issue_data = [{
            "id": "orch-cli-abc",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 1,
        }]

        mock_comments = [
            {"text": "Phase: Complete - All tests pass", "created_at": "2025-12-02T12:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'show' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_issue_data), stderr="")
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            result = runner.invoke(cli, ['check', '--issue', 'orch-cli-abc'])

            # Should show Complete phase
            assert result.exit_code == 0
            assert 'Complete' in result.output

    def test_check_issue_not_found_error(self):
        """Test that orch check --issue handles missing issue gracefully."""
        from orch.cli import cli

        runner = CliRunner()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Issue not found")

            result = runner.invoke(cli, ['check', '--issue', 'nonexistent-id'])

            # Should show error message
            assert result.exit_code != 0 or 'not found' in result.output.lower()

    def test_check_issue_json_format(self):
        """Test that orch check --issue --format json returns valid JSON."""
        from orch.cli import cli

        runner = CliRunner()

        mock_issue_data = [{
            "id": "orch-cli-xyz",
            "title": "Test issue",
            "description": "Description here",
            "status": "open",
            "priority": 1,
        }]

        mock_comments = [
            {"text": "Phase: Planning", "created_at": "2025-12-02T10:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'show' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_issue_data), stderr="")
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            result = runner.invoke(cli, ['check', '--issue', 'orch-cli-xyz', '--format', 'json'])

            # Should return valid JSON
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert 'issue' in data
            assert data['issue']['id'] == 'orch-cli-xyz'

    def test_check_issue_bypasses_registry(self):
        """Test that orch check --issue doesn't require agent in registry."""
        from orch.cli import cli

        runner = CliRunner()

        mock_issue_data = [{
            "id": "orch-cli-xyz",
            "title": "Test issue",
            "description": "",
            "status": "open",
            "priority": 1,
        }]

        # Mock BeadsIntegration, but NOT the registry
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_issue_data),
                stderr=""
            )

            # This should work without any registry setup
            result = runner.invoke(cli, ['check', '--issue', 'orch-cli-xyz'])

            # Should succeed without registry
            assert result.exit_code == 0


class TestCompleteIssueFlag:
    """Tests for orch complete --issue <beads-id>."""

    def test_complete_issue_closes_beads_issue(self):
        """Test that orch complete --issue closes the beads issue."""
        from orch.cli import cli

        runner = CliRunner()

        mock_comments = [
            {"text": "Phase: Complete - All done", "created_at": "2025-12-02T12:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                if 'close' in args:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            result = runner.invoke(cli, ['complete', '--issue', 'orch-cli-xyz'])

            # Should close successfully
            assert result.exit_code == 0
            assert 'closed' in result.output.lower() or 'complete' in result.output.lower()

    def test_complete_issue_requires_phase_complete(self):
        """Test that orch complete --issue fails if phase is not Complete."""
        from orch.cli import cli

        runner = CliRunner()

        mock_comments = [
            {"text": "Phase: Implementing - Still working", "created_at": "2025-12-02T11:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_comments),
                stderr=""
            )

            result = runner.invoke(cli, ['complete', '--issue', 'orch-cli-xyz'])

            # Should fail with error about phase
            assert result.exit_code != 0 or 'phase' in result.output.lower()
            assert 'Complete' in result.output or 'complete' in result.output.lower()

    def test_complete_issue_not_found_error(self):
        """Test that orch complete --issue handles missing issue gracefully."""
        from orch.cli import cli

        runner = CliRunner()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Issue not found")

            result = runner.invoke(cli, ['complete', '--issue', 'nonexistent-id'])

            # Should show error message
            assert result.exit_code != 0 or 'not found' in result.output.lower()

    def test_complete_issue_bypasses_registry(self):
        """Test that orch complete --issue doesn't require agent in registry."""
        from orch.cli import cli

        runner = CliRunner()

        mock_comments = [
            {"text": "Phase: Complete - Done", "created_at": "2025-12-02T12:00:00Z"},
        ]

        # Mock BeadsIntegration, but NOT the registry
        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                if 'close' in args:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            # This should work without any registry setup
            result = runner.invoke(cli, ['complete', '--issue', 'orch-cli-xyz'])

            # Should succeed without registry
            assert result.exit_code == 0

    def test_complete_issue_bypasses_workspace_verification(self):
        """Test that orch complete --issue skips workspace verification."""
        from orch.cli import cli

        runner = CliRunner()

        mock_comments = [
            {"text": "Phase: Complete - Done", "created_at": "2025-12-02T12:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                if 'close' in args:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            # No workspace exists - should still work
            result = runner.invoke(cli, ['complete', '--issue', 'orch-cli-xyz'])

            # Should succeed without workspace
            assert result.exit_code == 0


class TestCheckIssueAndAgentIdMutualExclusion:
    """Test that --issue and agent_id are mutually exclusive."""

    def test_check_cannot_use_both_issue_and_agent_id(self):
        """Test that providing both --issue and agent_id fails."""
        from orch.cli import cli

        runner = CliRunner()

        result = runner.invoke(cli, ['check', 'my-agent', '--issue', 'orch-cli-xyz'])

        # Should fail with error
        assert result.exit_code != 0 or 'cannot' in result.output.lower() or 'either' in result.output.lower()

    def test_complete_cannot_use_both_issue_and_agent_id(self):
        """Test that providing both --issue and agent_id fails."""
        from orch.cli import cli

        runner = CliRunner()

        result = runner.invoke(cli, ['complete', 'my-agent', '--issue', 'orch-cli-xyz'])

        # Should fail with error
        assert result.exit_code != 0 or 'cannot' in result.output.lower() or 'either' in result.output.lower()

    def test_check_requires_one_of_issue_or_agent_id(self):
        """Test that check requires either --issue or agent_id."""
        from orch.cli import cli

        runner = CliRunner()

        result = runner.invoke(cli, ['check'])

        # Should fail with usage error
        assert result.exit_code != 0


class TestCompleteIssueWithDiscover:
    """Test interaction between --issue and --discover flags."""

    def test_complete_issue_with_discover_flag(self):
        """Test that --discover works with --issue flag."""
        from orch.cli import cli

        runner = CliRunner()

        mock_comments = [
            {"text": "Phase: Complete - All done", "created_at": "2025-12-02T12:00:00Z"},
        ]

        with patch('subprocess.run') as mock_run:
            def subprocess_side_effect(args, **kwargs):
                if 'comments' in args:
                    return Mock(returncode=0, stdout=json.dumps(mock_comments), stderr="")
                if 'close' in args:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = subprocess_side_effect

            # Simulate no user input for discovery prompt
            result = runner.invoke(cli, ['complete', '--issue', 'orch-cli-xyz', '--discover'], input='\n')

            # Should work (may prompt for discoveries or complete directly)
            # The key is it shouldn't error out
            assert result.exit_code == 0 or 'discover' in result.output.lower()
