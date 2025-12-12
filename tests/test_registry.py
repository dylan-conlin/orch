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

    def test_reconcile_marks_completed_when_window_closed(
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

class TestRegistryFindByBeadsId:
    """Tests for registry.find() searching by beads_id."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test-registry.json"
        return AgentRegistry(registry_path=registry_path)

    def test_find_by_agent_id(self, temp_registry, tmp_path):
        """Test that find() returns agent by agent ID (workspace name)."""
        temp_registry.register(
            agent_id="my-workspace-name",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/my-workspace-name",
            beads_id="project-abc"
        )

        agent = temp_registry.find("my-workspace-name")
        assert agent is not None
        assert agent["id"] == "my-workspace-name"
        assert agent["beads_id"] == "project-abc"

    def test_find_by_beads_id(self, temp_registry, tmp_path):
        """Test that find() returns agent when searching by beads_id."""
        temp_registry.register(
            agent_id="my-workspace-name",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/my-workspace-name",
            beads_id="project-abc"
        )

        # Search by beads_id should find the agent
        agent = temp_registry.find("project-abc")
        assert agent is not None
        assert agent["id"] == "my-workspace-name"
        assert agent["beads_id"] == "project-abc"

    def test_find_prefers_agent_id_over_beads_id(self, temp_registry, tmp_path):
        """Test that find() prefers exact agent ID match over beads_id match.

        When both an exact agent_id match AND a beads_id match exist,
        find() should return the exact agent_id match first.
        """
        # Register agent with beads_id "shared-id"
        temp_registry.register(
            agent_id="agent-1",
            task="Task 1 - matched by beads_id",
            window="test:1",
            window_id="@101",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/agent-1",
            beads_id="shared-id"
        )
        # Register agent with agent_id "shared-id" (same value)
        temp_registry.register(
            agent_id="shared-id",  # Same as first agent's beads_id
            task="Task 2 - matched by agent_id",
            window="test:2",
            window_id="@102",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/shared-id",
            beads_id="other-beads-id"
        )

        # Should find the second agent by exact ID match, not the first by beads_id
        agent = temp_registry.find("shared-id")
        assert agent is not None
        assert agent["id"] == "shared-id"
        assert agent["task"] == "Task 2 - matched by agent_id"

    def test_find_returns_none_for_unknown_id(self, temp_registry, tmp_path):
        """Test that find() returns None for unknown ID."""
        temp_registry.register(
            agent_id="my-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/my-agent",
            beads_id="project-abc"
        )

        agent = temp_registry.find("unknown-id")
        assert agent is None


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


class TestRegistryMerge:
    """Tests for registry merge logic - ensures status changes persist after save/reload."""

    @pytest.fixture
    def temp_registry_path(self, tmp_path):
        """Create a temporary registry path for testing."""
        return tmp_path / "agent-registry.json"

    def test_reconcile_status_change_persists_after_reload(self, temp_registry_path):
        """
        Regression test: Status changes from reconcile() must persist after save() and reload.

        Bug: _merge_agents was using spawned_at for conflict resolution. Since spawned_at
        is identical for disk and in-memory versions, disk always won, discarding status
        changes made by reconcile().

        Fix: Use updated_at (which is set when status changes) for conflict resolution.
        """
        # Step 1: Create a registry and register an agent
        registry1 = AgentRegistry(temp_registry_path)
        registry1.register(
            agent_id="test-agent-merge",
            task="Test merge behavior",
            window="test:1",
            window_id="@456",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-merge",
        )

        # Verify agent has updated_at field
        agent = registry1.find("test-agent-merge")
        assert "updated_at" in agent, "Agent should have updated_at field"
        assert agent["status"] == "active"

        # Step 2: Reconcile with empty window list (window closed)
        # This should mark the agent as completed AND update updated_at
        registry1.reconcile(active_windows=[])

        # Verify status changed in-memory
        agent = registry1.find("test-agent-merge")
        assert agent["status"] == "completed", "Status should be 'completed' in memory"
        assert "completed_at" in agent

        # Step 3: Create a new registry instance and reload from disk
        # This is the critical test - the status change must have been persisted
        registry2 = AgentRegistry(temp_registry_path)
        agent_reloaded = registry2.find("test-agent-merge")

        assert agent_reloaded is not None, "Agent should be found after reload"
        assert agent_reloaded["status"] == "completed", \
            "Bug: Status change was discarded during merge. " \
            "Expected 'completed' but got '{}'".format(agent_reloaded["status"])
        assert "completed_at" in agent_reloaded, "completed_at should persist after reload"

    def test_updated_at_is_set_on_status_changes(self, temp_registry_path):
        """Verify that updated_at is set whenever status changes."""
        import time

        registry = AgentRegistry(temp_registry_path)
        registry.register(
            agent_id="test-updated-at",
            task="Test updated_at field",
            window="test:1",
            window_id="@789",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-updated",
        )

        agent = registry.find("test-updated-at")
        initial_updated_at = agent["updated_at"]

        # Small delay to ensure timestamp changes
        time.sleep(0.01)

        # Reconcile to mark as completed
        registry.reconcile(active_windows=[])

        agent_after = registry.find("test-updated-at")
        assert agent_after["updated_at"] > initial_updated_at, \
            "updated_at should be updated when status changes"

    def test_merge_prefers_newer_updated_at(self, temp_registry_path):
        """
        Test that merge logic correctly prefers the version with newer updated_at.
        """
        import time

        # Create initial registry with an agent
        registry1 = AgentRegistry(temp_registry_path)
        registry1.register(
            agent_id="merge-test",
            task="Merge test",
            window="test:1",
            window_id="@999",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-merge-test",
        )

        # Create second instance (simulates another process reading the registry)
        registry2 = AgentRegistry(temp_registry_path)

        # Small delay
        time.sleep(0.01)

        # First registry updates the agent (reconcile marks as completed)
        registry1.reconcile(active_windows=[])
        # This calls save() which should persist the change

        # Second registry makes a different change (simulate concurrent modification)
        # But registry2 still has the old in-memory state
        agent_in_registry2 = registry2.find("merge-test")
        assert agent_in_registry2["status"] == "active", \
            "Registry2 should have stale in-memory state"

        # When registry2 saves, the merge should detect that disk has newer updated_at
        # and keep the disk version (completed), not the in-memory version (active)
        registry2.save()

        # Reload and verify the completed status was preserved
        registry_final = AgentRegistry(temp_registry_path)
        agent_final = registry_final.find("merge-test")
        assert agent_final["status"] == "completed", \
            "Merge should prefer disk version with newer updated_at"
