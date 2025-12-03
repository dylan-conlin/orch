"""
Tests for deprecation warnings on knowledge commands.

These commands are deprecated in favor of the standalone kb CLI:
- orch search → kb search
- orch create-investigation → kb create investigation
- orch create-decision → kb create decision
"""

import pytest
from pathlib import Path
from click.testing import CliRunner


class TestDeprecationWarnings:
    """Tests for deprecation warnings on knowledge commands."""

    def test_search_shows_deprecation_warning(self, cli_runner, tmp_path):
        """orch search should show deprecation warning for kb search."""
        from orch.cli import cli

        # Create minimal project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Run search (it will fail to find anything, but should show warning first)
        result = cli_runner.invoke(cli, ['search', 'test', '--global'])

        # Should show deprecation warning
        assert 'DEPRECATED' in result.output or 'deprecated' in result.output.lower()
        assert 'kb search' in result.output

    def test_create_investigation_shows_deprecation_warning(self, cli_runner, tmp_path, mocker):
        """orch create-investigation should show deprecation warning for kb create investigation."""
        from orch.cli import cli

        # Create minimal project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Mock find_orch_root to return our test project
        mocker.patch('orch.path_utils.find_orch_root', return_value=str(project))

        # Create template (command will fail without it, but warning should show first)
        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'SIMPLE.md'
        template_file.write_text('# Investigation\n## Test performed\n')

        try:
            result = cli_runner.invoke(cli, ['create-investigation', 'test-topic'])

            # Should show deprecation warning
            assert 'DEPRECATED' in result.output or 'deprecated' in result.output.lower()
            assert 'kb create investigation' in result.output
        finally:
            # Cleanup
            if template_file.exists():
                template_file.unlink()

    def test_create_decision_shows_deprecation_warning(self, cli_runner, tmp_path, mocker):
        """orch create-decision should show deprecation warning for kb create decision."""
        from orch.cli import cli

        # Create minimal project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Mock find_orch_root to return our test project
        mocker.patch('orch.path_utils.find_orch_root', return_value=str(project))

        # Create template (command will fail without it, but warning should show first)
        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'DECISION.md'
        template_file.write_text('# Decision\n')

        try:
            result = cli_runner.invoke(cli, ['create-decision', 'test-decision'])

            # Should show deprecation warning
            assert 'DEPRECATED' in result.output or 'deprecated' in result.output.lower()
            assert 'kb create decision' in result.output
        finally:
            # Cleanup
            if template_file.exists():
                template_file.unlink()

    def test_deprecation_warning_includes_install_hint(self, cli_runner, tmp_path):
        """Deprecation warnings should include hint about installing kb CLI."""
        from orch.cli import cli

        # Create minimal project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        result = cli_runner.invoke(cli, ['search', 'test', '--global'])

        # Should include installation hint
        assert 'go install' in result.output.lower() or 'kb-cli' in result.output


class TestCommandsStillWork:
    """Ensure deprecated commands still function (just with warnings)."""

    def test_search_still_functions(self, cli_runner, tmp_path, mocker):
        """orch search should still work despite deprecation."""
        from orch.cli import cli

        # Create project with searchable content
        project = tmp_path / 'test-project'
        inv_dir = project / '.orch' / 'investigations' / 'simple'
        inv_dir.mkdir(parents=True)
        (inv_dir / '2025-01-01-test.md').write_text('# Test Investigation\nSome searchable content')

        # Mock find_orch_root
        mocker.patch('orch.path_utils.find_orch_root', return_value=str(project))

        # Mock the searcher to avoid real file system operations
        mocker.patch('orch.artifact_search.ArtifactSearcher._detect_project_dir',
                    return_value=project)

        result = cli_runner.invoke(cli, ['search', 'test', '--global'])

        # Command should complete (exit code 0 or normal completion)
        # The important thing is it doesn't crash due to deprecation
        assert result.exit_code == 0 or 'No matches found' in result.output

    def test_create_investigation_still_functions(self, cli_runner, tmp_path, mocker):
        """orch create-investigation should still work despite deprecation."""
        from orch.cli import cli

        # Create project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Mock find_orch_root
        mocker.patch('orch.path_utils.find_orch_root', return_value=str(project))

        # Create template
        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'SIMPLE.md'
        template_file.write_text('# Investigation\n## Test performed\n')

        try:
            result = cli_runner.invoke(cli, ['create-investigation', 'still-works'])

            # Should succeed
            assert result.exit_code == 0
            assert 'Investigation created' in result.output
        finally:
            if template_file.exists():
                template_file.unlink()

    def test_create_decision_still_functions(self, cli_runner, tmp_path, mocker):
        """orch create-decision should still work despite deprecation."""
        from orch.cli import cli

        # Create project structure
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Mock find_orch_root
        mocker.patch('orch.path_utils.find_orch_root', return_value=str(project))

        # Create template
        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'DECISION.md'
        template_file.write_text('# Decision\n')

        try:
            result = cli_runner.invoke(cli, ['create-decision', 'still-works'])

            # Should succeed
            assert result.exit_code == 0
            assert 'Decision record created' in result.output
        finally:
            if template_file.exists():
                template_file.unlink()
