"""
Tests for orch registry reconciliation.

Note: WORKSPACE.md is no longer used for agent state tracking.
Beads is now the source of truth. Reconciliation now:
- Uses primary_artifact phase for investigation agents
- Treats window closure as completion for agents without primary_artifact
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from orch.registry import AgentRegistry


class TestRegistryReconciliation:
    """Tests for registry reconciliation."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test-registry.json"
        return AgentRegistry(registry_path=registry_path)

    @pytest.fixture
    def temp_artifact(self, tmp_path):
        """Create a temporary primary artifact file."""
        artifact_dir = tmp_path / ".kb" / "investigations"
        artifact_dir.mkdir(parents=True)
        return artifact_dir / "test-investigation.md"

    def test_reconcile_marks_completed_when_primary_artifact_complete(
        self, temp_registry, temp_artifact, tmp_path
    ):
        """
        When window closes and primary_artifact Phase is 'Complete',
        reconcile should mark agent as 'completed'.
        """
        # Setup: Register an active agent with primary_artifact
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
            primary_artifact=str(temp_artifact),
        )

        # Create artifact with Status: Complete
        temp_artifact.write_text(
            """**TLDR:** Test investigation
---
# Investigation: Test

**Status:** Complete
"""
        )

        # Execute: Reconcile with empty window list (window closed)
        temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as completed
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "completed"
        assert "completed_at" in agent

    def test_reconcile_marks_terminated_when_primary_artifact_not_complete(
        self, temp_registry, temp_artifact, tmp_path
    ):
        """
        When window closes and primary_artifact Phase is NOT 'Complete',
        reconcile should mark agent as 'terminated'.
        """
        # Setup: Register an active agent with primary_artifact
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
            primary_artifact=str(temp_artifact),
        )

        # Create artifact with Status: Investigating (not complete)
        temp_artifact.write_text(
            """**TLDR:** Test investigation
---
# Investigation: Test

**Status:** Investigating
"""
        )

        # Execute: Reconcile with empty window list (window closed)
        temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as terminated
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "terminated"
        assert "terminated_at" in agent
        assert "completed_at" not in agent

    def test_reconcile_marks_completed_when_no_primary_artifact(
        self, temp_registry, tmp_path
    ):
        """
        When window closes and agent has no primary_artifact,
        reconcile should mark agent as 'completed' (trust window closure).

        Beads is the source of truth for agent state.
        """
        # Setup: Register an active agent without primary_artifact
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
        )

        # Execute: Reconcile with empty window list (window closed)
        temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as completed (trust window closure)
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "completed"
        assert "completed_at" in agent

    def test_reconcile_keeps_active_when_window_exists(
        self, temp_registry, tmp_path
    ):
        """
        When window still exists, reconcile should keep agent as 'active'.
        """
        # Setup: Register an active agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
        )

        # Execute: Reconcile with window still active
        temp_registry.reconcile(active_windows=["@123"])

        # Assert: Agent still active
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "active"
        assert "completed_at" not in agent
        assert "terminated_at" not in agent

    def test_get_history_only_returns_completed_agents(self, temp_registry):
        """
        get_history() should only return agents with status='completed',
        not 'terminated' agents.
        """
        # Setup: Register multiple agents with different statuses
        temp_registry.register(
            agent_id="completed-agent",
            task="Completed task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp",
            workspace="/tmp/ws1",
        )

        temp_registry.register(
            agent_id="terminated-agent",
            task="Terminated task",
            window="test:2",
            window_id="@124",
            project_dir="/tmp",
            workspace="/tmp/ws2",
        )

        # Manually mark one as completed, one as terminated
        completed = temp_registry.find("completed-agent")
        completed["status"] = "completed"
        completed["completed_at"] = datetime.now().isoformat()

        terminated = temp_registry.find("terminated-agent")
        terminated["status"] = "terminated"
        terminated["terminated_at"] = datetime.now().isoformat()

        temp_registry.save()

        # Execute: Get history
        history = temp_registry.get_history()

        # Assert: Only completed agent in history
        assert len(history) == 1
        assert history[0]["id"] == "completed-agent"
        assert history[0]["status"] == "completed"

    def test_reconcile_handles_phase_case_insensitive(
        self, temp_registry, temp_artifact, tmp_path
    ):
        """
        Reconcile should handle Phase/Status field case-insensitively.
        """
        # Setup: Register an active agent with primary_artifact
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
            primary_artifact=str(temp_artifact),
        )

        # Create artifact with lowercase 'complete'
        temp_artifact.write_text(
            """**TLDR:** Test investigation
---
# Investigation: Test

**Status:** complete
"""
        )

        # Execute: Reconcile
        temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as completed (case-insensitive match)
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "completed"


class TestRegistryConcurrency:
    """Tests for registry file locking and concurrent operations."""

    @pytest.fixture
    def temp_registry_path(self, tmp_path):
        """Create a temporary registry path for testing."""
        return tmp_path / "agent-registry.json"

    def test_concurrent_spawn_operations_no_data_loss(self, temp_registry_path):
        """
        Concurrent spawns should not lose agent entries.

        This test verifies that file locking prevents race conditions
        where concurrent spawn operations overwrite each other's registry changes.
        """
        import concurrent.futures

        def register_agent(i):
            """Register a single agent - each creates its own registry instance."""
            import time
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    reg = AgentRegistry(temp_registry_path)
                    reg.register(
                        agent_id=f"agent-{i}",
                        task=f"Task {i}",
                        window=f"orchestrator:{i}",
                        window_id=f"@{100+i}",
                        project_dir="/tmp/test",
                        workspace=f"/tmp/workspace-{i}",
                    )
                    return  # Success
                except json.JSONDecodeError:
                    # File corrupted during concurrent access
                    if attempt < max_retries - 1:
                        time.sleep(0.01 * (attempt + 1))  # Exponential backoff
                        continue
                    raise  # Give up after retries

        # Spawn 10 agents concurrently (simulates real-world concurrent spawns)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_agent, i) for i in range(10)]
            # Wait for all to complete
            concurrent.futures.wait(futures)
            # Check for exceptions
            for future in futures:
                future.result()  # Will raise if any failed

        # Verify all 10 agents are registered (no data loss)
        final_registry = AgentRegistry(temp_registry_path)
        agents = final_registry.list_active_agents()
        agent_ids = {a['id'] for a in agents}

        expected_ids = {f"agent-{i}" for i in range(10)}
        assert agent_ids == expected_ids, f"Missing agents: {expected_ids - agent_ids}"

    def test_file_locking_prevents_concurrent_writes(self, temp_registry_path):
        """
        Test that file locking prevents data corruption during concurrent writes.
        """
        import concurrent.futures
        import threading

        errors = []
        lock = threading.Lock()

        def concurrent_operation(i):
            try:
                reg = AgentRegistry(temp_registry_path)
                reg.register(
                    agent_id=f"concurrent-{i}",
                    task=f"Concurrent task {i}",
                    window=f"test:{i}",
                    window_id=f"@{200+i}",
                    project_dir="/tmp",
                    workspace=f"/tmp/ws-{i}",
                )
            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Run 5 concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(5)]
            concurrent.futures.wait(futures)

        # Verify no errors and all agents registered
        assert len(errors) == 0, f"Errors during concurrent operations: {errors}"

        final_registry = AgentRegistry(temp_registry_path)
        agents = final_registry.list_active_agents()
        assert len(agents) == 5
