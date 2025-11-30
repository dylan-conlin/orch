"""
Tests for context_ref file loading in orch spawn.

When spawning from backlog.json with a context_ref field, the referenced file's
content should be loaded and included in the spawn prompt.

Related: .orch/investigations/design/2025-11-28-artifact-flow-brainstorming-to-feature-impl.md
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    SpawnConfig,
)
from orch.spawn_prompt import build_spawn_prompt


class TestContextRefLoading:
    """
    Tests for context_ref file content loading in spawn prompts.

    When a feature has a context_ref pointing to a design doc or investigation,
    the spawn prompt should include that content to give agents design context.
    """

    def test_spawn_prompt_includes_context_ref_content(self, tmp_path):
        """Verify spawn prompt includes content from context_ref file."""
        # Create a mock context_ref file
        context_file = tmp_path / ".orch" / "investigations" / "design" / "2025-11-28-test-design.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text("""# Test Design Document

## Decision

We decided to use approach A because of X, Y, Z.

## Implementation Notes

Key constraint: Must integrate with existing auth system.
""")

        # Create config with context_ref
        config = SpawnConfig(
            task="Implement test feature",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=str(context_file.relative_to(tmp_path)),
        )

        # Generate spawn prompt
        prompt = build_spawn_prompt(config)

        # Verify context_ref content is included
        assert "Test Design Document" in prompt, (
            "Spawn prompt should include context_ref file content"
        )
        assert "approach A because of X, Y, Z" in prompt
        assert "Must integrate with existing auth system" in prompt

    def test_spawn_prompt_labels_context_ref_section(self, tmp_path):
        """Verify context_ref content appears under a labeled section."""
        # Create a mock context_ref file
        context_file = tmp_path / ".orch" / "decisions" / "2025-11-28-test-decision.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text("Decision content here")

        config = SpawnConfig(
            task="Implement feature from decision",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=str(context_file.relative_to(tmp_path)),
        )

        prompt = build_spawn_prompt(config)

        # Verify labeled section exists
        assert "DESIGN CONTEXT" in prompt or "Design Context" in prompt, (
            "Context_ref content should appear under a labeled section"
        )

    def test_spawn_prompt_handles_missing_context_ref_file(self, tmp_path):
        """Verify graceful handling when context_ref file doesn't exist."""
        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=".orch/investigations/nonexistent.md",
        )

        # Should not raise, should handle gracefully
        prompt = build_spawn_prompt(config)

        # Prompt should still be generated
        assert "Implement feature" in prompt

    def test_spawn_prompt_no_context_ref_when_none(self, tmp_path):
        """Verify no context section when context_ref is None."""
        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=None,
        )

        prompt = build_spawn_prompt(config)

        # Should not have design context section when no context_ref
        # (checking for absence of section header)
        assert "DESIGN CONTEXT:" not in prompt

    def test_spawn_prompt_context_ref_includes_file_path(self, tmp_path):
        """Verify context section includes path to original file for reference."""
        context_file = tmp_path / ".orch" / "investigations" / "design" / "test.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text("Design content")

        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=".orch/investigations/design/test.md",
        )

        prompt = build_spawn_prompt(config)

        # Should include path reference so agent can find original
        assert ".orch/investigations/design/test.md" in prompt


class TestFrontendAestheticsContext:
    """
    Tests for frontend aesthetics context file integration.

    When spawning UI work with context_ref pointing to frontend-aesthetics.md,
    the spawn prompt should include design principles for typography, color,
    motion, and spatial composition.

    Related: .orch/investigations/simple/2025-11-29-study-claude-code-frontend-design.md
    """

    def test_frontend_aesthetics_file_exists(self):
        """Verify the frontend aesthetics context file exists in .orch/contexts/."""
        from pathlib import Path

        # Use the actual project path
        project_root = Path(__file__).parent.parent
        context_file = project_root / ".orch" / "contexts" / "frontend-aesthetics.md"

        assert context_file.exists(), (
            f"Frontend aesthetics file should exist at {context_file}"
        )

    def test_frontend_aesthetics_includes_core_principles(self):
        """Verify frontend aesthetics file includes all key design principles."""
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        context_file = project_root / ".orch" / "contexts" / "frontend-aesthetics.md"

        content = context_file.read_text()

        # Core principle
        assert "BOLD aesthetic direction" in content, "Should include bold direction principle"

        # Typography section
        assert "Typography" in content, "Should include typography section"
        assert "system font" in content.lower(), "Should warn against system fonts"

        # Color section
        assert "Color" in content, "Should include color section"
        assert "dominant color" in content.lower(), "Should recommend dominant colors"

        # Motion section
        assert "Motion" in content, "Should include motion section"
        assert "page load" in content.lower(), "Should discuss page load animation"

        # Spatial composition
        assert "Spatial" in content or "composition" in content.lower(), (
            "Should include spatial composition guidance"
        )

    def test_spawn_prompt_includes_frontend_aesthetics_content(self, tmp_path):
        """Verify spawn prompt includes frontend aesthetics when context_ref provided."""
        # Create a mock frontend-aesthetics file in tmp_path
        context_file = tmp_path / ".orch" / "contexts" / "frontend-aesthetics.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy subset of actual content
        context_file.write_text("""# Frontend Aesthetics Guidelines

## Core Principle

**Commit to BOLD aesthetic direction, not safe defaults.**

## Typography

**DON'T (Anti-patterns):**
- System font stacks: `-apple-system, BlinkMacSystemFont`

## Color

**DO:**
- Choose a dominant color that sets the mood
""")

        config = SpawnConfig(
            task="Redesign dashboard with distinctive aesthetics",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            context_ref=".orch/contexts/frontend-aesthetics.md",
        )

        prompt = build_spawn_prompt(config)

        # Verify frontend aesthetics content is included
        assert "BOLD aesthetic direction" in prompt, (
            "Spawn prompt should include core design principle"
        )
        assert "Typography" in prompt, (
            "Spawn prompt should include typography guidance"
        )
        assert "dominant color" in prompt, (
            "Spawn prompt should include color guidance"
        )

    def test_frontend_aesthetics_anti_patterns_included(self):
        """Verify anti-patterns are documented to guide agents away from defaults."""
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        context_file = project_root / ".orch" / "contexts" / "frontend-aesthetics.md"

        content = context_file.read_text()

        # Key anti-patterns from investigation
        anti_patterns = [
            "system font",  # System font stacks
            "gray-900",     # Generic gray dark themes
            "timid",        # Timid palettes
        ]

        found_anti_patterns = sum(1 for ap in anti_patterns if ap.lower() in content.lower())

        assert found_anti_patterns >= 2, (
            f"Frontend aesthetics should document at least 2 anti-patterns. "
            f"Found {found_anti_patterns}: {[ap for ap in anti_patterns if ap.lower() in content.lower()]}"
        )
