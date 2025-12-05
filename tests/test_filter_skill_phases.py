"""
Tests for filtering skill phases to only configured ones.

When spawning with feature-impl, if --phases="implementation,validation" is specified,
the skill content should only include those phase sections, not all 8 phases.

Related: orch-cli-jjb (P0: Filter skill phases to only configured ones)
"""

import pytest

from orch.spawn_prompt import filter_skill_phases


# Sample skill content with phase markers (simplified for testing)
SAMPLE_SKILL_CONTENT = """# Feature Implementation (Unified Framework)

**For orchestrators:** Spawn via `orch spawn feature-impl "task" --phases "..." --mode ... --validation ...`

**For workers:** You've been spawned to implement a feature using a phased approach.

---

## Your Configuration

Read from SPAWN_CONTEXT.md to understand your configuration.

---

<!-- SKILL-TEMPLATE: investigation -->
<!-- Auto-generated from src/phases/investigation.md -->

# Investigation Phase

**Purpose:** Understand the existing system before making changes.

Content for investigation phase goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: clarifying-questions -->
<!-- Auto-generated from src/phases/clarifying-questions.md -->

# Clarifying Questions Phase

**Purpose:** Surface all ambiguities BEFORE design work begins.

Content for clarifying questions phase goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: design -->
<!-- Auto-generated from src/phases/design.md -->

# Design Phase

**Purpose:** Document architectural approach before implementation.

Content for design phase goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: implementation-tdd -->
<!-- Auto-generated from src/phases/implementation-tdd.md -->

# Implementation Phase (TDD Mode)

**Purpose:** Implement feature using test-driven development.

Content for TDD implementation goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: implementation-direct -->
<!-- Auto-generated from src/phases/implementation-direct.md -->

# Implementation Phase (Direct Mode)

**Purpose:** Implement non-behavioral changes directly.

Content for direct implementation goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: validation -->
<!-- Auto-generated from src/phases/validation.md -->

# Validation Phase

**Purpose:** Verify implementation works as intended.

Content for validation phase goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: self-review -->
<!-- Auto-generated from src/phases/self-review.md -->

# Self-Review Phase

**Purpose:** Quality gate before completion.

Content for self-review phase goes here.

<!-- /SKILL-TEMPLATE -->

---

<!-- SKILL-TEMPLATE: integration -->
<!-- Auto-generated from src/phases/integration.md -->

# Integration Phase

**Purpose:** Combine multiple validated phases.

Content for integration phase goes here.

<!-- /SKILL-TEMPLATE -->

---

## Phase Transitions

After completing each phase, report progress.

---

## Footer Content

This content should always be preserved.
"""


class TestFilterSkillPhasesBasic:
    """Basic filtering tests."""

    def test_keeps_header_content(self):
        """Header content before first phase marker should be preserved."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # Header content should be present
        assert "# Feature Implementation (Unified Framework)" in result
        assert "## Your Configuration" in result
        assert "Read from SPAWN_CONTEXT.md" in result

    def test_keeps_footer_content(self):
        """Footer content after last phase marker should be preserved."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # Footer content should be present
        assert "## Phase Transitions" in result
        assert "## Footer Content" in result

    def test_filters_out_unconfigured_phases(self):
        """Phases not in the configured list should be excluded."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # These phases should NOT be present
        assert "# Investigation Phase" not in result
        assert "# Clarifying Questions Phase" not in result
        assert "# Design Phase" not in result
        assert "# Self-Review Phase" not in result
        assert "# Integration Phase" not in result

    def test_keeps_configured_phases(self):
        """Phases in the configured list should be included."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # These phases SHOULD be present
        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Validation Phase" in result


