"""
Tests for generate_agent_file() functionality.

Tests agent file generation at spawn time from skill metadata.
Agent files provide tool restrictions and model configuration for Claude Code --agent flag.
"""

import pytest
from pathlib import Path

from orch.skill_discovery import SkillMetadata, SkillDeliverable
from orch.spawn import SpawnConfig, generate_agent_file


class TestGenerateAgentFile:
    """Tests for generate_agent_file() function."""

    def test_generate_agent_file_with_allowed_tools(self, tmp_path):
        """Test generating agent file when skill has allowed_tools."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="investigation",
            skill_metadata=SkillMetadata(
                name="investigation",
                triggers=["investigate"],
                deliverables=[],
                allowed_tools=["Read", "Grep", "Glob", "Bash", "WebFetch"],
                default_model="sonnet",
            ),
        )

        agent_path = generate_agent_file(config)

        # Should create agent file
        assert agent_path is not None
        assert agent_path.exists()
        assert agent_path.name == "investigation-worker.md"
        assert agent_path.parent.name == "agents"
        assert agent_path.parent.parent.name == ".claude"

        # Check content
        content = agent_path.read_text()
        assert "name: investigation-worker" in content
        assert "tools: Read, Grep, Glob, Bash, WebFetch" in content
        assert "model: sonnet" in content

    def test_generate_agent_file_with_disallowed_tools(self, tmp_path):
        """Test generating agent file when skill has disallowed_tools."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="audit",
            skill_metadata=SkillMetadata(
                name="audit",
                triggers=["audit"],
                deliverables=[],
                disallowed_tools=["Edit", "Write", "MultiEdit"],
            ),
        )

        agent_path = generate_agent_file(config)

        # Should create agent file
        assert agent_path is not None
        assert agent_path.exists()

        # Check content has disallowed_tools
        content = agent_path.read_text()
        assert "name: audit-worker" in content
        assert "disallowedTools: Edit, Write, MultiEdit" in content

    def test_generate_agent_file_returns_none_without_tool_restrictions(self, tmp_path):
        """Test that generate_agent_file returns None when skill has no tool restrictions."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="feature-impl",
            skill_metadata=SkillMetadata(
                name="feature-impl",
                triggers=["implement"],
                deliverables=[],
                # No allowed_tools or disallowed_tools
            ),
        )

        agent_path = generate_agent_file(config)

        # Should return None (no agent file needed)
        assert agent_path is None

    def test_generate_agent_file_returns_none_without_skill_metadata(self, tmp_path):
        """Test that generate_agent_file returns None when no skill metadata."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name=None,
            skill_metadata=None,
        )

        agent_path = generate_agent_file(config)

        # Should return None (no skill to generate agent for)
        assert agent_path is None

    def test_generate_agent_file_uses_config_model_override(self, tmp_path):
        """Test that config.model overrides skill's default_model."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="investigation",
            model="opus",  # Override model
            skill_metadata=SkillMetadata(
                name="investigation",
                triggers=["investigate"],
                deliverables=[],
                allowed_tools=["Read", "Grep"],
                default_model="sonnet",  # Default is sonnet
            ),
        )

        agent_path = generate_agent_file(config)

        assert agent_path is not None
        content = agent_path.read_text()
        # Should use opus (config override), not sonnet (default)
        assert "model: opus" in content

    def test_generate_agent_file_includes_description(self, tmp_path):
        """Test that agent file includes skill description if available."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="investigation",
            skill_metadata=SkillMetadata(
                name="investigation",
                triggers=["investigate"],
                deliverables=[],
                allowed_tools=["Read", "Grep"],
                description="Research and explore codebases",
            ),
        )

        agent_path = generate_agent_file(config)

        assert agent_path is not None
        content = agent_path.read_text()
        assert "description: Research and explore codebases" in content

    def test_generate_agent_file_creates_agents_directory(self, tmp_path):
        """Test that generate_agent_file creates .claude/agents/ directory if needed."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        # Ensure .claude/agents/ doesn't exist
        agents_dir = project_dir / ".claude" / "agents"
        assert not agents_dir.exists()

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace-09dec",
            skill_name="investigation",
            skill_metadata=SkillMetadata(
                name="investigation",
                triggers=["investigate"],
                deliverables=[],
                allowed_tools=["Read"],
            ),
        )

        agent_path = generate_agent_file(config)

        # Should create directory and file
        assert agents_dir.exists()
        assert agent_path.exists()


class TestClaudeBackendAgentFlag:
    """Tests for ClaudeBackend --agent flag support."""

    def test_build_command_with_agent_name(self):
        """Test that build_command includes --agent flag when agent_name provided."""
        from orch.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        cmd = backend.build_command(
            "test prompt",
            options={"agent_name": "investigation-worker"}
        )

        assert "--agent investigation-worker" in cmd
        # Should NOT have --allowed-tools when using --agent
        assert "--allowed-tools" not in cmd

    def test_build_command_without_agent_falls_back(self):
        """Test that build_command uses --allowed-tools '*' without agent."""
        from orch.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        cmd = backend.build_command("test prompt")

        assert "--allowed-tools '*'" in cmd
        assert "--agent" not in cmd

    def test_build_command_with_agent_and_model(self):
        """Test build_command with both agent and model options."""
        from orch.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        cmd = backend.build_command(
            "test prompt",
            options={"agent_name": "investigation-worker", "model": "opus"}
        )

        assert "--agent investigation-worker" in cmd
        # Model should still be passed even with agent
        assert "--model" in cmd
        assert "opus" in cmd


class TestSpawnIntegration:
    """Integration tests for agent file generation during spawn."""

    def test_spawn_in_tmux_generates_agent_file_for_skill_with_tools(self, tmp_path):
        """Test that spawn_in_tmux generates agent file when skill has tool restrictions."""
        from unittest.mock import patch, Mock
        from orch.spawn import spawn_in_tmux, SpawnConfig
        from orch.skill_discovery import SkillMetadata

        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()

        config = SpawnConfig(
            task="Test investigation task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-inv-09dec",
            skill_name="investigation",
            backend="claude",
            skill_metadata=SkillMetadata(
                name="investigation",
                triggers=["investigate"],
                deliverables=[],
                allowed_tools=["Read", "Grep", "Glob"],
                default_model="sonnet",
            ),
        )

        mock_session = Mock()

        # Mock subprocess.run to return successful window creation
        def create_subprocess_mock(stdout="10:@1234\n"):
            def mock_run(*args, **kwargs):
                return Mock(returncode=0, stdout=stdout, stderr="")
            return mock_run

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.spawn.ensure_tmuxinator_config'), \
             patch('orch.spawn.start_workers_session', return_value=True), \
             patch('orch.spawn.switch_workers_client', return_value=True), \
             patch('orch.spawn.validate_spawn_context_length'), \
             patch('subprocess.run', side_effect=create_subprocess_mock()), \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True):

            result = spawn_in_tmux(config)

        # Verify agent file was created
        agent_file = project_dir / ".claude" / "agents" / "investigation-worker.md"
        assert agent_file.exists()

        # Verify agent file content
        content = agent_file.read_text()
        assert "name: investigation-worker" in content
        assert "tools: Read, Grep, Glob" in content
        assert "model: sonnet" in content

    def test_spawn_in_tmux_skips_agent_file_for_skill_without_tools(self, tmp_path):
        """Test that spawn_in_tmux doesn't generate agent file when skill has no tool restrictions."""
        from unittest.mock import patch, Mock
        from orch.spawn import spawn_in_tmux, SpawnConfig
        from orch.skill_discovery import SkillMetadata

        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".orch").mkdir()

        config = SpawnConfig(
            task="Test feature task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-feat-09dec",
            skill_name="feature-impl",
            backend="claude",
            skill_metadata=SkillMetadata(
                name="feature-impl",
                triggers=["implement"],
                deliverables=[],
                # No allowed_tools or disallowed_tools
            ),
        )

        mock_session = Mock()

        # Mock subprocess.run to return successful window creation
        def create_subprocess_mock(stdout="10:@1234\n"):
            def mock_run(*args, **kwargs):
                return Mock(returncode=0, stdout=stdout, stderr="")
            return mock_run

        with patch('orch.tmux_utils.is_tmux_available', return_value=True), \
             patch('orch.tmux_utils.find_session', return_value=mock_session), \
             patch('orch.spawn.ensure_tmuxinator_config'), \
             patch('orch.spawn.start_workers_session', return_value=True), \
             patch('orch.spawn.switch_workers_client', return_value=True), \
             patch('orch.spawn.validate_spawn_context_length'), \
             patch('subprocess.run', side_effect=create_subprocess_mock()), \
             patch('orch.tmux_utils.get_window_by_target', return_value=True), \
             patch('orch.backends.claude.ClaudeBackend.wait_for_ready', return_value=True):

            result = spawn_in_tmux(config)

        # Verify no agent file was created
        agents_dir = project_dir / ".claude" / "agents"
        assert not agents_dir.exists() or not list(agents_dir.glob("*.md"))
