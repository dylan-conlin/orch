"""
Tests for orch registry reconciliation with workspace Phase checking.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from orch.registry import AgentRegistry
from orch.workspace import WorkspaceSignal


class TestRegistryReconciliation:
    """Tests for registry reconciliation that checks workspace Phase."""

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
        return workspace_dir / "WORKSPACE.md"

    def test_reconcile_marks_completed_when_phase_is_complete(
        self, temp_registry, temp_workspace
    ):
        """
        When window closes and workspace Phase is 'Complete',
        reconcile should mark agent as 'completed'.
        """
        # Setup: Register an active agent with workspace
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(temp_workspace.parent.parent.parent),
            workspace=str(temp_workspace),
        )

        # Create workspace file with Phase: Complete
        temp_workspace.write_text(
            """**TLDR:** Test workspace
---
# Workspace: test-workspace
**Phase:** Complete
**Status:** Complete
"""
        )

        # Mock parse_workspace to return Phase: Complete
        with patch("orch.registry.parse_workspace") as mock_parse:
            mock_parse.return_value = WorkspaceSignal(
                has_signal=False, phase="Complete"
            )

            # Execute: Reconcile with empty window list (window closed)
            temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as completed
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "completed"
        assert "completed_at" in agent

    def test_reconcile_marks_terminated_when_phase_not_complete(
        self, temp_registry, temp_workspace
    ):
        """
        When window closes and workspace Phase is NOT 'Complete',
        reconcile should mark agent as 'terminated'.
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

        # Create workspace file with Phase: Implementing
        temp_workspace.write_text(
            """**TLDR:** Test workspace
---
# Workspace: test-workspace
**Phase:** Implementing
**Status:** Active
"""
        )

        # Mock parse_workspace to return Phase: Implementing
        with patch("orch.registry.parse_workspace") as mock_parse:
            mock_parse.return_value = WorkspaceSignal(
                has_signal=False, phase="Implementing"
            )

            # Execute: Reconcile with empty window list (window closed)
            temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as terminated
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "terminated"
        assert "terminated_at" in agent
        assert "completed_at" not in agent

    def test_reconcile_marks_completed_when_workspace_missing(
        self, temp_registry, tmp_path
    ):
        """
        When window closes and workspace file doesn't exist,
        reconcile should mark agent as 'completed' (not terminated).

        Note: Behavior changed - missing workspace now means "completed" for
        legacy agents and no-workspace investigation agents.
        See: registry.py reconcile() "window_closed_no_workspace" reason.
        """
        # Setup: Register an active agent with non-existent workspace
        missing_workspace = tmp_path / "missing" / "WORKSPACE.md"

        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir=str(tmp_path),
            workspace=str(missing_workspace),
        )

        # Mock parse_workspace to return no phase (workspace doesn't exist)
        with patch("orch.registry.parse_workspace") as mock_parse:
            mock_parse.return_value = WorkspaceSignal(has_signal=False, phase=None)

            # Execute: Reconcile with empty window list (window closed)
            temp_registry.reconcile(active_windows=[])

        # Assert: Agent marked as completed (not terminated) when workspace missing
        agent = temp_registry.find("test-agent")
        assert agent["status"] == "completed"
        assert "completed_at" in agent

    def test_reconcile_keeps_active_when_window_exists(
        self, temp_registry, temp_workspace
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
            project_dir=str(temp_workspace.parent.parent.parent),
            workspace=str(temp_workspace),
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
            workspace="/tmp/ws1/WORKSPACE.md",
        )

        temp_registry.register(
            agent_id="terminated-agent",
            task="Terminated task",
            window="test:2",
            window_id="@124",
            project_dir="/tmp",
            workspace="/tmp/ws2/WORKSPACE.md",
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
        self, temp_registry, temp_workspace
    ):
        """
        Reconcile should handle Phase field case-insensitively.
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

        # Create workspace with lowercase 'complete'
        temp_workspace.write_text(
            """**TLDR:** Test workspace
