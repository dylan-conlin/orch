"""
Tests for orch complete functionality.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from orch.complete import (
    verify_agent_work,
    VerificationResult,
    complete_agent_work,
)


class TestVerification:
    """Tests for agent work verification.

    Note: WORKSPACE.md is no longer used. Verification uses:
    1. beads_id (beads comments) - primary path
    2. primary_artifact (investigation file) - for investigation skills
    3. spawned_at (git commits) - fallback for ad-hoc spawns
    """

    def test_verify_agent_work_passes_with_beads_id(self, tmp_path):
        """Test verification passes when beads_id is provided."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)

        project_dir = tmp_path
        (project_dir / ".git").mkdir()

        # Agent info with beads_id - phase verification happens in close_beads_issue()
        agent_info = {'beads_id': 'test-123'}

        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir,
            agent_info=agent_info
        )

        assert result.passed is True
        assert len(result.errors) == 0

    def test_verify_agent_work_fails_without_beads_or_artifact(self, tmp_path):
        """Test verification fails when no beads_id or primary_artifact."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)

        project_dir = tmp_path

        # No agent_info - cannot verify
        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        assert result.passed is False
        assert any("Cannot verify" in error for error in result.errors)

    def test_verify_agent_work_fails_without_verification_path(self, tmp_path):
        """Test verification fails when no verification method available."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "nonexistent"
        project_dir = tmp_path

        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        assert result.passed is False
        assert any("Cannot verify" in error for error in result.errors)

    def test_verification_result_has_error_details(self, tmp_path):
        """Test that VerificationResult includes detailed error messages."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)

        project_dir = tmp_path

        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        # Should have detailed error about verification
        assert result.passed is False
        assert len(result.errors) > 0
        assert isinstance(result.errors, list)
        # Check for verification error message
        assert any("verify" in error.lower() for error in result.errors)

    def test_verify_adhoc_spawn_passes_with_commits_but_no_workspace(self, tmp_path):
        """Test that ad-hoc spawns (no beads_id, no WORKSPACE.md) can complete when commits exist.

        Bug: When agents are spawned ad-hoc (without --issue), there's no beads_id.
        Verification currently requires either WORKSPACE.md OR beads_id to verify completion.
        Since WORKSPACE.md is no longer created (Dec 4 fix), ad-hoc spawns can't complete
        even when commits exist.

        Fix: Allow completion when commits exist since spawn time, regardless of beads_id.
        """
        import subprocess
        from datetime import datetime, timedelta

        # Setup: Create a git repo with at least one commit
        project_dir = tmp_path
        (project_dir / ".git").mkdir()

        # Initialize git repo properly
        subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_dir, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_dir, check=True)

        # Create initial commit (before agent spawn)
        test_file = project_dir / "initial.txt"
        test_file.write_text("initial content")
        subprocess.run(['git', 'add', 'initial.txt'], cwd=project_dir, check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=project_dir, check=True)

        # Simulate agent spawn time (1 minute ago)
        spawn_time = datetime.now() - timedelta(minutes=1)

        # Create workspace directory but NO WORKSPACE.md (Dec 4 fix - no longer created)
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-adhoc-agent"
        workspace_dir.mkdir(parents=True)
        # Explicitly NOT creating WORKSPACE.md

        # Create agent info (ad-hoc spawn - no beads_id)
        agent_info = {
            'id': 'test-adhoc-agent',
            'workspace': str(workspace_dir.relative_to(project_dir)),
            'spawned_at': spawn_time.isoformat(),
            'status': 'active'
            # NO beads_id - this is an ad-hoc spawn
        }

        # Make a commit AFTER spawn time (simulating agent work)
        work_file = project_dir / "work.txt"
        work_file.write_text("agent work")
        subprocess.run(['git', 'add', 'work.txt'], cwd=project_dir, check=True)
        subprocess.run(['git', 'commit', '-m', 'feat: implement feature'], cwd=project_dir, check=True)

        # Verify should PASS because commits exist since spawn time
        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir,
            agent_info=agent_info
        )

        assert result.passed is True, f"Expected verification to pass with commits. Errors: {result.errors}"
        assert len(result.errors) == 0


class TestCompleteIntegration:
    """Integration tests for complete_agent_work function."""

    def test_complete_agent_work_success(self, tmp_path):
        """Test successful complete workflow with beads_id."""
        # Setup workspace
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Setup git repo
        (tmp_path / ".git").mkdir()

        # Mock agent registry with beads_id for verification
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-123'  # Beads ID for verification
        }

        # Complete the work
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent') as mock_cleanup:
                with patch('orch.git_utils.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.close_beads_issue', return_value=True):
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path
                        )

        # Verify success
        assert result['success'] is True
        assert result['verified'] is True

        # Verify cleanup was called
        mock_cleanup.assert_called_once()

    def test_complete_agent_work_fails_verification_no_beads(self, tmp_path):
        """Test complete workflow fails when no beads_id and no other verification path."""
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active'
        }

        # Complete should fail verification
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent') as mock_cleanup:
                result = complete_agent_work(
                    agent_id=workspace_name,
                    project_dir=tmp_path
                )

        # Verify failure
        assert result['success'] is False
        assert result['verified'] is False
        assert 'errors' in result
        assert len(result['errors']) > 0

        # Verify cleanup was NOT called (don't clean up failed agents)
        mock_cleanup.assert_not_called()

    def test_complete_agent_work_with_beads_issue(self, tmp_path):
        """Test that completing an agent with beads_id closes the beads issue."""
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Setup git repo
        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-project-abc'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.git_utils.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.close_beads_issue', return_value=True) as mock_close:
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path
                        )

        assert result['success'] is True
        assert result.get('beads_closed') is True
        mock_close.assert_called_once_with('test-project-abc', db_path=None)


class TestSessionPreservation:
    """Tests for preserving orchestrator session when completing last agent."""

    def test_clean_up_agent_creates_default_window_when_last_window(self):
        """
        Test that clean_up_agent creates a default window before killing the last window.

        Bug: When orchestrator session has only one window and that agent is completed
        via 'orch complete', the entire tmux session disappears.

        Fix: Before killing the last window, create a default 'main' window to preserve
        the session.
        """
        from orch.complete import clean_up_agent

        # Setup: Mock agent in registry with window_id
        mock_agent = {
            'id': 'test-agent',
            'window_id': '@123',
            'status': 'active'
        }

        # Mock registry to return our agent
        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry_instance = Mock()
            mock_registry_instance.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry_instance

            # Mock has_active_processes to return False (no processes running)
            with patch('orch.complete.has_active_processes', return_value=False):
                # Mock list_windows to return only 1 window (the agent window)
                with patch('orch.complete.list_windows') as mock_list_windows:
                    mock_list_windows.return_value = [{'index': '1', 'name': 'agent-window', 'id': '@123'}]

                    # Mock subprocess.run to capture tmux commands
                    with patch('subprocess.run') as mock_run:
                        # Setup subprocess.run to return session name for display-message
                        def subprocess_side_effect(cmd, *args, **kwargs):
                            if 'display-message' in cmd:
                                # Return mock session name
                                result = Mock()
                                result.returncode = 0
                                result.stdout = 'orchestrator\n'
                                return result
                            return Mock(returncode=0, stdout='', stderr='')

                        mock_run.side_effect = subprocess_side_effect

                        # Execute
                        clean_up_agent('test-agent')

                        # Verify: Should have called tmux new-window to create default window
                        new_window_calls = [call for call in mock_run.call_args_list
                                           if any('new-window' in str(arg) for arg in call[0])]
                        assert len(new_window_calls) == 1, "Should create default window before killing last one"

                        # Verify: new-window call should create 'main' window in 'orchestrator' session
                        new_window_call = new_window_calls[0]
                        assert 'orchestrator' in str(new_window_call), "Should create window in orchestrator session"
                        assert 'main' in str(new_window_call), "Should name default window 'main'"

                        # Verify: Should also call kill-window for the agent
                        kill_window_calls = [call for call in mock_run.call_args_list
                                            if any('kill-window' in str(arg) for arg in call[0])]
                        assert len(kill_window_calls) == 1, "Should kill agent window"

                        # Verify: kill-window should use window_id '@123'
                        kill_window_call = kill_window_calls[0]
                        assert '@123' in str(kill_window_call), "Should kill window by ID"

    def test_clean_up_agent_does_not_create_window_when_multiple_windows(self):
        """
        Test that clean_up_agent does NOT create default window when multiple windows exist.

        When there are multiple windows, killing one should not trigger default window creation.
        """
        from orch.complete import clean_up_agent

        mock_agent = {
            'id': 'test-agent',
            'window_id': '@123',
            'status': 'active'
        }

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry_instance = Mock()
            mock_registry_instance.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry_instance

            # Mock has_active_processes to return False (no processes running)
            with patch('orch.complete.has_active_processes', return_value=False):
                # Mock list_windows to return 3 windows (not the last one)
                with patch('orch.complete.list_windows') as mock_list_windows:
                    mock_list_windows.return_value = [
                        {'index': '1', 'name': 'main', 'id': '@100'},
                        {'index': '2', 'name': 'agent-1', 'id': '@123'},
                        {'index': '3', 'name': 'agent-2', 'id': '@124'}
                    ]

                    with patch('subprocess.run') as mock_run:
                        def subprocess_side_effect(cmd, *args, **kwargs):
                            if 'display-message' in cmd:
                                result = Mock()
                                result.returncode = 0
                                result.stdout = 'orchestrator\n'
                                return result
                            return Mock(returncode=0, stdout='', stderr='')

                        mock_run.side_effect = subprocess_side_effect

                        # Execute
                        clean_up_agent('test-agent')

                        # Verify: Should NOT create new-window (since not last window)
                        new_window_calls = [call for call in mock_run.call_args_list
                                           if any('new-window' in str(arg) for arg in call[0])]
                        assert len(new_window_calls) == 0, "Should NOT create default window when multiple windows exist"

                        # Verify: Should still kill the agent window
                        kill_window_calls = [call for call in mock_run.call_args_list
                                            if any('kill-window' in str(arg) for arg in call[0])]
                        assert len(kill_window_calls) == 1, "Should still kill agent window"


class TestProcessChecking:
    """Tests for checking active processes before kill-window."""

    def test_has_active_processes_returns_true_when_processes_running(self):
        """Test that has_active_processes() returns True when tmux window has running child processes."""
        from orch.complete import has_active_processes

        with patch('subprocess.run') as mock_run:
            # Mock tmux list-panes to return a PID
            mock_run.side_effect = [
                Mock(returncode=0, stdout='12345\n', stderr=''),  # tmux list-panes
                Mock(returncode=0, stdout='12346\n12347\n', stderr='')  # pgrep -P (children found)
            ]

            result = has_active_processes('@123')

            assert result is True, "Should return True when child processes exist"
            assert mock_run.call_count == 2
            # Verify correct tmux command
            assert mock_run.call_args_list[0][0][0] == ['tmux', 'list-panes', '-t', '@123', '-F', '#{pane_pid}']
            # Verify correct pgrep command
            assert mock_run.call_args_list[1][0][0] == ['pgrep', '-P', '12345']

    def test_has_active_processes_returns_false_when_no_processes(self):
        """Test that has_active_processes() returns False when no child processes running."""
        from orch.complete import has_active_processes

        with patch('subprocess.run') as mock_run:
            # Mock tmux list-panes to return a PID
            # Mock pgrep to return nothing (no children)
            mock_run.side_effect = [
                Mock(returncode=0, stdout='12345\n', stderr=''),  # tmux list-panes
                Mock(returncode=1, stdout='', stderr='')  # pgrep -P (no children - returns 1)
            ]

            result = has_active_processes('@123')

            assert result is False, "Should return False when no child processes exist"
            assert mock_run.call_count == 2

    def test_has_active_processes_returns_false_when_window_not_found(self):
        """Test that has_active_processes() returns False when tmux window doesn't exist."""
        from orch.complete import has_active_processes

        with patch('subprocess.run') as mock_run:
            # Mock tmux list-panes to fail (window not found)
            mock_run.return_value = Mock(returncode=1, stdout='', stderr='can\'t find window: @999')

            result = has_active_processes('@999')

            assert result is False, "Should return False when window doesn't exist"
            assert mock_run.call_count == 1  # Should not call pgrep if window not found

    def test_clean_up_agent_raises_error_when_processes_running(self):
        """Test that clean_up_agent raises RuntimeError when agent has active processes."""
        from orch.complete import clean_up_agent

        mock_agent = {
            'id': 'test-agent',
            'window_id': '@123',
            'status': 'active'
        }

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry_instance = Mock()
            mock_registry_instance.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry_instance

            # Mock has_active_processes to return True (processes running)
            # Mock graceful_shutdown_window to return False (shutdown failed)
            with patch('orch.complete.has_active_processes', return_value=True):
                with patch('orch.complete.graceful_shutdown_window', return_value=False):
                    # Should raise RuntimeError when processes are running
                    with pytest.raises(RuntimeError) as exc_info:
                        clean_up_agent('test-agent')

                    assert 'active processes' in str(exc_info.value).lower()
                    assert 'test-agent' in str(exc_info.value)

    def test_clean_up_agent_proceeds_when_no_processes_running(self):
        """Test that clean_up_agent proceeds with cleanup when no active processes."""
        from orch.complete import clean_up_agent

        mock_agent = {
            'id': 'test-agent',
            'window_id': '@123',
            'status': 'active'
        }

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry_instance = Mock()
            mock_registry_instance.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry_instance

            # Mock has_active_processes to return False (no processes)
            with patch('orch.complete.has_active_processes') as mock_has_processes:
                mock_has_processes.return_value = False

                with patch('orch.complete.list_windows') as mock_list_windows:
                    mock_list_windows.return_value = [
                        {'index': '1', 'name': 'main', 'id': '@100'},
                        {'index': '2', 'name': 'agent', 'id': '@123'}
                    ]

                    with patch('subprocess.run') as mock_run:
                        def subprocess_side_effect(cmd, *args, **kwargs):
                            if 'display-message' in cmd:
                                result = Mock()
                                result.returncode = 0
                                result.stdout = 'orchestrator\n'
                                return result
                            return Mock(returncode=0, stdout='', stderr='')

                        mock_run.side_effect = subprocess_side_effect

                        # Should NOT raise error when no processes
                        clean_up_agent('test-agent')

                        # Should have called kill-window
                        kill_window_calls = [call for call in mock_run.call_args_list
                                            if any('kill-window' in str(arg) for arg in call[0])]
                        assert len(kill_window_calls) == 1


