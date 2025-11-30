"""
Tests for orch skill_discovery module.

Tests the skill discovery functionality including:
- Data classes (SkillDeliverable, SkillVerification, SkillMetadata)
- YAML frontmatter parsing
- Skill directory scanning
- Cache behavior
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from orch.skill_discovery import (
    SkillDeliverable,
    SkillVerification,
    SkillMetadata,
    DEFAULT_DELIVERABLES,
    discover_skills,
    parse_skill_metadata,
    _discover_skills_cached,
)


class TestSkillDeliverable:
    """Tests for SkillDeliverable dataclass."""

    def test_creates_with_required_fields(self):
        """Should create deliverable with type and path."""
        deliverable = SkillDeliverable(type="workspace", path=".orch/workspace/{name}")
        assert deliverable.type == "workspace"
        assert deliverable.path == ".orch/workspace/{name}"
        assert deliverable.required is True  # default
        assert deliverable.description == ""  # default

    def test_creates_with_all_fields(self):
        """Should create deliverable with all fields."""
        deliverable = SkillDeliverable(
            type="investigation",
            path=".orch/investigations/{slug}.md",
            required=False,
            description="Investigation findings"
        )
        assert deliverable.type == "investigation"
        assert deliverable.path == ".orch/investigations/{slug}.md"
        assert deliverable.required is False
        assert deliverable.description == "Investigation findings"


class TestSkillVerification:
    """Tests for SkillVerification dataclass."""

    def test_creates_with_required_fields(self):
        """Should create verification with requirements."""
        verification = SkillVerification(requirements="- [ ] Tests pass")
        assert verification.requirements == "- [ ] Tests pass"
        assert verification.required is True  # default
        assert verification.test_command is None  # default
        assert verification.timeout == 300  # default

    def test_creates_with_all_fields(self):
        """Should create verification with all fields."""
        verification = SkillVerification(
            requirements="- [ ] Tests pass\n- [ ] Lint clean",
            required=False,
            test_command="pytest",
            timeout=600
        )
        assert "Tests pass" in verification.requirements
        assert "Lint clean" in verification.requirements
        assert verification.required is False
        assert verification.test_command == "pytest"
        assert verification.timeout == 600


class TestSkillMetadata:
    """Tests for SkillMetadata dataclass."""

    def test_creates_with_required_fields(self):
        """Should create metadata with name, triggers, deliverables."""
        metadata = SkillMetadata(
            name="test-skill",
            triggers=["test", "debug"],
            deliverables=DEFAULT_DELIVERABLES
        )
        assert metadata.name == "test-skill"
        assert metadata.triggers == ["test", "debug"]
        assert len(metadata.deliverables) == 1
        assert metadata.verification is None  # default
        assert metadata.category is None  # default

    def test_creates_with_all_fields(self):
        """Should create metadata with all fields including verification."""
        verification = SkillVerification(requirements="- [ ] Test")
        deliverable = SkillDeliverable(type="workspace", path=".orch/workspace")

        metadata = SkillMetadata(
            name="full-skill",
            triggers=["build", "test"],
            deliverables=[deliverable],
            verification=verification,
            category="worker"
        )
        assert metadata.name == "full-skill"
        assert metadata.triggers == ["build", "test"]
        assert len(metadata.deliverables) == 1
        assert metadata.verification is not None
        assert metadata.category == "worker"


class TestParseSkillMetadata:
    """Tests for parse_skill_metadata function."""

    def test_parses_minimal_frontmatter(self):
        """Should parse skill name from frontmatter."""
        content = """---
name: minimal-skill
triggers:
  - test
---

# Skill Content
"""
        metadata = parse_skill_metadata(content, "fallback-name")
        assert metadata.name == "minimal-skill"
        assert metadata.triggers == ["test"]
        assert len(metadata.deliverables) == 1  # DEFAULT_DELIVERABLES

    def test_uses_skill_field_over_name(self):
        """Should prefer 'skill' field over 'name' field."""
        content = """---
