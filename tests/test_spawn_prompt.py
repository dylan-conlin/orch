"""
Tests for spawn prompt generation in orch spawn.

Tests that spawn prompts use beads as the source of truth for progress tracking,
not WORKSPACE.md files.

Related: orch-cli-30j (Remove legacy WORKSPACE.md instructions)
"""

import pytest
from pathlib import Path

from orch.spawn import (
    build_spawn_prompt,
    SpawnConfig,
    DEFAULT_DELIVERABLES,
)


class TestSpawnPromptBeadsFirst:
    """
    Validates that spawn prompts use beads for progress tracking.

    Beads (`bd comment`) is the source of truth for agent progress.
    WORKSPACE.md instructions should not be included in spawn prompts.
    Related: orch-cli-30j
    """

    def test_spawn_prompt_does_not_include_workspace_instructions(self):
        """Verify spawn prompts do NOT include WORKSPACE.md creation/update instructions."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # These WORKSPACE.md-specific instructions should NOT appear
        # (beads is now source of truth)
        legacy_sections = [
            "COORDINATION ARTIFACT POPULATION (REQUIRED):",
            "Fill TLDR / summary section (problem, status, next)",
            "Capture Session Scope (validate scope estimate, mark checkpoint points)",
            "Fill Progress Tracking (tasks with time estimates)",
            "Update metadata fields (Owner, Started, Phase, Status)",
            "Update Last Activity after each completed task",
            ".orch/docs/workspace-conventions.md for details",
            "Workspace still tracks detailed work state",
            "VERIFY workspace exists",
            "UPDATE workspace",
            "Update workspace Phase field",
        ]

        found_legacy = []
        for section in legacy_sections:
            if section in prompt:
                found_legacy.append(section)

        assert not found_legacy, (
            f"Spawn prompt contains legacy WORKSPACE.md instructions:\n"
            f"{chr(10).join('- ' + s for s in found_legacy)}\n\n"
            f"Beads is now the source of truth for progress tracking.\n"
            f"Remove workspace-specific instructions from spawn_prompt.py.\n"
            f"Reference: orch-cli-30j"
        )

    def test_spawn_prompt_includes_beads_tracking_when_beads_id_provided(self):
        """Verify spawn prompts include beads tracking when beads_id is provided."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Beads progress tracking should be present
        required_beads_sections = [
            "BEADS PROGRESS TRACKING",
            "bd comment test-123",
            "Phase: Planning",
            "Phase: Implementing",
            "Phase: Complete",
        ]

        missing_sections = []
        for section in required_beads_sections:
            if section not in prompt:
                missing_sections.append(section)

        assert not missing_sections, (
            f"Spawn prompt missing beads tracking sections:\n"
            f"{chr(10).join('- ' + s for s in missing_sections)}\n\n"
            f"Beads is the source of truth for progress tracking.\n"
            f"Reference: orch-cli-30j"
        )

    def test_spawn_prompt_status_updates_use_beads_not_workspace(self):
        """Verify STATUS UPDATES section references beads, not workspace."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should NOT reference workspace for status updates
        assert "Update Phase: field in your coordination artifact (WORKSPACE.md)" not in prompt, \
            "STATUS UPDATES should not reference WORKSPACE.md"
        assert "Update Phase: field in WORKSPACE.md" not in prompt, \
            "STATUS UPDATES should not reference WORKSPACE.md"
        assert "reads workspace Phase field" not in prompt, \
            "Monitoring should not reference workspace Phase field"

    def test_spawn_prompt_verification_does_not_reference_workspace(self):
        """Verify verification guidance does not tell agents to copy to workspace."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should NOT tell agents to copy verification requirements to workspace
        assert "Copy the verification requirements above to your workspace" not in prompt, \
            "Verification should not reference copying to workspace"

    def test_fallback_template_does_not_reference_workspace(self):
        """Verify fallback template does not contain WORKSPACE.md references."""
        from orch.spawn_prompt import fallback_template

        template = fallback_template()

        # Fallback should not reference WORKSPACE.md
        assert "WORKSPACE.md" not in template, \
            "Fallback template should not reference WORKSPACE.md"
        assert "Update workspace" not in template, \
            "Fallback template should not reference updating workspace"


class TestSpawnPromptCompletionProtocol:
    """
    Validates that spawn prompts include prominent completion protocol instructions.

    Agents were completing work but not following completion protocol (no Phase: Complete,
    no /exit). This adds prominent instructions at the start of the prompt.
    Related: orch-cli-bha
    """

    def test_spawn_prompt_includes_session_complete_protocol_block(self):
        """Verify spawn prompts include SESSION COMPLETE PROTOCOL block prominently."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # SESSION COMPLETE PROTOCOL should be present
        assert "SESSION COMPLETE PROTOCOL" in prompt, \
            "Spawn prompt must include SESSION COMPLETE PROTOCOL block"

        # Should include the key completion instructions
        assert "Phase: Complete" in prompt, \
            "Spawn prompt must mention Phase: Complete in completion protocol"
        assert "/exit" in prompt, \
            "Spawn prompt must mention /exit command"

    def test_session_complete_protocol_appears_early_in_prompt(self):
        """Verify SESSION COMPLETE PROTOCOL appears before skill content (early visibility)."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Find positions of key sections
        protocol_pos = prompt.find("SESSION COMPLETE PROTOCOL")
        skill_pos = prompt.find("## SKILL GUIDANCE")

        assert protocol_pos > 0, "SESSION COMPLETE PROTOCOL should be in prompt"
        assert skill_pos > 0, "SKILL GUIDANCE should be in prompt"

        # Protocol should appear BEFORE skill guidance (early in prompt)
        assert protocol_pos < skill_pos, (
            f"SESSION COMPLETE PROTOCOL (pos {protocol_pos}) should appear "
            f"before SKILL GUIDANCE (pos {skill_pos}) for early visibility"
        )

    def test_completion_protocol_warns_about_consequences(self):
        """Verify completion protocol explains consequences of not following it."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should warn agents about consequences
        assert "Work is NOT complete" in prompt or "cannot close" in prompt.lower(), \
            "Completion protocol should warn about consequences of not completing"
