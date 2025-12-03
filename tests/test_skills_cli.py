"""Tests for the skills CLI tool.

This tests the separate 'skills' command (not 'orch skills').
Entry point: skills -> orch.skills_cli:cli
"""

import pytest
from pathlib import Path
from click.testing import CliRunner


@pytest.fixture
def skills_cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_skills_source(tmp_path):
    """Create a mock skills source directory (like orch-knowledge/skills/src/)."""
    skills_src = tmp_path / "skills" / "src"

    # Create worker/feature-impl with template structure
    feature_impl = skills_src / "worker" / "feature-impl"
    feature_impl.mkdir(parents=True)

    # Create src/ subdirectory for templated skill
    src_dir = feature_impl / "src"
    src_dir.mkdir()

    # Template file
    (src_dir / "SKILL.md.template").write_text("""---
name: feature-impl
audience: worker
spawnable: true
description: Feature implementation skill
---

# Feature Implementation

<!-- SKILL-TEMPLATE: planning -->
<!-- /SKILL-TEMPLATE -->

## Implementation

This is static content.
""")

    # Phase files
    phases_dir = src_dir / "phases"
    phases_dir.mkdir()

    (phases_dir / "planning.md").write_text("""# Planning Phase

1. Analyze requirements
2. Design approach
3. Plan implementation
""")

    # Create a non-templated skill (shared/session-transition)
    session_skill = skills_src / "shared" / "session-transition"
    session_skill.mkdir(parents=True)

    (session_skill / "SKILL.md").write_text("""---
name: session-transition
audience: shared
spawnable: false
description: Handle session transitions
---

# Session Transition

Simple skill without template.
""")

    return tmp_path


@pytest.fixture
def mock_deployed_skills(tmp_path):
    """Create a mock deployed skills directory (~/.claude/skills/)."""
    skills_dir = tmp_path / ".claude" / "skills"

    # Create worker category
    worker_dir = skills_dir / "worker"
    worker_dir.mkdir(parents=True)

    # Create investigation skill
    investigation = worker_dir / "investigation"
    investigation.mkdir()
    (investigation / "SKILL.md").write_text("""---
name: investigation
audience: worker
spawnable: true
description: Systematic exploration of systems/components.
---

# Investigation

Explore the codebase.
""")

    # Create feature-impl skill
    feature_impl = worker_dir / "feature-impl"
    feature_impl.mkdir()
    (feature_impl / "SKILL.md").write_text("""---
name: feature-impl
audience: worker
spawnable: true
description: Feature implementation with TDD.
---

# Feature Implementation

Build features.
""")

    # Create shared category
    shared_dir = skills_dir / "shared"
    shared_dir.mkdir()

    session = shared_dir / "session-transition"
    session.mkdir()
    (session / "SKILL.md").write_text("""---
name: session-transition
audience: shared
spawnable: false
description: Handle session transitions.
---

# Session Transition

Manage sessions.
""")

    # Create symlinks at top level (Claude Code discovery)
    (skills_dir / "investigation").symlink_to("worker/investigation")
    (skills_dir / "feature-impl").symlink_to("worker/feature-impl")
    (skills_dir / "session-transition").symlink_to("shared/session-transition")

    return tmp_path


class TestSkillsList:
    """Tests for 'skills list' command."""

    def test_skills_list_shows_available_skills(self, skills_cli_runner, mock_deployed_skills, mocker):
        """Test that skills list shows deployed skills."""
        from orch.skills_cli import cli

        # Mock Path.home() to use our mock directory
        mocker.patch('pathlib.Path.home', return_value=mock_deployed_skills)

        result = skills_cli_runner.invoke(cli, ['list'])

        assert result.exit_code == 0
        assert 'investigation' in result.output
        assert 'feature-impl' in result.output
        assert 'session-transition' in result.output

    def test_skills_list_shows_descriptions(self, skills_cli_runner, mock_deployed_skills, mocker):
        """Test that skills list shows skill descriptions."""
        from orch.skills_cli import cli

        mocker.patch('pathlib.Path.home', return_value=mock_deployed_skills)

        result = skills_cli_runner.invoke(cli, ['list'])

        assert result.exit_code == 0
        assert 'Systematic exploration' in result.output
        assert 'Feature implementation' in result.output

    def test_skills_list_shows_categories(self, skills_cli_runner, mock_deployed_skills, mocker):
        """Test that skills list shows skill categories."""
        from orch.skills_cli import cli

        mocker.patch('pathlib.Path.home', return_value=mock_deployed_skills)

        result = skills_cli_runner.invoke(cli, ['list'])

        assert result.exit_code == 0
        assert 'worker' in result.output
        assert 'shared' in result.output

    def test_skills_list_filter_by_category(self, skills_cli_runner, mock_deployed_skills, mocker):
        """Test filtering skills by category."""
        from orch.skills_cli import cli

        mocker.patch('pathlib.Path.home', return_value=mock_deployed_skills)

        result = skills_cli_runner.invoke(cli, ['list', '--category', 'worker'])

        assert result.exit_code == 0
        assert 'investigation' in result.output
        assert 'feature-impl' in result.output
        # shared skills should not appear
        assert 'session-transition' not in result.output


