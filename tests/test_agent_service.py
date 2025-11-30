"""Tests for agent service layer."""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch


class TestGetAllAgents:
    """Test get_all_agents() method."""

    def test_returns_empty_list_when_no_registry(self, tmp_path):
        """Should return empty list when registry file doesn't exist."""
        from web.backend.services.agent_service import AgentService

        # Use non-existent path
        registry_path = tmp_path / "nonexistent" / "agent-registry.json"

        agents = AgentService.get_all_agents(registry_path=registry_path)

        assert agents == []

    def test_parses_registry_correctly(self, tmp_path):
        """Should parse agent registry JSON correctly."""
        from web.backend.services.agent_service import AgentService

        # Create test registry file
        registry_path = tmp_path / "agent-registry.json"
        test_agents = [
            {
                "id": "test-agent-1",
                "task": "Test task 1",
                "status": "active",
                "window": "orchestrator:1",
                "window_id": "@1001",
                "project_dir": "/path/to/project",
                "workspace": ".orch/workspace/test-1/",
                "spawned_at": "2025-11-14T10:00:00Z",
                "is_interactive": False
            },
            {
                "id": "test-agent-2",
                "task": "Test task 2",
                "status": "active",
                "window": "orchestrator:2",
                "window_id": "@1002",
                "project_dir": "/path/to/project",
                "workspace": ".orch/workspace/test-2/",
                "spawned_at": "2025-11-14T10:05:00Z",
                "is_interactive": False
            }
        ]
        registry_path.write_text(json.dumps({"agents": test_agents}))

        agents = AgentService.get_all_agents(registry_path=registry_path)

        assert len(agents) == 2
        assert agents[0]["id"] == "test-agent-1"
        assert agents[1]["id"] == "test-agent-2"
        assert agents[0]["task"] == "Test task 1"

    def test_handles_corrupted_registry(self, tmp_path):
        """Should return empty list when registry JSON is corrupted."""
        from web.backend.services.agent_service import AgentService

        # Create corrupted JSON file
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text("{ invalid json }")

        agents = AgentService.get_all_agents(registry_path=registry_path)

        assert agents == []

    def test_filters_to_only_active_agents(self, tmp_path):
        """Should return only agents with status='active', excluding completed and abandoned."""
        from web.backend.services.agent_service import AgentService

        # Create registry with mixed statuses
        registry_path = tmp_path / "agent-registry.json"
        test_agents = [
            {
                "id": "active-1",
                "task": "Active task 1",
                "status": "active",
                "window": "orchestrator:1",
                "window_id": "@1001",
            },
            {
                "id": "completed-1",
                "task": "Completed task",
                "status": "completed",
                "window": "orchestrator:2",
                "window_id": "@1002",
            },
            {
                "id": "active-2",
                "task": "Active task 2",
                "status": "active",
                "window": "orchestrator:3",
                "window_id": "@1003",
            },
            {
                "id": "abandoned-1",
                "task": "Abandoned task",
                "status": "abandoned",
                "window": "orchestrator:4",
                "window_id": "@1004",
            },
            {
                "id": "active-3",
                "task": "Active task 3",
                "status": "active",
                "window": "orchestrator:5",
                "window_id": "@1005",
            },
        ]
        registry_path.write_text(json.dumps({"agents": test_agents}))

        agents = AgentService.get_all_agents(registry_path=registry_path)

        # Should only return the 3 active agents
        assert len(agents) == 3
        agent_ids = [a["id"] for a in agents]
        assert "active-1" in agent_ids
        assert "active-2" in agent_ids
        assert "active-3" in agent_ids
        assert "completed-1" not in agent_ids
        assert "abandoned-1" not in agent_ids


class TestGetAgentDetails:
    """Test get_agent_details() method."""

    def test_returns_none_when_agent_not_found(self, tmp_path):
        """Should return None when agent doesn't exist."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        agent = AgentService.get_agent_details("nonexistent", registry_path=registry_path)

        assert agent is None

    def test_returns_agent_from_registry(self, tmp_path):
        """Should return agent data from registry."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": "/path/to/project",
            "workspace": ".orch/workspace/test/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        agent = AgentService.get_agent_details("test-agent", registry_path=registry_path)

        assert agent is not None
        assert agent["id"] == "test-agent"
        assert agent["task"] == "Test task"

    def test_includes_workspace_phase_when_available(self, tmp_path):
        """Should read and include workspace Phase field."""
        from web.backend.services.agent_service import AgentService

        # Create registry
        registry_path = tmp_path / "agent-registry.json"
        workspace_dir = tmp_path / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": str(tmp_path),
            "workspace": "workspace/test/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        # Create workspace file with Phase field
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace

