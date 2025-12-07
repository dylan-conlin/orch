"""
Integration tests for SPAWN_CONTEXT.md content validation.

Tests that spawn prompt generation produces correct content for workers.
These tests verify the spawn prompt pipeline without starting Claude.
"""

import pytest
from pathlib import Path

from orch.spawn import SpawnConfig
from orch.spawn_prompt import build_spawn_prompt, load_skill_content


@pytest.mark.e2e
class TestSpawnContextContent:
    """
    Test that spawn generates SPAWN_CONTEXT.md with expected content.

    These tests verify the full prompt generation without starting Claude.
    """

    def test_spawn_context_contains_task(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains the task description."""
        task = "Implement user authentication flow"

        config = SpawnConfig(
            task=task,
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name=None,
            beads_id=None,
        )

        prompt = build_spawn_prompt(config)

        # Task should appear in context
        assert task in prompt, f"Task '{task}' not found in SPAWN_CONTEXT"
        assert "TASK:" in prompt, "TASK: header not found in SPAWN_CONTEXT"

    def test_spawn_context_contains_project_dir(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains absolute project directory path."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name=None,
            beads_id=None,
        )

        prompt = build_spawn_prompt(config)

        # Project directory should appear in context
        assert "PROJECT_DIR:" in prompt, "PROJECT_DIR: header not found in SPAWN_CONTEXT"
        assert str(project_dir) in prompt, f"Project dir {project_dir} not found in SPAWN_CONTEXT"

    def test_spawn_context_contains_completion_protocol(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains completion protocol instructions."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should include completion protocol
        assert "SESSION COMPLETE PROTOCOL" in prompt, \
            "SESSION COMPLETE PROTOCOL not found in SPAWN_CONTEXT"
        assert "Phase: Complete" in prompt, \
            "Phase: Complete not found in SPAWN_CONTEXT"
        assert "/exit" in prompt, \
            "/exit not found in SPAWN_CONTEXT"

    def test_spawn_context_contains_beads_tracking(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains beads tracking when beads_id provided."""
        beads_id = "test-123"

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id=beads_id,
        )

        prompt = build_spawn_prompt(config)

        # Should include beads tracking section
        assert "BEADS PROGRESS TRACKING" in prompt, \
            "BEADS PROGRESS TRACKING section not found when beads_id provided"
        assert beads_id in prompt, \
            f"Beads ID '{beads_id}' not found in SPAWN_CONTEXT"
        assert "bd comment" in prompt, \
            "bd comment instruction not found in SPAWN_CONTEXT"

    def test_spawn_context_contains_authority_section(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains AUTHORITY section with decision guidance."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name=None,
            beads_id=None,
        )

        prompt = build_spawn_prompt(config)

        # Should include authority section
        assert "AUTHORITY:" in prompt, "AUTHORITY: section not found in SPAWN_CONTEXT"
        assert "escalate" in prompt.lower(), "Escalation guidance not found in SPAWN_CONTEXT"

    def test_spawn_context_contains_verification_requirements(self, project_dir):
        """Verify SPAWN_CONTEXT.md contains verification requirements for feature-impl."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should include verification requirements
        assert "VERIFICATION REQUIRED:" in prompt, \
            "VERIFICATION REQUIRED section not found for feature-impl skill"

    def test_spawn_context_contains_context_available_section(self, project_dir):
        """Verify SPAWN_CONTEXT.md lists available context paths."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should list available context
        assert "CONTEXT AVAILABLE:" in prompt, \
            "CONTEXT AVAILABLE section not found in SPAWN_CONTEXT"
        assert "CLAUDE.md" in prompt, \
            "CLAUDE.md reference not found in CONTEXT AVAILABLE section"


