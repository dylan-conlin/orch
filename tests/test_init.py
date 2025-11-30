"""Tests for init.py - Project orchestration bootstrap."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from click.testing import CliRunner

from orch import init


@pytest.fixture
def project_dir(tmp_path):
    """Create temporary project directory."""
    return tmp_path / "test-project"


@pytest.fixture
def template_dir(tmp_path):
    """Create temporary templates directory with sample templates."""
    templates = tmp_path / "templates"
    templates.mkdir()

    # Create sample templates
    (templates / "orch-CLAUDE.md.template").write_text(
        "# {{PROJECT_NAME}}\n{{PROJECT_PURPOSE}}\nDate: {{DATE}}"
    )
    (templates / "project-CLAUDE.md.template").write_text(
        "# {{PROJECT_NAME}} - Worker Context\n\n## Foundation\n@.orch/CLAUDE.md"
    )
    (templates / "coordination-workspace.md.template").write_text(
        "---\nProject: {{PROJECT_NAME}}\nCreated: {{DATE}}\n---\n"
    )

    return templates


def test_get_template_path():
    """Test get_template_path() returns correct path."""
    template_path = init.get_template_path()

    assert isinstance(template_path, Path)
    assert template_path.name == "templates"
    # Should be sibling to tools/
    assert "templates" in str(template_path)


def test_read_template(template_dir):
    """Test read_template() reads template file."""
    with patch.object(init, 'get_template_path', return_value=template_dir):
        content = init.read_template("orch-CLAUDE.md.template")

        assert "{{PROJECT_NAME}}" in content
        assert "{{PROJECT_PURPOSE}}" in content


def test_read_template_not_found(template_dir):
    """Test read_template() raises error for missing template."""
    with patch.object(init, 'get_template_path', return_value=template_dir):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            init.read_template("nonexistent.template")


def test_substitute_variables():
    """Test substitute_variables() replaces placeholders."""
    content = "Project: {{PROJECT_NAME}}, Purpose: {{PROJECT_PURPOSE}}"
    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Testing substitution"
    }

    result = init.substitute_variables(content, variables)

    assert "Test Project" in result
    assert "Testing substitution" in result
    assert "{{" not in result  # No placeholders left


def test_substitute_variables_partial():
    """Test substitute_variables() handles partial substitution."""
    content = "{{VAR1}} and {{VAR2}} and {{VAR3}}"
    variables = {
        "VAR1": "First",
        "VAR2": "Second"
    }

    result = init.substitute_variables(content, variables)

    assert "First" in result
    assert "Second" in result
    assert "{{VAR3}}" in result  # Unmatched variable remains


def test_prompt_for_project_info(project_dir):
    """Test prompt_for_project_info() collects user input."""
    project_dir.mkdir(parents=True)

    with patch('click.prompt') as mock_prompt:
        mock_prompt.side_effect = ["My Project", "Testing project info"]

        variables = init.prompt_for_project_info(project_dir)

        assert variables["PROJECT_NAME"] == "My Project"
        assert variables["PROJECT_PURPOSE"] == "Testing project info"
        assert "DATE" in variables
        assert len(variables["DATE"]) == 10  # YYYY-MM-DD format


def test_create_orch_directory_structure(project_dir):
    """Test create_orch_directory_structure() creates directories."""
    project_dir.mkdir(parents=True)

    init.create_orch_directory_structure(project_dir)

    orch_dir = project_dir / ".orch"
    assert orch_dir.exists()
    assert (orch_dir / "workspace").exists()


def test_create_orch_claude_md(project_dir, template_dir):
    """Test create_orch_claude_md() creates CLAUDE.md from template."""
    project_dir.mkdir(parents=True)
    (project_dir / ".orch").mkdir()

    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Test purpose",
        "DATE": "2025-11-16"
    }

    # No need to mock template path - use the real implementation
    init.create_orch_claude_md(project_dir, variables)

    orch_claude = project_dir / ".orch" / "CLAUDE.md"
    assert orch_claude.exists()

    content = orch_claude.read_text()
    assert "Test Project" in content
    assert "Test purpose" in content
    # The template no longer uses DATE variable in CLAUDE.md


def test_create_project_claude_md_new(project_dir, template_dir):
    """Test create_project_claude_md() creates new file from template."""
    project_dir.mkdir(parents=True)

    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Test purpose",
        "DATE": "2025-11-16"
    }

    with patch.object(init, 'get_template_path', return_value=template_dir):
        init.create_project_claude_md(project_dir, variables, yes=True)

    project_claude = project_dir / "CLAUDE.md"
    assert project_claude.exists()

    content = project_claude.read_text()
    assert "Test Project" in content
    assert "@.orch/CLAUDE.md" in content


def test_create_project_claude_md_update_existing(project_dir):
    """Test create_project_claude_md() updates existing file."""
    project_dir.mkdir(parents=True)
    project_claude = project_dir / "CLAUDE.md"
    project_claude.write_text("# Existing Content\n\nSome documentation here.")

    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Test purpose",
        "DATE": "2025-11-16"
    }

    init.create_project_claude_md(project_dir, variables, yes=True)

    content = project_claude.read_text()
    assert "@.orch/CLAUDE.md" in content
    assert "Existing Content" in content  # Original content preserved


def test_create_project_claude_md_skip_if_imported(project_dir):
    """Test create_project_claude_md() skips if already importing."""
    project_dir.mkdir(parents=True)
    project_claude = project_dir / "CLAUDE.md"
    project_claude.write_text("# Test\n@.orch/CLAUDE.md\nContent")

    variables = {"PROJECT_NAME": "Test", "PROJECT_PURPOSE": "Test", "DATE": "2025-11-16"}

    init.create_project_claude_md(project_dir, variables, yes=True)

    # Should not modify file
    content = project_claude.read_text()
    assert content.count("@.orch/CLAUDE.md") == 1


@pytest.mark.skip(reason="create_coordination_journal function was removed - coordination workspaces are now created on-demand")
def test_create_coordination_journal(project_dir, template_dir):
    """Test create_coordination_journal() creates workspace from template."""
    project_dir.mkdir(parents=True)
    (project_dir / ".orch" / "workspace" / "coordination").mkdir(parents=True)

    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Test purpose",
        "DATE": "2025-11-16"
    }

    with patch.object(init, 'get_template_path', return_value=template_dir):
        init.create_coordination_journal(project_dir, variables)

    journal = project_dir / ".orch" / "workspace" / "coordination" / "WORKSPACE.md"
    assert journal.exists()

    content = journal.read_text()
    assert "Test Project" in content
    assert "2025-11-16" in content


def test_add_gitignore_entries_solo_project(project_dir):
    """Test add_gitignore_entries() for solo project (ignore entire .orch/)."""
    project_dir.mkdir(parents=True)

    init.add_gitignore_entries(project_dir, team_project=False)

    gitignore = project_dir / ".gitignore"
    assert gitignore.exists()

    content = gitignore.read_text()
    assert ".orch/" in content
    assert "solo project" in content.lower()


def test_add_gitignore_entries_team_project(project_dir):
    """Test add_gitignore_entries() for team project (ignore only state)."""
    project_dir.mkdir(parents=True)

    init.add_gitignore_entries(project_dir, team_project=True)

    gitignore = project_dir / ".gitignore"
    assert gitignore.exists()

    content = gitignore.read_text()
    assert ".orch/workspace/" in content
    # active-agents.md and agents/ are no longer created
    assert "orchestration state" in content.lower() or "team" in content.lower()


def test_add_gitignore_entries_existing_file(project_dir):
    """Test add_gitignore_entries() appends to existing .gitignore."""
    project_dir.mkdir(parents=True)
    gitignore = project_dir / ".gitignore"
    gitignore.write_text("# Existing entries\n*.pyc\n__pycache__/\n")

    init.add_gitignore_entries(project_dir, team_project=False)

    content = gitignore.read_text()
    assert "*.pyc" in content  # Original content preserved
    assert ".orch/" in content  # New entry added


def test_add_gitignore_entries_skip_if_exists(project_dir):
    """Test add_gitignore_entries() skips if .orch already mentioned."""
    project_dir.mkdir(parents=True)
    gitignore = project_dir / ".gitignore"
    gitignore.write_text("# Existing\n.orch/\n")

    original_content = gitignore.read_text()
    init.add_gitignore_entries(project_dir, team_project=False)

    # Should not modify file
    assert gitignore.read_text() == original_content


def test_setup_sessionstart_hook_creates_script():
    """Test setup_sessionstart_hook() creates hook script."""
    fake_home = Path("/fake/home")

    with patch('pathlib.Path.home', return_value=fake_home), \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.write_text') as mock_write, \
         patch('pathlib.Path.chmod') as mock_chmod:

        # Mock exists() to return False for hook script, True for settings
        hook_script_path = fake_home / ".claude" / "hooks" / "inject-orch-patterns.sh"
        settings_path = fake_home / ".claude" / "settings.json"

        original_exists = Path.exists

        def mock_exists(self):
            if self == hook_script_path:
                return False  # Hook script doesn't exist
            elif self == settings_path:
                return True   # Settings file exists
            return original_exists(self)

        with patch.object(Path, 'exists', mock_exists), \
             patch.object(Path, 'read_text', return_value='{"hooks": {"SessionStart": []}}'):

            init.setup_sessionstart_hook()

            # Should create executable script
            assert mock_write.called
            assert mock_chmod.called


def test_init_project_orchestration_full(project_dir, template_dir):
    """Test init_project_orchestration() full workflow."""
    project_dir.mkdir(parents=True)

    variables = {
        "PROJECT_NAME": "Test Project",
        "PROJECT_PURPOSE": "Full integration test",
        "DATE": "2025-11-16"
    }

    with patch.object(init, 'setup_sessionstart_hook'):

        result = init.init_project_orchestration(
            project_path=str(project_dir),
            project_name="Test Project",
            project_purpose="Full integration test",
            yes=True
        )

    assert result is True

    # Verify directory structure
    orch_dir = project_dir / ".orch"
    assert orch_dir.exists()
    assert (orch_dir / "CLAUDE.md").exists()
    assert (orch_dir / "workspace").exists()
    # Note: coordination workspace and agents directory are no longer created by init

    # Verify project CLAUDE.md
    assert (project_dir / "CLAUDE.md").exists()

    # Verify .gitignore
    assert (project_dir / ".gitignore").exists()


def test_init_project_orchestration_nonexistent_directory():
    """Test init_project_orchestration() fails for nonexistent directory."""
    result = init.init_project_orchestration(
        project_path="/nonexistent/path",
        yes=True
    )

    assert result is False


def test_init_project_orchestration_already_initialized(project_dir):
    """Test init_project_orchestration() handles already initialized project."""
    project_dir.mkdir(parents=True)
    orch_dir = project_dir / ".orch"
    orch_dir.mkdir()
    (orch_dir / "CLAUDE.md").write_text("# Existing")

    with patch('click.confirm', return_value=False):
        result = init.init_project_orchestration(
            project_path=str(project_dir),
            yes=False
        )

    assert result is False


def test_init_project_orchestration_team_mode(project_dir, template_dir):
    """Test init_project_orchestration() in team mode."""
    project_dir.mkdir(parents=True)

    with patch.object(init, 'setup_sessionstart_hook'):

        result = init.init_project_orchestration(
            project_path=str(project_dir),
            project_name="Team Project",
            project_purpose="Team collaboration test",
            team=True,
            yes=True
        )

    assert result is True

    # Verify .gitignore uses team mode (only ignores state)
    gitignore = project_dir / ".gitignore"
    content = gitignore.read_text()
    assert ".orch/workspace/" in content
    # active-agents.md is no longer created
    # Should NOT ignore entire .orch/
    lines = content.split('\n')
    assert ".orch/" not in [line.strip() for line in lines if not line.startswith('#')]
