"""
Tests for workspace name utilities.

Note: WORKSPACE.md-specific functionality has been removed.
Only workspace naming utilities remain.
"""

import pytest
from orch.workspace import truncate_at_word_boundary


class TestTruncateAtWordBoundary:
    """Tests for truncate_at_word_boundary() helper function."""

    def test_truncate_at_word_boundary_function_exists(self):
        """Test that truncate_at_word_boundary() function exists."""
        assert callable(truncate_at_word_boundary)

    def test_truncates_at_last_hyphen_before_limit(self):
        """Test that truncation happens at last hyphen before max_length."""
        text = "explore-websocket-patterns-for-dashboard-components"
        max_length = 30

        result = truncate_at_word_boundary(text, max_length)

        # Should truncate at last hyphen before position 30
        # "explore-websocket-patterns" = 26 chars (within limit)
        assert result == "explore-websocket-patterns"
        assert len(result) <= max_length

    def test_returns_unchanged_when_under_limit(self):
        """Test that text under limit is returned unchanged."""
        text = "short-name"
        max_length = 50

        result = truncate_at_word_boundary(text, max_length)

        assert result == text

    def test_handles_text_with_no_hyphens(self):
        """Test that truncation handles text with no hyphens gracefully."""
        text = "verylongtextwithouthyphenstotruncate"
        max_length = 20

        result = truncate_at_word_boundary(text, max_length)

        # Should truncate at max_length when no hyphens found
        assert len(result) <= max_length

    def test_handles_empty_string(self):
        """Test that empty string is handled correctly."""
        result = truncate_at_word_boundary("", 50)

        assert result == ""


class TestInteractiveSpawnTruncation:
    """Tests for interactive spawn truncation behavior."""

    def test_interactive_spawn_truncates_long_context(self):
        """Test that spawn_interactive() truncates long context slugs."""
        from orch.workspace_naming import create_workspace_adhoc

        # Very long context that would exceed 70 chars with date + interactive prefix
        long_context = "Explore WebSocket connection patterns for real-time dashboard with authentication and session management"

        # Generate workspace name for interactive mode
        base_name = create_workspace_adhoc(long_context, skill_name=None, project_dir=None)

        # Insert 'interactive-' after date prefix with truncation
        parts = base_name.split('-', 3)
        if len(parts) >= 4:
            date_prefix = f"{parts[0]}-{parts[1]}-{parts[2]}"  # YYYY-MM-DD
            context_slug = parts[3]

            # Calculate available chars for context after 'interactive-' prefix
            # Total: 70, Date: 10, Hyphens: 2, Interactive: 11 = 47 chars available
            available_chars = 70 - len(date_prefix) - 1 - len("interactive") - 1

            # Truncate context slug if needed
            context_slug = truncate_at_word_boundary(context_slug, available_chars)

            workspace_name = f"{date_prefix}-interactive-{context_slug}"
        else:
            workspace_name = f"interactive-{base_name}"

        # Should be truncated to fit within 70 chars
        assert len(workspace_name) <= 70, \
            f"Workspace name too long: {len(workspace_name)} chars (max 70)\n{workspace_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