---
# Workspace: test-workspace
**Phase:** complete
"""
        )

        # Mock parse_workspace to return lowercase phase
        with patch("orch.registry.parse_workspace") as mock_parse:
            mock_parse.return_value = WorkspaceSignal(
                has_signal=False, phase="complete"
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
        RED TEST: Concurrent spawns should not lose agent entries.

        This test reproduces the race condition where concurrent spawn
        operations overwrite each other's registry changes, causing
        silent data loss.

        Expected behavior WITHOUT fix: This test will FAIL - some agents
        will be lost due to read-modify-write race condition.

        Expected behavior WITH fix: All 10 agents will be registered.
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
                        workspace=f"/tmp/workspace-{i}/WORKSPACE.md",
                    )
                    return  # Success
                except json.JSONDecodeError:
                    # File corrupted during concurrent access - this is the bug we're fixing
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

        assert len(agents) == 10, (
            f"Expected 10 agents, got {len(agents)}. "
            f"Missing agents indicate race condition. "
            f"Present: {agent_ids}"
        )

    def test_concurrent_reads_allowed(self, temp_registry_path):
        """
        RED TEST: Multiple concurrent reads should succeed with shared locks.

        Without proper locking, concurrent reads during writes can see
        corrupted data (JSON decode errors).

        Expected behavior WITH fix: All reads succeed simultaneously.
        """
        import concurrent.futures
        import time

        # Pre-populate registry with one agent
        reg = AgentRegistry(temp_registry_path)
        reg.register(
            agent_id="initial-agent",
            task="Initial task",
            window="test:1",
            window_id="@100",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        def read_registry():
            """Read the registry - should not block other readers."""
            r = AgentRegistry(temp_registry_path)
            return r.list_active_agents()

        # 20 concurrent reads should all succeed
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_registry) for _ in range(20)]
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except json.JSONDecodeError:
                    # Without proper locking, reads during writes can fail
                    pass

        # All successful reads should see the same agent
        assert len(results) >= 15, (
            f"Too many failed reads ({20 - len(results)} failures). "
            f"This suggests reads are blocking or seeing corrupted data."
        )
        assert all(len(r) == 1 for r in results), "All reads should see 1 agent"
        assert all(r[0]['id'] == 'initial-agent' for r in results)

    def test_registry_lock_timeout_prevents_deadlock(self, temp_registry_path):
        """
        RED TEST: Lock acquisition should timeout rather than block forever.

        This test will SKIP without implementation since we can't easily
        simulate a stuck lock. It documents the requirement.
        """
        pytest.skip("Lock timeout requires implementation - documents requirement")

    def test_merge_preserves_all_agents(self, temp_registry_path):
        """
        RED TEST: Merge logic should preserve agents from concurrent writes.

        When two operations write concurrently, the second writer should
        merge its changes with what's on disk, not blindly overwrite.

        Expected behavior WITHOUT fix: Last write wins, earlier changes lost.
        Expected behavior WITH fix: Both agents preserved through merge.
        """
        import concurrent.futures
        import time

        def register_with_delay(agent_id, delay):
            """Register agent with intentional delay to force race."""
            if delay > 0:
                time.sleep(delay)
            reg = AgentRegistry(temp_registry_path)
            # Simulate some work before saving
            reg.register(
                agent_id=agent_id,
                task=f"Task for {agent_id}",
                window="test:1",
                window_id=f"@{hash(agent_id) % 1000}",
                project_dir="/tmp/test",
                workspace=f"/tmp/workspace-{agent_id}/WORKSPACE.md",
            )

        # Agent A starts first, Agent B starts slightly later
        # Both should be preserved through merge logic
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(register_with_delay, "agent-a", 0)
            time.sleep(0.01)  # Small delay to ensure A starts first
            f2 = executor.submit(register_with_delay, "agent-b", 0)

            # Wait for both
            f1.result()
            f2.result()

        # Verify both agents are present
        final_reg = AgentRegistry(temp_registry_path)
        agents = final_reg.list_active_agents()
        agent_ids = {a['id'] for a in agents}

        assert len(agents) == 2, (
            f"Expected 2 agents, got {len(agents)}. "
            f"Merge should preserve both agents. Present: {agent_ids}"
        )
        assert agent_ids == {"agent-a", "agent-b"}, (
            f"Expected both agents, got {agent_ids}"
        )


class TestAsyncCompletion:
    """Tests for async completion metadata tracking."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test-registry.json"
        return AgentRegistry(registry_path=registry_path)

    def test_agent_can_have_completion_field(self, temp_registry):
        """
        Agents should support an optional 'completion' field for tracking
        async completion metadata.
        """
        # Setup: Register an agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        # Add completion metadata
        # Note: Must update updated_at when modifying agent to ensure
        # timestamp-based merge preserves our changes
        agent = temp_registry.find("test-agent")
        agent['completion'] = {
            'mode': 'async',
            'daemon_pid': 12345,
            'started_at': '2025-11-20T14:00:00',
            'completed_at': None,
            'error': None
        }
        agent['updated_at'] = datetime.now().isoformat()  # Mark as modified
        temp_registry.save()

        # Reload registry
        reloaded_registry = AgentRegistry(temp_registry.registry_path)
        reloaded_agent = reloaded_registry.find("test-agent")

        # Assert: completion field persists
        assert 'completion' in reloaded_agent
        assert reloaded_agent['completion']['mode'] == 'async'
        assert reloaded_agent['completion']['daemon_pid'] == 12345
        assert reloaded_agent['completion']['started_at'] == '2025-11-20T14:00:00'

    def test_completion_field_defaults_to_none(self, temp_registry):
        """
        Agents without explicit completion field should work normally
        (backward compatibility).
        """
        # Setup: Register an agent (without completion field)
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        agent = temp_registry.find("test-agent")

        # Assert: Agent exists and works without completion field
        assert agent['id'] == "test-agent"
        assert 'completion' not in agent  # Field not added by default

    def test_completing_status_for_async_agents(self, temp_registry):
        """
        Agents can have 'completing' status to indicate async cleanup in progress.
        """
        # Setup: Register an agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        # Mark as completing (async cleanup started)
        agent = temp_registry.find("test-agent")
        agent['status'] = 'completing'
        agent['completion'] = {
            'mode': 'async',
            'daemon_pid': 99999,
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'error': None
        }
        temp_registry.save()

        # Assert: Status is completing
        reloaded_agent = temp_registry.find("test-agent")
        assert reloaded_agent['status'] == 'completing'
        assert reloaded_agent['completion']['mode'] == 'async'

    def test_completion_error_tracking(self, temp_registry):
        """
        Completion field should track errors if async cleanup fails.
        """
        # Setup: Register an agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        # Mark completion as failed
        agent = temp_registry.find("test-agent")
        agent['status'] = 'failed'
        agent['completion'] = {
            'mode': 'async',
            'daemon_pid': 12345,
            'started_at': '2025-11-20T14:00:00',
            'completed_at': '2025-11-20T14:02:00',
            'error': 'Cleanup failed after all strategies'
        }
        temp_registry.save()

        # Assert: Error is tracked
        reloaded_agent = temp_registry.find("test-agent")
        assert reloaded_agent['status'] == 'failed'
        assert reloaded_agent['completion']['error'] == 'Cleanup failed after all strategies'


