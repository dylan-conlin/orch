"""
Tests for auto-close beads issue on orch complete.

When completing an agent that has a beads_id in its metadata (spawned from beads issue),
automatically run 'bd close <id>' to close the beads issue.

Reference: beads issue orch-cli-y73
Pattern: Similar to feature_id handling in complete_agent_work()
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner


class TestCloseBeadsIssueFunction:
    """Tests for close_beads_issue helper function in complete module."""

    def test_close_beads_issue_calls_beads_integration(self):
        """Test that close_beads_issue calls BeadsIntegration.close_issue."""
        from orch.complete import close_beads_issue

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            # Phase 3: Must return "Complete" phase for close to proceed
            mock_beads.get_phase_from_comments.return_value = "Complete"
            MockBeads.return_value = mock_beads

            result = close_beads_issue('orch-cli-abc')

            # Should have created BeadsIntegration and called close_issue
            MockBeads.assert_called_once()
            mock_beads.get_phase_from_comments.assert_called_once_with('orch-cli-abc')
            mock_beads.close_issue.assert_called_once_with(
                'orch-cli-abc',
                reason='Resolved via orch complete'
            )
            assert result is True

    def test_close_beads_issue_returns_false_on_cli_not_found(self):
        """Test that close_beads_issue returns False when bd CLI not found."""
        from orch.complete import close_beads_issue
        from orch.beads_integration import BeadsCLINotFoundError

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            # Phase 3: Must return "Complete" phase for close to proceed
            mock_beads.get_phase_from_comments.return_value = "Complete"
            mock_beads.close_issue.side_effect = BeadsCLINotFoundError()
            MockBeads.return_value = mock_beads

            result = close_beads_issue('orch-cli-abc')

            assert result is False

    def test_close_beads_issue_returns_false_on_issue_not_found(self):
        """Test that close_beads_issue returns False when issue not found."""
        from orch.complete import close_beads_issue
        from orch.beads_integration import BeadsIssueNotFoundError

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            # Phase 3: Must return "Complete" phase for close to proceed
            mock_beads.get_phase_from_comments.return_value = "Complete"
            mock_beads.close_issue.side_effect = BeadsIssueNotFoundError('orch-cli-abc')
            MockBeads.return_value = mock_beads

            result = close_beads_issue('orch-cli-abc')

            assert result is False

    def test_close_beads_issue_raises_on_phase_not_complete(self):
        """Test that close_beads_issue raises error when phase is not Complete."""
        from orch.complete import close_beads_issue, BeadsPhaseNotCompleteError

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            # Phase 3: Return non-complete phase
            mock_beads.get_phase_from_comments.return_value = "Implementing"
            MockBeads.return_value = mock_beads

            with pytest.raises(BeadsPhaseNotCompleteError) as exc_info:
                close_beads_issue('orch-cli-abc')

            assert 'orch-cli-abc' in str(exc_info.value)
            assert 'Implementing' in str(exc_info.value)
            # close_issue should NOT have been called
            mock_beads.close_issue.assert_not_called()

    def test_close_beads_issue_raises_on_no_phase(self):
        """Test that close_beads_issue raises error when no phase exists."""
        from orch.complete import close_beads_issue, BeadsPhaseNotCompleteError

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            # Phase 3: Return None (no phase comments)
            mock_beads.get_phase_from_comments.return_value = None
            MockBeads.return_value = mock_beads

            with pytest.raises(BeadsPhaseNotCompleteError) as exc_info:
                close_beads_issue('orch-cli-abc')

            assert 'orch-cli-abc' in str(exc_info.value)
            # close_issue should NOT have been called
            mock_beads.close_issue.assert_not_called()

    def test_close_beads_issue_skip_verify_phase(self):
        """Test that close_beads_issue can skip phase verification."""
        from orch.complete import close_beads_issue

        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            MockBeads.return_value = mock_beads

            result = close_beads_issue('orch-cli-abc', verify_phase=False)

            # Should NOT have called get_phase_from_comments
            mock_beads.get_phase_from_comments.assert_not_called()
            # Should have called close_issue directly
            mock_beads.close_issue.assert_called_once()
            assert result is True


class TestCompleteAgentWorkBeadsClose:
    """Tests for auto-close beads in complete_agent_work function."""

    def test_complete_agent_work_closes_beads_issue(self, tmp_path):
        """Test that complete_agent_work closes beads issue when agent has beads_id."""
        from orch.complete import complete_agent_work

        # Create minimal workspace structure
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""
**TLDR:** Test workspace

---

# Workspace: test-agent

**Phase:** Complete
**Status:** Complete

---

## Verification Required

- [x] All tests passing

---

## Handoff Notes

Done.
""")

        with patch('orch.complete.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': str(tmp_path),
                'status': 'active',
                'beads_id': 'orch-cli-xyz'
            }

            with patch('orch.complete.verify_agent_work') as mock_verify:
                mock_verify.return_value = Mock(passed=True, errors=[])

                with patch('orch.git_utils.validate_work_committed') as mock_git:
                    mock_git.return_value = (True, None)

                    with patch('orch.complete.close_beads_issue') as mock_close:
                        mock_close.return_value = True

                        with patch('orch.complete.clean_up_agent'):
                            result = complete_agent_work(
                                agent_id='test-agent',
                                project_dir=tmp_path,
                                                            )

                            # Should have called close_beads_issue with db_path=None (no cross-repo)
                            mock_close.assert_called_once_with('orch-cli-xyz', db_path=None)
                            assert result['success'] is True
                            assert result.get('beads_closed') is True

    def test_complete_agent_work_closes_beads_issue_cross_repo(self, tmp_path):
        """Test that complete_agent_work passes beads_db_path for cross-repo spawning."""
        from orch.complete import complete_agent_work

        # Create minimal workspace structure
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""
**TLDR:** Test workspace

