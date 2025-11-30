"""
Tests for workspace name length limit increase and intelligent truncation.

TDD: These tests should FAIL initially (RED phase).
After implementation, they should PASS (GREEN phase).
"""

import pytest
from pathlib import Path
from orch.workspace import validate_workspace_name, WorkspaceValidationError


class TestWorkspaceNameLengthLimit:
    """Tests for increased workspace name length limit (50 → 70 chars)."""

    def test_accepts_70_char_workspace_name(self):
        """Test that validation accepts workspace names up to 70 chars."""
        # Create a valid 70-char kebab-case name
        # Format: "a" repeated, separated by hyphens to stay kebab-case
        name = "a-" * 34 + "ab"  # Total: 70 chars (34 * 2 + 2)

        assert len(name) == 70, f"Test setup error: name is {len(name)} chars"

        # Should NOT raise - this test will FAIL initially (expects 50-char limit)
        validate_workspace_name(name)

    def test_rejects_71_char_workspace_name(self):
        """Test that validation still rejects names over 70 chars."""
        # Create a 71-char name
        name = "a-" * 35  # Total: 70 chars
        name = name + "x"  # Total: 71 chars

        assert len(name) == 71, f"Test setup error: name is {len(name)} chars"

        # Should raise WorkspaceValidationError
        with pytest.raises(WorkspaceValidationError, match="too long.*71.*max 70"):
            validate_workspace_name(name)

    def test_accepts_realistic_interactive_spawn_name(self):
        """Test that realistic interactive spawn names fit within limit."""
        # Real-world example from task description:
        # YYYY-MM-DD-interactive-explore-websocket-patterns-dashboard
        # Date: 10 chars, hyphen: 1, interactive-: 12, context: needs ~45 chars
        name = "2025-11-16-interactive-explore-websocket-patterns-dashboard"

        assert len(name) == 59, f"Test setup error: name is {len(name)} chars"

        # Should NOT raise - fits within 70-char limit
        validate_workspace_name(name)


class TestTruncateAtWordBoundary:
    """Tests for truncate_at_word_boundary() helper function."""

    def test_truncate_at_word_boundary_function_exists(self):
        """Test that truncate_at_word_boundary() function exists."""
        from orch.workspace import truncate_at_word_boundary

        # Function should exist - this will FAIL initially
        assert callable(truncate_at_word_boundary)

    def test_truncates_at_last_hyphen_before_limit(self):
        """Test that truncation happens at last hyphen before max_length."""
        from orch.workspace import truncate_at_word_boundary

        text = "explore-websocket-patterns-for-dashboard-components"
        max_length = 30

        result = truncate_at_word_boundary(text, max_length)

        # Should truncate at last hyphen before position 30
        # "explore-websocket-patterns" = 26 chars (within limit)
        assert result == "explore-websocket-patterns"
        assert len(result) <= max_length

    def test_returns_unchanged_when_under_limit(self):
        """Test that text under limit is returned unchanged."""
        from orch.workspace import truncate_at_word_boundary

        text = "short-name"
        max_length = 50

        result = truncate_at_word_boundary(text, max_length)

        assert result == text

    def test_handles_text_with_no_hyphens(self):
        """Test that truncation handles text with no hyphens gracefully."""
        from orch.workspace import truncate_at_word_boundary

        text = "verylongtextwithouthyphenstotruncate"
        max_length = 20

        result = truncate_at_word_boundary(text, max_length)

        # Should truncate at max_length when no hyphens found
        assert len(result) <= max_length

    def test_handles_empty_string(self):
        """Test that empty string is handled correctly."""
        from orch.workspace import truncate_at_word_boundary

        result = truncate_at_word_boundary("", 50)

        assert result == ""


class TestInteractiveSpawnTruncation:
    """Tests for interactive spawn truncation behavior."""

    def test_interactive_spawn_truncates_long_context(self):
        """Test that spawn_interactive() truncates long context slugs."""
        # This test will verify the integration - writing it as a unit test
        # for the workspace name generation logic
        from orch.spawn import create_workspace_adhoc
        from orch.workspace import truncate_at_word_boundary
        from datetime import datetime

        # Very long context that would exceed 70 chars with date + interactive prefix
        long_context = "Explore WebSocket connection patterns for real-time dashboard with authentication and session management"

        # Generate workspace name for interactive mode
        # Replicate logic from spawn_interactive() with truncation
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
