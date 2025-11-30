"""Tests for orch serve command."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


# cli_runner fixture provided by conftest.py


class TestServeCommand:
    """Test orch serve command."""

    def test_serve_accessible_via_dashboard_web(self, cli_runner):
        """Serve functionality accessible via dashboard --web."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['dashboard', '--help'])

        # serve is now hidden, accessible via dashboard --web
        assert '--web' in result.output

    def test_serve_checks_for_built_assets(self, tmp_path):
        """Should check if dist/ exists before starting server."""
        from orch import serve

        # Mock project root
        with patch('orch.serve.get_project_root', return_value=tmp_path):
            result = serve.check_dist_exists()

            assert result is False

    def test_serve_returns_error_when_dist_missing(self, tmp_path):
        """Should return error message when dist/ doesn't exist."""
        from orch import serve

        with patch('orch.serve.get_project_root', return_value=tmp_path):
            dist_path, error = serve.get_dist_path()

            assert dist_path is None
            assert error is not None
            assert 'npm run build' in error

    def test_serve_finds_dist_when_present(self, tmp_path):
        """Should find dist/ when it exists."""
        from orch import serve

        # Create dist directory
        dist_dir = tmp_path / 'web' / 'frontend' / 'dist'
        dist_dir.mkdir(parents=True)
        (dist_dir / 'index.html').write_text('<html></html>')

        with patch('orch.serve.get_project_root', return_value=tmp_path):
            dist_path, error = serve.get_dist_path()

            assert dist_path is not None
            assert error is None
            assert dist_path.exists()
