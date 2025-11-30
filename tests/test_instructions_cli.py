import os
from pathlib import Path

import pytest

from orch.cli import cli


# cli_runner fixture provided by conftest.py


def _write_context_files(base: Path, with_gemini: bool = True, with_agents: bool = True) -> None:
    """Helper to create minimal .orch context files for testing."""
    orch_dir = base / ".orch"
    orch_dir.mkdir(parents=True, exist_ok=True)

    # Minimal CLAUDE.md with PROJECT-SPECIFIC marker to give insertion point
    (orch_dir / "CLAUDE.md").write_text(
        "**TLDR:** Test\n\n---\n\n<!-- PROJECT-SPECIFIC-START -->\n\n## Reference\n"
    )

    if with_gemini:
        (orch_dir / "GEMINI.md").write_text(
            "**TLDR:** Gemini\n\n---\n\n<!-- PROJECT-SPECIFIC-START -->\n\n## Reference\n"
        )

    if with_agents:
        (orch_dir / "AGENTS.md").write_text(
            "**TLDR:** Agents\n\n---\n\n<!-- PROJECT-SPECIFIC-START -->\n\n## Reference\n"
        )


def _setup_templates(tmp_path: Path) -> Path:
    """Create a fake orchestrator template directory with a single template."""
    home = tmp_path
    templates_dir = home / ".orch" / "templates" / "orchestrator"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "test-instruction.md").write_text("# Test instruction\n\nBody")
    return home


@pytest.fixture
def mock_home(monkeypatch, tmp_path):
    """Patch Path.home() to point at a temporary directory with templates."""
    home = _setup_templates(tmp_path)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return home


@pytest.fixture
def mock_build(monkeypatch):
    """Monkeypatch subprocess.run used by _run_build_orchestrator_context_for_project."""
    import subprocess as real_subprocess

    class Result:
        def __init__(self):
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def fake_run(*args, **kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    return real_subprocess


def test_add_instruction_single_and_remove(tmp_path, mock_home, mock_build, monkeypatch, cli_runner):
    """add-instruction NAME adds markers to all context files and remove-instruction removes them."""
    project = tmp_path / "project"
    project.mkdir()
    _write_context_files(project)

    # Point cwd at project for CLI
    monkeypatch.chdir(project)

    # Add a single instruction
    result = cli_runner.invoke(cli, ["add-instruction", "test-instruction"])
    assert result.exit_code == 0

    claude = (project / ".orch" / "CLAUDE.md").read_text()
    gemini = (project / ".orch" / "GEMINI.md").read_text()
    agents = (project / ".orch" / "AGENTS.md").read_text()

    # Markers should appear in all three context files
    for content in (claude, gemini, agents):
        assert "<!-- ORCH-INSTRUCTION: test-instruction -->" in content
        assert "<!-- /ORCH-INSTRUCTION -->" in content

    # Now remove the instruction
    result = cli_runner.invoke(cli, ["remove-instruction", "test-instruction"])
    assert result.exit_code == 0

    claude_after = (project / ".orch" / "CLAUDE.md").read_text()
    gemini_after = (project / ".orch" / "GEMINI.md").read_text()
    agents_after = (project / ".orch" / "AGENTS.md").read_text()

    for content in (claude_after, gemini_after, agents_after):
        assert "test-instruction" not in content


def test_add_instruction_all_missing_and_upgrade(tmp_path, mock_home, mock_build, monkeypatch, cli_runner):
    """add-instruction --all-missing and upgrade-instructions both add missing markers, with upgrade migrating markers."""
    project = tmp_path / "project"
    project.mkdir()
    _write_context_files(project, with_gemini=True, with_agents=True)

    # Seed CLAUDE.md with an old ORCH-TEMPLATE marker to test migration
    claude_path = project / ".orch" / "CLAUDE.md"
    original = claude_path.read_text()
    claude_path.write_text(
        original
        + "\n<!-- ORCH-TEMPLATE: legacy-instruction -->\nBody\n<!-- /ORCH-TEMPLATE -->\n"
    )

    monkeypatch.chdir(project)

    # First, add all missing instructions (should add test-instruction)
    result = cli_runner.invoke(cli, ["add-instruction", "--all-missing"])
    assert result.exit_code == 0

    claude = claude_path.read_text()
    assert "test-instruction" in claude

    # Then run upgrade-instructions, which should migrate ORCH-TEMPLATE to ORCH-INSTRUCTION
    result = cli_runner.invoke(cli, ["upgrade-instructions"])
    assert result.exit_code == 0

    upgraded = claude_path.read_text()
    assert "<!-- ORCH-INSTRUCTION: legacy-instruction -->" in upgraded
    assert "<!-- /ORCH-INSTRUCTION -->" in upgraded
    assert "ORCH-TEMPLATE: legacy-instruction" not in upgraded