# Note: TestWorkspaceSafeReading removed - WORKSPACE.md no longer used
# Beads is now the source of truth for agent state


class TestInvestigationArtifactFallback:
    """Tests for investigation file verification fallback behavior.

    When primary_artifact path doesn't exist, verification should:
    1. Try to get actual path from beads comments (investigation_path)
    2. Search for investigation files in standard locations
    """

    def test_verify_finds_investigation_via_beads_comment(self, tmp_path):
        """Test verification finds investigation file from beads investigation_path comment."""
        from orch.verification import _verify_investigation_artifact

        # Setup: Create actual investigation file at different location
        actual_dir = tmp_path / ".kb" / "investigations" / "debug"
        actual_dir.mkdir(parents=True)
        actual_file = actual_dir / "2025-12-09-debug-my-task.md"
        actual_file.write_text("""
**Phase:** Complete
# Investigation
""")

        # Expected path is different from actual
        expected_path = tmp_path / ".kb" / "investigations" / "2025-12-09-wrong-name.md"

        workspace_path = tmp_path / ".orch" / "workspace" / "my-task-09dec"
        workspace_path.mkdir(parents=True)

        # Mock beads to return actual path
        agent_info = {
            'beads_id': 'test-123',
            'primary_artifact': str(expected_path)
        }

        with patch('orch.verification._get_investigation_path_from_beads') as mock_beads:
            mock_beads.return_value = str(actual_file)

            result = _verify_investigation_artifact(
                primary_artifact=expected_path,
                workspace_path=workspace_path,
                project_dir=tmp_path,
                agent_info=agent_info
            )

        assert result.passed is True
        assert len(result.errors) == 0
        # Should have a warning about the different location
        assert any("found via beads" in w.lower() or "different location" in w.lower()
                   for w in result.warnings)

    def test_verify_searches_investigation_directory_as_fallback(self, tmp_path):
        """Test verification searches .kb/investigations/ when primary_artifact doesn't exist."""
        from orch.verification import _verify_investigation_artifact

        # Setup: Create investigation file that matches workspace name
        inv_dir = tmp_path / ".kb" / "investigations"
        inv_dir.mkdir(parents=True)
        actual_file = inv_dir / "2025-12-09-my-task-name.md"
        actual_file.write_text("""
**Phase:** Complete
# Investigation
""")

        # Expected path doesn't exist
        expected_path = tmp_path / ".kb" / "investigations" / "wrong-name.md"

        workspace_path = tmp_path / ".orch" / "workspace" / "my-task-name-09dec"
        workspace_path.mkdir(parents=True)

        agent_info = {
            'beads_id': 'test-123',
            'primary_artifact': str(expected_path)
        }

        # Mock beads to return None (no path in comments)
        with patch('orch.verification._get_investigation_path_from_beads') as mock_beads:
            mock_beads.return_value = None

            result = _verify_investigation_artifact(
                primary_artifact=expected_path,
                workspace_path=workspace_path,
                project_dir=tmp_path,
                agent_info=agent_info
            )

        assert result.passed is True
        assert len(result.errors) == 0
        # Should have a warning about the different location
        assert any("different location" in w.lower() or "expected" in w.lower()
                   for w in result.warnings)

    def test_verify_fails_when_investigation_not_found(self, tmp_path):
        """Test verification fails when investigation file cannot be found anywhere."""
        from orch.verification import _verify_investigation_artifact

        # No investigation file exists anywhere
        expected_path = tmp_path / ".kb" / "investigations" / "nonexistent.md"

        workspace_path = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_path.mkdir(parents=True)

        agent_info = {
            'beads_id': 'test-123',
            'primary_artifact': str(expected_path)
        }

        # Mock beads to return None (no path in comments)
        with patch('orch.verification._get_investigation_path_from_beads') as mock_beads:
            mock_beads.return_value = None

            result = _verify_investigation_artifact(
                primary_artifact=expected_path,
                workspace_path=workspace_path,
                project_dir=tmp_path,
                agent_info=agent_info
            )

        assert result.passed is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_verify_fails_when_phase_not_complete(self, tmp_path):
        """Test verification fails when investigation exists but Phase is not Complete."""
        from orch.verification import _verify_investigation_artifact

        # Setup: Create investigation file with incomplete phase
        inv_dir = tmp_path / ".kb" / "investigations"
        inv_dir.mkdir(parents=True)
        actual_file = inv_dir / "2025-12-09-my-task.md"
        actual_file.write_text("""
**Phase:** In Progress
# Investigation - still working
""")

        workspace_path = tmp_path / ".orch" / "workspace" / "my-task"
        workspace_path.mkdir(parents=True)

        agent_info = {'beads_id': 'test-123'}

        result = _verify_investigation_artifact(
            primary_artifact=actual_file,
            workspace_path=workspace_path,
            project_dir=tmp_path,
            agent_info=agent_info
        )

        assert result.passed is False
        assert any("In Progress" in e and "Complete" in e for e in result.errors)
