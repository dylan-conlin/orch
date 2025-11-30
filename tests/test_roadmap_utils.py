"""
Tests for orch roadmap_utils module.

Tests utilities for ROADMAP format detection and parser selection.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orch.roadmap_utils import (
    detect_roadmap_format,
    parse_roadmap,
    find_roadmap_file,
    detect_project_roadmap,
    find_roadmap_item_for_workspace,
    mark_roadmap_item_done,
)


class TestDetectRoadmapFormat:
    """Tests for detect_roadmap_format function."""

    def test_detects_markdown_format(self, tmp_path):
        """Should detect markdown format from .md extension."""
        roadmap_path = tmp_path / 'ROADMAP.md'
        result = detect_roadmap_format(roadmap_path)
        assert result == 'markdown'

    def test_detects_org_format(self, tmp_path):
        """Should detect org format from .org extension."""
        roadmap_path = tmp_path / 'ROADMAP.org'
        result = detect_roadmap_format(roadmap_path)
        assert result == 'org'

    def test_raises_for_unknown_format(self, tmp_path):
        """Should raise ValueError for unknown extension."""
        roadmap_path = tmp_path / 'ROADMAP.txt'
        with pytest.raises(ValueError) as exc_info:
            detect_roadmap_format(roadmap_path)
        assert 'Unknown ROADMAP format' in str(exc_info.value)


class TestParseRoadmap:
    """Tests for parse_roadmap function."""

    def test_returns_empty_when_file_not_exists(self, tmp_path):
        """Should return empty list when file doesn't exist."""
        result = parse_roadmap(tmp_path / 'ROADMAP.md')
        assert result == []

    def test_uses_markdown_parser_for_md(self, tmp_path):
        """Should use markdown parser for .md files."""
        roadmap = tmp_path / 'ROADMAP.md'
        roadmap.write_text('# Roadmap\n')

        with patch('orch.roadmap_utils.parse_md') as mock_parse:
            mock_parse.return_value = []
            parse_roadmap(roadmap)
            mock_parse.assert_called_once()

    def test_uses_org_parser_for_org(self, tmp_path):
        """Should use org parser for .org files."""
        roadmap = tmp_path / 'ROADMAP.org'
        roadmap.write_text('* Roadmap\n')

        with patch('orch.roadmap_utils.parse_org') as mock_parse:
            mock_parse.return_value = []
            parse_roadmap(roadmap)
            mock_parse.assert_called_once()


class TestFindRoadmapFile:
    """Tests for find_roadmap_file function."""

    def test_returns_none_when_no_roadmap(self, tmp_path):
        """Should return None when no roadmap file exists."""
        result = find_roadmap_file(tmp_path)
        assert result is None

    def test_finds_markdown_roadmap(self, tmp_path):
        """Should find ROADMAP.md file."""
        roadmap = tmp_path / 'ROADMAP.md'
        roadmap.write_text('# Roadmap')

        with patch('orch.roadmap_utils.get_roadmap_format', return_value='markdown'):
            result = find_roadmap_file(tmp_path)
            assert result == roadmap

    def test_finds_org_roadmap(self, tmp_path):
        """Should find ROADMAP.org file."""
        roadmap = tmp_path / 'ROADMAP.org'
        roadmap.write_text('* Roadmap')

        with patch('orch.roadmap_utils.get_roadmap_format', return_value='org'):
            result = find_roadmap_file(tmp_path)
            assert result == roadmap

    def test_prefers_configured_format(self, tmp_path):
        """Should prefer format from config."""
        # Create both files
        (tmp_path / 'ROADMAP.md').write_text('# Roadmap')
        (tmp_path / 'ROADMAP.org').write_text('* Roadmap')

        # Prefer markdown
        with patch('orch.roadmap_utils.get_roadmap_format', return_value='markdown'):
            result = find_roadmap_file(tmp_path)
            assert result.suffix == '.md'

        # Prefer org
        with patch('orch.roadmap_utils.get_roadmap_format', return_value='org'):
            result = find_roadmap_file(tmp_path)
            assert result.suffix == '.org'

    def test_falls_back_to_other_format(self, tmp_path):
        """Should fall back to other format if preferred doesn't exist."""
        # Only create org file
        (tmp_path / 'ROADMAP.org').write_text('* Roadmap')

        # Prefer markdown but fall back to org
        with patch('orch.roadmap_utils.get_roadmap_format', return_value='markdown'):
            result = find_roadmap_file(tmp_path)
            assert result.suffix == '.org'


class TestDetectProjectRoadmap:
    """Tests for detect_project_roadmap function."""

    def test_returns_none_when_no_orch_dir(self, tmp_path):
        """Should return None when no .orch directory found."""
        with patch('pathlib.Path.cwd', return_value=tmp_path):
            result = detect_project_roadmap()
            assert result is None

    def test_finds_roadmap_in_current_dir(self, tmp_path):
        """Should find roadmap in current directory's .orch."""
        orch_dir = tmp_path / '.orch'
        orch_dir.mkdir()
        roadmap = orch_dir / 'ROADMAP.md'
        roadmap.write_text('# Roadmap')

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            with patch('orch.roadmap_utils.get_roadmap_format', return_value='markdown'):
                result = detect_project_roadmap()
                assert result == roadmap


class TestFindRoadmapItemForWorkspace:
    """Tests for find_roadmap_item_for_workspace function."""

    def test_returns_none_when_no_path(self):
        """Should return None when roadmap_path is None."""
        result = find_roadmap_item_for_workspace('test-workspace', None)
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path):
        """Should return None when file doesn't exist."""
        result = find_roadmap_item_for_workspace('test-workspace', tmp_path / 'nonexistent.md')
        assert result is None

    def test_uses_correct_parser_for_format(self, tmp_path):
        """Should use format-appropriate search function."""
        roadmap = tmp_path / 'ROADMAP.md'
        roadmap.write_text('# Roadmap')

        with patch('orch.roadmap_utils.find_item_workspace_md') as mock_find:
            mock_find.return_value = None
            find_roadmap_item_for_workspace('test-workspace', roadmap)
            mock_find.assert_called_once()


class TestMarkRoadmapItemDone:
    """Tests for mark_roadmap_item_done function."""

    def test_raises_when_no_identifier(self, tmp_path):
        """Should raise ValueError when neither title nor workspace provided."""
        roadmap = tmp_path / 'ROADMAP.md'
        with pytest.raises(ValueError) as exc_info:
            mark_roadmap_item_done(roadmap)
        assert 'Must provide either' in str(exc_info.value)

    def test_returns_false_when_file_not_exists(self, tmp_path):
        """Should return False when file doesn't exist."""
        result = mark_roadmap_item_done(
            tmp_path / 'nonexistent.md',
            task_title='Test Task'
        )
        assert result is False

    def test_uses_markdown_marker_for_md(self, tmp_path):
        """Should use markdown marker for .md files."""
        roadmap = tmp_path / 'ROADMAP.md'
        roadmap.write_text('# Roadmap')

        with patch('orch.roadmap_utils.mark_done_md') as mock_mark:
            mock_mark.return_value = True
            mark_roadmap_item_done(roadmap, task_title='Test')
            mock_mark.assert_called_once()

    def test_uses_org_marker_for_org(self, tmp_path):
        """Should use org marker for .org files."""
        roadmap = tmp_path / 'ROADMAP.org'
        roadmap.write_text('* Roadmap')

        with patch('orch.roadmap_utils.mark_done_org') as mock_mark:
            mock_mark.return_value = True
            mark_roadmap_item_done(roadmap, task_title='Test')
            mock_mark.assert_called_once()
