"""
Tests for orch decisions module.

Tests decision record template management.
"""

import pytest
import os
from pathlib import Path
from datetime import date
from unittest.mock import patch

from orch.decisions import (
    DecisionError,
    detect_project_dir,
    create_decision,
)


class TestDetectProjectDir:
    """Tests for detect_project_dir function."""

    def test_uses_explicit_project_dir(self, tmp_path):
        """Should use explicitly provided project directory."""
        (tmp_path / '.orch').mkdir()
        result = detect_project_dir(tmp_path)
        assert result == tmp_path

    def test_raises_when_explicit_has_no_orch(self, tmp_path):
        """Should raise when explicit directory has no .orch."""
        with pytest.raises(DecisionError) as exc_info:
            detect_project_dir(tmp_path)
        assert 'No .orch directory' in str(exc_info.value)

    def test_uses_claude_project_env(self, tmp_path):
        """Should use CLAUDE_PROJECT environment variable."""
        (tmp_path / '.orch').mkdir()

        with patch.dict(os.environ, {'CLAUDE_PROJECT': str(tmp_path)}):
            result = detect_project_dir()
            assert result == tmp_path

    def test_raises_when_env_has_no_orch(self, tmp_path):
        """Should raise when CLAUDE_PROJECT has no .orch."""
        with patch.dict(os.environ, {'CLAUDE_PROJECT': str(tmp_path)}):
            with pytest.raises(DecisionError) as exc_info:
                detect_project_dir()
            assert 'CLAUDE_PROJECT' in str(exc_info.value)

    def test_uses_find_orch_root_fallback(self, tmp_path):
        """Should fall back to find_orch_root when no explicit dir or env."""
        (tmp_path / '.orch').mkdir()

        # Clear CLAUDE_PROJECT if set
        env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_PROJECT'}

        with patch.dict(os.environ, env, clear=True):
            with patch('orch.path_utils.find_orch_root', return_value=str(tmp_path)):
                result = detect_project_dir()
                assert result == tmp_path

    def test_raises_when_no_orch_found(self, tmp_path):
        """Should raise when no .orch directory found anywhere."""
        env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_PROJECT'}

        with patch.dict(os.environ, env, clear=True):
            with patch('orch.path_utils.find_orch_root', return_value=None):
                with pytest.raises(DecisionError) as exc_info:
                    detect_project_dir()
                assert 'No .orch directory found' in str(exc_info.value)


class TestCreateDecision:
    """Tests for create_decision function."""

    def test_creates_decision_file(self, tmp_path):
        """Should create decision file from template."""
        # Setup project and template
        (tmp_path / '.orch').mkdir()
        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / 'DECISION.md').write_text('# Decision\n\nDate: YYYY-MM-DD')

        result = create_decision('test-decision', tmp_path)

        assert 'file_path' in result
        assert Path(result['file_path']).exists()
        assert 'test-decision' in result['file_path']

    def test_substitutes_date(self, tmp_path):
        """Should substitute date placeholders."""
        (tmp_path / '.orch').mkdir()
        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / 'DECISION.md').write_text('Date: YYYY-MM-DD')

        result = create_decision('test-decision', tmp_path)

        content = Path(result['file_path']).read_text()
        today = date.today().strftime('%Y-%m-%d')
        assert today in content
        assert 'YYYY-MM-DD' not in content

    def test_rejects_invalid_slug(self, tmp_path):
        """Should reject slugs with path traversal or slashes."""
        (tmp_path / '.orch').mkdir()

        with pytest.raises(DecisionError) as exc_info:
            create_decision('../escape', tmp_path)
        assert 'Invalid slug' in str(exc_info.value)

        with pytest.raises(DecisionError) as exc_info:
            create_decision('sub/path', tmp_path)
        assert 'Invalid slug' in str(exc_info.value)

    def test_raises_when_file_exists(self, tmp_path):
        """Should raise when decision file already exists."""
        (tmp_path / '.orch' / 'decisions').mkdir(parents=True)
        today = date.today().strftime('%Y-%m-%d')
        existing = tmp_path / '.orch' / 'decisions' / f'{today}-existing.md'
        existing.write_text('Already exists')

        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / 'DECISION.md').write_text('# Template')

        with pytest.raises(DecisionError) as exc_info:
            create_decision('existing', tmp_path)
        assert 'File already exists' in str(exc_info.value)

    def test_raises_when_template_missing(self, tmp_path):
        """Should raise when template file doesn't exist."""
        (tmp_path / '.orch').mkdir()

        # Ensure template doesn't exist
        template_path = Path.home() / '.orch' / 'templates' / 'DECISION.md'
        if template_path.exists():
            template_path.unlink()

        with pytest.raises(DecisionError) as exc_info:
            create_decision('test', tmp_path)
        assert 'Template not found' in str(exc_info.value)

    def test_creates_decisions_directory(self, tmp_path):
        """Should create decisions directory if it doesn't exist."""
        (tmp_path / '.orch').mkdir()
        template_dir = Path.home() / '.orch' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / 'DECISION.md').write_text('# Template')

        # decisions dir doesn't exist yet
        assert not (tmp_path / '.orch' / 'decisions').exists()

        result = create_decision('test', tmp_path)

        assert (tmp_path / '.orch' / 'decisions').exists()
        assert Path(result['file_path']).exists()


class TestDecisionError:
    """Tests for DecisionError exception."""

    def test_is_exception(self):
        """Should be an Exception subclass."""
        assert issubclass(DecisionError, Exception)

    def test_accepts_message(self):
        """Should accept and store message."""
        error = DecisionError('Test error message')
        assert str(error) == 'Test error message'
