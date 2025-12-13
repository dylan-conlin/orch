"""
Tests for orch build opencode command.

Tests OpenCode configuration validation including:
- JSON/JSONC parsing
- Instruction file resolution
- Glob pattern expansion
- Error handling
"""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner


class TestOpencodeConfigParsing:
    """Test OpenCode JSON/JSONC parsing."""

    def test_valid_json_config(self, tmp_path):
        """Should parse valid JSON config."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": []
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "JSON syntax valid" in result.output
        assert "No instructions configured" in result.output

    def test_invalid_json_syntax(self, tmp_path):
        """Should report JSON syntax errors."""
        from orch.cli import cli

        # Invalid JSON (missing comma)
        config_file = tmp_path / "opencode.json"
        config_file.write_text('{"$schema": "https://opencode.ai/config.json" "instructions": []}')

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert "JSON syntax error" in result.output
        assert "Expecting" in result.output  # Part of JSON error message

    def test_jsonc_with_single_line_comments(self, tmp_path):
        """Should parse JSONC with // comments."""
        from orch.cli import cli

        config_file = tmp_path / "opencode.jsonc"
        config_file.write_text("""
{
  "$schema": "https://opencode.ai/config.json",
  // This is a comment
  "instructions": []
}
""")

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "JSON syntax valid" in result.output

    def test_jsonc_with_multi_line_comments(self, tmp_path):
        """Should parse JSONC with /* */ comments."""
        from orch.cli import cli

        config_file = tmp_path / "opencode.jsonc"
        config_file.write_text("""
{
  "$schema": "https://opencode.ai/config.json",
  /* Multi-line
     comment */
  "instructions": []
}
""")

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "JSON syntax valid" in result.output

    def test_jsonc_preserves_urls_in_strings(self, tmp_path):
        """Should not strip // from URLs in strings."""
        from orch.cli import cli

        config_file = tmp_path / "opencode.jsonc"
        config_file.write_text("""
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": []
}
""")

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "JSON syntax valid" in result.output


class TestInstructionFileResolution:
    """Test instruction file path resolution."""

    def test_existing_file(self, tmp_path):
        """Should validate existing instruction files."""
        from orch.cli import cli

        # Create instruction file
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "rules.md").write_text("# Rules")

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["docs/rules.md"]
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "docs/rules.md" in result.output
        assert "MISSING" not in result.output

    def test_missing_file(self, tmp_path):
        """Should report missing instruction files."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["nonexistent.md"]
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert "MISSING" in result.output
        assert "Validation FAILED" in result.output

    def test_glob_pattern_matches(self, tmp_path):
        """Should expand glob patterns and count matched files."""
        from orch.cli import cli

        # Create multiple files matching glob
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "rule1.md").write_text("# Rule 1")
        (docs_dir / "rule2.md").write_text("# Rule 2")
        (docs_dir / "rule3.md").write_text("# Rule 3")

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["docs/*.md"]
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "3 file(s) matched" in result.output

    def test_glob_pattern_no_matches(self, tmp_path):
        """Should report when glob pattern matches nothing."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["nonexistent/*.md"]
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert "no files matched" in result.output
        assert "Validation FAILED" in result.output

    def test_home_directory_expansion(self, tmp_path, monkeypatch):
        """Should expand ~ to home directory."""
        from orch.cli import cli

        # Create a test file in a subdirectory of tmp_path
        # and patch Path.home() to return tmp_path
        test_file = tmp_path / "test-file.md"
        test_file.write_text("# Test")

        monkeypatch.setattr(Path, 'home', lambda: tmp_path)

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["~/test-file.md"]
        }
        # Create config in a different directory
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_file = project_dir / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(project_dir)])

        assert result.exit_code == 0
        assert "~/test-file.md" in result.output
        assert "MISSING" not in result.output


class TestCheckMode:
    """Test --check flag behavior."""

    def test_check_mode_success(self, tmp_path):
        """Should exit 0 when validation passes with --check."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": []
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--check', '--project', str(tmp_path)])

        assert result.exit_code == 0

    def test_check_mode_failure(self, tmp_path):
        """Should exit non-zero when validation fails with --check."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["nonexistent.md"]
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--check', '--project', str(tmp_path)])

        assert result.exit_code != 0

    def test_check_mode_missing_config(self, tmp_path):
        """Should exit non-zero when config file missing with --check."""
        from orch.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--check', '--project', str(tmp_path)])

        assert result.exit_code != 0
        assert "No opencode.json" in result.output


class TestNoConfigFile:
    """Test behavior when no config file exists."""

    def test_no_config_without_check(self, tmp_path):
        """Should warn but not error when config missing without --check."""
        from orch.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert result.exit_code == 0
        assert "No opencode.json" in result.output

    def test_prefers_json_over_jsonc(self, tmp_path):
        """Should prefer opencode.json over opencode.jsonc."""
        from orch.cli import cli

        # Create both files with different instructions
        (tmp_path / "opencode.json").write_text(json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "instructions": []
        }))
        (tmp_path / "opencode.jsonc").write_text("""
{
  "$schema": "https://opencode.ai/config.json",
  // Should not be used
  "instructions": ["should-not-see.md"]
}
""")

        runner = CliRunner()
        result = runner.invoke(cli, ['build', 'opencode', '--project', str(tmp_path)])

        assert "opencode.json" in result.output
        assert "should-not-see" not in result.output


class TestFlagStyle:
    """Test --opencode flag style invocation."""

    def test_opencode_flag(self, tmp_path, monkeypatch):
        """Should work with orch build --opencode flag."""
        from orch.cli import cli

        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": []
        }
        config_file = tmp_path / "opencode.json"
        config_file.write_text(json.dumps(config))

        # Change to tmp_path since --project is not available in flag style
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ['build', '--opencode'])

        # Verify the flag is recognized and validation runs
        assert "Validating OpenCode config" in result.output
        assert "JSON syntax valid" in result.output