class TestFilterSkillPhasesImplementationMode:
    """Tests for implementation mode handling (tdd vs direct)."""

    def test_tdd_mode_includes_implementation_tdd(self):
        """TDD mode should include implementation-tdd section."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Implementation Phase (TDD Mode)" in result
        assert "Content for TDD implementation goes here" in result

    def test_tdd_mode_excludes_implementation_direct(self):
        """TDD mode should exclude implementation-direct section."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Implementation Phase (Direct Mode)" not in result
        assert "Content for direct implementation goes here" not in result

    def test_direct_mode_includes_implementation_direct(self):
        """Direct mode should include implementation-direct section."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="direct")

        assert "# Implementation Phase (Direct Mode)" in result
        assert "Content for direct implementation goes here" in result

    def test_direct_mode_excludes_implementation_tdd(self):
        """Direct mode should exclude implementation-tdd section."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="direct")

        assert "# Implementation Phase (TDD Mode)" not in result
        assert "Content for TDD implementation goes here" not in result

    def test_default_mode_is_tdd(self):
        """When no mode specified, should default to TDD."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode=None)

        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Implementation Phase (Direct Mode)" not in result


class TestFilterSkillPhasesEdgeCases:
    """Edge case tests."""

    def test_no_phases_returns_header_and_footer_only(self):
        """Empty phases list should return header and footer only."""
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, [], mode="tdd")

        # Header and footer should be present
        assert "# Feature Implementation (Unified Framework)" in result
        assert "## Footer Content" in result

        # No phase content should be present
        assert "# Investigation Phase" not in result
        assert "# Implementation Phase" not in result
        assert "# Validation Phase" not in result

    def test_all_phases_returns_full_content(self):
        """All phases configured should return full content."""
        all_phases = [
            "investigation",
            "clarifying-questions",
            "design",
            "implementation",
            "validation",
            "self-review",
            "integration",
        ]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, all_phases, mode="tdd")

        # All phases should be present
        assert "# Investigation Phase" in result
        assert "# Clarifying Questions Phase" in result
        assert "# Design Phase" in result
        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Validation Phase" in result
        assert "# Self-Review Phase" in result
        assert "# Integration Phase" in result

    def test_content_without_markers_returns_unchanged(self):
        """Content without phase markers should be returned unchanged."""
        simple_content = "# Simple Skill\n\nNo phases here."
        result = filter_skill_phases(simple_content, ["implementation"], mode="tdd")

        assert result == simple_content

    def test_none_content_returns_none(self):
        """None input should return None."""
        result = filter_skill_phases(None, ["implementation"], mode="tdd")
        assert result is None

    def test_empty_content_returns_empty(self):
        """Empty string input should return empty string."""
        result = filter_skill_phases("", ["implementation"], mode="tdd")
        assert result == ""

    def test_preserves_markers_in_output(self):
        """Phase markers should be preserved in filtered output for debugging."""
        phases = ["validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # Markers for included phases should be present
        assert "<!-- SKILL-TEMPLATE: validation -->" in result
        assert "<!-- /SKILL-TEMPLATE -->" in result


class TestFilterSkillPhasesPhaseNameVariants:
    """Tests for phase name handling."""

    def test_design_phase_standalone(self):
        """Design phase should be included when configured."""
        phases = ["design", "implementation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Design Phase" in result
        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Investigation Phase" not in result

    def test_investigation_phase_standalone(self):
        """Investigation phase should be included when configured."""
        phases = ["investigation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Investigation Phase" in result
        assert "# Implementation Phase" not in result

    def test_self_review_phase(self):
        """Self-review phase should be recognized with hyphen."""
        phases = ["self-review"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Self-Review Phase" in result

    def test_clarifying_questions_phase(self):
        """Clarifying-questions phase should be recognized with hyphen."""
        phases = ["clarifying-questions"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        assert "# Clarifying Questions Phase" in result


class TestFilterSkillPhasesInBuildSpawnPrompt:
    """Tests that filter_skill_phases is called correctly in build_spawn_prompt."""

    def test_build_spawn_prompt_filters_feature_impl_phases(self, tmp_path, monkeypatch):
        """Verify build_spawn_prompt filters feature-impl skill phases."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        # Mock load_skill_content to return our test content
        def mock_load_skill_content(skill_name, skill_metadata=None):
            return SAMPLE_SKILL_CONTENT

        monkeypatch.setattr(
            "orch.spawn_prompt.load_skill_content",
            mock_load_skill_content
        )

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            phases="implementation,validation",
            mode="tdd",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should include configured phases
        assert "# Implementation Phase (TDD Mode)" in prompt
        assert "# Validation Phase" in prompt

        # Should NOT include unconfigured phases
        assert "# Investigation Phase" not in prompt
        assert "# Design Phase" not in prompt
        assert "# Self-Review Phase" not in prompt

    def test_build_spawn_prompt_respects_mode_for_implementation(self, tmp_path, monkeypatch):
        """Verify build_spawn_prompt uses mode to select implementation variant."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        def mock_load_skill_content(skill_name, skill_metadata=None):
            return SAMPLE_SKILL_CONTENT

        monkeypatch.setattr(
            "orch.spawn_prompt.load_skill_content",
            mock_load_skill_content
        )

        # Test with direct mode
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            phases="implementation,validation",
            mode="direct",
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # Should include direct mode implementation
        assert "# Implementation Phase (Direct Mode)" in prompt
        # Should NOT include TDD mode
        assert "# Implementation Phase (TDD Mode)" not in prompt

    def test_build_spawn_prompt_does_not_filter_non_feature_impl_skills(self, tmp_path, monkeypatch):
        """Verify non-feature-impl skills are not filtered."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        def mock_load_skill_content(skill_name, skill_metadata=None):
            return SAMPLE_SKILL_CONTENT

        monkeypatch.setattr(
            "orch.spawn_prompt.load_skill_content",
            mock_load_skill_content
        )

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="investigation",  # Not feature-impl
            beads_id="test-123",
        )

        prompt = build_spawn_prompt(config)

        # All phases should be present (no filtering for non-feature-impl)
        assert "# Investigation Phase" in prompt
        assert "# Implementation Phase (TDD Mode)" in prompt
        assert "# Validation Phase" in prompt


class TestFilterSkillPhasesIntegration:
    """Integration tests with realistic scenarios."""

    def test_typical_feature_impl_config(self):
        """Test typical feature-impl configuration: implementation,validation."""
        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # Should have header
        assert "# Feature Implementation (Unified Framework)" in result

        # Should have only these phases
        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Validation Phase" in result

        # Should NOT have these phases
        assert "# Investigation Phase" not in result
        assert "# Design Phase" not in result
        assert "# Self-Review Phase" not in result

        # Should have footer
        assert "## Footer Content" in result

    def test_full_investigation_flow(self):
        """Test full investigation flow: investigation,design,implementation,validation."""
        phases = ["investigation", "design", "implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")

        # Should have these phases
        assert "# Investigation Phase" in result
        assert "# Design Phase" in result
        assert "# Implementation Phase (TDD Mode)" in result
        assert "# Validation Phase" in result

        # Should NOT have these phases
        assert "# Clarifying Questions Phase" not in result
        assert "# Self-Review Phase" not in result
        assert "# Integration Phase" not in result

    def test_line_count_reduction(self):
        """Filtering should significantly reduce line count."""
        full_lines = len(SAMPLE_SKILL_CONTENT.splitlines())

        phases = ["implementation", "validation"]
        result = filter_skill_phases(SAMPLE_SKILL_CONTENT, phases, mode="tdd")
        filtered_lines = len(result.splitlines())

        # Should have fewer lines (at least 30% reduction in test content)
        assert filtered_lines < full_lines * 0.7, (
            f"Expected significant line reduction. "
            f"Full: {full_lines}, Filtered: {filtered_lines}"
        )
