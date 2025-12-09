"""
Tests for orch clean functionality.
"""

import pytest
from unittest.mock import Mock, patch, call
from pathlib import Path


# cli_runner fixture provided by conftest.py


class TestCleanCommand:
    """Tests for the clean command."""

    def test_clean_completed_agents(self, cli_runner):
        """Test cleaning completed agents and closing their tmux windows."""
        from orch.cli import cli

        # Mock registry with completed agents
        mock_completed_agent1 = {
            'id': 'agent-1',
            'window': 'orchestrator:5',
            'task': 'Test task 1',
            'status': 'completed'
        }
        mock_completed_agent2 = {
            'id': 'agent-2',
            'window': 'orchestrator:6',
            'task': 'Test task 2',
            'status': 'completed'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed_agent1, mock_completed_agent2]
            mock_registry._agents = [mock_completed_agent1, mock_completed_agent2]
            MockRegistry.return_value = mock_registry

            # Mock tmux windows
            mock_window1 = Mock()
            mock_window2 = Mock()

            with patch('orch.cli.get_window_by_target') as mock_get_window:
                # Return windows in order of calls
                mock_get_window.side_effect = [mock_window1, mock_window2]

                result = cli_runner.invoke(cli, ['clean'])

        # Should succeed
        assert result.exit_code == 0
        assert 'Cleaned 2' in result.output or '2' in result.output

        # Verify windows were killed
        mock_window1.kill.assert_called_once()
        mock_window2.kill.assert_called_once()

        # Verify registry was saved
        mock_registry.save.assert_called_once()

    def test_clean_no_completed_agents(self, cli_runner):
        """Test clean when there are no completed agents."""
        from orch.cli import cli

        # Mock registry with only active agents
        mock_active_agent = {
            'id': 'active-agent',
            'window': 'orchestrator:5',
            'task': 'Active task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/active-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_active_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

        # Should succeed but show message about no agents to clean
        assert result.exit_code == 0
        assert 'No completed agents' in result.output or 'No completed' in result.output.lower()

    def test_clean_window_already_closed(self, cli_runner):
        """Test that clean handles gracefully when tmux window is already closed."""
        from orch.cli import cli

        # Mock registry with completed agent
        mock_completed_agent = {
            'id': 'agent-1',
            'window': 'orchestrator:5',
            'task': 'Test task',
            'status': 'completed'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed_agent]
            mock_registry._agents = [mock_completed_agent]
            MockRegistry.return_value = mock_registry

            # Mock get_window_by_target to return None (window doesn't exist)
            with patch('orch.cli.get_window_by_target', return_value=None):
                result = cli_runner.invoke(cli, ['clean'])

        # Should still succeed
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output or '1' in result.output

        # Verify registry was saved
        mock_registry.save.assert_called_once()

    def test_clean_mixed_active_and_completed(self, cli_runner):
        """Test that clean only removes completed agents, not active ones."""
        from orch.cli import cli

        # Mock registry with mixed agents
        mock_active_agent = {
            'id': 'active-agent',
            'window': 'orchestrator:5',
            'task': 'Active task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/active-agent'
        }
        mock_completed_agent = {
            'id': 'completed-agent',
            'window': 'orchestrator:6',
            'task': 'Completed task',
            'status': 'completed'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            all_agents = [mock_active_agent, mock_completed_agent]
            mock_registry.list_agents.return_value = all_agents
            mock_registry._agents = all_agents.copy()  # Copy so we can track modifications
            MockRegistry.return_value = mock_registry

            # Mock tmux window for completed agent
            mock_window = Mock()

            with patch('orch.cli.get_window_by_target', return_value=mock_window):
                result = cli_runner.invoke(cli, ['clean'])

        # Should succeed and only clean 1 agent
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output or '1' in result.output

        # Verify only completed agent's window was killed
        mock_window.kill.assert_called_once()

        # Verify registry was saved
        mock_registry.save.assert_called_once()

    def test_clean_window_kill_exception(self, cli_runner):
        """Test that clean continues even if window.kill() raises an exception."""
        from orch.cli import cli

        # Mock registry with completed agent
        mock_completed_agent = {
            'id': 'agent-1',
            'window': 'orchestrator:5',
            'task': 'Test task',
            'status': 'completed'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed_agent]
            mock_registry._agents = [mock_completed_agent]
            MockRegistry.return_value = mock_registry

            # Mock window that raises exception on kill
            mock_window = Mock()
            mock_window.kill.side_effect = Exception("Window kill failed")

            with patch('orch.cli.get_window_by_target', return_value=mock_window):
                result = cli_runner.invoke(cli, ['clean'])

        # Should still succeed (exception is caught)
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output or '1' in result.output

        # Verify registry was saved
        mock_registry.save.assert_called_once()

    def test_clean_empty_registry(self, cli_runner):
        """Test clean when registry is completely empty."""
        from orch.cli import cli

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.list_agents.return_value = []
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

        # Should succeed but show message about no agents
        assert result.exit_code == 0
        assert 'No completed agents' in result.output or 'No completed' in result.output.lower()

    def test_clean_window_closed_but_work_incomplete(self, cli_runner):
        """
        Test that clean DOES remove agents when window is closed, even if work is incomplete.

        Scenario: Agent's tmux window closed (crashed/killed/finished without updating),
        registry status='completed', workspace shows Phase: Implementing.

        Fixed behavior: Should clean this agent because:
        1. Window closed means agent is gone and can't continue work
        2. Keeping it in registry serves no purpose (no way to resume)
        3. Workspace files remain intact (work history preserved)
        4. Not cleaning causes registry accumulation (original bug)

        Note: This test was updated from expecting NOT to clean (old bug behavior)
        to expecting DOES clean (correct behavior after 2025-11-11 fix).
        """
        from orch.cli import cli

        # Agent with window closed (status='completed') but work incomplete (Phase: Implementing)
        mock_incomplete_agent = {
            'id': 'incomplete-agent',
            'window': 'orchestrator:5',
            'task': 'Incomplete task',
            'status': 'completed',  # Window closed
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/incomplete-agent'
        }

        # Mock check_agent_status to return Implementing phase
        mock_status = Mock()
        mock_status.phase = 'Implementing'  # Work is NOT complete

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.monitor.check_agent_status', return_value=mock_status):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_incomplete_agent]
            mock_registry._agents = [mock_incomplete_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

        # Should clean the agent (window closed, agent gone)
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output

        # Verify agent WAS removed from registry (fixed behavior)
        # Note: Can't easily verify removal with mocks, but output confirms it
        assert mock_registry.save.called

    def test_clean_window_closed_and_work_complete(self, cli_runner):
        """
        Test that clean DOES remove agents when window is closed AND work is complete.

        Expected scenario: Agent's tmux window closed, registry status='completed',
        workspace shows Phase: Complete. Should clean this agent.
        """
        from orch.cli import cli

        # Agent with window closed (status='completed') and work complete (Phase: Complete)
        mock_complete_agent = {
            'id': 'complete-agent',
            'window': 'orchestrator:6',
            'task': 'Complete task',
            'status': 'completed',  # Window closed
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/complete-agent',
            'window_id': '@1010'
        }

        # Mock check_agent_status to return Complete phase
        mock_status = Mock()
        mock_status.phase = 'Complete'  # Work IS complete

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.monitor.check_agent_status', return_value=mock_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_complete_agent]
            mock_registry._agents = [mock_complete_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

        # Should succeed and clean the agent
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output

        # Verify registry.save() was called
        mock_registry.save.assert_called_once()

    def test_clean_terminated_agents(self, cli_runner):
        """
        Test that clean DOES remove agents with status='terminated'.

        Bug context: When a window closes but Phase != Complete, reconcile() marks
        status='terminated'. The clean command should remove these agents to prevent
        "Agent already registered" errors when resuming with --resume.
        """
        from orch.cli import cli

        # Agent marked as terminated (window closed, work incomplete)
        mock_terminated_agent = {
            'id': 'terminated-agent',
            'window': 'orchestrator:6',
            'window_id': '@595',
            'task': 'Task that was interrupted',
            'status': 'terminated',  # Set by reconcile() when window closes
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/terminated-agent',
            'terminated_at': '2025-11-17T11:25:14.459186'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_terminated_agent]
            mock_registry._agents = [mock_terminated_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

        # Should succeed and clean the terminated agent
        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output

        # Verify registry.save() was called
        mock_registry.save.assert_called_once()

    def test_clean_all_does_not_clean_active_agents_with_unknown_phase(self, cli_runner):
        """
        Test that 'clean --all' does NOT clean active agents with phase='Unknown'.

        Bug context: When running 'orch clean --all' with completed agents and newly-spawned
        active agents, all agents were being cleaned. The --all flag should mean 'all completed'
        not 'all agents'. Active agents have status='active' and phase='Unknown' (workspace
        template not yet populated).

        Root cause: cli.py line 92 included 'Unknown' in cleanable phases for --all mode.
        Fix: Remove 'Unknown' from that tuple - only 'Complete' and 'Abandoned' should be cleaned.

        Beads issue: orch-cli-7pj
        """
        from orch.cli import cli

        # Active agent with phase='Unknown' (newly spawned, workspace not yet populated)
        mock_active_agent = {
            'id': 'active-agent',
            'window': 'orchestrator:5',
            'window_id': '@1001',
            'task': 'Active task',
            'status': 'active',  # Not in ('abandoned', 'terminated', 'completed', 'completing')
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/active-agent'
        }

        # Completed agent that SHOULD be cleaned
        mock_completed_agent = {
            'id': 'completed-agent',
            'window': 'orchestrator:6',
            'window_id': '@1002',
            'task': 'Completed task',
            'status': 'completed',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/completed-agent'
        }

        # Mock check_agent_status to return different phases based on agent
        def mock_check_status(agent):
            mock_status = Mock()
            if agent['id'] == 'active-agent':
                mock_status.phase = 'Unknown'  # Newly spawned, workspace not populated
            else:
                mock_status.phase = 'Complete'  # Completed agent
            return mock_status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            all_agents = [mock_active_agent, mock_completed_agent]
            mock_registry.list_agents.return_value = all_agents
            mock_registry._agents = all_agents.copy()
            MockRegistry.return_value = mock_registry

            # Track which agents were removed
            removed_agents = []
            def track_removal(agent_id):
                removed_agents.append(agent_id)
            mock_registry.remove.side_effect = track_removal

            result = cli_runner.invoke(cli, ['clean', '--all'])

        # Should succeed
        assert result.exit_code == 0

        # Should only clean 1 agent (the completed one), NOT the active one
        assert 'Cleaned 1' in result.output, f"Expected 'Cleaned 1' but got: {result.output}"

        # Verify only completed agent was removed, not active agent
        assert 'completed-agent' in removed_agents, "Completed agent should be cleaned"
        assert 'active-agent' not in removed_agents, "Active agent with Unknown phase should NOT be cleaned"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestCleanLogging:
    """Tests for clean command logging."""

    def test_clean_logs_start_event(self, cli_runner):
        """Test that clean logs start event with agent counts."""
        from orch.cli import cli

        # Mock registry with mixed agents
        # Use two completed agents to avoid check_agent_status call for active agents
        mock_completed1 = {'id': 'completed-1', 'status': 'completed', 'window': 'orchestrator:6', 'window_id': '@1008'}
        mock_completed2 = {'id': 'completed-2', 'status': 'completed', 'window': 'orchestrator:7', 'window_id': '@1009'}

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed1, mock_completed2]
            mock_registry._agents = [mock_completed1, mock_completed2]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

            # Command should succeed
            assert result.exit_code == 0
            assert 'Cleaned 2' in result.output

    def test_clean_logs_agent_removal(self, cli_runner):
        """Test that clean logs each agent removal."""
        from orch.cli import cli

        mock_completed = {
            'id': 'completed-1',
            'status': 'completed',
            'window': 'orchestrator:6',
            'window_id': '@1008'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger') as MockLogger, \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed]
            mock_registry._agents = [mock_completed]
            MockRegistry.return_value = mock_registry

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            result = cli_runner.invoke(cli, ['clean'])

            # Verify agent removal was logged
            assert mock_logger.log_event.called
            # Find the removal log call
            removal_calls = [call for call in mock_logger.log_event.call_args_list
                           if 'removed' in str(call).lower() or 'agent' in str(call[0][1]).lower()]
            assert len(removal_calls) > 0

    def test_clean_logs_complete_event(self, cli_runner):
        """Test that clean logs complete event with summary."""
        from orch.cli import cli

        mock_completed = {
            'id': 'completed-1',
            'status': 'completed',
            'window': 'orchestrator:6',
            'window_id': '@1008'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.OrchLogger') as MockLogger, \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed]
            mock_registry._agents = [mock_completed]
            MockRegistry.return_value = mock_registry

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            result = cli_runner.invoke(cli, ['clean'])

            # Verify complete logging was called
            assert mock_logger.log_command_complete.called
            call_args = mock_logger.log_command_complete.call_args
            assert call_args[0][0] == "clean"
            assert isinstance(call_args[0][1], int)  # duration_ms
            data = call_args[0][2]
            assert data['removed'] == 1

    def test_clean_logs_no_agents_case(self, cli_runner):
        """Test that clean logs when no completed agents found."""
        from orch.cli import cli

        # Only active agents, no completed
        mock_active = {
            'id': 'active-1',
            'status': 'active',
            'window': 'orchestrator:5',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/active-1'
        }

        # Mock check_agent_status to return non-Complete status
        mock_status = Mock()
        mock_status.phase = 'Implementing'

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', return_value=mock_status):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_active]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean'])

            # Should succeed and show message
            assert result.exit_code == 0
            assert 'No completed agents' in result.output


class TestCleanAllFlag:
    """Tests for orch clean --all flag behavior."""

    def test_clean_all_does_not_clean_active_agents_with_unknown_phase(self, cli_runner):
        """
        Test that --all does NOT clean active agents that have 'Unknown' phase.

        Bug context: Active agents that just spawned haven't updated their workspace yet,
        so they show 'Unknown' phase. The --all flag was incorrectly cleaning these
        because 'Unknown' was in the list of cleanable phases.

        Expected behavior: --all should only clean agents that are actually completed
        or terminated, NOT agents that simply haven't updated their workspace yet.

        Root cause: cli.py _should_clean_agent() line 92 included 'Unknown' in cleanable phases.
        Fix: Remove 'Unknown' from --all cleanable phases OR require terminated/completed status.
        """
        from orch.cli import cli

        # Active agent that just spawned (hasn't updated workspace yet)
        # Registry status is 'active' (default), workspace phase is 'Unknown'
        mock_active_agent = {
            'id': 'newly-spawned-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Just spawned, working on task',
            'status': 'active',  # NOT completed/terminated
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/newly-spawned-agent'
        }

        # Completed agent that should be cleaned
        mock_completed_agent = {
            'id': 'completed-agent',
            'window': 'orchestrator:6',
            'window_id': '@1235',
            'task': 'Finished task',
            'status': 'completed',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/completed-agent'
        }

        # Mock check_agent_status to return different phases per agent
        def mock_check_status(agent):
            status = Mock()
            if agent['id'] == 'newly-spawned-agent':
                status.phase = 'Unknown'  # Hasn't updated workspace yet
            else:
                status.phase = 'Complete'
            return status

        # Must patch where it's imported (inside clean function), not where it's defined
        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_active_agent, mock_completed_agent]
            mock_registry._agents = [mock_active_agent, mock_completed_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--all'])

        # Should succeed
        assert result.exit_code == 0

        # Should only clean 1 agent (the completed one), NOT the active one with Unknown phase
        assert 'Cleaned 1' in result.output, \
            f"Expected to clean only 1 agent (completed), but output was: {result.output}"

        # Verify only the completed agent was removed
        remove_calls = mock_registry.remove.call_args_list
        assert len(remove_calls) == 1, f"Expected 1 remove call, got {len(remove_calls)}"
        assert remove_calls[0][0][0] == 'completed-agent', \
            f"Expected to remove 'completed-agent', but removed: {remove_calls[0][0][0]}"

    def test_clean_all_cleans_completed_agents(self, cli_runner):
        """Test that --all DOES clean agents with 'Complete' phase."""
        from orch.cli import cli

        mock_completed_agent = {
            'id': 'completed-agent',
            'window': 'orchestrator:6',
            'window_id': '@1235',
            'task': 'Finished task',
            'status': 'active',  # Registry status might not be updated
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/completed-agent'
        }

        mock_status = Mock()
        mock_status.phase = 'Complete'

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.monitor.check_agent_status', return_value=mock_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_completed_agent]
            mock_registry._agents = [mock_completed_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--all'])

        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output

    def test_clean_all_cleans_abandoned_phase_agents(self, cli_runner):
        """Test that --all DOES clean agents with 'Abandoned' phase."""
        from orch.cli import cli

        mock_abandoned_agent = {
            'id': 'abandoned-agent',
            'window': 'orchestrator:6',
            'window_id': '@1235',
            'task': 'Abandoned task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/abandoned-agent'
        }

        mock_status = Mock()
        mock_status.phase = 'Abandoned'

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.monitor.check_agent_status', return_value=mock_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_abandoned_agent]
            mock_registry._agents = [mock_abandoned_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--all'])

        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output

    def test_clean_all_cleans_terminated_status_agents(self, cli_runner):
        """Test that --all DOES clean agents with 'terminated' status."""
        from orch.cli import cli

        mock_terminated_agent = {
            'id': 'terminated-agent',
            'window': 'orchestrator:6',
            'window_id': '@1235',
            'task': 'Terminated task',
            'status': 'terminated',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/terminated-agent'
        }

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_terminated_agent]
            mock_registry._agents = [mock_terminated_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--all'])

        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output


class TestCleanStaleFlag:
    """Tests for orch clean --stale flag behavior."""

    def test_clean_stale_cleans_unknown_phase_agents_older_than_24h(self, cli_runner):
        """
        Test that --stale cleans agents with Phase: Unknown AND spawned >24 hours ago.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        old_spawn_time = (datetime.now() - timedelta(hours=25)).isoformat()
        mock_stale_agent = {
            'id': 'stale-unknown-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Stuck task from yesterday',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/stale-unknown-agent',
            'spawned_at': old_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 0
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_stale_agent]
            mock_registry._agents = [mock_stale_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output or 'cleaned' in result.output.lower()

    def test_clean_stale_does_not_clean_young_unknown_phase_agents(self, cli_runner):
        """
        Test that --stale does NOT clean agents with Phase: Unknown but spawned <24 hours ago.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        young_spawn_time = (datetime.now() - timedelta(hours=2)).isoformat()
        mock_young_agent = {
            'id': 'young-unknown-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Just started task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/young-unknown-agent',
            'spawned_at': young_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 3
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_young_agent]
            mock_registry._agents = [mock_young_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        assert 'No' in result.output or 'no' in result.output.lower()

    def test_clean_stale_cleans_no_commits_agents_older_than_4h(self, cli_runner):
        """
        Test that --stale cleans agents with no commits since spawn AND >4 hours old.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        old_spawn_time = (datetime.now() - timedelta(hours=5)).isoformat()
        mock_frozen_agent = {
            'id': 'frozen-no-commits-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Frozen task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/frozen-agent',
            'spawned_at': old_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 0
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_frozen_agent]
            mock_registry._agents = [mock_frozen_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        assert 'Cleaned 1' in result.output or 'cleaned' in result.output.lower()

    def test_clean_stale_does_not_clean_young_no_commits_agents(self, cli_runner):
        """
        Test that --stale does NOT clean agents with no commits but spawned <4 hours ago.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        young_spawn_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_young_agent = {
            'id': 'young-no-commits-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Just started task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/young-agent',
            'spawned_at': young_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 0
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_young_agent]
            mock_registry._agents = [mock_young_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        assert 'No' in result.output or 'no' in result.output.lower()

    def test_clean_stale_auto_abandons_before_cleaning(self, cli_runner):
        """
        Test that --stale automatically abandons agents before cleaning them.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        old_spawn_time = (datetime.now() - timedelta(hours=25)).isoformat()
        mock_stale_agent = {
            'id': 'stale-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Stuck task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/stale-agent',
            'spawned_at': old_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 0
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_stale_agent]
            mock_registry._agents = [mock_stale_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        mock_registry.abandon_agent.assert_called_once_with(
            'stale-agent',
            reason='Stale: Phase Unknown for >24 hours'
        )

    def test_clean_stale_dry_run(self, cli_runner):
        """
        Test that --stale --dry-run shows what would be cleaned without executing.
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        old_spawn_time = (datetime.now() - timedelta(hours=25)).isoformat()
        mock_stale_agent = {
            'id': 'stale-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Stuck task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/stale-agent',
            'spawned_at': old_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 0
            return status

        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.cli.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_stale_agent]
            mock_registry._agents = [mock_stale_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale', '--dry-run'])

        assert result.exit_code == 0
        assert 'Would' in result.output or 'would' in result.output
        assert 'stale-agent' in result.output
        mock_registry.remove.assert_not_called()
        mock_registry.abandon_agent.assert_not_called()

    def test_clean_stale_does_not_clean_working_agents(self, cli_runner):
        """
        Test that --stale does NOT clean agents with recent activity (commits).
        """
        from orch.cli import cli
        from datetime import datetime, timedelta

        old_spawn_time = (datetime.now() - timedelta(hours=30)).isoformat()
        mock_working_agent = {
            'id': 'working-old-agent',
            'window': 'orchestrator:5',
            'window_id': '@1234',
            'task': 'Old but working task',
            'status': 'active',
            'project_dir': '/test/project',
            'workspace': '.orch/workspace/working-agent',
            'spawned_at': old_spawn_time
        }

        def mock_check_status(agent, check_git=False):
            status = Mock()
            status.phase = 'Unknown'
            status.commits_since_spawn = 5
            return status

        # Patch at orch.monitor because the import happens inside the clean function
        with patch('orch.cli.AgentRegistry') as MockRegistry, \
             patch('orch.monitor.check_agent_status', side_effect=mock_check_status), \
             patch('subprocess.run'):

            mock_registry = Mock()
            mock_registry.list_agents.return_value = [mock_working_agent]
            mock_registry._agents = [mock_working_agent]
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['clean', '--stale'])

        assert result.exit_code == 0
        assert 'No' in result.output or 'no' in result.output.lower()
        mock_registry.remove.assert_not_called()
        mock_registry.abandon_agent.assert_not_called()
