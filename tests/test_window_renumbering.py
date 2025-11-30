"""
Integration tests for tmux window renumbering scenarios.

Tests that orch commands continue working correctly when tmux renumbers
windows (e.g., after closing a window with gaps, tmux fills the gap).
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from orch.registry import AgentRegistry
from orch.send import send_message_to_agent
from orch.tail import tail_agent_output


class TestWindowRenumbering:
    """Tests for window renumbering resilience."""

    def test_spawn_three_agents_close_middle_commands_still_work(self, tmp_path):
        """
        Scenario: Spawn 3 agents, close middle window, verify remaining agents work.

        Setup:
        - Spawn agent1 in window 1 (@1001)
        - Spawn agent2 in window 2 (@1002)
        - Spawn agent3 in window 3 (@1003)

        Action:
        - Close window 2 (agent2)
        - Tmux renumbers: window 3 becomes window 2

        Verify:
        - agent1 commands still work (window 1, @1001)
        - agent3 commands still work (now window 2, still @1003)
        - Commands use stable window_id, not affected by renumbering
        """
        # Setup registry
        registry_path = tmp_path / "agent-registry.json"
        registry = AgentRegistry(registry_path)

        # Register 3 agents with stable window_ids
        agent1 = registry.register(
            agent_id="agent1",
            task="Task 1",
            window="orchestrator:1",
            window_id="@1001",
            project_dir="/test/project1",
            workspace=".orch/workspace/agent1"
        )

        agent2 = registry.register(
            agent_id="agent2",
            task="Task 2",
            window="orchestrator:2",
            window_id="@1002",
            project_dir="/test/project2",
            workspace=".orch/workspace/agent2"
        )

        agent3 = registry.register(
            agent_id="agent3",
            task="Task 3",
            window="orchestrator:3",
            window_id="@1003",
            project_dir="/test/project3",
            workspace=".orch/workspace/agent3"
        )

        # Verify initial state
        agents = registry.list_active_agents()
        assert len(agents) == 3
        assert agents[0]['window'] == "orchestrator:1"
        assert agents[1]['window'] == "orchestrator:2"
        assert agents[2]['window'] == "orchestrator:3"

        # Simulate closing window 2 (agent2)
        # Mark agent2 as completed
        agent2['status'] = 'completed'
        registry.save()

        # Simulate tmux renumbering after window 2 closes:
        # - Window 1 stays at index 1 (@1001)
        # - Window 3 renumbers to index 2 (@1003)
        # Registry still has old window indices, but window_ids are stable

        # Mock list_windows to show renumbered state
        mock_windows = [
            {'index': '1', 'id': '@1001', 'name': 'agent1'},
            {'index': '2', 'id': '@1003', 'name': 'agent3'},  # Renumbered!
        ]

        with patch('orch.tmux_utils.list_windows', return_value=mock_windows):
            # Test 1: send_message_to_agent for agent1 (unchanged window)
            with patch('orch.send.get_window_by_id') as mock_get_by_id, \
                 patch('subprocess.run') as mock_subprocess, \
                 patch('time.sleep'):
                mock_window1 = Mock()
                mock_get_by_id.return_value = mock_window1

                send_message_to_agent(agent1, "test message 1")

                # Verify it used window_id, not window index
                # Session name is extracted from agent's window field (orchestrator:1 → orchestrator)
                mock_get_by_id.assert_called_once_with("@1001", "orchestrator")
                # Verify subprocess was called with window_id
                assert any("@1001" in str(call) for call in mock_subprocess.call_args_list)

            # Test 2: send_message_to_agent for agent3 (renumbered window)
            with patch('orch.send.get_window_by_id') as mock_get_by_id, \
                 patch('subprocess.run') as mock_subprocess, \
                 patch('time.sleep'):
                mock_window3 = Mock()
                mock_get_by_id.return_value = mock_window3

                send_message_to_agent(agent3, "test message 3")

                # Verify it used stable window_id (@1003), not old window index (3) or new index (2)
                # Session name is extracted from agent's window field (orchestrator:3 → orchestrator)
                mock_get_by_id.assert_called_once_with("@1003", "orchestrator")
                # Verify subprocess was called with stable window_id
                assert any("@1003" in str(call) for call in mock_subprocess.call_args_list)

            # Test 3: tail_agent_output for agent3 (renumbered window)
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout="Agent output line 1\nAgent output line 2",
                    stderr=""
                )

                output = tail_agent_output(agent3, lines=20)

                # Verify subprocess.run was called with stable window_id
                call_args = mock_run.call_args
                assert "@1003" in call_args[0][0]  # Window ID in command
                assert "Agent output line 1" in output

    def test_registry_reconciliation_uses_window_id(self, tmp_path):
        """
        Test that registry reconciliation uses stable window_id for comparison.

        Scenario:
        - Agent registered with window="orchestrator:3", window_id="@1003"
        - Window renumbers to index 2
        - Reconciliation should find agent by window_id, not by window index
        """
        registry_path = tmp_path / "agent-registry.json"
        registry = AgentRegistry(registry_path)

        # Register agent
        agent = registry.register(
            agent_id="test-agent",
            task="Test task",
            window="orchestrator:3",
            window_id="@1003",
            project_dir="/test/project",
            workspace=".orch/workspace/test"
        )

        # Simulate active windows after renumbering (window moved from 3 to 2)
        # Reconcile expects a list of window IDs, not session name
        active_window_ids = ['@1003']  # Agent window still exists, just renumbered

        # Reconcile - should find agent by window_id
        registry.reconcile(active_window_ids)

        # Agent should still be active (found by window_id)
        updated_agent = registry.find("test-agent")
        assert updated_agent is not None
        assert updated_agent['status'] == 'active'

    def test_window_id_fallback_for_legacy_agents(self, tmp_path):
        """
        Test that commands fall back to window target for legacy agents without window_id.

        This ensures backward compatibility with agents registered before window_id was added.
        """
        registry_path = tmp_path / "agent-registry.json"
        registry = AgentRegistry(registry_path)

        # Register legacy agent without window_id
        agent = {
            'id': 'legacy-agent',
            'task': 'Legacy task',
            'window': 'orchestrator:5',
            'window_id': None,  # Legacy agent
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/legacy',
            'spawned_at': '2025-11-12T10:00:00',
            'status': 'active',
            'is_interactive': False
        }
        registry._agents.append(agent)
        registry.save()

        # Test send_message_to_agent falls back to window target
        with patch('orch.send.get_window_by_target') as mock_get_by_target, \
             patch('subprocess.run') as mock_subprocess, \
             patch('time.sleep'):
            mock_window = Mock()
            mock_get_by_target.return_value = mock_window

            send_message_to_agent(agent, "test message")

            # Should fall back to window target when window_id is None
            mock_get_by_target.assert_called_once_with("orchestrator:5")
            # Verify subprocess was called with window target (not window_id)
            assert any("orchestrator:5" in str(call) for call in mock_subprocess.call_args_list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
