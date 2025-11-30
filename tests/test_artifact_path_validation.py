"""Tests for artifact path validation security."""
import pytest
import json
from pathlib import Path


class TestValidateArtifactPath:
    """Test AgentService.validate_artifact_path security function."""

    def test_blocks_absolute_path_outside_orch(self, tmp_path):
        """Should reject paths outside .orch directories."""
        from web.backend.services.agent_service import AgentService

        # Create empty registry
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        # Create a file outside .orch
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("sensitive data")

        is_valid, _, error = AgentService.validate_artifact_path(
            str(secret_file),
            registry_path=registry_path
        )

        assert is_valid is False
        assert error is not None
        assert "outside allowed directories" in error.lower()

    def test_blocks_etc_passwd(self, tmp_path):
        """Should reject requests for system files like /etc/passwd."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        is_valid, _, error = AgentService.validate_artifact_path(
            "/etc/passwd",
            registry_path=registry_path
        )

        assert is_valid is False
        assert "outside allowed directories" in error.lower()

    def test_blocks_home_ssh_keys(self, tmp_path):
        """Should reject requests for sensitive home directory files."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        ssh_path = Path.home() / ".ssh" / "id_rsa"

        is_valid, _, error = AgentService.validate_artifact_path(
            str(ssh_path),
            registry_path=registry_path
        )

        assert is_valid is False
        assert "outside allowed directories" in error.lower()

    def test_blocks_path_traversal_with_dotdot(self, tmp_path):
        """Should reject paths with .. traversal attempts."""
        from web.backend.services.agent_service import AgentService

        # Create project with .orch
        project_dir = tmp_path / "project"
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir(parents=True)

        # Create registry pointing to project
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({
            "agents": [{
                "id": "test-agent",
                "status": "active",
                "project_dir": str(project_dir),
                "workspace": ".orch/workspace/test/"
            }]
        }))

        # Create a file outside .orch that we want to protect
        secret_file = project_dir / "secret.txt"
        secret_file.write_text("sensitive")

        # Try to access it via path traversal
        traversal_path = str(orch_dir / ".." / "secret.txt")

        is_valid, _, error = AgentService.validate_artifact_path(
            traversal_path,
            registry_path=registry_path
        )

        assert is_valid is False
        assert "outside allowed directories" in error.lower()

    def test_allows_valid_orch_workspace_file(self, tmp_path):
        """Should allow files within project .orch directories."""
        from web.backend.services.agent_service import AgentService

        # Create project with .orch/workspace
        project_dir = tmp_path / "project"
        workspace_dir = project_dir / ".orch" / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        # Create valid artifact
        artifact_file = workspace_dir / "WORKSPACE.md"
        artifact_file.write_text("# Workspace")

        # Create registry pointing to project
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({
            "agents": [{
                "id": "test-agent",
                "status": "active",
                "project_dir": str(project_dir),
                "workspace": ".orch/workspace/test/"
            }]
        }))

        is_valid, resolved_path, error = AgentService.validate_artifact_path(
            str(artifact_file),
            registry_path=registry_path
        )

        assert is_valid is True
        assert resolved_path is not None
        assert error is None
        assert resolved_path.exists()

    def test_allows_global_orch_files(self, tmp_path, monkeypatch):
        """Should allow files within global ~/.orch directory."""
        from web.backend.services.agent_service import AgentService

        # Create mock home with .orch
        mock_home = tmp_path / "home"
        global_orch = mock_home / ".orch"
        global_orch.mkdir(parents=True)

        # Create a valid global artifact
        global_artifact = global_orch / "config.json"
        global_artifact.write_text("{}")

        # Mock Path.home() to return our tmp directory
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        is_valid, resolved_path, error = AgentService.validate_artifact_path(
            str(global_artifact),
            registry_path=registry_path
        )

        assert is_valid is True
        assert resolved_path is not None
        assert error is None

    def test_rejects_empty_path(self, tmp_path):
        """Should reject empty path."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        is_valid, _, error = AgentService.validate_artifact_path(
            "",
            registry_path=registry_path
        )

        assert is_valid is False
        assert error is not None
        assert "required" in error.lower()

    def test_rejects_none_path(self, tmp_path):
        """Should reject None path."""
        from web.backend.services.agent_service import AgentService

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        is_valid, _, error = AgentService.validate_artifact_path(
            None,
            registry_path=registry_path
        )

        assert is_valid is False
        assert error is not None

    def test_resolves_symlinks(self, tmp_path):
        """Should resolve symlinks to prevent bypasses."""
        from web.backend.services.agent_service import AgentService

        # Create project with .orch
        project_dir = tmp_path / "project"
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir(parents=True)

        # Create a secret file outside .orch
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "password.txt"
        secret_file.write_text("supersecret")

        # Create symlink inside .orch pointing to secret
        symlink = orch_dir / "symlink_to_secrets"
        try:
            symlink.symlink_to(secret_dir)
        except OSError:
            pytest.skip("Symlink creation not supported")

        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({
            "agents": [{
                "id": "test-agent",
                "status": "active",
                "project_dir": str(project_dir),
                "workspace": ".orch/workspace/test/"
            }]
        }))

        # Try to access secret via symlink
        symlink_path = str(symlink / "password.txt")

        is_valid, _, error = AgentService.validate_artifact_path(
            symlink_path,
            registry_path=registry_path
        )

        # After resolving symlink, the real path is outside .orch
        assert is_valid is False
        assert "outside allowed directories" in error.lower()

    def test_only_active_agents_projects_allowed(self, tmp_path):
        """Should only allow paths from active agent projects."""
        from web.backend.services.agent_service import AgentService

        # Create two projects
        active_project = tmp_path / "active-project"
        inactive_project = tmp_path / "inactive-project"

        for proj in [active_project, inactive_project]:
            orch_dir = proj / ".orch" / "workspace" / "test"
            orch_dir.mkdir(parents=True)
            (orch_dir / "file.md").write_text("content")

        # Registry only has one active agent
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({
            "agents": [
                {
                    "id": "active-agent",
                    "status": "active",
                    "project_dir": str(active_project),
                    "workspace": ".orch/workspace/test/"
                },
                {
                    "id": "inactive-agent",
                    "status": "completed",  # Not active
                    "project_dir": str(inactive_project),
                    "workspace": ".orch/workspace/test/"
                }
            ]
        }))

        # Active project should be allowed
        active_file = active_project / ".orch" / "workspace" / "test" / "file.md"
        is_valid, _, _ = AgentService.validate_artifact_path(
            str(active_file),
            registry_path=registry_path
        )
        assert is_valid is True

        # Inactive project should NOT be allowed
        # (unless it's in global ~/.orch)
        inactive_file = inactive_project / ".orch" / "workspace" / "test" / "file.md"
        is_valid, _, error = AgentService.validate_artifact_path(
            str(inactive_file),
            registry_path=registry_path
        )
        # Should be rejected because inactive agent's project is not in allowed list
        assert is_valid is False


class TestArtifactContentEndpointSecurity:
    """Integration tests for /api/artifacts/content security."""

    # Skip these tests due to httpx/starlette version mismatch (same as other API tests)
    pytestmark = pytest.mark.skip(
        reason="Dashboard dependencies not in setup.py - httpx/starlette version mismatch"
    )

    def test_returns_403_for_path_outside_orch(self, tmp_path):
        """Should return 403 Forbidden for paths outside allowed directories."""
        from web.backend.main import app
        from fastapi.testclient import TestClient

        # Create empty registry
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({"agents": []}))

        # Create a file we want to protect
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("sensitive data")

        client = TestClient(app)
        response = client.get(
            "/api/artifacts/content",
            params={"path": str(secret_file)}
        )

        assert response.status_code == 403
        assert "outside allowed directories" in response.json()["detail"].lower()

    def test_returns_403_for_etc_passwd(self, tmp_path):
        """Should return 403 Forbidden for /etc/passwd."""
        from web.backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get(
            "/api/artifacts/content",
            params={"path": "/etc/passwd"}
        )

        assert response.status_code == 403

    def test_allows_valid_workspace_file(self, tmp_path):
        """Should allow reading valid workspace files."""
        from web.backend.main import app
        from fastapi.testclient import TestClient
        import web.backend.services.agent_service

        # Create project with workspace
        project_dir = tmp_path / "project"
        workspace_dir = project_dir / ".orch" / "workspace" / "test"
        workspace_dir.mkdir(parents=True)

        artifact_file = workspace_dir / "WORKSPACE.md"
        artifact_file.write_text("# Test Workspace\nContent here")

        # Create registry
        registry_path = tmp_path / "agent-registry.json"
        registry_path.write_text(json.dumps({
            "agents": [{
                "id": "test-agent",
                "status": "active",
                "project_dir": str(project_dir),
                "workspace": ".orch/workspace/test/"
            }]
        }))

        # Patch registry path
        original = web.backend.services.agent_service.AgentService.get_all_agents

        def mock_get_all(**kwargs):
            return original(registry_path=registry_path)

        web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(mock_get_all)

        try:
            client = TestClient(app)
            response = client.get(
                "/api/artifacts/content",
                params={"path": str(artifact_file)}
            )

            assert response.status_code == 200
            data = response.json()
            assert "content" in data
            assert "# Test Workspace" in data["content"]
        finally:
            web.backend.services.agent_service.AgentService.get_all_agents = staticmethod(original)
