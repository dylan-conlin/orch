"""Tests for investigation template management."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch
from orch.investigations import (
    create_investigation,
    validate_investigation,
    detect_project_dir,
    InvestigationError,
    TEMPLATE_MAP
)


class TestDetectProjectDir:
    """Tests for project directory detection."""

    def test_explicit_project_dir(self, tmp_path):
        """Test explicit project directory parameter."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        result = detect_project_dir(project)
        assert result == project

    def test_explicit_project_dir_no_orch(self, tmp_path):
        """Test error when explicit project has no .orch directory."""
        project = tmp_path / 'test-project'
        project.mkdir()

        with pytest.raises(InvestigationError, match="No .orch directory found"):
            detect_project_dir(project)

    def test_claude_project_env_var(self, tmp_path):
        """Test CLAUDE_PROJECT environment variable."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        with patch.dict(os.environ, {'CLAUDE_PROJECT': str(project)}):
            result = detect_project_dir()

        assert result == project

    def test_no_project_found(self):
        """Test error when no project can be detected."""
        with patch.dict(os.environ, {}, clear=True):
            # Patch the correct location - detect_project_dir imports from path_utils
            with patch('orch.path_utils.find_orch_root', return_value=None):
                with pytest.raises(InvestigationError, match="No .orch directory found"):
                    detect_project_dir()


class TestCreateInvestigation:
    """Tests for investigation creation."""

    def test_create_investigation_success(self, tmp_path):
        """Test successful investigation creation."""
        # Setup project
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Create template
        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'SYSTEM_EXPLORATION.md'
        template_file.write_text(
            '# Investigation\n'
            '**Started:** YYYY-MM-DD\n'
            '**Resolution-Status:** Unresolved\n'
        )

        try:
            # Execute
            result = create_investigation('test-topic', 'systems', project)

            # Assert result structure
            assert 'file_path' in result
            assert 'investigation_type' in result
            assert 'template_name' in result
            assert 'date' in result
            assert result['investigation_type'] == 'systems'
            assert result['template_name'] == 'SYSTEM_EXPLORATION.md'
            assert 'test-topic' in result['file_path']

            # Assert file exists
            file_path = Path(result['file_path'])
            assert file_path.exists()

            # Assert content
            content = file_path.read_text()
            assert 'Resolution-Status:' in content
            assert 'YYYY-MM-DD' not in content  # Placeholder should be replaced

        finally:
            # Cleanup
            if template_file.exists():
                template_file.unlink()

    def test_create_investigation_all_types(self, tmp_path):
        """Test all investigation types can be created."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Create all templates
        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)

        templates_created = []
        try:
            for inv_type, template_name in TEMPLATE_MAP.items():
                template_file = template_dir / template_name
                template_file.write_text(f'# {inv_type}\n**Resolution-Status:** Unresolved\n')
                templates_created.append(template_file)

                result = create_investigation(f'test-{inv_type}', inv_type, project)

                assert result['investigation_type'] == inv_type
                assert result['template_name'] == template_name
                assert Path(result['file_path']).exists()

        finally:
            # Cleanup
            for template_file in templates_created:
                if template_file.exists():
                    template_file.unlink()

    def test_create_investigation_missing_template(self, tmp_path):
        """Test error when template not found."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Ensure template doesn't exist
        template_file = Path.home() / '.orch' / 'templates' / 'investigations' / 'SYSTEM_EXPLORATION.md'
        if template_file.exists():
            template_file.unlink()

        with pytest.raises(InvestigationError, match="Template not found"):
            create_investigation('test-topic', 'systems', project)

    def test_create_investigation_duplicate_file(self, tmp_path):
        """Test error when file already exists."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        # Create template
        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'SYSTEM_EXPLORATION.md'
        template_file.write_text('# Investigation\n**Resolution-Status:** Unresolved\n')

        try:
            # First creation succeeds
            create_investigation('test-duplicate', 'systems', project)

            # Second creation fails
            with pytest.raises(InvestigationError, match="File already exists"):
                create_investigation('test-duplicate', 'systems', project)

        finally:
            # Cleanup
            if template_file.exists():
                template_file.unlink()

    def test_create_investigation_invalid_slug_path_traversal(self, tmp_path):
        """Test error when slug contains path traversal."""
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        with pytest.raises(InvestigationError, match="Invalid slug"):
            create_investigation('../evil', 'systems', project)

        with pytest.raises(InvestigationError, match="Invalid slug"):
            create_investigation('/absolute/path', 'systems', project)

        with pytest.raises(InvestigationError, match="Invalid slug"):
            create_investigation('sub/directory', 'systems', project)