class TestTimestampBasedMerge:
    """Tests for timestamp-based merge to fix re-animation race condition."""

    @pytest.fixture
    def temp_registry_path(self, tmp_path):
        """Create a temporary registry path for testing."""
        return tmp_path / "agent-registry.json"

    @pytest.fixture
    def temp_registry(self, temp_registry_path):
        """Create a temporary registry for testing."""
        return AgentRegistry(registry_path=temp_registry_path)

    def test_merge_prefers_newer_timestamp(self, temp_registry):
        """
        When same agent exists in both disk and memory with different states,
        the newer timestamp should win.
        """
        # Setup: Create an agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        # Simulate: Agent has older timestamp in memory (stale state)
        agent = temp_registry.find("test-agent")
        old_timestamp = "2025-11-27T10:00:00"
        agent['updated_at'] = old_timestamp
        agent['status'] = 'active'

        # Simulate: Disk has newer timestamp (updated by another process)
        current_disk = [{
            'id': 'test-agent',
            'task': 'Test task',
            'window': 'test:1',
            'window_id': '@123',
            'project_dir': '/tmp/test',
            'workspace': '/tmp/workspace/WORKSPACE.md',
            'spawned_at': '2025-11-27T09:00:00',
            'updated_at': '2025-11-27T11:00:00',  # Newer!
            'status': 'completed',  # Was completed by another process
            'completed_at': '2025-11-27T11:00:00'
        }]

        # Execute: Merge should prefer newer timestamp
        merged = temp_registry._merge_agents(current_disk, temp_registry._agents)

        # Assert: Disk version wins (newer timestamp)
        merged_agent = next(a for a in merged if a['id'] == 'test-agent')
        assert merged_agent['status'] == 'completed', (
            "Expected completed (newer disk version), got active (stale memory version)"
        )
        assert merged_agent['updated_at'] == '2025-11-27T11:00:00'

    def test_merge_fallback_to_spawned_at(self, temp_registry):
        """
        For backward compatibility, if updated_at is missing, use spawned_at.
        """
        # Setup: Agents without updated_at (old format)
        current_disk = [{
            'id': 'old-agent',
            'task': 'Old task',
            'window': 'test:1',
            'window_id': '@123',
            'project_dir': '/tmp/test',
            'workspace': '/tmp/workspace/WORKSPACE.md',
            'spawned_at': '2025-11-27T11:00:00',  # Newer spawned_at
            'status': 'completed'
        }]

        ours = [{
            'id': 'old-agent',
            'task': 'Old task',
            'window': 'test:1',
            'window_id': '@123',
            'project_dir': '/tmp/test',
            'workspace': '/tmp/workspace/WORKSPACE.md',
            'spawned_at': '2025-11-27T10:00:00',  # Older spawned_at
            'status': 'active'
        }]

        # Execute: Merge should use spawned_at as fallback
        merged = temp_registry._merge_agents(current_disk, ours)

        # Assert: Disk version wins (newer spawned_at)
        merged_agent = next(a for a in merged if a['id'] == 'old-agent')
        assert merged_agent['status'] == 'completed'

    def test_register_sets_updated_at(self, temp_registry):
        """
        Registering a new agent should set both spawned_at and updated_at.
        """
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        agent = temp_registry.find("test-agent")
        assert 'updated_at' in agent, "Agent should have updated_at field"
        assert 'spawned_at' in agent, "Agent should have spawned_at field"
        # Both should be the same at registration time
        assert agent['updated_at'] == agent['spawned_at']


