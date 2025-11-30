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
    """Tests for agent work verification."""

    def test_verify_agent_work_passes_when_complete(self, tmp_path):
        """Test verification passes when all requirements met."""
        # Create workspace with Phase: Complete
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-workspace
**Phase:** Complete
**Type:** Implementation

## Deliverables
- Implementation complete
- Tests passing
""")

        # Create project dir with git repo
        project_dir = tmp_path
        (project_dir / ".git").mkdir()

        # Verify should pass
        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        assert result.passed is True
        assert len(result.errors) == 0

    def test_verify_agent_work_fails_when_not_complete(self, tmp_path):
        """Test verification fails when Phase is not Complete."""
        # Create workspace with Phase: Implementing
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-workspace
**Phase:** Implementing
**Type:** Implementation
""")

        project_dir = tmp_path

        # Verify should fail
        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        assert result.passed is False
        assert any("Complete" in error for error in result.errors)

    def test_verify_agent_work_fails_when_workspace_missing(self, tmp_path):
        """Test verification fails when workspace file doesn't exist."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "nonexistent"
        project_dir = tmp_path

        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        assert result.passed is False
        assert any("not found" in error for error in result.errors)

    def test_verification_result_has_error_details(self, tmp_path):
        """Test that VerificationResult includes detailed error messages."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Planning\n")

        project_dir = tmp_path

        result = verify_agent_work(
            workspace_path=workspace_dir,
            project_dir=project_dir
        )

        # Should have detailed error about phase
        assert result.passed is False
        assert len(result.errors) > 0
        assert isinstance(result.errors, list)
        # Check specific error message
        assert any("Complete" in error for error in result.errors)


class TestCompleteIntegration:
    """Integration tests for complete_agent_work function."""

    def test_complete_agent_work_success(self, tmp_path):
        """Test successful complete workflow."""
        # Setup workspace
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-workspace
**Phase:** Complete
**Type:** Implementation
""")

        # Setup git repo
        (tmp_path / ".git").mkdir()

        # Mock agent registry
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active'
        }

        # Complete the work
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent') as mock_cleanup:
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path
                    )

        # Verify success
        assert result['success'] is True
        assert result['verified'] is True

        # Verify cleanup was called
        mock_cleanup.assert_called_once()

    def test_complete_agent_work_fails_verification(self, tmp_path):
        """Test complete workflow fails when verification fails."""
        workspace_name = "test-workspace"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        # Phase is NOT Complete
        workspace_file.write_text("""# Workspace: test-workspace
**Phase:** Implementing
""")

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
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-workspace
**Phase:** Complete
**Type:** Implementation
""")

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
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.close_beads_issue', return_value=True) as mock_close:
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path
                        )

        assert result['success'] is True
        assert result.get('beads_closed') is True
        mock_close.assert_called_once_with('test-project-abc')


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

            # Mock list_windows to return only 1 window (the agent window)
            with patch('orch.tmux_utils.list_windows') as mock_list_windows:
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

            # Mock list_windows to return 3 windows (not the last one)
            with patch('orch.tmux_utils.list_windows') as mock_list_windows:
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

                with patch('orch.tmux_utils.list_windows') as mock_list_windows:
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


class TestWorkspaceSafeReading:
    """Tests for the workspace safe reading functionality that prevents race conditions."""

    def test_read_workspace_safe_returns_content(self, tmp_path):
        """Test basic read functionality."""
        from orch.workspace import read_workspace_safe

        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Complete\nTest content")

        # Wait a bit for file to be "stable"
        import time
        time.sleep(0.6)

        content = read_workspace_safe(workspace_file)

        assert "**Phase:** Complete" in content
        assert "Test content" in content

    def test_read_workspace_safe_raises_on_missing_file(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        from orch.workspace import read_workspace_safe

        workspace_file = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            read_workspace_safe(workspace_file)

    def test_read_workspace_safe_waits_for_stability(self, tmp_path):
        """Test that read waits for file to stabilize."""
        from orch.workspace import read_workspace_safe
        import time
        import threading

        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text("Initial content")

        # Create a flag to track if we read during the "write"
        read_during_write = []

        def update_file():
            # Simulate slow write by updating file multiple times
            for i in range(3):
                workspace_file.write_text(f"Content update {i}")
                time.sleep(0.1)
            workspace_file.write_text("**Phase:** Complete\nFinal content")

        # Start the "writer" thread
        writer = threading.Thread(target=update_file)
        writer.start()

        # Let writer start
        time.sleep(0.05)

        # Read with stability check (should wait for writes to complete)
        content = read_workspace_safe(workspace_file, stability_window=0.2)

        writer.join()

        # Should have final content (not an intermediate state)
        assert "Final content" in content

    def test_read_workspace_safe_without_stability_check(self, tmp_path):
        """Test immediate read without stability check."""
        from orch.workspace import read_workspace_safe

        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Complete\nImmediate read content")

        # Read immediately without stability check
        content = read_workspace_safe(workspace_file, check_stability=False)

        assert "Immediate read content" in content

    def test_parse_workspace_uses_safe_read(self, tmp_path):
        """Test that parse_workspace uses the safe reading mechanism."""
        from orch.workspace import parse_workspace
        import time

        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Complete\n**Status:** Active")

        # Wait for stability
        time.sleep(0.6)

        signal = parse_workspace(workspace_file)

        assert signal.phase == "Complete"

    def test_parse_workspace_verification_uses_safe_read(self, tmp_path):
        """Test that parse_workspace_verification uses the safe reading mechanism."""
        from orch.workspace import parse_workspace_verification
        import time

        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text("""**Phase:** Complete
**Status:** Active

## Verification Required

- [x] Test passed
- [x] Code reviewed
""")

        # Wait for stability
        time.sleep(0.6)

        data = parse_workspace_verification(workspace_file)

        assert data.phase == "Complete"
        assert data.verification_complete is True
