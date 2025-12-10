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
        # Default behavior: verify_phase=True (force=False by default)
        mock_close.assert_called_once_with('test-project-abc', verify_phase=True, db_path=None)


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


class TestAutoExitOnComplete:
    """Tests for auto-sending /exit when Phase: Complete but process still running."""

    def test_clean_up_agent_sends_exit_when_graceful_shutdown_fails(self):
        """
        Test that clean_up_agent sends /exit command when graceful shutdown fails.

        When Phase: Complete is verified but processes are still running,
        clean_up_agent should:
        1. Try graceful_shutdown_window (Ctrl+C) - which fails
        2. Auto-send /exit command to the agent
        3. Wait for processes to terminate
        4. Only raise error if still running after exit attempt
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

            # Mock has_active_processes to return True first (processes running),
            # then False after /exit (processes terminated)
            has_active_processes_calls = [True, True, False]  # First call, second after Ctrl+C, third after /exit

            with patch('orch.complete.has_active_processes') as mock_has_processes:
                mock_has_processes.side_effect = has_active_processes_calls

                # graceful_shutdown_window returns False (Ctrl+C didn't work)
                with patch('orch.complete.graceful_shutdown_window', return_value=False):
                    # Mock send_exit_command to track it was called
                    with patch('orch.complete.send_exit_command') as mock_send_exit:
                        mock_send_exit.return_value = True  # Exit succeeded

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

                                # Should NOT raise error - exit command should work
                                clean_up_agent('test-agent')

                                # Verify send_exit_command was called
                                mock_send_exit.assert_called_once_with('@123')

    def test_clean_up_agent_raises_error_if_exit_fails(self):
        """
        Test that clean_up_agent raises error if /exit doesn't terminate processes.

        If even /exit doesn't work, we should still raise RuntimeError.
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

            # Processes always running (both Ctrl+C and /exit fail)
            with patch('orch.complete.has_active_processes', return_value=True):
                with patch('orch.complete.graceful_shutdown_window', return_value=False):
                    with patch('orch.complete.send_exit_command', return_value=False):
                        # Should raise RuntimeError since /exit also failed
                        with pytest.raises(RuntimeError) as exc_info:
                            clean_up_agent('test-agent')

                        assert 'active processes' in str(exc_info.value).lower()
                        assert 'test-agent' in str(exc_info.value)

    def test_clean_up_agent_shows_exit_message(self, capsys):
        """Test that clean_up_agent prints message when sending /exit."""
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

            # Processes running until /exit
            has_active_calls = [True, True, False]
            with patch('orch.complete.has_active_processes') as mock_has_processes:
                mock_has_processes.side_effect = has_active_calls
                with patch('orch.complete.graceful_shutdown_window', return_value=False):
                    with patch('orch.complete.send_exit_command', return_value=True):
                        with patch('orch.complete.list_windows', return_value=[
                            {'index': '1', 'name': 'main', 'id': '@100'},
                            {'index': '2', 'name': 'agent', 'id': '@123'}
                        ]):
                            with patch('subprocess.run') as mock_run:
                                mock_run.return_value = Mock(returncode=0, stdout='orchestrator\n', stderr='')

                                clean_up_agent('test-agent')

                                captured = capsys.readouterr()
                                assert '/exit' in captured.out.lower() or 'sending' in captured.out.lower()


