"""Tests for agent REST API endpoints."""
import pytest
import json
from pathlib import Path

# Skip all dashboard tests due to httpx/starlette version mismatch
# httpx 0.28.1 is incompatible with starlette 0.27.0's TestClient
# These dependencies are not tracked in setup.py
# TODO: Add fastapi/starlette/httpx to setup.py with proper versions
pytestmark = pytest.mark.skip(reason="Dashboard dependencies not in setup.py - httpx/starlette version mismatch")

from fastapi.testclient import TestClient


class TestAgentListEndpoint:
    """Test GET /api/agents endpoint."""

    def test_returns_empty_list_when_no_agents(self, tmp_path):
        """Should return empty list when no agents registered."""
        from web.backend.main import app

        # Create empty registry
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        # Patch registry path in AgentService
        import web.backend.services.agent_service
        original_get_all = web.backend.services.agent_service.AgentService.get_all_agents

        def mock_get_all(**kwargs):
            return original_get_all(registry_path=registry_path)

        web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

        try:
            client = TestClient(app)
            response = client.get("/api/agents")

            assert response.status_code == 200
            data = response.json()
            assert "agents" in data
            assert data["agents"] == []
        finally:
            # Restore original
            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original_get_all)

    def test_returns_agent_list(self, tmp_path):
        """Should return list of agents from registry."""
        from web.backend.main import app

        # Create registry with test agents
        registry_path = tmp_path / "agent-registry.json"
        test_agents = [
            {
                "id": "agent-1",
                "task": "Task 1",
                "status": "active",
                "window": "orchestrator:1",
                "project_dir": "/path/to/project",
                "workspace": ".orch/workspace/test-1/",
            },
            {
                "id": "agent-2",
                "task": "Task 2",
                "status": "active",
                "window": "orchestrator:2",
                "project_dir": "/path/to/project",
                "workspace": ".orch/workspace/test-2/",
            }
        ]
        registry_path.write_text(json.dumps({"agents": test_agents}))

        # Patch registry path
        import web.backend.services.agent_service
        original_get_all = web.backend.services.agent_service.AgentService.get_all_agents

        def mock_get_all(**kwargs):
            return original_get_all(registry_path=registry_path)

        web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

        try:
            client = TestClient(app)
            response = client.get("/api/agents")

            assert response.status_code == 200
            data = response.json()
            assert len(data["agents"]) == 2
            assert data["agents"][0]["id"] == "agent-1"
            assert data["agents"][1]["id"] == "agent-2"
        finally:
            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original_get_all)


class TestAgentDetailEndpoint:
    """Test GET /api/agents/{agent_id} endpoint."""

    def test_returns_404_when_agent_not_found(self, tmp_path):
        """Should return 404 when agent doesn't exist."""
        from web.backend.main import app

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        # Patch registry path
        import web.backend.services.agent_service
        original_get_details = web.backend.services.agent_service.AgentService.get_agent_details

        def mock_get_details(agent_id, **kwargs):
            return original_get_details(agent_id, registry_path=registry_path)

        web.backend.services.agent_service.AgentService.get_agent_details = staticmethod(mock_get_details)

        try:
            client = TestClient(app)
            response = client.get("/api/agents/nonexistent")

            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()
        finally:
            web.backend.services.agent_service.AgentService.get_agent_details = staticmethod(original_get_details)

    def test_returns_agent_details(self, tmp_path):
        """Should return agent details including phase."""
        from web.backend.main import app

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

        # Create workspace with Phase
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Implementing")

        # Patch registry path
        import web.backend.services.agent_service
        original_get_details = web.backend.services.agent_service.AgentService.get_agent_details

        def mock_get_details(agent_id, **kwargs):
            return original_get_details(agent_id, registry_path=registry_path)

        web.backend.services.agent_service.AgentService.get_agent_details = staticmethod(mock_get_details)

        try:
            client = TestClient(app)
            response = client.get("/api/agents/test-agent")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test-agent"
            assert data["task"] == "Test task"
            assert data["phase"] == "Implementing"
        finally:
            web.backend.services.agent_service.AgentService.get_agent_details = staticmethod(original_get_details)