skill: preferred-name
name: secondary-name
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert metadata.name == "preferred-name"

    def test_uses_fallback_when_no_name(self):
        """Should use fallback name when frontmatter has no name."""
        content = """---
triggers:
  - test
---
"""
        metadata = parse_skill_metadata(content, "fallback-skill")
        assert metadata.name == "fallback-skill"

    def test_returns_defaults_when_no_frontmatter(self):
        """Should return defaults when no frontmatter exists."""
        content = "# Skill without frontmatter"
        metadata = parse_skill_metadata(content, "no-fm-skill")
        assert metadata.name == "no-fm-skill"
        assert metadata.triggers == []
        assert len(metadata.deliverables) == 1

    def test_parses_list_format_deliverables(self):
        """Should parse deliverables in list format."""
        content = """---
name: list-skill
deliverables:
  - type: workspace
    path: .orch/workspace/{name}
    required: true
    description: Workspace file
  - type: investigation
    path: .orch/investigations/{slug}.md
    required: false
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert len(metadata.deliverables) == 2
        assert metadata.deliverables[0].type == "workspace"
        assert metadata.deliverables[0].required is True
        assert metadata.deliverables[1].type == "investigation"
        assert metadata.deliverables[1].required is False

    def test_parses_dict_format_deliverables(self):
        """Should parse deliverables in dict format."""
        content = """---
name: dict-skill
deliverables:
  workspace:
    required: true
    description: Main workspace file
  investigation:
    required: false
    path: .orch/investigations/{slug}.md
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert len(metadata.deliverables) == 2
        # Find deliverables by type
        workspace = next(d for d in metadata.deliverables if d.type == "workspace")
        investigation = next(d for d in metadata.deliverables if d.type == "investigation")
        assert workspace.required is True
        assert investigation.required is False

    def test_parses_verification_requirements_as_string(self):
        """Should parse verification requirements when string."""
        content = """---
name: verified-skill
verification:
  requirements: "- [ ] Tests pass\\n- [ ] Lint clean"
  required: true
  test_command: pytest
  timeout: 120
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert metadata.verification is not None
        assert "Tests pass" in metadata.verification.requirements
        assert metadata.verification.required is True
        assert metadata.verification.test_command == "pytest"
        assert metadata.verification.timeout == 120

    def test_parses_verification_requirements_as_list(self):
        """Should convert list requirements to markdown checklist."""
        content = """---
name: list-verified-skill
verification:
  requirements:
    - Tests pass
    - Lint clean
    - No security issues
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert metadata.verification is not None
        assert "- [ ] Tests pass" in metadata.verification.requirements
        assert "- [ ] Lint clean" in metadata.verification.requirements
        assert "- [ ] No security issues" in metadata.verification.requirements

    def test_handles_invalid_yaml(self):
        """Should return defaults on invalid YAML."""
        content = """---
name: [invalid yaml
---
"""
        metadata = parse_skill_metadata(content, "fallback-skill")
        assert metadata.name == "fallback-skill"
        assert metadata.triggers == []

    def test_parses_category_from_frontmatter(self):
        """Should parse category field from frontmatter."""
        content = """---
name: categorized-skill
category: worker
---
"""
        metadata = parse_skill_metadata(content, "fallback")
        assert metadata.category == "worker"


