"""
Tests for spawn context quality display in orch check command.

Validates that the check command displays spawn context quality indicators
when SPAWN_CONTEXT.md exists in a workspace.

Related: Phase 2 of SPAWN_CONTEXT.md as first-class artifact feature.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from orch.spawn_context_quality import (
    validate_spawn_context_quality,
    format_quality_for_human,
    format_quality_for_json,
    SpawnContextQuality,
    QualityIndicator,
)


class TestFormatQualityForHuman:
    """Test human-readable formatting of spawn context quality."""

    def test_complete_quality_shows_checkmark(self):
        """Complete spawn context should show success indicator."""
        quality = SpawnContextQuality(
            is_complete=True,
            warnings=[],
            score=100,
            sections_present=["TASK", "SCOPE", "DELIVERABLES"],
            sections_missing=[]
        )

        output = format_quality_for_human(quality)

        assert "✅" in output
        assert "Complete" in output
        assert "✓ TASK defined" in output

    def test_incomplete_quality_shows_warnings(self):
        """Incomplete spawn context should show warnings."""
        quality = SpawnContextQuality(
            is_complete=False,
            warnings=[
                QualityIndicator("Missing SCOPE section", "critical", "SCOPE"),
                QualityIndicator("Missing SESSION SCOPE section", "warning", "SESSION SCOPE"),
            ],
            score=60,
            sections_present=["TASK"],
            sections_missing=["SCOPE", "SESSION SCOPE"]
        )

        output = format_quality_for_human(quality)

        assert "⚠️" in output
        assert "60%" in output
        assert "❌" in output  # Critical warning
        assert "Missing SCOPE" in output

    def test_shows_present_sections(self):
        """Should list all present sections with checkmarks."""
        quality = SpawnContextQuality(
            is_complete=False,
            warnings=[],
            score=80,
            sections_present=["TASK", "SCOPE", "DELIVERABLES"],
            sections_missing=["SESSION SCOPE"]
        )

        output = format_quality_for_human(quality)

        assert "✓ TASK defined" in output
        assert "✓ SCOPE defined" in output
        assert "✓ DELIVERABLES defined" in output


class TestFormatQualityForJson:
    """Test JSON formatting of spawn context quality."""

    def test_json_format_has_required_fields(self):
        """JSON output should have all required fields."""
        quality = SpawnContextQuality(
            is_complete=True,
            warnings=[],
            score=100,
            sections_present=["TASK", "SCOPE"],
            sections_missing=[]
        )

        result = format_quality_for_json(quality)

        assert "is_complete" in result
        assert "score" in result
        assert "sections_present" in result
        assert "sections_missing" in result
        assert "warnings" in result
        assert result["is_complete"] is True
        assert result["score"] == 100

    def test_json_format_includes_warnings(self):
        """JSON output should include warning details."""
        quality = SpawnContextQuality(
            is_complete=False,
            warnings=[
                QualityIndicator("Missing SCOPE", "critical", "SCOPE"),
            ],
            score=60,
            sections_present=["TASK"],
            sections_missing=["SCOPE"]
        )

        result = format_quality_for_json(quality)

        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["message"] == "Missing SCOPE"
        assert result["warnings"][0]["severity"] == "critical"
        assert result["warnings"][0]["section"] == "SCOPE"


class TestCheckCommandSpawnContextIntegration:
    """Integration tests for spawn context quality in orch check command."""

    def test_check_displays_spawn_context_quality_when_present(self, tmp_path):
        """Check command should display spawn context quality when SPAWN_CONTEXT.md exists."""
        from orch.cli import cli
        from orch.registry import AgentRegistry

        runner = CliRunner()

        # Create test workspace with SPAWN_CONTEXT.md
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)

        spawn_context = workspace_dir / "SPAWN_CONTEXT.md"
        spawn_context.write_text("""TASK: Test task for spawn context

PROJECT_DIR: /test/project

SESSION SCOPE: Small (estimated 1-2h)

SCOPE:
- IN: Test scope
- OUT: Not in scope

AUTHORITY:
**You have authority to decide:**
- Implementation