class TestSkillsBuild:
    """Tests for 'skills build' command."""

    def test_skills_build_compiles_templates(self, skills_cli_runner, mock_skills_source, mocker):
        """Test that skills build compiles SKILL.md from templates."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, ['build', '--source', str(mock_skills_source / 'skills' / 'src')])

        assert result.exit_code == 0

        # Check SKILL.md was created from template
        skill_md = mock_skills_source / 'skills' / 'src' / 'worker' / 'feature-impl' / 'SKILL.md'
        assert skill_md.exists()

        content = skill_md.read_text()
        # Template should be expanded
        assert 'Planning Phase' in content
        assert 'Analyze requirements' in content
        # Auto-generated header should be added
        assert 'AUTO-GENERATED' in content

    def test_skills_build_dry_run(self, skills_cli_runner, mock_skills_source, mocker):
        """Test that --dry-run shows what would be built without changes."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, ['build', '--source', str(mock_skills_source / 'skills' / 'src'), '--dry-run'])

        assert result.exit_code == 0
        assert 'Would' in result.output or 'would' in result.output

        # SKILL.md should NOT be created
        skill_md = mock_skills_source / 'skills' / 'src' / 'worker' / 'feature-impl' / 'SKILL.md'
        assert not skill_md.exists()

    def test_skills_build_check_mode(self, skills_cli_runner, mock_skills_source, mocker):
        """Test that --check reports if rebuild needed."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, ['build', '--source', str(mock_skills_source / 'skills' / 'src'), '--check'])

        assert result.exit_code == 0
        assert 'Needs rebuild' in result.output or 'needs rebuild' in result.output


class TestSkillsDeploy:
    """Tests for 'skills deploy' command."""

    def test_skills_deploy_copies_to_target(self, skills_cli_runner, mock_skills_source, tmp_path, mocker):
        """Test that skills deploy copies skills to ~/.claude/skills/."""
        from orch.skills_cli import cli

        # First build the skills
        skills_src = mock_skills_source / 'skills' / 'src'

        # Create a simple non-templated skill for deploy test
        test_skill = skills_src / 'worker' / 'test-skill'
        test_skill.mkdir(parents=True)
        (test_skill / 'SKILL.md').write_text("""---
name: test-skill
description: Test skill
---
# Test
""")

        target_dir = tmp_path / 'deploy-target'
        target_dir.mkdir()

        result = skills_cli_runner.invoke(cli, [
            'deploy',
            '--source', str(skills_src),
            '--target', str(target_dir)
        ])

        assert result.exit_code == 0

        # Check skill was deployed
        deployed = target_dir / 'worker' / 'test-skill' / 'SKILL.md'
        assert deployed.exists()

    def test_skills_deploy_creates_symlinks(self, skills_cli_runner, mock_skills_source, tmp_path, mocker):
        """Test that skills deploy creates discovery symlinks."""
        from orch.skills_cli import cli

        skills_src = mock_skills_source / 'skills' / 'src'

        # Create test skill
        test_skill = skills_src / 'worker' / 'my-skill'
        test_skill.mkdir(parents=True)
        (test_skill / 'SKILL.md').write_text("""---
name: my-skill
description: My skill
---
# My Skill
""")

        target_dir = tmp_path / 'deploy-target'
        target_dir.mkdir()

        result = skills_cli_runner.invoke(cli, [
            'deploy',
            '--source', str(skills_src),
            '--target', str(target_dir)
        ])

        assert result.exit_code == 0

        # Check symlink was created at top level
        symlink = target_dir / 'my-skill'
        assert symlink.exists()
        assert symlink.is_symlink()


class TestSkillsNew:
    """Tests for 'skills new' command."""

    def test_skills_new_scaffolds_skill(self, skills_cli_runner, tmp_path):
        """Test that skills new creates a new skill directory."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, [
            'new', 'worker/my-new-skill',
            '--output', str(tmp_path)
        ])

        assert result.exit_code == 0

        # Check directory structure was created
        skill_dir = tmp_path / 'worker' / 'my-new-skill'
        assert skill_dir.exists()
        assert (skill_dir / 'SKILL.md').exists()

    def test_skills_new_with_template_flag(self, skills_cli_runner, tmp_path):
        """Test that --template creates src/ subdirectory."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, [
            'new', 'worker/complex-skill',
            '--output', str(tmp_path),
            '--template'
        ])

        assert result.exit_code == 0

        skill_dir = tmp_path / 'worker' / 'complex-skill'
        assert skill_dir.exists()

        # Should have src/ subdirectory with template
        src_dir = skill_dir / 'src'
        assert src_dir.exists()
        assert (src_dir / 'SKILL.md.template').exists()
        assert (src_dir / 'phases').exists()

    def test_skills_new_refuses_invalid_path(self, skills_cli_runner, tmp_path):
        """Test that skills new rejects invalid category/name format."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, [
            'new', 'invalid-path',  # Missing category
            '--output', str(tmp_path)
        ])

        assert result.exit_code != 0
        assert 'category/name' in result.output.lower() or 'format' in result.output.lower()


class TestSkillsVersion:
    """Tests for 'skills --version' command."""

    def test_skills_version(self, skills_cli_runner):
        """Test that --version shows version info."""
        from orch.skills_cli import cli

        result = skills_cli_runner.invoke(cli, ['--version'])

        assert result.exit_code == 0
        # Should show some version information
        assert 'skills' in result.output.lower() or '0.' in result.output