class TestDiscoverSkills:
    """Tests for discover_skills and _discover_skills_cached functions."""

    def test_returns_empty_when_skills_dir_not_exists(self, tmp_path):
        """Should return empty dict when skills directory doesn't exist."""
        with patch.object(Path, 'home', return_value=tmp_path):
            # Clear cache before test
            _discover_skills_cached.cache_clear()

            skills = discover_skills()
            assert skills == {}

    def test_discovers_skills_from_hierarchical_structure(self, tmp_path):
        """Should discover skills from category/skill/SKILL.md structure."""
        # Create skill directory structure
        skills_dir = tmp_path / ".claude" / "skills"
        worker_dir = skills_dir / "worker" / "test-skill"
        worker_dir.mkdir(parents=True)

        skill_content = """---
name: test-skill
triggers:
  - test
---
# Test Skill
"""
        (worker_dir / "SKILL.md").write_text(skill_content)

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            assert "test-skill" in skills
            assert skills["test-skill"].name == "test-skill"
            assert skills["test-skill"].triggers == ["test"]
            assert skills["test-skill"].category == "worker"

    def test_uses_directory_category_when_frontmatter_missing(self, tmp_path):
        """Should use directory name as category when not in frontmatter."""
        skills_dir = tmp_path / ".claude" / "skills"
        orchestrator_dir = skills_dir / "orchestrator" / "spawn-worker"
        orchestrator_dir.mkdir(parents=True)

        skill_content = """---
name: spawn-worker
---
# Spawn Worker
"""
        (orchestrator_dir / "SKILL.md").write_text(skill_content)

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            assert "spawn-worker" in skills
            assert skills["spawn-worker"].category == "orchestrator"

    def test_skips_hidden_directories(self, tmp_path):
        """Should skip hidden directories starting with dot."""
        skills_dir = tmp_path / ".claude" / "skills"
        hidden_dir = skills_dir / ".hidden" / "hidden-skill"
        hidden_dir.mkdir(parents=True)
        (hidden_dir / "SKILL.md").write_text("---\nname: hidden\n---")

        visible_dir = skills_dir / "worker" / "visible-skill"
        visible_dir.mkdir(parents=True)
        (visible_dir / "SKILL.md").write_text("---\nname: visible\n---")

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            # Skills are indexed by directory name, not frontmatter name
            assert "hidden-skill" not in skills
            assert "visible-skill" in skills

    def test_handles_missing_skill_file_gracefully(self, tmp_path):
        """Should skip directories without SKILL.md."""
        skills_dir = tmp_path / ".claude" / "skills"
        no_skill_dir = skills_dir / "worker" / "no-skill-file"
        no_skill_dir.mkdir(parents=True)
        # Don't create SKILL.md

        with_skill_dir = skills_dir / "worker" / "with-skill-file"
        with_skill_dir.mkdir(parents=True)
        (with_skill_dir / "SKILL.md").write_text("---\nname: with-skill\n---")

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            # Skills are indexed by directory name
            assert "no-skill-file" not in skills
            assert "with-skill-file" in skills

    def test_handles_parse_errors_gracefully(self, tmp_path):
        """Should use defaults when skill file has parse errors."""
        skills_dir = tmp_path / ".claude" / "skills"
        bad_skill_dir = skills_dir / "worker" / "bad-skill"
        bad_skill_dir.mkdir(parents=True)

        # Create skill with invalid YAML that causes parse error
        (bad_skill_dir / "SKILL.md").write_text("---\nname: [invalid yaml\n---")

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            # Should still have the skill with defaults
            assert "bad-skill" in skills
            assert skills["bad-skill"].name == "bad-skill"
            assert skills["bad-skill"].category == "worker"

    def test_discovers_multiple_categories(self, tmp_path):
        """Should discover skills from multiple category directories."""
        skills_dir = tmp_path / ".claude" / "skills"

        # Create skills in different categories
        for category in ["worker", "orchestrator", "shared"]:
            skill_dir = skills_dir / category / f"{category}-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"---\nname: {category}-skill\n---")

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()
            skills = discover_skills()

            assert "worker-skill" in skills
            assert "orchestrator-skill" in skills
            assert "shared-skill" in skills
            assert skills["worker-skill"].category == "worker"
            assert skills["orchestrator-skill"].category == "orchestrator"
            assert skills["shared-skill"].category == "shared"

    def test_cache_returns_same_result(self, tmp_path):
        """Should return cached result on subsequent calls with same mtime."""
        skills_dir = tmp_path / ".claude" / "skills"
        worker_dir = skills_dir / "worker" / "cached-skill"
        worker_dir.mkdir(parents=True)
        (worker_dir / "SKILL.md").write_text("---\nname: cached-skill\n---")

        with patch.object(Path, 'home', return_value=tmp_path):
            _discover_skills_cached.cache_clear()

            # First call
            skills1 = discover_skills()

            # Second call should return same object (cached)
            skills2 = discover_skills()

            assert skills1 is skills2
            assert "cached-skill" in skills1


class TestDefaultDeliverables:
    """Tests for DEFAULT_DELIVERABLES constant."""

    def test_default_deliverables_has_workspace(self):
        """DEFAULT_DELIVERABLES should include workspace deliverable."""
        assert len(DEFAULT_DELIVERABLES) == 1
        assert DEFAULT_DELIVERABLES[0].type == "workspace"
        assert DEFAULT_DELIVERABLES[0].required is True
        assert ".orch/workspace" in DEFAULT_DELIVERABLES[0].path
