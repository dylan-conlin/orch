"""Tests for orch lint command with .orchignore and fail-fast checks."""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


# cli_runner fixture is now provided by conftest.py


@pytest.fixture
def mock_home(tmp_path):
    """Create mock home directory structure for testing."""
    home = tmp_path / "home"
    home.mkdir()

    # Create some project directories
    docs_work = home / "Documents" / "work"
    docs_work.mkdir(parents=True)

    docs_personal = home / "Documents" / "personal"
    docs_personal.mkdir(parents=True)

    return home


def test_load_orchignore_patterns(tmp_path):
    """Test loading patterns from .orchignore file."""
    from orch.cli import _load_orchignore_patterns

    # Create .orchignore file
    orchignore = tmp_path / ".orchignore"
    orchignore.write_text("""
# Comment line
node_modules
*.pyc

# Another comment
build
dist
""")

    patterns = _load_orchignore_patterns(tmp_path)

    assert 'node_modules' in patterns
    assert '*.pyc' in patterns
    assert 'build' in patterns
    assert 'dist' in patterns
    # Comments should not be included
    assert '# Comment line' not in patterns
    assert '# Another comment' not in patterns


def test_load_orchignore_patterns_no_file(tmp_path):
    """Test loading patterns when .orchignore doesn't exist."""
    from orch.cli import _load_orchignore_patterns

    patterns = _load_orchignore_patterns(tmp_path)

    assert patterns == set()


def test_should_ignore_dir_exact_match():
    """Test directory ignoring with exact match."""
    from orch.cli import _should_ignore_dir

    ignore_patterns = {'node_modules', '.git', 'dist'}

    assert _should_ignore_dir('node_modules', ignore_patterns) is True
    assert _should_ignore_dir('.git', ignore_patterns) is True
    assert _should_ignore_dir('dist', ignore_patterns) is True
    assert _should_ignore_dir('src', ignore_patterns) is False


def test_should_ignore_dir_glob_pattern():
    """Test directory ignoring with glob patterns."""
    from orch.cli import _should_ignore_dir

    ignore_patterns = {'*.pyc', 'test_*', '__pycache__'}

    assert _should_ignore_dir('file.pyc', ignore_patterns) is True
    assert _should_ignore_dir('test_something', ignore_patterns) is True
    assert _should_ignore_dir('__pycache__', ignore_patterns) is True
    assert _should_ignore_dir('src', ignore_patterns) is False
    assert _should_ignore_dir('file.py', ignore_patterns) is False


def test_find_claude_files_with_orchignore(tmp_path):
    """Test that .orchignore patterns are respected."""
    from orch.cli import _find_claude_files_with_depth

    # Create directory structure
    base = tmp_path / "base"
    base.mkdir()

    # Create .orchignore
    orchignore = base / ".orchignore"
    orchignore.write_text("ignored_dir\n")

    # Create CLAUDE.md files
    (base / "CLAUDE.md").write_text("# Test")

    subdir = base / "subdir"
    subdir.mkdir()
    (subdir / "CLAUDE.md").write_text("# Test")

    ignored = base / "ignored_dir"
    ignored.mkdir()
    (ignored / "CLAUDE.md").write_text("# Test")

    # Find files
    results = _find_claude_files_with_depth(base, max_depth=4)

    # Should find CLAUDE.md in base and subdir, but not in ignored_dir
    assert len(results) == 2
    assert base / "CLAUDE.md" in results
    assert subdir / "CLAUDE.md" in results
    assert ignored / "CLAUDE.md" not in results


