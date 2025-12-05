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
    build_window_name,
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
        """Test auto-generating workspace name with skill prefix and date suffix."""
        task = "Fix database not persisting user sessions"
        name = create_workspace_adhoc(task, skill_name="systematic-debugging")

        # Should have skill prefix and date suffix (DDMMM)
        assert name.startswith("debug-")
        assert re.search(r'-\d{2}[a-z]{3}$', name)  # ends with -DDmmm
        assert "fix" in name or "database" in name
        assert len(name) <= 35

    def test_create_workspace_adhoc_without_skill(self):
        """Test auto-generating workspace name without skill."""
        task = "Implement heat map visualization for empty cells"
        name = create_workspace_adhoc(task)

        assert "impl" in name or "heat" in name or "map" in name
        assert len(name) <= 35
        assert not name.startswith("debug-")
        assert re.search(r'-\d{2}[a-z]{3}$', name)  # ends with date suffix

    def test_create_workspace_adhoc_truncates_long_names(self):
        """Test that long workspace names are truncated."""
        task = "Implement comprehensive authentication system with OAuth2 JWT tokens multi-factor biometric verification"
        name = create_workspace_adhoc(task, skill_name="feature-impl")

        assert len(name) <= 35

    def test_create_workspace_adhoc_handles_collision(self, tmp_path):
        """Test collision detection and hash suffix."""
        from datetime import datetime

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        workspace_dir = project_dir / ".orch" / "workspace"
        workspace_dir.mkdir(parents=True)

        # Create existing workspace with today's date suffix
        task = "Fix database issue"
        date_suffix = datetime.now().strftime("%d%b").lower()
        existing_name = f"debug-fix-database-issue-{date_suffix}"
        (workspace_dir / existing_name).mkdir()

        # Try to create same workspace
        name = create_workspace_adhoc(task, skill_name="systematic-debugging", project_dir=project_dir)

        # Should have hash suffix before date suffix
        assert name.startswith("debug-")
        assert name != existing_name
        assert len(name) <= 35
        assert re.search(r'-\d{4}-\d{2}[a-z]{3}$', name)  # Should have 4-digit hash then date

    def test_create_workspace_adhoc_with_empty_task(self):
        """Test handling empty or all-stop-words task."""
        task = "the and or"
        name = create_workspace_adhoc(task, skill_name="systematic-debugging")

        # Should still generate a valid name (skill prefix + date suffix)
        assert re.match(r'^debug-\d{2}[a-z]{3}$', name)

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

    def test_create_workspace_adhoc_no_duplicate_prefix(self):
        """Test that workspace names don't have duplicate prefixes like inv-inv-.

        When spawning an investigation with task "investigate tmux config",
        the word "investigate" becomes "inv" via abbreviation, and the skill
        prefix is also "inv". Without filtering, this produces "inv-inv-tmux-config".

        Regression test for orch-cli-916.
        """
        # Investigation skill: task contains "investigate" which abbreviates to "inv"
        task = "investigate tmux ghostty config"
        name = create_workspace_adhoc(task, skill_name="investigation")

        # Should start with single "inv-", not "inv-inv-"
        assert name.startswith("inv-")
        assert not name.startswith("inv-inv-")

        # Debugging skill: task contains "debug"
        task = "debug sendcutsend issue"
        name = create_workspace_adhoc(task, skill_name="systematic-debugging")

        # Should start with single "debug-", not "debug-debug-"
        assert name.startswith("debug-")
        assert not name.startswith("debug-debug-")

        # Feature-impl skill: task contains "implement" which abbreviates to "impl"
        # (but prefix is "feat", so no collision expected)
        task = "implement new feature"
        name = create_workspace_adhoc(task, skill_name="feature-impl")
        assert name.startswith("feat-")
        # This one should still have "impl" after "feat-" since they don't collide
        assert "impl" in name

    def test_create_workspace_adhoc_truncates_at_word_boundaries(self):
        """Test that truncation happens at word boundaries, not mid-word."""
        task = "Implement comprehensive authentication system with OAuth2 JWT tokens multifactor biometric verification passwordless"
        name = create_workspace_adhoc(task)

        # Should end with date suffix (DDmmm)
        assert re.search(r'-\d{2}[a-z]{3}$', name)
        # Second to last word (before date) should be complete
        words = name.split('-')
        second_to_last = words[-2]
        assert len(second_to_last) >= 3
        # Name should be within limit
        assert len(name) <= 35

    def test_create_workspace_adhoc_includes_date_suffix(self):
        """Test that all workspace names include date suffix."""
        from datetime import datetime

        task = "Fix the bug"
        name = create_workspace_adhoc(task)

        # Should end with today's date in compact format (DDmmm)
        today = datetime.now().strftime("%d%b").lower()
        assert name.endswith(today)


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


class TestBuildWindowName:
    """Tests for build_window_name functionality."""

    def test_build_window_name_with_beads_id(self, tmp_path):
        """Test window name includes project and beads ID."""
        project_dir = tmp_path / "orch-cli"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="debug-fix-prefixes-05dec",
            project_dir=project_dir,
            skill_name="systematic-debugging",
            beads_id="orch-cli-916"
        )

        # Should have format: emoji project: id: task
        assert "🔍" in name  # debugging emoji
        assert "orch-cli:" in name
        assert "916:" in name
        assert "fix-prefixes" in name
        # Should NOT have skill prefix or date suffix
        assert "debug-" not in name.split(": ")[-1]  # task slug shouldn't start with debug-
        assert "05dec" not in name

    def test_build_window_name_without_beads_id(self, tmp_path):
        """Test window name without beads ID."""
        project_dir = tmp_path / "price-watch"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="feat-config-parts-05dec",
            project_dir=project_dir,
            skill_name="feature-impl",
            beads_id=None
        )

        # Should have format: emoji project: task
        assert "✨" in name  # feature-impl emoji
        assert "price-watch:" in name
        assert "config-parts" in name
        # Should NOT have colons for ID
        assert name.count(":") == 1  # Only one colon (after project)

    def test_build_window_name_strips_date_suffix(self, tmp_path):
        """Test that date suffix is removed from task slug."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="inv-something-30nov",
            project_dir=project_dir,
            skill_name="investigation"
        )

        assert "30nov" not in name
        assert "something" in name

    def test_build_window_name_strips_skill_prefix(self, tmp_path):
        """Test that skill prefix is removed from task slug."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="debug-fix-bug-05dec",
            project_dir=project_dir,
            skill_name="systematic-debugging"
        )

        # The task slug should be "fix-bug", not "debug-fix-bug"
        task_part = name.split(": ")[-1]
        assert task_part == "fix-bug"

    def test_build_window_name_respects_max_length(self, tmp_path):
        """Test that window names are truncated to max_length."""
        project_dir = tmp_path / "very-long-project-name"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="feat-very-long-task-description-here-05dec",
            project_dir=project_dir,
            skill_name="feature-impl",
            max_length=35
        )

        assert len(name) <= 35

    def test_build_window_name_with_none_skill(self, tmp_path):
        """Test window name with no skill (interactive mode)."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        name = build_window_name(
            workspace_name="interactive-explore-05dec",
            project_dir=project_dir,
            skill_name=None
        )

        assert "⚙️" in name  # fallback emoji
        assert "myproject:" in name
