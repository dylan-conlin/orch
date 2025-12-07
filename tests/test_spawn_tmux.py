"""
Tests for tmux spawning functionality in orch spawn.

Tests the tmux window management including:
- Creating windows in tmux sessions
- Gap-filling window indices
- Building spawn prompts
- Agent registration
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from orch.spawn import (
    spawn_in_tmux,
    build_spawn_prompt,
    register_agent,
    SpawnConfig,
    SkillDeliverable,
)


def create_subprocess_mock(tmux_output="10:@1008\n"):
    """
    Create a mock for subprocess.run that handles both git and tmux commands.
    """
    def side_effect(args, **kwargs):
        cmd = args if isinstance(args, list) else [args]
        if cmd == ['git', 'branch', '--show-current']:
            return Mock(returncode=0, stdout="master\n", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status'] and '--porcelain' in cmd:
            return Mock(returncode=0, stdout="", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['git', 'status']:
            return Mock(returncode=0, stdout="nothing to commit, working tree clean\n", stderr="")
        if len(cmd) >= 2 and cmd[:2] == ['tmux', 'capture-pane']:
            return Mock(returncode=0, stdout="─────────────────────────────────────────\n> Try 'refactor ui.py'\n─────────────────────────────────────────\n", stderr="")
        if cmd and 'tmux' in str(cmd[0]):
            return Mock(returncode=0, stdout=tmux_output, stderr="")
        return Mock(returncode=0, stdout="", stderr="")
    return side_effect


class TestTmuxSpawning:
    """Tests for tmux spawning functionality."""

    def test_spawn_fills_gaps_in_window_indices(self, tmp_path):
        """Test that spawn creates windows with tmux gap-filling behavior."""
        # Use real temp directory to avoid mkdir failures
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch" / "workspace").mkdir(parents=True)

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        # Mock windows with gap at index 2
        mock_windows = [
            {'index': '1', 'name': 'window1'},
            {'index': '3', 'name': 'window3'},
        ]

        mock_session = Mock()
        # tmux fills gap and creates window 2 (not max+1=4)

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.tmux_utils.list_windows', return_value=mock_windows), \
             patch('subprocess.run', side_effect=create_subprocess_mock("2:@1002\n")) as mock_subprocess, \
             patch('time.sleep'), \
             patch('orch.tmux_utils.get_window_by_target', return_value=True):

            result = spawn_in_tmux(config)

            # Verify window 2 was created (gap-filled), not window 4 (max+1)
            # Default session is 'workers' (from config.py defaults)
            assert result['window'] == "workers:2"

            # Verify tmux command does NOT use explicit index
            # (should be "-t workers", not "-t workers:4")
            mock_subprocess.assert_called()
            calls = mock_subprocess.call_args_list
            # Find the new-window call
            new_window_call = None
            for call in calls:
                args = call[0][0] if call[0] else call[1].get('args', [])
                if 'new-window' in args:
                    new_window_call = args
                    break

            assert new_window_call is not None, "new-window command not found"
            # Check that -t flag is NOT followed by an explicit window index
            t_index = new_window_call.index('-t')
            target_arg = new_window_call[t_index + 1]
            # Should be just "workers", not "workers:4"
            assert target_arg == "workers", f"Expected 'workers', got '{target_arg}'"

    def test_build_spawn_prompt(self):
        """Test building spawn prompt with all components."""
        config = SpawnConfig(
            task="Fix database issue",
            project="test-project",
            project_dir=Path("/home/user/test-project"),
            workspace_name="debug-db-issue",
            skill_name="systematic-debugging",
            deliverables=[
                SkillDeliverable(
                    type="investigation",
                    path=".kb/investigations/{date}-{slug}.md",
                    required=True
                )
            ]
        )

        prompt = build_spawn_prompt(config)

        assert "TASK: Fix database issue" in prompt
        assert "PROJECT_DIR: /home/user/test-project" in prompt
        assert "systematic-debugging" in prompt
        assert "DELIVERABLES (REQUIRED):" in prompt
        assert "investigation:" in prompt
        assert "WORKSPACE DIR:" in prompt  # Updated: now shows workspace dir, not WORKSPACE.md
        assert "STATUS UPDATES (CRITICAL):" in prompt
        assert "CONTEXT AVAILABLE:" in prompt

    def test_build_spawn_prompt_includes_beads_tracking(self):
        """Test that spawn prompt includes beads tracking instructions (not workspace population)."""
        config = SpawnConfig(
            task="Implement user authentication",
            project="test-project",
            project_dir=Path("/home/user/test-project"),
            workspace_name="feature-auth",
            beads_id="test-beads-123"
        )

        prompt = build_spawn_prompt(config)

        # Verify beads progress tracking is present (beads is source of truth)
        assert "BEADS PROGRESS TRACKING" in prompt
        assert "bd comment test-beads-123" in prompt

        # Verify phase tracking via beads
        assert "Phase: Planning" in prompt
        assert "Phase: Implementing" in prompt
        assert "Phase: Complete" in prompt

        # Verify coordination artifact population section is NOT present
        # (replaced by beads tracking - orch-cli-30j)
        assert "COORDINATION ARTIFACT POPULATION (REQUIRED):" not in prompt
        assert "Fill TLDR / summary section (problem, status, next)" not in prompt
        assert ".orch/docs/workspace-conventions.md for details" not in prompt

    def test_spawn_in_tmux_success(self, tmp_path):
        """Test successful tmux spawn."""
        # Use tmp_path fixture instead of hardcoded path
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()
        (project_dir / ".orch" / "workspace").mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace"
        )

        mock_session = Mock()

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('subprocess.run', side_effect=create_subprocess_mock("10:@1008\n")), \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('pathlib.Path.write_text'):

            result = spawn_in_tmux(config)

            # Session name is "workers" not "orchestrator"
            assert result['window'] == "workers:10"
            assert result['agent_id'] == "test-workspace"
            assert "worker: test-workspace" in result['window_name']

    def test_spawn_in_tmux_no_tmux_available(self):
        """Test spawn failure when tmux not available."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace"
        )

        with patch('orch.tmux_utils.is_tmux_available', return_value=False), \
             patch('subprocess.run', side_effect=create_subprocess_mock()):
            with pytest.raises(RuntimeError, match="Tmux not available"):
                spawn_in_tmux(config)

    def test_spawn_in_tmux_session_not_found(self):
        """Test spawn failure when tmux session doesn't exist."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace"
        )

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=None), \
             patch('subprocess.run', side_effect=create_subprocess_mock()):

            with pytest.raises(RuntimeError, match="session.*not found"):
                spawn_in_tmux(config)


class TestRegistration:
    """Tests for agent registration functionality."""

    def test_register_agent_success(self, tmp_path):
        """Test successful agent registration."""
        # Mock registry path
        registry_path = tmp_path / "agent-registry.json"

        with patch('orch.registry.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            MockRegistry.return_value = mock_registry

            register_agent(
                agent_id="test-agent",
                task="Test task",
                window="orchestrator:10",
                window_id="@1008",
                project_dir=Path("/test/project"),
                workspace_name="test-workspace"
            )

            # Verify register was called
            mock_registry.register.assert_called_once()
            call_kwargs = mock_registry.register.call_args.kwargs
            assert call_kwargs['agent_id'] == "test-agent"
            assert call_kwargs['task'] == "Test task"