class TestSendExitCommand:
    """Tests for the send_exit_command helper function."""

    def test_send_exit_command_sends_exit_and_waits(self):
        """Test send_exit_command sends /exit and waits for processes to terminate."""
        from orch.complete import send_exit_command

        # Processes terminate after /exit (only checked once at end)
        with patch('orch.complete.has_active_processes', return_value=False):  # Terminated
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                with patch('time.sleep'):  # Don't actually sleep in tests
                    result = send_exit_command('@123')

        assert result is True

        # Verify /exit was sent via tmux send-keys
        send_keys_calls = [call for call in mock_run.call_args_list
                          if 'send-keys' in str(call)]
        assert len(send_keys_calls) >= 1
        # First call should send /exit
        assert '/exit' in str(send_keys_calls[0])

    def test_send_exit_command_returns_false_if_timeout(self):
        """Test send_exit_command returns False if processes don't terminate."""
        from orch.complete import send_exit_command

        # Processes never terminate
        with patch('orch.complete.has_active_processes', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                with patch('time.sleep'):
                    result = send_exit_command('@123', timeout_seconds=5)

        assert result is False


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


class TestBeadsExclusionFromGitValidation:
    """Tests for excluding .beads/ directory from git validation.

    Bug: When running multiple `orch complete` commands in parallel, each completion
    that closes a beads issue modifies `.beads/issues.jsonl`. Subsequent completions
    fail with git validation errors because they see uncommitted changes.

    Fix: Exclude `.beads/` directory from git validation since beads changes are
    committed separately by the beads workflow (bd sync).
    """

    def test_complete_agent_work_excludes_beads_from_git_validation(self, tmp_path):
        """
        Test that complete_agent_work excludes .beads/ from git validation.

        When `.beads/issues.jsonl` is modified (e.g., by a previous `orch complete`
        closing a beads issue), the validation should still pass because `.beads/`
        changes are managed by the beads workflow, not by orch complete.
        """
        import subprocess

        # Setup: Create git repo
        project_dir = tmp_path
        subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=project_dir, check=True, capture_output=True)

        # Create initial commit
        (project_dir / "README.md").write_text("# Test")
        subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=project_dir, check=True, capture_output=True)

        # Setup workspace
        workspace_name = "test-agent"
        workspace_dir = project_dir / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Simulate beads change (as if previous orch complete modified it)
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir(parents=True)
        (beads_dir / "issues.jsonl").write_text('{"id":"test-123","status":"closed"}\n')

        # Verify .beads/ is uncommitted
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=project_dir, capture_output=True, text=True)
        assert '.beads/' in status.stdout or 'issues.jsonl' in status.stdout, "Setup: .beads should be uncommitted"

        # Mock agent with beads_id
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-456'
        }

        # Complete should succeed despite uncommitted .beads/ changes
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.close_beads_issue', return_value=True):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=project_dir
                    )

        # Should succeed - .beads/ changes should be excluded from validation
        assert result['success'] is True, f"Complete should succeed with uncommitted .beads/. Errors: {result.get('errors', [])}"
        assert 'beads' not in str(result.get('errors', [])).lower(), "Should not report .beads/ as uncommitted"

    def test_complete_agent_work_excludes_kn_from_git_validation(self, tmp_path):
        """
        Test that complete_agent_work excludes .kn/ from git validation.

        When `.kn/entries.jsonl` is modified (e.g., by `kn constrain` or `kn decide`
        during parallel agent operations), the validation should still pass because
        `.kn/` changes are managed by the kn sync workflow, not by orch complete.
        """
        import subprocess

        # Setup: Create git repo
        project_dir = tmp_path
        subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=project_dir, check=True, capture_output=True)

        # Create initial commit
        (project_dir / "README.md").write_text("# Test")
        subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=project_dir, check=True, capture_output=True)

        # Setup workspace
        workspace_name = "test-agent"
        workspace_dir = project_dir / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Simulate kn change (as if kn constrain modified it during parallel ops)
        kn_dir = project_dir / ".kn"
        kn_dir.mkdir(parents=True)
        (kn_dir / "entries.jsonl").write_text('{"id":"kn-123","type":"constraint"}\n')

        # Verify .kn/ is uncommitted
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=project_dir, capture_output=True, text=True)
        assert '.kn/' in status.stdout or 'entries.jsonl' in status.stdout, "Setup: .kn should be uncommitted"

        # Mock agent with beads_id
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-456'
        }

        # Complete should succeed despite uncommitted .kn/ changes
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.close_beads_issue', return_value=True):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=project_dir
                    )

        # Should succeed - .kn/ changes should be excluded from validation
        assert result['success'] is True, f"Complete should succeed with uncommitted .kn/. Errors: {result.get('errors', [])}"
        assert '.kn' not in str(result.get('errors', [])), "Should not report .kn/ as uncommitted"

    def test_complete_still_fails_for_other_uncommitted_files(self, tmp_path):
        """
        Test that complete_agent_work still fails for non-.beads uncommitted files.

        We only exclude .beads/ - other uncommitted files should still fail validation.
        """
        import subprocess

        # Setup: Create git repo
        project_dir = tmp_path
        subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=project_dir, check=True, capture_output=True)

        # Create initial commit
        (project_dir / "README.md").write_text("# Test")
        subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=project_dir, check=True, capture_output=True)

        # Setup workspace
        workspace_name = "test-agent"
        workspace_dir = project_dir / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Create uncommitted source file (NOT in .beads/)
        (project_dir / "uncommitted.py").write_text("# uncommitted work")

        # Mock agent with beads_id
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-456'
        }

        # Complete should fail because of uncommitted non-.beads file
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.close_beads_issue', return_value=True):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=project_dir
                    )

        # Should fail - uncommitted.py should cause validation to fail
        assert result['success'] is False, "Complete should fail with uncommitted non-.beads files"
        assert any('uncommitted' in str(e).lower() for e in result.get('errors', [])), \
            f"Should report uncommitted file. Errors: {result.get('errors', [])}"