---

# Workspace: test-agent

**Phase:** Complete
**Status:** Complete

---

## Verification Required

- [x] All tests passing

---

## Handoff Notes

Done.
""")

        with patch('orch.complete.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': str(tmp_path),
                'status': 'active',
                'beads_id': 'orch-knowledge-abc',
                'beads_db_path': '/path/to/other/repo/.beads/beads.db'
            }

            with patch('orch.complete.verify_agent_work') as mock_verify:
                mock_verify.return_value = Mock(passed=True, errors=[])

                with patch('orch.git_utils.validate_work_committed') as mock_git:
                    mock_git.return_value = (True, None)

                    with patch('orch.complete.close_beads_issue') as mock_close:
                        mock_close.return_value = True

                        with patch('orch.complete.clean_up_agent'):
                            result = complete_agent_work(
                                agent_id='test-agent',
                                project_dir=tmp_path,
                                                            )

                            # Should have called close_beads_issue with cross-repo db_path
                            mock_close.assert_called_once_with(
                                'orch-knowledge-abc',
                                db_path='/path/to/other/repo/.beads/beads.db'
                            )
                            assert result['success'] is True
                            assert result.get('beads_closed') is True

    def test_complete_agent_work_skips_beads_close_when_no_beads_id(self, tmp_path):
        """Test that complete_agent_work doesn't close beads when agent has no beads_id."""
        from orch.complete import complete_agent_work

        # Create minimal workspace structure
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""
**TLDR:** Test workspace

---

# Workspace: test-agent

**Phase:** Complete
**Status:** Complete

---

## Verification Required

- [x] All tests passing

---

## Handoff Notes

Done.
""")

        with patch('orch.complete.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': str(tmp_path),
                'status': 'active'
                # No beads_id field
            }

            with patch('orch.complete.verify_agent_work') as mock_verify:
                mock_verify.return_value = Mock(passed=True, errors=[])

                with patch('orch.git_utils.validate_work_committed') as mock_git:
                    mock_git.return_value = (True, None)

                    with patch('orch.complete.close_beads_issue') as mock_close:
                        with patch('orch.complete.clean_up_agent'):
                            result = complete_agent_work(
                                agent_id='test-agent',
                                project_dir=tmp_path,
                                                            )

                            # Should NOT have called close_beads_issue
                            mock_close.assert_not_called()
                            assert result['success'] is True

    def test_complete_agent_work_warns_on_beads_close_failure(self, tmp_path):
        """Test that complete_agent_work warns but continues when beads close fails."""
        from orch.complete import complete_agent_work

        # Create minimal workspace structure
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""
**TLDR:** Test workspace

---

# Workspace: test-agent

**Phase:** Complete
**Status:** Complete

---

## Verification Required

- [x] All tests passing

---

## Handoff Notes

Done.
""")

        with patch('orch.complete.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': str(tmp_path),
                'status': 'active',
                'beads_id': 'orch-cli-xyz'
            }

            with patch('orch.complete.verify_agent_work') as mock_verify:
                mock_verify.return_value = Mock(passed=True, errors=[])

                with patch('orch.git_utils.validate_work_committed') as mock_git:
                    mock_git.return_value = (True, None)

                    with patch('orch.complete.close_beads_issue') as mock_close:
                        mock_close.return_value = False  # Failure

                        with patch('orch.complete.clean_up_agent'):
                            result = complete_agent_work(
                                agent_id='test-agent',
                                project_dir=tmp_path,
                                                            )

                            # Should still succeed but have warning
                            assert result['success'] is True
                            assert 'beads' in str(result.get('warnings', [])).lower()

class TestCLIBeadsClose:
    """Tests for beads close output in CLI."""

    def test_complete_cli_shows_beads_closed_message(self):
        """Test that CLI shows confirmation when beads issue is closed."""
        from orch.cli import cli

        runner = CliRunner()

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': '/tmp/test-project',
                'status': 'active',
                'beads_id': 'orch-cli-xyz'
            }
            MockRegistry.return_value = mock_registry

            with patch('orch.complete.complete_agent_work') as mock_complete:
                mock_complete.return_value = {
                    'success': True,
                    'verified': True,
                    'beads_closed': True,
                    'errors': [],
                    'warnings': []
                }

                result = runner.invoke(cli, ['complete', 'test-agent'])

                # Should show beads closed message
                assert 'beads' in result.output.lower() or result.exit_code == 0