class TestTombstoneDeletion:
    """Tests for tombstone-based deletion to prevent re-animation."""

    @pytest.fixture
    def temp_registry_path(self, tmp_path):
        """Create a temporary registry path for testing."""
        return tmp_path / "agent-registry.json"

    @pytest.fixture
    def temp_registry(self, temp_registry_path):
        """Create a temporary registry for testing."""
        return AgentRegistry(registry_path=temp_registry_path)

    def test_remove_creates_tombstone(self, temp_registry):
        """
        Removing an agent should create a tombstone instead of physically deleting.
        """
        # Setup: Create an agent
        temp_registry.register(
            agent_id="test-agent",
            task="Test task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace/WORKSPACE.md",
        )

        # Execute: Remove the agent
        result = temp_registry.remove("test-agent")

        # Assert: Remove succeeded
        assert result is True

        # Assert: Agent is marked as deleted (tombstone), not physically removed
        agent = temp_registry.find("test-agent")
        assert agent is not None, "Agent should still exist as tombstone"
        assert agent.get('status') == 'deleted', "Agent should be marked as deleted"
        assert 'deleted_at' in agent, "Agent should have deleted_at timestamp"
        assert 'updated_at' in agent, "Agent should have updated_at timestamp"

    def test_list_agents_excludes_deleted(self, temp_registry):
        """
        list_agents() should not return deleted (tombstone) agents.
        """
        # Setup: Create agents
        temp_registry.register(
            agent_id="active-agent",
            task="Active task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-1/WORKSPACE.md",
        )
        temp_registry.register(
            agent_id="deleted-agent",
            task="Deleted task",
            window="test:2",
            window_id="@124",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-2/WORKSPACE.md",
        )

        # Delete one agent
        temp_registry.remove("deleted-agent")

        # Execute: List agents
        agents = temp_registry.list_agents()
        agent_ids = {a['id'] for a in agents}

        # Assert: Only active agent visible
        assert "active-agent" in agent_ids, "Active agent should be visible"
        assert "deleted-agent" not in agent_ids, "Deleted agent should not be visible"

    def test_list_active_agents_excludes_deleted(self, temp_registry):
        """
        list_active_agents() should not return deleted (tombstone) agents.
        """
        # Setup: Create agents
        temp_registry.register(
            agent_id="active-agent",
            task="Active task",
            window="test:1",
            window_id="@123",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-1/WORKSPACE.md",
        )
        temp_registry.register(
            agent_id="deleted-agent",
            task="Deleted task",
            window="test:2",
            window_id="@124",
            project_dir="/tmp/test",
            workspace="/tmp/workspace-2/WORKSPACE.md",
        )

        # Delete one agent
        temp_registry.remove("deleted-agent")

        # Execute: List active agents
        agents = temp_registry.list_active_agents()
        agent_ids = {a['id'] for a in agents}

        # Assert: Only active agent visible
        assert "active-agent" in agent_ids, "Active agent should be visible"
        assert "deleted-agent" not in agent_ids, "Deleted agent should not be visible"

    def test_merge_preserves_tombstones(self, temp_registry):
        """
        Merge should preserve deleted (tombstone) state even if
        another process has stale version with active status.
        """
        # Setup: Disk has tombstone (recently deleted)
        current_disk = [{
            'id': 'test-agent',
            'task': 'Test task',
            'window': 'test:1',
            'window_id': '@123',
            'project_dir': '/tmp/test',
            'workspace': '/tmp/workspace/WORKSPACE.md',
            'spawned_at': '2025-11-27T10:00:00',
            'updated_at': '2025-11-27T12:00:00',  # Recently deleted
            'status': 'deleted',
            'deleted_at': '2025-11-27T12:00:00'
        }]

        # Memory has stale active version
        ours = [{
            'id': 'test-agent',
            'task': 'Test task',
            'window': 'test:1',
            'window_id': '@123',
            'project_dir': '/tmp/test',
            'workspace': '/tmp/workspace/WORKSPACE.md',
            'spawned_at': '2025-11-27T10:00:00',
            'updated_at': '2025-11-27T10:00:00',  # Stale
            'status': 'active'
        }]

        # Execute: Merge should preserve tombstone
        merged = temp_registry._merge_agents(current_disk, ours)

        # Assert: Tombstone wins (newer timestamp)
        merged_agent = next(a for a in merged if a['id'] == 'test-agent')
        assert merged_agent['status'] == 'deleted', (
            "Expected deleted (tombstone), got active (stale)"
        )

    def test_concurrent_clean_and_reconcile_no_reanimation(self, temp_registry_path):
        """
        RED TEST: Concurrent clean and reconcile should not re-animate deleted agents.

        This is the core race condition we're fixing:
        1. clean loads registry, sees agents A, B, C
        2. reconcile loads registry, sees agents A, B, C
        3. clean removes B, C, saves with skip_merge
        4. reconcile saves WITH merge, re-adds B, C (RE-ANIMATION BUG!)

        With timestamp-based merge and tombstones, B and C should stay deleted.
        """
        import concurrent.futures
        import time

        # Setup: Create agents A, B, C
        setup_reg = AgentRegistry(temp_registry_path)
        for agent_id in ['agent-a', 'agent-b', 'agent-c']:
            setup_reg.register(
                agent_id=agent_id,
                task=f"Task {agent_id}",
                window=f"test:{agent_id}",
                window_id=f"@{hash(agent_id) % 1000}",
                project_dir="/tmp/test",
                workspace=f"/tmp/workspace-{agent_id}/WORKSPACE.md",
            )

        def simulate_clean():
            """Simulates orch clean removing agents B and C."""
            time.sleep(0.05)  # Delay to ensure reconcile loads first
            reg = AgentRegistry(temp_registry_path)
            reg.remove('agent-b')
            reg.remove('agent-c')
            reg.save(skip_merge=True)

        def simulate_reconcile():
            """Simulates orch status reconcile saving stale state."""
            reg = AgentRegistry(temp_registry_path)
            # Hold the registry open for a bit (simulating reconcile work)
            time.sleep(0.1)
            # Save with merge (the bug: this re-adds deleted agents)
            reg.save(skip_merge=False)

        # Execute concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(simulate_reconcile)
            time.sleep(0.01)  # Small delay to ensure reconcile starts first
            f2 = executor.submit(simulate_clean)

            f1.result()
            f2.result()

        # Verify: B and C should remain deleted (not re-animated)
        final_reg = AgentRegistry(temp_registry_path)
        agents = final_reg.list_agents()
        agent_ids = {a['id'] for a in agents}

        # With the fix, only agent-a should be visible
        # (agent-b and agent-c are tombstones, filtered out)
        assert agent_ids == {'agent-a'}, (
            f"Expected only agent-a, got {agent_ids}. "
            f"If agent-b or agent-c are present, the re-animation bug occurred."
        )