**Phase:** Implementing

## Summary
Test workspace
""")

        agent = AgentService.get_agent_details("test-agent", registry_path=registry_path)

        assert agent is not None
        assert "phase" in agent
        assert agent["phase"] == "Implementing"

    def test_phase_none_when_workspace_missing(self, tmp_path):
        """Phase should be None when workspace file doesn't exist."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": str(tmp_path),
            "workspace": "nonexistent/workspace/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        agent = AgentService.get_agent_details("test-agent", registry_path=registry_path)

        assert agent is not None
        assert agent.get("phase") is None


class TestGetWorkspaceArtifacts:
    """Test get_workspace_artifacts() method."""

    def test_returns_empty_list_when_workspace_not_exists(self, tmp_path):
        """Should return empty list when workspace directory doesn't exist."""
        from web.backend.services.agent_service import AgentService

        artifacts = AgentService.get_workspace_artifacts(
            project_dir=str(tmp_path),
            workspace_path="nonexistent/workspace/"
        )

        assert artifacts == []

    def test_returns_empty_list_when_params_missing(self):
        """Should return empty list when project_dir or workspace_path is None."""
        from web.backend.services.agent_service import AgentService

        assert AgentService.get_workspace_artifacts(None, "workspace/") == []
        assert AgentService.get_workspace_artifacts("/path", None) == []
        assert AgentService.get_workspace_artifacts(None, None) == []

    def test_lists_workspace_files(self, tmp_path):
        """Should list all files in workspace directory."""
        from web.backend.services.agent_service import AgentService

        # Create workspace with files
        workspace_dir = tmp_path / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        (workspace_dir / "WORKSPACE.md").write_text("# Workspace")
        (workspace_dir / "plan.md").write_text("# Plan")
        (workspace_dir / "notes.md").write_text("# Notes")

        artifacts = AgentService.get_workspace_artifacts(
            project_dir=str(tmp_path),
            workspace_path="workspace/test/"
        )

        assert len(artifacts) == 3
        names = [a["name"] for a in artifacts]
        assert "WORKSPACE.md" in names
        assert "plan.md" in names
        assert "notes.md" in names

    def test_excludes_hidden_files(self, tmp_path):
        """Should not include files starting with dot."""
        from web.backend.services.agent_service import AgentService

        workspace_dir = tmp_path / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        (workspace_dir / "WORKSPACE.md").write_text("# Workspace")
        (workspace_dir / ".hidden").write_text("hidden")
        (workspace_dir / ".DS_Store").write_text("metadata")

        artifacts = AgentService.get_workspace_artifacts(
            project_dir=str(tmp_path),
            workspace_path="workspace/test/"
        )

        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "WORKSPACE.md"

    def test_artifact_structure(self, tmp_path):
        """Artifacts should have correct structure with name, type, and path."""
        from web.backend.services.agent_service import AgentService

        workspace_dir = tmp_path / "workspace" / "test"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "WORKSPACE.md").write_text("# Workspace")

        artifacts = AgentService.get_workspace_artifacts(
            project_dir=str(tmp_path),
            workspace_path="workspace/test/"
        )

        assert len(artifacts) == 1
        artifact = artifacts[0]
        assert artifact["name"] == "WORKSPACE.md"
        assert artifact["type"] == "artifact"
        assert artifact["path"] == "workspace/test/WORKSPACE.md"

    def test_returns_sorted_artifacts(self, tmp_path):
        """Artifacts should be returned in sorted order."""
        from web.backend.services.agent_service import AgentService

        workspace_dir = tmp_path / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        # Create files in non-alphabetical order
        (workspace_dir / "zebra.md").write_text("Z")
        (workspace_dir / "alpha.md").write_text("A")
        (workspace_dir / "beta.md").write_text("B")

        artifacts = AgentService.get_workspace_artifacts(
            project_dir=str(tmp_path),
            workspace_path="workspace/test/"
        )

        names = [a["name"] for a in artifacts]
        assert names == ["alpha.md", "beta.md", "zebra.md"]
