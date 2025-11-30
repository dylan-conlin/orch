"""Tests for orch skills command."""

import pytest
from pathlib import Path


# cli_runner fixture is now provided by conftest.py


@pytest.fixture
def mock_skills_dir(tmp_path):
    """Create a mock skills directory with sample skills."""
    skills_dir = tmp_path / "skills" / "worker"
    skills_dir.mkdir(parents=True)

    # Create a sample skill with YAML frontmatter
    investigation_skill = skills_dir / "investigation"
    investigation_skill.mkdir()

    skill_content = """---
name: investigation
audience: worker
spawnable: true
category: investigation
description: Systematic exploration of systems/components before implementation.
---

# Investigation Process

This is the skill content.
"""
    (investigation_skill / "SKILL.md").write_text(skill_content)

    # Create another skill
    debugging_skill = skills_dir / "systematic-debugging"
    debugging_skill.mkdir()

    debug_content = """---
name: systematic-debugging
audience: worker
spawnable: true
category: debugging
description: Root cause investigation for bugs and broken behavior.
---

# Systematic Debugging

Debug skill content.
"""
    (debugging_skill / "SKILL.md").write_text(debug_content)

    return skills_dir


def test_skills_command_lists_available_skills(cli_runner, mock_skills_dir, mocker):
    """Test that orch skills lists available worker skills."""
    from orch.cli import cli
    from pathlib import Path

    # Mock Path.home() to return a path that will make ~/.claude/skills/worker point to mock_skills_dir
    # If mock_skills_dir is /tmp/xyz/skills/worker, we need home to be /tmp/xyz parent
    # So that home/.claude/skills/worker = /tmp/xyz/.claude/skills/worker
    home_dir = mock_skills_dir.parent.parent.parent  # Go up from worker -> skills -> .claude -> home

    # Create the expected .claude/skills/worker structure
    actual_skills_dir = home_dir / ".claude" / "skills" / "worker"
    actual_skills_dir.mkdir(parents=True, exist_ok=True)

    # Copy our mock skills to the right location
    import shutil
    for skill_dir in mock_skills_dir.iterdir():
        if skill_dir.is_dir():
            dest = actual_skills_dir / skill_dir.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill_dir, dest)

    mocker.patch('pathlib.Path.home', return_value=home_dir)

    # Run the skills command
    result = cli_runner.invoke(cli, ['skills'])

    # Verify command succeeded
    assert result.exit_code == 0

    # Verify both skills are listed
    assert 'investigation' in result.output
    assert 'systematic-debugging' in result.output

    # Verify descriptions are shown
    assert 'Systematic exploration' in result.output
    assert 'Root cause investigation' in result.output
