"""
Tests for preview display functionality in orch spawn.

Tests the preview display mechanism including:
- Rendering deliverable paths with template variables
- Text wrapping for display
- Preview output formatting
"""

import re
import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    render_deliverable_path,
    _wrap_text,
    show_preview,
    SpawnConfig,
    SkillDeliverable,
)


class TestPreviewDisplay:
    """Tests for preview display functionality."""

    def test_render_deliverable_path_with_all_variables(self):
        """Test rendering deliverable path with all template variables."""
        config = SpawnConfig(
            task="Fix database persistence issue",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="debug-db-persistence"
        )

        template = ".orch/investigations/{date}-{slug}.md"
        rendered = render_deliverable_path(template, config)

        assert ".orch/investigations/" in rendered
        assert "-fix-database-persistence-issue.md" in rendered
        # Check date format (YYYY-MM-DD)
        assert re.search(r'\d{4}-\d{2}-\d{2}', rendered)

    def test_render_deliverable_path_with_workspace_name(self):
        """Test rendering with workspace-name variable."""
        config = SpawnConfig(
            task="Some task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="my-workspace"
        )

        template = ".orch/workspace/{workspace-name}/WORKSPACE.md"
        rendered = render_deliverable_path(template, config)

        assert rendered == ".orch/workspace/my-workspace/WORKSPACE.md"

    def test_wrap_text_single_line(self):
        """Test text wrapping with text that fits on one line."""
        text = "Short text"
        lines = _wrap_text(text, 60)

        assert len(lines) == 1
        assert lines[0] == "Short text"

    def test_wrap_text_multiple_lines(self):
        """Test text wrapping with text that needs multiple lines."""
        text = "This is a very long text that will definitely need to be wrapped to multiple lines because it exceeds the width"
        lines = _wrap_text(text, 30)

        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 30

    def test_show_preview_displays_correctly(self, capsys):
        """Test that show_preview outputs formatted preview."""
        config = SpawnConfig(
            task="Implement user authentication",
            project="test-project",
            project_dir=Path("/home/user/test-project"),
            workspace_name="feature-user-auth",
            skill_name="implement-feature",
            deliverables=[
                SkillDeliverable(
                    type="workspace",
                    path=".orch/workspace/{workspace-name}/WORKSPACE.md",
                    required=True
                )
            ]
        )

        show_preview(config)

        captured = capsys.readouterr()
        output = captured.out

        # Check key elements are present
        assert "orch spawn" in output
        assert "test-project" in output
        assert "feature-user-auth" in output
        assert "implement-feature" in output
        assert "Implement user authentication" in output
        assert "Deliverables:" in output
        assert "Context:" in output
        assert "PROJECT_DIR" in output