@pytest.mark.e2e
class TestSpawnContextSkillContent:
    """
    Test that spawn includes skill content when using skill-based spawning.
    """

    def test_spawn_with_skill_includes_skill_guidance(self, project_dir):
        """Verify skill-based spawn includes SKILL GUIDANCE section."""
        config = SpawnConfig(
            task="Investigate test patterns",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="investigation",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should include skill guidance section
        assert "SKILL GUIDANCE" in prompt, "SKILL GUIDANCE section not found in SPAWN_CONTEXT"
        assert "investigation" in prompt.lower(), "Skill name not found in SPAWN_CONTEXT"

    def test_spawn_with_feature_impl_includes_phases(self, project_dir):
        """Verify feature-impl spawn includes phase configuration."""
        config = SpawnConfig(
            task="Build authentication",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            phases="investigation,implementation,validation",
            mode="tdd",
            validation="tests",
        )

        prompt = build_spawn_prompt(config)

        # Should include feature-impl configuration
        assert "FEATURE-IMPL CONFIGURATION:" in prompt, \
            "FEATURE-IMPL CONFIGURATION section not found"
        assert "investigation,implementation,validation" in prompt, \
            "Phases not found in SPAWN_CONTEXT"
        assert "tdd" in prompt.lower(), \
            "Mode not found in SPAWN_CONTEXT"

    def test_spawn_with_investigation_includes_type(self, project_dir):
        """Verify investigation spawn includes investigation type."""
        config = SpawnConfig(
            task="Investigate auth flow",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="investigation",
            beads_id="test-123",
            investigation_type="simple",
            beads_only=False,
        )

        prompt = build_spawn_prompt(config)

        # Should include investigation configuration
        assert "INVESTIGATION CONFIGURATION:" in prompt, \
            "INVESTIGATION CONFIGURATION section not found"
        assert "simple" in prompt.lower(), \
            "Investigation type not found in SPAWN_CONTEXT"


@pytest.mark.e2e
class TestSpawnContextIsolation:
    """
    Test that spawn context variables are properly isolated.
    """

    def test_different_tasks_produce_different_contexts(self, project_dir):
        """Verify different tasks produce different contexts."""
        config1 = SpawnConfig(
            task="First unique task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="workspace-1",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        config2 = SpawnConfig(
            task="Second unique task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="workspace-2",
            skill_name="feature-impl",
            beads_id="test-456",
        )

        prompt1 = build_spawn_prompt(config1)
        prompt2 = build_spawn_prompt(config2)

        # Prompts should contain their respective tasks
        assert "First unique task" in prompt1
        assert "Second unique task" in prompt2
        assert "First unique task" not in prompt2
        assert "Second unique task" not in prompt1

        # Prompts should contain their respective beads IDs
        assert "test-123" in prompt1
        assert "test-456" in prompt2
        assert "test-123" not in prompt2
        assert "test-456" not in prompt1

    def test_different_projects_produce_different_paths(self, project_dir, tmp_path):
        """Verify different projects produce different paths."""
        project_dir2 = tmp_path / "project2"
        project_dir2.mkdir()
        (project_dir2 / ".orch").mkdir()
        (project_dir2 / ".orch" / "workspace").mkdir()

        config1 = SpawnConfig(
            task="Task",
            project="project1",
            project_dir=project_dir,
            workspace_name="workspace",
            skill_name=None,
            beads_id=None,
        )

        config2 = SpawnConfig(
            task="Task",
            project="project2",
            project_dir=project_dir2,
            workspace_name="workspace",
            skill_name=None,
            beads_id=None,
        )

        prompt1 = build_spawn_prompt(config1)
        prompt2 = build_spawn_prompt(config2)

        # Each should contain its own project path
        assert str(project_dir) in prompt1
        assert str(project_dir2) in prompt2


@pytest.mark.e2e
class TestSpawnContextNoLegacyContent:
    """
    Test that spawn context doesn't include legacy workspace instructions.

    Beads is now the source of truth for progress tracking.
    """

    def test_spawn_context_no_workspace_population_instructions(self, project_dir):
        """Verify spawn context doesn't include legacy WORKSPACE.md population instructions."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # These legacy instructions should NOT appear
        legacy_sections = [
            "COORDINATION ARTIFACT POPULATION (REQUIRED):",
            "Fill TLDR / summary section",
            "Capture Session Scope",
            "Fill Progress Tracking",
            "Update metadata fields (Owner, Started, Phase, Status)",
            "Update Last Activity after each completed task",
        ]

        found_legacy = []
        for section in legacy_sections:
            if section in prompt:
                found_legacy.append(section)

        assert not found_legacy, (
            f"Spawn context contains legacy WORKSPACE.md instructions:\n"
            f"{chr(10).join('- ' + s for s in found_legacy)}\n"
            f"Beads is now the source of truth for progress tracking."
        )

    def test_spawn_context_no_agent_mail_instructions(self, project_dir):
        """Verify spawn context doesn't include Agent Mail instructions (deprecated)."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Agent Mail is no longer used
        assert "AGENT MAIL COORDINATION" not in prompt, \
            "Agent Mail section should not appear (deprecated)"
        assert "mcp__agent-mail" not in prompt, \
            "Agent Mail MCP instructions should not appear"


@pytest.mark.e2e
class TestSpawnContextInvestigationPath:
    """
    Test investigation path reporting instructions.
    """

    def test_investigation_skill_includes_path_reporting_instruction(self, project_dir):
        """Verify investigation skills instruct agents to report investigation_path."""
        config = SpawnConfig(
            task="Investigate auth flow",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="investigation",
            beads_id="test-123",
            beads_only=False,  # Investigations use investigation file
        )

        prompt = build_spawn_prompt(config)

        # Should include instruction to report investigation_path
        assert "investigation_path:" in prompt, \
            "Investigation path reporting instruction not found"

    def test_feature_impl_does_not_include_kb_create_instruction(self, project_dir):
        """Verify feature-impl doesn't include kb create investigation instruction."""
        config = SpawnConfig(
            task="Build feature",
            project="test-project",
            project_dir=project_dir,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            beads_only=True,  # feature-impl uses beads-only
        )

        prompt = build_spawn_prompt(config)

        # feature-impl should NOT have kb create investigation instruction
        assert "Run `kb create investigation" not in prompt, \
            "feature-impl should not have kb create investigation instruction"
