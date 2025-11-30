"""
Tests for spawn prompt documentation drift in orch spawn.

Tests that spawn.py implementation matches SPAWN_PROMPT.md documentation.
Prevents drift where documentation describes ideal behavior but code doesn't implement it.

Related: .orch/investigations/2025-11-16-workspace-population-pattern-violation.md
"""

import pytest
from pathlib import Path

from orch.spawn import (
    build_spawn_prompt,
    SpawnConfig,
    DEFAULT_DELIVERABLES,
)


class TestSpawnPromptDocumentationDrift:
    """
    Validates that spawn.py implementation matches SPAWN_PROMPT.md documentation.

    Prevents drift where documentation describes ideal behavior but code doesn't implement it.
    Related: .orch/investigations/2025-11-16-workspace-population-pattern-violation.md
    """

    def test_spawn_prompt_includes_required_sections(self):
        """Verify spawn prompts include all required sections from SPAWN_PROMPT.md."""
        # Create minimal config for prompt generation
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="test-skill",
            deliverables=DEFAULT_DELIVERABLES
        )

        # Generate spawn prompt
        prompt = build_spawn_prompt(config)

        # Required sections that must exist in spawn prompts for workspace-based spawns
        # (extracted from .orch/templates/SPAWN_PROMPT.md and investigation findings)
        required_sections = [
            # STATUS UPDATES section
            "STATUS UPDATES (CRITICAL):",
            "Phase: Planning",
            "Phase: Implementing",
            "Phase: Complete",

            # COORDINATION ARTIFACT POPULATION section (for workspace-based spawns)
            "COORDINATION ARTIFACT POPULATION (REQUIRED):",
            "Immediately after planning phase:",
            "Fill TLDR",
            "Capture Session Scope",
            "Fill Progress Tracking",
            "Update metadata fields",
            "During execution:",
            "Update Last Activity after each completed task",
            "Update Phase field at workflow transitions",
            "Mark checkpoint opportunities",
        ]

        # Validate all required sections are present
        missing_sections = []
        for section in required_sections:
            if section not in prompt:
                missing_sections.append(section)

        assert not missing_sections, (
            f"Spawn prompt missing required sections (documentation drift detected):\n"
            f"{chr(10).join('- ' + s for s in missing_sections)}\n\n"
            f"This indicates spawn.py has drifted from SPAWN_PROMPT.md template.\n"
            f"Update build_spawn_prompt() to include missing sections.\n"
            f"Reference: .orch/templates/SPAWN_PROMPT.md"
        )

    def test_spawn_prompt_workspace_population_details(self):
        """Verify workspace population instructions include specific guidance."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="test-skill",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Detailed coordination artifact population requirements
        # (prevents agents from skipping workspace fields)
        required_details = [
            "TLDR / summary section (problem, status, next)",
            "Capture Session Scope (validate scope estimate, mark checkpoint points)",
            "Progress Tracking (tasks with time estimates)",
            "Owner, Started, Phase, Status",
            ".orch/docs/workspace-conventions.md",
        ]

        missing_details = []
        for detail in required_details:
            if detail not in prompt:
                missing_details.append(detail)

        assert not missing_details, (
            f"Coordination artifact population instructions missing specific details:\n"
            f"{chr(10).join('- ' + d for d in missing_details)}\n\n"
            f"These details are critical for preventing workspace population violations.\n"
            f"Update COORDINATION ARTIFACT POPULATION section in build_spawn_prompt().\n"
            f"Reference: .orch/investigations/2025-11-16-workspace-population-pattern-violation.md"
        )