DELIVERABLES (REQUIRED):
1. Something
""")

        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""**TLDR:** Test workspace

# Workspace: test-agent

**Phase:** Implementation
**Status:** Active
""")

        # Create mock registry with agent
        registry_path = tmp_path / "registry.json"
        import json
        registry_data = {
            "agents": [{
                "id": "test-agent",
                "task": "Test task",
                "window": "workers:1",
                "project_dir": str(tmp_path),
                "workspace": ".orch/workspace/test-agent",
                "spawned_at": "2025-11-28T10:00:00Z",
                "status": "active"
            }]
        }
        registry_path.write_text(json.dumps(registry_data))

        # Mock the check_agent_status to return a simple status
        mock_status = MagicMock()
        mock_status.phase = "Implementation"
        mock_status.priority = "normal"
        mock_status.alerts = []
        mock_status.violations = []
        mock_status.last_commit = None
        mock_status.commits_since_spawn = 0

        with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
            result = runner.invoke(cli, ['check', 'test-agent', '--registry', str(registry_path)])

        # Should succeed
        assert result.exit_code == 0, f"Check failed: {result.output}"

        # Should show spawn context quality section
        assert "Spawn Context" in result.output or "spawn context" in result.output.lower()

    def test_check_handles_missing_spawn_context_gracefully(self, tmp_path):
        """Check should work when SPAWN_CONTEXT.md doesn't exist."""
        from orch.cli import cli
        from orch.registry import AgentRegistry

        runner = CliRunner()

        # Create test workspace WITHOUT SPAWN_CONTEXT.md
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)

        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""**TLDR:** Test workspace

# Workspace: test-agent

**Phase:** Implementation
**Status:** Active
""")

        # Create mock registry
        registry_path = tmp_path / "registry.json"
        import json
        registry_data = {
            "agents": [{
                "id": "test-agent",
                "task": "Test task",
                "window": "workers:1",
                "project_dir": str(tmp_path),
                "workspace": ".orch/workspace/test-agent",
                "spawned_at": "2025-11-28T10:00:00Z",
                "status": "active"
            }]
        }
        registry_path.write_text(json.dumps(registry_data))

        mock_status = MagicMock()
        mock_status.phase = "Implementation"
        mock_status.priority = "normal"
        mock_status.alerts = []
        mock_status.violations = []
        mock_status.last_commit = None
        mock_status.commits_since_spawn = 0

        with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
            result = runner.invoke(cli, ['check', 'test-agent', '--registry', str(registry_path)])

        # Should succeed even without SPAWN_CONTEXT.md
        assert result.exit_code == 0, f"Check failed: {result.output}"

    def test_check_json_includes_spawn_context_quality(self, tmp_path):
        """Check --format json should include spawn_context_quality field."""
        from orch.cli import cli

        runner = CliRunner()

        # Create test workspace with SPAWN_CONTEXT.md
        workspace_dir = tmp_path / ".orch" / "workspace" / "test-agent"
        workspace_dir.mkdir(parents=True)

        spawn_context = workspace_dir / "SPAWN_CONTEXT.md"
        spawn_context.write_text("""TASK: Test task

PROJECT_DIR: /test/project

SCOPE:
- IN: Something
- OUT: Something else

DELIVERABLES:
1. Output
""")

        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""**TLDR:** Test

**Phase:** Implementation
**Status:** Active
""")

        # Create mock registry
        registry_path = tmp_path / "registry.json"
        import json
        registry_data = {
            "agents": [{
                "id": "test-agent",
                "task": "Test task",
                "window": "workers:1",
                "project_dir": str(tmp_path),
                "workspace": ".orch/workspace/test-agent",
                "spawned_at": "2025-11-28T10:00:00Z",
                "status": "active"
            }]
        }
        registry_path.write_text(json.dumps(registry_data))

        mock_status = MagicMock()
        mock_status.phase = "Implementation"
        mock_status.priority = "normal"
        mock_status.alerts = []
        mock_status.violations = []
        mock_status.last_commit = None
        mock_status.commits_since_spawn = 0

        with patch('orch.monitoring_commands.check_agent_status', return_value=mock_status):
            result = runner.invoke(cli, ['check', 'test-agent', '--format', 'json', '--registry', str(registry_path)])

        assert result.exit_code == 0, f"Check failed: {result.output}"

        # Parse JSON output
        output_data = json.loads(result.output)

        # Should include spawn_context_quality
        assert "spawn_context_quality" in output_data.get("agent", output_data)
