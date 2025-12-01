"""
Tests for cross-repo spawn workspace sync.

When spawning an agent with --project (cross-repo spawn), the workspace should be
synced back to the origin repo on completion.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import subprocess


class TestRegistryOriginDir:
    """Tests for origin_dir in registry."""

    def test_register_stores_origin_dir(self, temp_registry):
        """Test that register() stores origin_dir when provided."""
        agent = temp_registry.register(
            agent_id="test-cross-repo-agent",
            task="Test task",
            window="workers:1",
            window_id="@100",
            project_dir="/path/to/target/repo",
            workspace=".orch/workspace/test-workspace",
            origin_dir="/path/to/origin/repo"
        )

        assert agent['origin_dir'] == "/path/to/origin/repo"
        assert agent['project_dir'] == "/path/to/target/repo"

    def test_register_origin_dir_none_when_same_repo(self, temp_registry):
        """Test that origin_dir is None when spawning in same repo."""
        agent = temp_registry.register(
            agent_id="test-same-repo-agent",
            task="Test task",
            window="workers:1",
            window_id="@100",
            project_dir="/path/to/same/repo",
            workspace=".orch/workspace/test-workspace"
            # No origin_dir - same repo spawn
        )

        # Should not have origin_dir when not provided
        assert agent.get('origin_dir') is None

    def test_registry_persists_origin_dir(self, temp_registry_path):
        """Test that origin_dir persists across registry reload."""
        from orch.registry import AgentRegistry

        # Register agent with origin_dir
        registry1 = AgentRegistry(temp_registry_path)
        registry1.register(
            agent_id="test-persist-agent",
            task="Test task",
            window="workers:1",
            window_id="@100",
            project_dir="/path/to/target/repo",
            workspace=".orch/workspace/test-workspace",
            origin_dir="/path/to/origin/repo"
        )

        # Reload registry and check origin_dir persists
        registry2 = AgentRegistry(temp_registry_path)
        agent = registry2.find("test-persist-agent")

        assert agent is not None
        assert agent['origin_dir'] == "/path/to/origin/repo"


class TestSpawnConfigOriginDir:
    """Tests for origin_dir in SpawnConfig."""

    def test_spawn_config_has_origin_dir_field(self):
        """Test that SpawnConfig dataclass has origin_dir field."""
        from orch.spawn import SpawnConfig

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/path/to/target"),
            workspace_name="test-workspace",
            origin_dir=Path("/path/to/origin")
        )

        assert config.origin_dir == Path("/path/to/origin")

    def test_spawn_config_origin_dir_defaults_to_none(self):
        """Test that origin_dir defaults to None when not provided."""
        from orch.spawn import SpawnConfig

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/path/to/target"),
            workspace_name="test-workspace"
        )

        assert config.origin_dir is None


class TestCrossRepoWorkspaceSync:
    """Tests for syncing workspace back to origin repo on completion."""

    def test_sync_workspace_to_origin_repo(self, tmp_path):
        """Test that workspace is synced to origin repo on completion."""
        from orch.complete import sync_workspace_to_origin

        # Setup: create two git repos
        origin_repo = tmp_path / "origin"
        target_repo = tmp_path / "target"

        # Initialize origin repo
        origin_repo.mkdir()
        subprocess.run(['git', 'init'], cwd=origin_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=origin_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=origin_repo, check=True, capture_output=True)
        (origin_repo / ".orch").mkdir()
        (origin_repo / ".orch" / "workspace").mkdir()
        (origin_repo / "README.md").write_text("# Origin\n")
        subprocess.run(['git', 'add', '.'], cwd=origin_repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=origin_repo, check=True, capture_output=True)

        # Initialize target repo with workspace
        target_repo.mkdir()
        subprocess.run(['git', 'init'], cwd=target_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=target_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=target_repo, check=True, capture_output=True)
        (target_repo / ".orch").mkdir()
        (target_repo / ".orch" / "workspace").mkdir()
        workspace_dir = target_repo / ".orch" / "workspace" / "test-cross-repo"
        workspace_dir.mkdir()
        (workspace_dir / "WORKSPACE.md").write_text("# Test Workspace\n**Phase:** Complete\n")
        (workspace_dir / "SPAWN_CONTEXT.md").write_text("Task: test\n")
        subprocess.run(['git', 'add', '.'], cwd=target_repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=target_repo, check=True, capture_output=True)

        # Act: sync workspace to origin
        result = sync_workspace_to_origin(
            workspace_name="test-cross-repo",
            project_dir=target_repo,
            origin_dir=origin_repo
        )

        # Assert: workspace exists in origin repo
        assert result is True
        origin_workspace = origin_repo / ".orch" / "workspace" / "test-cross-repo"
        assert origin_workspace.exists()
        assert (origin_workspace / "WORKSPACE.md").exists()

    def test_sync_skipped_when_same_repo(self, tmp_path):
        """Test that sync is skipped when origin_dir == project_dir."""
        from orch.complete import sync_workspace_to_origin

        # Same repo - should return early
        result = sync_workspace_to_origin(
            workspace_name="test-workspace",
            project_dir=tmp_path,
            origin_dir=tmp_path
        )

        # Should return True (no-op success) without error
        assert result is True

    def test_sync_skipped_when_origin_dir_none(self, tmp_path):
        """Test that sync is skipped when origin_dir is None."""
        from orch.complete import sync_workspace_to_origin

        result = sync_workspace_to_origin(
            workspace_name="test-workspace",
            project_dir=tmp_path,
            origin_dir=None
        )

        # Should return True (no-op success)
        assert result is True


class TestCompleteAgentCrossRepo:
    """Tests for complete_agent_work with cross-repo agents."""

    @patch('orch.complete.get_agent_by_id')
    @patch('orch.complete.verify_agent_work')
    @patch('orch.complete.validate_work_committed')
    @patch('orch.complete.sync_workspace_to_origin')
    @patch('orch.complete.clean_up_agent')
    def test_complete_agent_syncs_cross_repo_workspace(
        self,
        mock_cleanup,
        mock_sync,
        mock_validate,
        mock_verify,
        mock_get_agent,
        tmp_path
    ):
        """Test that complete_agent_work calls sync for cross-repo agents."""
        from orch.complete import complete_agent_work

        # Setup mock agent with origin_dir
        mock_agent = {
            'id': 'test-cross-repo-agent',
            'workspace': '.orch/workspace/test-workspace',
            'project_dir': '/path/to/target',
            'origin_dir': '/path/to/origin'
        }
        mock_get_agent.return_value = mock_agent

        # Mock verification to pass
        mock_verify.return_value = Mock(passed=True, errors=[])
        mock_validate.return_value = (True, None)
        mock_sync.return_value = True

        # Create workspace for verification
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-workspace"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("**Phase:** Complete\n")

        # Act
        result = complete_agent_work(
            agent_id="test-cross-repo-agent",
            project_dir=tmp_path
        )

        # Assert sync was called with correct arguments (positional)
        mock_sync.assert_called_once_with(
            "test-workspace",
            Path(mock_agent['project_dir']),
            Path(mock_agent['origin_dir'])
        )