class TestValidateInvestigation:
    """Tests for investigation validation."""

    def test_validate_investigation_success(self, tmp_path):
        """Test validation passes with Test performed section (simple type, the default)."""
        file = tmp_path / 'test.md'
        file.write_text('# Investigation\n## Test performed\n\nTested the thing.\n')

        assert validate_investigation(file) is True

    def test_validate_investigation_legacy_success(self, tmp_path):
        """Test validation passes for legacy types without Resolution-Status.

        Note: Resolution-Status is no longer required in investigation files.
        Problem resolution status is now tracked in backlog.json.
        See: .orch/decisions/2025-11-28-backlog-investigation-separation.md
        """
        file = tmp_path / 'test.md'
        file.write_text('# Investigation\n\nContent here.\n')

        # Legacy types no longer require Resolution-Status - just check file is readable
        assert validate_investigation(file, investigation_type='systems') is True

    def test_validate_investigation_missing_field(self, tmp_path):
        """Test validation fails without Test performed section (simple type)."""
        file = tmp_path / 'test.md'
        file.write_text('# Investigation\n')

        with pytest.raises(InvestigationError, match="missing 'Test performed' section"):
            validate_investigation(file)

    def test_validate_investigation_any_type_passes_without_resolution_status(self, tmp_path):
        """Test that all investigation types pass validation without Resolution-Status.

        Resolution status is now tracked in backlog.json, not in investigation files.
        """
        file = tmp_path / 'test.md'
        file.write_text('# Investigation\n\nContent without Resolution-Status field.\n')

        # All non-simple types should pass validation without Resolution-Status
        for inv_type in ['systems', 'feasibility', 'audits', 'performance', 'agent-failures']:
            assert validate_investigation(file, investigation_type=inv_type) is True

    def test_validate_investigation_file_not_found(self, tmp_path):
        """Test validation fails when file doesn't exist."""
        file = tmp_path / 'nonexistent.md'

        with pytest.raises(InvestigationError, match="Investigation file not found"):
            validate_investigation(file)


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow(self, tmp_path):
        """Test complete workflow: create and validate investigation.

        Note: Resolution-Status is no longer required in investigation files.
        Problem resolution status is now tracked in backlog.json.
        """
        # Setup
        project = tmp_path / 'test-project'
        (project / '.orch').mkdir(parents=True)

        template_dir = Path.home() / '.orch' / 'templates' / 'investigations'
        template_dir.mkdir(parents=True, exist_ok=True)
        template_file = template_dir / 'SYSTEM_EXPLORATION.md'
        template_file.write_text(
            '# Investigation: [Investigation Title]\n'
            '**Started:** YYYY-MM-DD\n'
            # Note: Resolution-Status no longer required (tracked in backlog.json)
        )

        try:
            # Create investigation
            result = create_investigation('integration-test', 'systems', project)

            # Validate investigation (no longer requires Resolution-Status)
            assert validate_investigation(Path(result['file_path']), investigation_type='systems') is True

            # Verify directory structure
            inv_dir = project / '.orch' / 'investigations' / 'systems'
            assert inv_dir.exists()
            assert inv_dir.is_dir()

            # Verify file naming
            file_path = Path(result['file_path'])
            assert file_path.parent == inv_dir
            assert 'integration-test.md' in file_path.name

        finally:
            # Cleanup
            if template_file.exists():
                template_file.unlink()
