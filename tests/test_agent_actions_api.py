"""Tests for agent action API endpoints (send, complete, kill)."""
import pytest
import json
from pathlib import Path

# Skip all dashboard tests due to httpx/starlette version mismatch
# httpx 0.28.1 is incompatible with starlette 0.27.0's TestClient
# These dependencies are not tracked in setup.py
# TODO: Add fastapi/starlette/httpx to setup.py with proper versions
pytestmark = pytest.mark.skip(reason="Dashboard dependencies not in setup.py - httpx/starlette version mismatch")

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestSendMessageEndpoint:
    """Test POST /api/agents/{agent_id}/send endpoint."""

    def test_returns_404_when_agent_not_found(self):
        """Should return 404 when agent doesn't exist."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.post(
            "/api/agents/nonexistent/send",
            json={"message": "Test message"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_returns_400_when_message_missing(self):
        """Should return 400 when message field is missing."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.post(
            "/api/agents/test-agent/send",
            json={}
        )

        assert response.status_code == 422  # FastAPI validation error

    def test_sends_message_to_agent(self, tmp_path):
        """Should send message to agent via CLI."""
        from web.backend.main import app

        # Create test registry
        registry_path = tmp_path / "agent-registry.json"
        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": str(tmp_path),
            "workspace": ".orch/workspace/test/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        # Patch send_message_to_agent function
        with patch('web.backend.routes.agents.send_message_to_agent') as mock_send:
            mock_send.return_value = True

            # Patch registry path
            import web.backend.services.agent_service
            original_get_all = web.backend.services.agent_service.AgentService.get_all_agents

            def mock_get_all(**kwargs):
                return original_get_all(registry_path=registry_path)

            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

            try:
                client = TestClient(app)
                response = client.post(
                    "/api/agents/test-agent/send",
                    json={"message": "Test message"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "test-agent" in data["message"].lower()

                # Verify send_message_to_agent was called
                mock_send.assert_called_once_with("test-agent", "Test message")
            finally:
                web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original_get_all)


class TestCompleteAgentEndpoint:
    """Test POST /api/agents/{agent_id}/complete endpoint."""

    def test_returns_404_when_agent_not_found(self):
        """Should return 404 when agent doesn't exist."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.post("/api/agents/nonexistent/complete")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_completes_agent_work(self, tmp_path):
        """Should complete agent work via CLI."""
        from web.backend.main import app

        # Create test registry
        registry_path = tmp_path / "agent-registry.json"
        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": str(tmp_path),
            "workspace": ".orch/workspace/test/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        # Patch complete_agent_work function
        with patch('web.backend.routes.agents.complete_agent_work') as mock_complete:
            mock_complete.return_value = True

            # Patch registry path
            import web.backend.services.agent_service
            original_get_all = web.backend.services.agent_service.AgentService.get_all_agents

            def mock_get_all(**kwargs):
                return original_get_all(registry_path=registry_path)

            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

            try:
                client = TestClient(app)
                response = client.post("/api/agents/test-agent/complete")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "test-agent" in data["message"].lower()

                # Verify complete_agent_work was called
                mock_complete.assert_called_once()
            finally:
                web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original_get_all)


class TestKillAgentEndpoint:
    """Test DELETE /api/agents/{agent_id} endpoint."""

    def test_returns_404_when_agent_not_found(self):
        """Should return 404 when agent doesn't exist."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.delete("/api/agents/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_kills_agent(self, tmp_path):
        """Should kill/abandon agent."""
        from web.backend.main import app

        # Create test registry
        registry_path = tmp_path / "agent-registry.json"
        test_agent = {
            "id": "test-agent",
            "task": "Test task",
            "status": "active",
            "window": "orchestrator:1",
            "project_dir": str(tmp_path),
            "workspace": ".orch/workspace/test/",
        }
        registry_path.write_text(json.dumps({"agents": [test_agent]}))

        # Patch AgentRegistry.abandon method
        with patch('web.backend.routes.agents.AgentRegistry') as MockRegistry:
            mock_registry_instance = MagicMock()
            mock_registry_instance.abandon.return_value = True
            MockRegistry.return_value = mock_registry_instance

            # Patch registry path for agent lookup
            import web.backend.services.agent_service
            original_get_all = web.backend.services.agent_service.AgentService.get_all_agents

            def mock_get_all(**kwargs):
                return original_get_all(registry_path=registry_path)

            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

            try:
                client = TestClient(app)
                response = client.delete("/api/agents/test-agent")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "test-agent" in data["message"].lower()

                # Verify registry.abandon was called
                mock_registry_instance.abandon.assert_called_once_with("test-agent")
            finally:
                web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original_get_all)
