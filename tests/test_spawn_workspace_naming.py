"""
Tests for workspace naming functionality in orch spawn.

Tests workspace name generation including:
- Extracting meaningful words from task descriptions
- Creating adhoc workspace names with date prefix
- Applying abbreviations for long words
- Handling collisions with hash suffixes
- Emoji detection for skills
"""

import re
import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    extract_meaningful_words,
    create_workspace_adhoc,
    get_emoji_for_skill,
)


class TestWorkspaceNaming:
    """Tests for workspace naming functionality."""

    def test_extract_meaningful_words(self):
        """Test extracting meaningful words from text."""
        text = "Fix the database persistence issue in the API"
        words = extract_meaningful_words(text)

        assert "fix" in words
        assert "database" in words
        assert "persistence" in words
        assert "issue" in words
        assert "api" in words
        # Stop words should be filtered
        assert "the" not in words
        assert "in" not in words

    def test_extract_meaningful_words_removes_short_words(self):
        """Test that short words (<=2 chars) are filtered."""
        text = "A to do or be in at"
        words = extract_meaningful_words(text)

        # All words are stop words or too short
        assert len(words) == 0

    def test_extract_meaningful_words_converts_underscores_to_hyphens(self):
        """Test that underscores are treated as word separators for kebab-case."""
        text = "add button to /collection_runs page"
        words = extract_meaningful_words(text)

        # Underscores should split into separate words
        assert "collection" in words
        assert "runs" in words
        # The underscore-connected word should NOT be preserved as one
        assert "collection_runs" not in words

    def test_extract_meaningful_words_handles_multiple_underscores(self):
        """Test handling of multiple consecutive underscores."""
        text = "test__double__underscores"
        words = extract_meaningful_words(text)

        # Should extract individual words, not preserve underscores
        assert "test" in words
        assert "double" in words
        assert "underscores" in words
        assert "test__double__underscores" not in words

    def test_create_workspace_adhoc_with_skill(self):
        """Test auto-generating workspace name with skill prefix and date."""
        task = "Fix database not persisting user sessions"
        name = create_workspace_adhoc(task, skill_name="systematic-debugging")

        # Should have date prefix (YYYY-MM-DD) then skill prefix
        assert re.match(r'^\d{4}-\d{2}-\d{2}-debug-', name)
        assert "fix" in name or "database" in name
        assert len(name) <= 70

    def test_create_workspace_adhoc_without_skill(self):
        """Test auto-generating workspace name without skill."""
        task = "Implement heat map visualization for empty cells"
        name = create_workspace_adhoc(task)

        assert "implement" in name or "heat" in name or "map" in name
        assert len(name) <= 70
        assert not name.startswith("debug-")

    def test_create_workspace_adhoc_truncates_long_names(self):
        """Test that long workspace names are truncated."""
        task = "Implement comprehensive authentication system with OAuth2 JWT tokens multi-factor biometric verification"
        name = create_workspace_adhoc(task, skill_name="implement-feature")

        assert len(name) <= 70

    def test_create_workspace_adhoc_handles_collision(self, tmp_path):
        """Test collision detection and hash suffix."""
        from datetime import datetime

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        workspace_dir = project_dir / ".orch" / "workspace"
        workspace_dir.mkdir(parents=True)

        # Create existing workspace with today's date
        task = "Fix database issue"
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        existing_name = f"{date_prefix}-debug-fix-database-issue"
        (workspace_dir / existing_name).mkdir()

        # Try to create same workspace
        name = create_workspace_adhoc(task, skill_name="systematic-debugging", project_dir=project_dir)

        # Should have hash suffix and still have date prefix
        assert re.match(r'^\d{4}-\d{2}-\d{2}-debug-', name)
        assert name != existing_name
        assert len(name) <= 50
        assert re.search(r'-\d{6}$', name)  # Should end with 6-digit hash

    def test_create_workspace_adhoc_with_empty_task(self):
        """Test handling empty or all-stop-words task."""
        task = "the and or"
        name = create_workspace_adhoc(task, skill_name="systematic-debugging")

        # Should still generate a valid name (date + skill prefix)
        assert re.match(r'^\d{4}-\d{2}-\d{2}-debug$', name)

    def test_create_workspace_adhoc_applies_abbreviations(self):
        """Test that common words are abbreviated."""
        task = "investigate database configuration authentication issue"
        name = create_workspace_adhoc(task)

        # Should abbreviate investigate, configuration, authentication
        assert "inv" in name or "config" in name or "auth" in name
        # Should not have full words
        assert "investigate" not in name
        assert "configuration" not in name
        assert "authentication" not in name

    def test_create_workspace_adhoc_truncates_at_word_boundaries(self):
        """Test that truncation happens at word boundaries, not mid-word."""
        task = "Implement comprehensive authentication system with OAuth2 JWT tokens multifactor biometric verification passwordless"
        name = create_workspace_adhoc(task)

        # Should not end with a partial word (no hyphen followed by incomplete word)
        words = name.split('-')
        last_word = words[-1]
        # Last word should be complete (at least 3 chars and not look truncated)
        assert len(last_word) >= 3
        # Name should be within limit
        assert len(name) <= 70

    def test_create_workspace_adhoc_includes_date_prefix(self):
        """Test that all workspace names include date prefix."""
        from datetime import datetime

        task = "Fix the bug"
        name = create_workspace_adhoc(task)

        # Should start with today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert name.startswith(today)


class TestEmojiDetection:
    """Tests for emoji detection functionality."""

    def test_get_emoji_for_known_skill(self):
        """Test getting emoji for known skill."""
        assert get_emoji_for_skill("systematic-debugging") == '🔍'
        assert get_emoji_for_skill("feature-impl") == '✨'
        assert get_emoji_for_skill("investigation") == '🔬'

    def test_get_emoji_for_unknown_skill(self):
        """Test fallback emoji for unknown skill."""
        assert get_emoji_for_skill("unknown-skill") == '⚙️'

    def test_get_emoji_for_none(self):
        """Test fallback emoji when skill_name is None."""
        assert get_emoji_for_skill(None) == '⚙️'
