"""Tests for orch dashboard backend."""
import pytest

# Skip all dashboard tests due to httpx/starlette version mismatch
# httpx 0.28.1 is incompatible with starlette 0.27.0's TestClient
# These dependencies are not tracked in setup.py
# TODO: Add fastapi/starlette/httpx to setup.py with proper versions
pytestmark = pytest.mark.skip(reason="Dashboard dependencies not in setup.py - httpx/starlette version mismatch")

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Health check should return 200 status."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200

    def test_health_check_returns_json(self):
        """Health check should return JSON with status."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestServerStartup:
    """Test FastAPI server initialization."""

    def test_app_creates_successfully(self):
        """FastAPI app should be created without errors."""
        from web.backend.main import app

        assert app is not None
        assert app.title == "Orch Dashboard API"


class TestSPARouting:
    """Test SPA static file serving and routing."""

    def test_root_serves_index_html(self):
        """Root path should serve index.html."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"<!DOCTYPE html>" in response.content

    def test_agents_route_serves_spa(self):
        """SPA routes like /agents should serve index.html for client-side routing."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.get("/agents")

        # Should serve HTML, not return 404 JSON
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"<!DOCTYPE html>" in response.content

    def test_api_routes_still_return_json(self):
        """API routes should still return JSON, not HTML."""
        from web.backend.main import app

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert response.json()["status"] == "healthy"
