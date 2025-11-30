"""
Integration tests for async agent completion workflow.

Tests the complete flow:
1. Agent marked as 'completing'
2. Daemon spawned in background
3. Daemon performs cleanup with timeout cascade
4. Registry updated to 'completed' or 'failed'
"""

import pytest
import time
import signal
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from orch.complete import complete_agent_async
from orch.registry import AgentRegistry


class TestAsyncCompletionIntegration:
    """Integration tests for async completion workflow."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test-registry.json"
        return AgentRegistry(registry_path=registry_path)

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace directory."""
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text(
            """**TLDR:** Test workspace
---
# Workspace: test-workspace
**Phase:** Complete
**Status:** Complete
"""
        )
        return workspace_file

    def test_async_completion_marks_agent_as_completing(
        self, temp_registry, temp_workspace, tmp_path
    ):
        """
        Test that async completion marks agent as 'completing' and spawns daemon.
        """
        # Setup: Register an active agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(temp_workspace.parent.parent.parent),
            workspace=str(temp_workspace),
        )

        # Mock daemon spawning to avoid actually running daemon
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 99999
            mock_popen.return_value = mock_process

            # Execute: Start async completion
            result = complete_agent_async(
                agent_id="test-agent",
                project_dir=temp_workspace.parent.parent.parent,
                roadmap_path=tmp_path / "ROADMAP.org",
                registry_path=temp_registry.registry_path
            )

        # Assert: Agent marked as completing (reload registry to get fresh state)
        reloaded_registry = AgentRegistry(temp_registry.registry_path)
        agent = reloaded_registry.find("test-agent")
        assert agent['status'] == 'completing'
        assert 'completion' in agent
        assert agent['completion']['mode'] == 'async'
        assert agent['completion']['daemon_pid'] == 99999
        assert agent['completion']['started_at'] is not None

        # Assert: Result indicates success
        assert result['success'] is True
        assert result['async_mode'] is True
        assert result['daemon_pid'] == 99999

    def test_async_completion_fails_gracefully_if_daemon_spawn_fails(
        self, temp_registry, temp_workspace, tmp_path
    ):
        """
        Test that async completion handles daemon spawn failures gracefully.
        """
        # Setup: Register an active agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(temp_workspace.parent.parent.parent),
            workspace=str(temp_workspace),
        )

        # Mock daemon spawning to fail
        with patch('subprocess.Popen', side_effect=Exception("Spawn failed")):
            # Execute: Start async completion
            result = complete_agent_async(
                agent_id="test-agent",
                project_dir=temp_workspace.parent.parent.parent,
                roadmap_path=tmp_path / "ROADMAP.org",
                registry_path=temp_registry.registry_path
            )

        # Assert: Agent marked as failed (reload registry to get fresh state)
        reloaded_registry = AgentRegistry(temp_registry.registry_path)
        agent = reloaded_registry.find("test-agent")
        assert agent['status'] == 'failed'
        assert agent['completion']['error'] is not None
        assert 'Spawn failed' in agent['completion']['error']

        # Assert: Result indicates failure
        assert result['success'] is False
        assert 'Failed to spawn cleanup daemon' in result['errors'][0]

    def test_daemon_script_exists_and_is_executable(self):
        """
        Test that cleanup_daemon.py exists and is executable.
        """
        daemon_script = Path(__file__).parent.parent / 'tools' / 'orch' / 'cleanup_daemon.py'

        # Assert: Script exists
        assert daemon_script.exists(), f"Daemon script not found at {daemon_script}"

        # Assert: Script is executable
        assert os.access(daemon_script, os.X_OK), "Daemon script is not executable"

    @pytest.mark.slow
    def test_daemon_cleanup_success_flow(self, temp_registry, temp_workspace, tmp_path):
        """
        Test that daemon successfully cleans up agent when window doesn't exist.

        This is a slow test because it actually runs the daemon script.
        """
        pytest.skip("Integration test - requires tmux setup")

        # This test would:
        # 1. Register agent with fake window_id that doesn't exist
        # 2. Run daemon script
        # 3. Wait for completion
        # 4. Verify agent status updated to 'completed'
