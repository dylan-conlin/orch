"""
Tests for codebase-audit --parallel feature.

Tests that the parallel execution mode is properly documented and available
in the codebase-audit skill.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch


# Paths to skill source files
# The codebase-audit skill source is in orch-knowledge repo
ORCH_KNOWLEDGE_PATH = Path.home() / "orch-knowledge"
CODEBASE_AUDIT_SRC = ORCH_KNOWLEDGE_PATH / "skills" / "src" / "worker" / "codebase-audit"


class TestCodebaseAuditParallel:
    """Tests for codebase-audit parallel execution feature."""

    @pytest.fixture
    def skill_src_dir(self):
        """Return path to codebase-audit skill source."""
        if not CODEBASE_AUDIT_SRC.exists():
            pytest.skip("codebase-audit skill source not found in orch-knowledge")
        return CODEBASE_AUDIT_SRC

    def test_parallel_phase_file_exists(self, skill_src_dir):
        """Should have a parallel execution phase file."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        assert phase_file.exists(), f"Missing parallel phase file: {phase_file}"

    def test_parallel_template_marker_in_template(self, skill_src_dir):
        """Should have SKILL-TEMPLATE marker for mode-parallel in template."""
        template_file = skill_src_dir / "src" / "SKILL.md.template"
        if not template_file.exists():
            pytest.skip("Template file doesn't exist")

        content = template_file.read_text()
        assert '<!-- SKILL-TEMPLATE: mode-parallel -->' in content, \
            "Missing mode-parallel template marker in SKILL.md.template"

    def test_parallel_phase_has_architecture_diagram(self, skill_src_dir):
        """Parallel phase should include multi-agent architecture diagram."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        # Should have architecture visualization
        assert '┌' in content or 'Architecture' in content, \
            "Should include architecture diagram or explanation"

    def test_parallel_phase_documents_5_agents(self, skill_src_dir):
        """Parallel phase should document 5 dimension agents."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        # Should mention the 5 dimensions that get parallel agents
        dimensions = ['security', 'performance', 'architecture', 'tests', 'organizational']
        found_dimensions = sum(1 for d in dimensions if d.lower() in content.lower())
        assert found_dimensions >= 4, \
            f"Should document at least 4 of 5 dimension agents, found {found_dimensions}"

    def test_parallel_phase_specifies_haiku_model(self, skill_src_dir):
        """Parallel phase should specify Haiku model for dimension agents."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        assert 'haiku' in content.lower() or 'Haiku' in content, \
            "Should specify Haiku model for dimension agents (cost-effective)"

    def test_parallel_phase_documents_synthesis_step(self, skill_src_dir):
        """Parallel phase should document synthesis agent combining findings."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        assert 'synthesis' in content.lower() or 'combine' in content.lower() or 'prioritize' in content.lower(), \
            "Should document synthesis step that combines dimension findings"

    def test_parallel_phase_documents_json_output(self, skill_src_dir):
        """Parallel phase should specify JSON output format for structured data."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        assert 'json' in content.lower() or 'JSON' in content, \
            "Should specify JSON output format for structured agent communication"

    def test_parallel_phase_has_workflow_section(self, skill_src_dir):
        """Parallel phase should have a workflow section."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        assert '## Workflow' in content or '## Process' in content or '### Workflow' in content, \
            "Should have workflow/process section"

    def test_parallel_phase_documents_speedup(self, skill_src_dir):
        """Parallel phase should document the expected speedup benefit."""
        phase_file = skill_src_dir / "src" / "phases" / "mode-parallel.md"
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()
        assert '3x' in content or 'faster' in content.lower() or 'speedup' in content.lower(), \
            "Should document expected speedup (approximately 3x)"


class TestParallelCLIFlag:
    """Tests for --parallel CLI flag integration."""

    def test_spawn_config_has_parallel_field(self):
        """SpawnConfig should have parallel field."""
        from orch.spawn import SpawnConfig
        from dataclasses import fields

        field_names = [f.name for f in fields(SpawnConfig)]
        assert 'parallel' in field_names, "SpawnConfig should have parallel field"

    def test_spawn_config_parallel_default_false(self):
        """SpawnConfig.parallel should default to False."""
        from orch.spawn import SpawnConfig

        config = SpawnConfig(
            task="test",
            project="test",
            project_dir=Path("/tmp"),
            workspace_name="test"
        )
        assert config.parallel is False, "parallel should default to False"

    def test_spawn_prompt_includes_parallel_mode_for_codebase_audit(self):
        """build_spawn_prompt should include parallel mode section when parallel=True and skill=codebase-audit."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        config = SpawnConfig(
            task="comprehensive audit",
            project="test",
            project_dir=Path("/tmp/test"),
            workspace_name="test-audit",
            skill_name="codebase-audit",
            parallel=True
        )

        prompt = build_spawn_prompt(config)
        assert "EXECUTION MODE: PARALLEL" in prompt, "Should include parallel mode header"
        assert "5 dimension agents" in prompt, "Should mention 5 dimension agents"

    def test_spawn_prompt_excludes_parallel_mode_when_flag_false(self):
        """build_spawn_prompt should not include parallel mode when parallel=False."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        config = SpawnConfig(
            task="comprehensive audit",
            project="test",
            project_dir=Path("/tmp/test"),
            workspace_name="test-audit",
            skill_name="codebase-audit",
            parallel=False
        )

        prompt = build_spawn_prompt(config)
        assert "EXECUTION MODE: PARALLEL" not in prompt, "Should not include parallel mode when disabled"

    def test_spawn_prompt_excludes_parallel_mode_for_other_skills(self):
        """build_spawn_prompt should not include parallel mode for non-codebase-audit skills."""
        from orch.spawn import SpawnConfig
        from orch.spawn_prompt import build_spawn_prompt

        config = SpawnConfig(
            task="some task",
            project="test",
            project_dir=Path("/tmp/test"),
            workspace_name="test-task",
            skill_name="feature-impl",
            parallel=True  # Flag set, but wrong skill
        )

        prompt = build_spawn_prompt(config)
        assert "EXECUTION MODE: PARALLEL" not in prompt, "Should not include parallel mode for other skills"
