"""Tests for WebSocket real-time updates.

NOTE: Full WebSocket functionality testing (connection, messages, updates) is done
during Task 8 (Integration Testing) with a real running server. TestClient has
limitations with long-running WebSocket connections containing infinite loops.
"""
import pytest


class TestWebSocketEndpoint:
    """Test WebSocket endpoint registration."""

    def test_websocket_endpoint_registered(self):
        """WebSocket endpoint should be registered at /ws/agents."""
        from web.backend.main import app

        # Check that the WebSocket route is registered
        routes = [route.path for route in app.routes]
        assert "/ws/agents" in routes

    def test_websocket_handler_exists(self):
        """WebSocket handler function should exist."""
        from web.backend.routes.agents import websocket_agent_updates

        assert websocket_agent_updates is not None
        assert callable(websocket_agent_updates)
