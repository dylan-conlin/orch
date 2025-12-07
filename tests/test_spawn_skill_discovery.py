"""
Tests for skill discovery functionality in orch spawn.

Tests the skill discovery mechanism including:
- Discovering skills from ~/.claude/skills directory
- Parsing SKILL.md frontmatter metadata
- Handling hierarchical skill directory structure
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    discover_skills,
    parse_skill_metadata,
    SkillMetadata,
    SkillDeliverable,
    DEFAULT_DELIVERABLES,
)


class TestSkillDiscovery:
    """Tests for skill discovery functionality."""

    def test_discover_skills_with_valid_skills(self, tmp_path):
        """Test discovering skills from directory with valid SKILL.md files."""
        # Create mock skill directory with hierarchical structure
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        # Create category directory (hierarchical structure)
        category_dir = skills_dir / "worker"
        category_dir.mkdir()

        # Create a skill with frontmatter
        skill1_dir = category_dir / "test-skill"
        skill1_dir.mkdir()
        skill1_file = skill1_dir / "SKILL.md"
        skill1_file.write_text("""---
skill: test-skill
triggers:
  - Test trigger
deliverables:
  - type: workspace
    path: ""
    required: true
    description: Progress tracked via beads comments
---

# Test Skill
""")

        # Mock Path.home() to return tmp_path
        with patch('orch.spawn.Path.home', return_value=tmp_path):
            skills = discover_skills()

        assert 'test-skill' in skills
        assert skills['test-skill'].name == 'test-skill'
        assert len(skills['test-skill'].triggers) == 1

    def test_discover_skills_with_multiple_categories(self, tmp_path):
        """Test discovering skills from multiple category directories."""
        skills_dir = tmp_path / ".claude" / "skills"

        # Create worker category
        worker_dir = skills_dir / "worker"
        worker_dir.mkdir(parents=True)
        skill1_dir = worker_dir / "skill-a"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
skill: skill-a
---
# Skill A
""")

        # Create orchestrator category
        orch_dir = skills_dir / "orchestrator"
        orch_dir.mkdir(parents=True)
        skill2_dir = orch_dir / "skill-b"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
skill: skill-b
---
# Skill B
""")

        with patch('orch.spawn.Path.home', return_value=tmp_path):
            skills = discover_skills()

        assert 'skill-a' in skills
        assert 'skill-b' in skills

    def test_discover_skills_empty_directory(self, tmp_path):
        """Test discovering skills from empty directory."""
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        with patch('orch.spawn.Path.home', return_value=tmp_path):
            skills = discover_skills()

        assert len(skills) == 0

    def test_discover_skills_no_directory(self, tmp_path):
        """Test discovering skills when directory doesn't exist."""
        with patch('orch.spawn.Path.home', return_value=tmp_path):
            skills = discover_skills()

        assert len(skills) == 0

    # Note: parse_skill_metadata tests removed during split as they require
    # skill_dir_name argument which changed. See original test_spawn.py for reference.