class TestForceBypassesPhaseCheck:
    """Tests for --force flag bypassing Phase: Complete verification.

    When --force is passed:
    - Trust that if commits exist (git validation passes), work is complete
    - Skip the Phase: Complete check in beads comments
    - This enables completing agents that have done work but forgot to report Phase: Complete
    """

    def test_close_beads_issue_with_force_bypasses_phase_check(self, tmp_path):
        """
        Test that close_beads_issue with force=True skips phase verification.

        Bug: --force bypasses active process checks but NOT phase verification.
        When force=True, we should trust commits over phase status.
        """
        from orch.complete import close_beads_issue, BeadsPhaseNotCompleteError

        # Mock BeadsIntegration - phase is NOT complete
        with patch('orch.complete.BeadsIntegration') as MockBeads:
            mock_beads = Mock()
            mock_beads.get_phase_from_comments.return_value = "Implementing"  # Not complete
            MockBeads.return_value = mock_beads

            # Without force - should raise error
            with pytest.raises(BeadsPhaseNotCompleteError):
                close_beads_issue('test-123', verify_phase=True)

            # With force - should succeed without checking phase
            mock_beads.reset_mock()
            result = close_beads_issue('test-123', verify_phase=False)

            # Should close issue without checking phase
            assert result is True
            mock_beads.close_issue.assert_called_once()
            # Phase should NOT be checked when verify_phase=False
            mock_beads.get_phase_from_comments.assert_not_called()

    def test_complete_agent_work_with_force_bypasses_phase_check(self, tmp_path):
        """
        Test that complete_agent_work with force=True bypasses phase verification.

        When force=True:
        1. Git validation still runs (work must be committed)
        2. Phase: Complete check is skipped
        3. Beads issue is closed regardless of phase status
        """
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Setup git repo
        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-123'
        }

        # Test with force=True - should pass verify_phase=False to close_beads_issue
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.git_utils.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.close_beads_issue', return_value=True) as mock_close:
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path,
                            force=True  # Force flag enabled
                        )

        assert result['success'] is True
        # close_beads_issue should be called with verify_phase=False when force=True
        mock_close.assert_called_once_with('test-123', verify_phase=False, db_path=None)

    def test_complete_agent_work_without_force_still_verifies_phase(self, tmp_path):
        """
        Test that complete_agent_work without force=True still verifies phase.

        Default behavior should remain unchanged - phase verification required.
        """
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-123'
        }

        # Test without force - should pass verify_phase=True (default)
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.git_utils.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.close_beads_issue', return_value=True) as mock_close:
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path,
                            force=False  # Force flag disabled
                        )

        assert result['success'] is True
        # close_beads_issue should be called with verify_phase=True (default)
        mock_close.assert_called_once_with('test-123', verify_phase=True, db_path=None)

    def test_force_still_requires_committed_work(self, tmp_path):
        """
        Test that force=True still requires work to be committed.

        Force bypasses phase check but NOT git validation.
        Work must still be committed for completion to succeed.
        """
        import subprocess

        # Setup: Create git repo with uncommitted changes
        project_dir = tmp_path
        subprocess.run(['git', 'init'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=project_dir, check=True, capture_output=True)

        # Create initial commit
        (project_dir / "README.md").write_text("# Test")
        subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=project_dir, check=True, capture_output=True)

        # Setup workspace
        workspace_name = "test-agent"
        workspace_dir = project_dir / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)

        # Create uncommitted work (not in .beads/)
        (project_dir / "uncommitted_work.py").write_text("# work in progress")

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'beads_id': 'test-123'
        }

        # Even with force=True, should fail due to uncommitted changes
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.close_beads_issue', return_value=True):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=project_dir,
                        force=True  # Force enabled but should still fail
                    )

        # Should fail - uncommitted work blocks completion even with force
        assert result['success'] is False
        assert any('uncommitted' in str(e).lower() for e in result.get('errors', []))
