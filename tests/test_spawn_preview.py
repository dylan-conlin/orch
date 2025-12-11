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
    determine_primary_artifact,
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

        template = ".kb/investigations/{date}-{slug}.md"
        rendered = render_deliverable_path(template, config)

        assert ".kb/investigations/" in rendered
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

        template = ".kb/workspace/{workspace-name}/WORKSPACE.md"
        rendered = render_deliverable_path(template, config)

        assert rendered == ".kb/workspace/my-workspace/WORKSPACE.md"

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
                    path="",  # No file path - workspace tracking via beads comments
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


class TestDeterminePrimaryArtifact:
    """Tests for determine_primary_artifact function."""

    def test_returns_none_when_no_deliverables(self):
        """Test returns None when config has no deliverables."""
        config = SpawnConfig(
            task="Some task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            deliverables=[]
        )

        result = determine_primary_artifact(config)
        assert result is None

    def test_returns_path_for_required_investigation(self):
        """Test returns path when investigation deliverable is required."""
        config = SpawnConfig(
            task="Fix database issue",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="debug-db",
            deliverables=[
                SkillDeliverable(
                    type="investigation",
                    path=".kb/investigations/{date}-{slug}.md",
                    required=True
                )
            ]
        )

        result = determine_primary_artifact(config)
        assert result is not None
        assert "investigations" in str(result)
        assert "-fix-database-issue.md" in str(result)

    def test_returns_none_for_non_required_investigation(self):
        """Test returns None when investigation deliverable is not required."""
        config = SpawnConfig(
            task="Some task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            deliverables=[
                SkillDeliverable(
                    type="investigation",
                    path=".kb/investigations/{date}-{slug}.md",
                    required=False  # Not required
                )
            ]
        )

        result = determine_primary_artifact(config)
        assert result is None

    def test_skips_non_required_finds_required(self):
        """Test skips non-required investigations and finds required one."""
        config = SpawnConfig(
            task="Some task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            deliverables=[
                SkillDeliverable(
                    type="investigation",
                    path=".orch/optional/{date}.md",
                    required=False  # Skip this
                ),
                SkillDeliverable(
                    type="investigation",
                    path=".orch/required/{date}-{slug}.md",
                    required=True  # Find this
                )
            ]
        )

        result = determine_primary_artifact(config)
        assert result is not None
        assert "required" in str(result)
        assert "optional" not in str(result)

    def test_ignores_non_investigation_deliverables(self):
        """Test ignores deliverables that are not investigations."""
        config = SpawnConfig(
            task="Some task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            deliverables=[
                SkillDeliverable(
                    type="workspace",
                    path="",  # No file path - workspace tracking via beads comments
                    required=True
                ),
                SkillDeliverable(
                    type="commit",
                    path="",
                    required=False
                )
            ]
        )

        result = determine_primary_artifact(config)
        assert result is None


class TestCompactSummary:
    """Tests for compact summary output (non-interactive mode)."""

    def test_show_compact_summary_basic(self, capsys):
        """Test compact summary outputs single line with key info."""
        from orch.spawn import show_compact_summary

        config = SpawnConfig(
            task="Optimize orch spawn output for Claude Code",
            project="orch-cli",
            project_dir=Path("/Users/test/orch-cli"),
            workspace_name="feat-optimize-spawn-11dec",
            skill_name="feature-impl",
        )

        show_compact_summary(config)

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Should be single line (or at most 2 short lines)
        lines = output.split('\n')
        assert len(lines) <= 2

        # Key info visible in output
        assert "feature-impl" in output
        assert "orch-cli" in output
        assert "Optimize" in output  # Task truncated but starts visible

    def test_show_compact_summary_truncates_long_task(self, capsys):
        """Test compact summary truncates very long task descriptions."""
        from orch.spawn import show_compact_summary

        long_task = "This is a very long task description that would take up way too much space if we showed it all in the compact summary line which should stay short"
        config = SpawnConfig(
            task=long_task,
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="investigation",
        )

        show_compact_summary(config)

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Output should be much shorter than task
        assert len(output) < len(long_task) + 50
        # Should have ellipsis indicating truncation
        assert "..." in output

    def test_show_compact_summary_shows_beads_id_when_present(self, capsys):
        """Test compact summary includes beads ID when spawned from issue."""
        from orch.spawn import show_compact_summary

        config = SpawnConfig(
            task="Fix bug in auth module",
            project="myapp",
            project_dir=Path("/test/myapp"),
            workspace_name="fix-auth-bug-11dec",
            skill_name="feature-impl",
            beads_id="myapp-abc",
        )

        show_compact_summary(config)

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Beads ID should be visible
        assert "myapp-abc" in output