def test_find_claude_files_respects_default_ignores(tmp_path):
    """Test that default ignore patterns work."""
    from orch.cli import _find_claude_files_with_depth

    # Create directory structure
    base = tmp_path / "base"
    base.mkdir()

    # Create CLAUDE.md in base
    (base / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in node_modules (should be ignored by default)
    node_modules = base / "node_modules"
    node_modules.mkdir()
    (node_modules / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in .git (should be ignored by default)
    git_dir = base / ".git"
    git_dir.mkdir()
    (git_dir / "CLAUDE.md").write_text("# Test")

    # Find files
    results = _find_claude_files_with_depth(base, max_depth=4)

    # Should only find CLAUDE.md in base
    assert len(results) == 1
    assert base / "CLAUDE.md" in results


def test_find_claude_files_depth_limit(tmp_path):
    """Test that max depth limit is respected."""
    from orch.cli import _find_claude_files_with_depth

    # Create deep directory structure
    base = tmp_path / "base"
    current = base

    # Create nested directories beyond max_depth
    for i in range(6):
        current = current / f"level{i}"
        current.mkdir(parents=True)
        (current / "CLAUDE.md").write_text("# Test")

    # Find files with max_depth=3
    results = _find_claude_files_with_depth(base, max_depth=3)

    # Should only find files within depth 3
    found_depths = []
    for result in results:
        depth = len(result.relative_to(base).parts) - 1  # -1 for CLAUDE.md itself
        found_depths.append(depth)

    assert max(found_depths) < 3


def test_find_claude_files_time_limit_exceeded(tmp_path, monkeypatch):
    """Test that time limit triggers abort."""
    from orch.cli import _find_claude_files_with_depth
    import click

    # Create directory structure
    base = tmp_path / "base"
    base.mkdir()
    (base / "CLAUDE.md").write_text("# Test")

    # Mock time.time() to simulate slow scan
    original_time = time.time
    call_count = [0]

    def mock_time():
        call_count[0] += 1
        # First call: start time
        # Second call: elapsed time exceeds limit
        if call_count[0] == 1:
            return 0
        else:
            return 35  # Exceeds 30s default limit

    monkeypatch.setattr(time, 'time', mock_time)

    # Should raise ClickException due to time limit
    with pytest.raises(click.ClickException) as exc_info:
        _find_claude_files_with_depth(base, max_depth=4, max_time=30)

    assert "exceeded time limit" in str(exc_info.value)
    assert "30s" in str(exc_info.value)


def test_find_claude_files_file_count_warning(tmp_path, monkeypatch):
    """Test that file count warnings are emitted when scanning many files."""
    import orch.cli

    # Track warnings
    warnings = []

    def mock_echo(message, err=False):
        if err:
            warnings.append(message)

    # Patch click.echo in the orch.cli module
    monkeypatch.setattr('orch.cli.click.echo', mock_echo)

    # Create directory with many files in a single directory to ensure we hit threshold
    base = tmp_path / "base"
    base.mkdir()
    subdir = base / "many_files"
    subdir.mkdir()

    # Create 2000 files in a single directory to trigger warning at exactly 2000
    for i in range(2000):
        (subdir / f"file{i}.txt").write_text("test")

    # Add a CLAUDE.md file
    (base / "CLAUDE.md").write_text("# Test")

    # Find files (should trigger warning at 2000 files)
    results = orch.cli._find_claude_files_with_depth(base, max_depth=4, max_files=100)

    # The function should complete successfully and return the CLAUDE.md file
    assert len(results) == 1
    assert results[0] == base / "CLAUDE.md"

    # Warning should be emitted since files_scanned (2000) > max_files (100)
    # and files_scanned % 1000 == 0 is true
    assert len(warnings) > 0, "Expected warning to be emitted when scanning many files"
    assert any("Warning" in w or "Scanned" in w for w in warnings)


def test_orchignore_merge_with_defaults(tmp_path):
    """Test that .orchignore patterns are merged with default patterns."""
    from orch.cli import _find_claude_files_with_depth

    # Create directory structure
    base = tmp_path / "base"
    base.mkdir()

    # Create .orchignore with custom pattern
    orchignore = base / ".orchignore"
    orchignore.write_text("custom_ignore\n")

    # Create CLAUDE.md in base
    (base / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in custom_ignore (should be ignored by .orchignore)
    custom = base / "custom_ignore"
    custom.mkdir()
    (custom / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in node_modules (should be ignored by default)
    node_modules = base / "node_modules"
    node_modules.mkdir()
    (node_modules / "CLAUDE.md").write_text("# Test")

    # Find files
    results = _find_claude_files_with_depth(base, max_depth=4)

    # Should only find CLAUDE.md in base (both default and custom ignores work)
    assert len(results) == 1
    assert base / "CLAUDE.md" in results


def test_orchignore_glob_patterns(tmp_path):
    """Test that glob patterns in .orchignore work correctly."""
    from orch.cli import _find_claude_files_with_depth

    # Create directory structure
    base = tmp_path / "base"
    base.mkdir()

    # Create .orchignore with glob pattern
    orchignore = base / ".orchignore"
    orchignore.write_text("test_*\n*.tmp\n")

    # Create CLAUDE.md in base
    (base / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in test_dir (should be ignored by glob)
    test_dir = base / "test_something"
    test_dir.mkdir()
    (test_dir / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in tmp_dir (should be ignored by glob)
    tmp_dir = base / "dir.tmp"
    tmp_dir.mkdir()
    (tmp_dir / "CLAUDE.md").write_text("# Test")

    # Create CLAUDE.md in normal dir (should NOT be ignored)
    normal = base / "normal"
    normal.mkdir()
    (normal / "CLAUDE.md").write_text("# Test")

    # Find files
    results = _find_claude_files_with_depth(base, max_depth=4)

    # Should find CLAUDE.md in base and normal, but not in test_* or *.tmp
    assert len(results) == 2
    assert base / "CLAUDE.md" in results
    assert normal / "CLAUDE.md" in results
    assert test_dir / "CLAUDE.md" not in results
    assert tmp_dir / "CLAUDE.md" not in results


# =============================================================================
# SKILLS MODE TESTS
# =============================================================================


def test_lint_skills_mode_detects_valid_commands(cli_runner, tmp_path, monkeypatch):
    """Test that --skills mode validates skill file CLI references."""
    from orch.cli import cli

    # Create a mock skills directory structure
    skills_dir = tmp_path / ".claude" / "skills" / "worker" / "test-skill"
    skills_dir.mkdir(parents=True)

    # Create a skill file with valid commands
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
---

# Test Skill

Use `orch spawn` to start an agent.
Run `orch status` to check progress.
Use `orch complete` when done.
""")

    # Point HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))

    result = cli_runner.invoke(cli, ['lint', '--skills'])

    # Should succeed with valid commands
    assert result.exit_code == 0
    assert "valid" in result.output.lower() or "passed" in result.output.lower() or "✅" in result.output


def test_lint_skills_mode_detects_invalid_commands(cli_runner, tmp_path, monkeypatch):
    """Test that --skills mode warns about unknown CLI commands."""
    from orch.cli import cli

    # Create a mock skills directory structure
    skills_dir = tmp_path / ".claude" / "skills" / "worker" / "test-skill"
    skills_dir.mkdir(parents=True)

    # Create a skill file with invalid commands
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
---

# Test Skill

Use `orch nonexistent-command` to do something.
Run `orch status` to check progress.
Use `orch fake-command` when done.
""")

    # Point HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))

    result = cli_runner.invoke(cli, ['lint', '--skills'])

    # Should warn about invalid commands
    assert "nonexistent-command" in result.output
    assert "fake-command" in result.output


def test_lint_skills_mode_detects_invalid_flags(cli_runner, tmp_path, monkeypatch):
    """Test that --skills mode warns about unknown flags on valid commands."""
    from orch.cli import cli

    # Create a mock skills directory structure
    skills_dir = tmp_path / ".claude" / "skills" / "worker" / "test-skill"
    skills_dir.mkdir(parents=True)

    # Create a skill file with invalid flags
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
---

# Test Skill

Use `orch spawn --nonexistent-flag` to start.
Run `orch status --fake-flag` to check.
""")

    # Point HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))

    result = cli_runner.invoke(cli, ['lint', '--skills'])

    # Should warn about invalid flags
    assert "--nonexistent-flag" in result.output or "nonexistent-flag" in result.output
    assert "--fake-flag" in result.output or "fake-flag" in result.output


def test_lint_skills_mode_handles_subcommands(cli_runner, tmp_path, monkeypatch):
    """Test that --skills mode correctly validates subcommands like 'build skills'."""
    from orch.cli import cli

    # Create a mock skills directory structure
    skills_dir = tmp_path / ".claude" / "skills" / "worker" / "test-skill"
    skills_dir.mkdir(parents=True)

    # Create a skill file with subcommands
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
---

# Test Skill

Run `orch build skills` to rebuild.
Run `orch projects list` to see all projects.
Run `orch build nonexistent` should warn.
""")

    # Point HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))

    result = cli_runner.invoke(cli, ['lint', '--skills'])

    # Valid subcommands should pass, invalid should warn
    # 'build skills' is valid, 'build nonexistent' is invalid
    assert "build nonexistent" in result.output.lower() or "nonexistent" in result.output


def test_lint_skills_mode_no_skills_found(cli_runner, tmp_path, monkeypatch):
    """Test graceful handling when no skill files exist."""
    from orch.cli import cli

    # Create empty skills directory
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    # Point HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))

    result = cli_runner.invoke(cli, ['lint', '--skills'])

    # Should handle gracefully
    assert result.exit_code == 0
    assert "no skill" in result.output.lower() or "0 skill" in result.output.lower()
