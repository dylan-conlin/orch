"""
Tests for .kb/ path migration with .orch/ fallback.

Per orch-cli-eae: Migrate artifact paths from .orch/ to .kb/ with fallback.
.kb/ is the new canonical location, .orch/ is legacy fallback.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from orch.complete import (
    is_investigation_ref,
    find_investigation_file,
)


class TestIsInvestigationRef:
    """Tests for is_investigation_ref() recognizing both .kb/ and .orch/ paths."""

    def test_recognizes_orch_investigations_path(self):
        """Legacy .orch/investigations/ paths should be recognized."""
        ref = ".orch/investigations/simple/2025-12-05-test.md"
        assert is_investigation_ref(ref) is True

    def test_recognizes_kb_investigations_path(self):
        """New .kb/investigations/ paths should be recognized."""
        ref = ".kb/investigations/simple/2025-12-05-test.md"
        assert is_investigation_ref(ref) is True

    def test_rejects_non_investigation_path(self):
        """Non-investigation paths should not be recognized."""
        assert is_investigation_ref(".orch/workspace/test.md") is False
        assert is_investigation_ref(".kb/workspace/test.md") is False
        assert is_investigation_ref("src/main.py") is False

    def test_handles_none_input(self):
        """None input should return False."""
        assert is_investigation_ref(None) is False

    def test_handles_empty_string(self):
        """Empty string should return False."""
        assert is_investigation_ref("") is False


class TestFindInvestigationFile:
    """Tests for find_investigation_file() checking .kb/ first then .orch/ fallback."""

    def test_finds_file_in_kb_directory(self, tmp_path):
        """Should find investigation file in .kb/investigations/ (new canonical)."""
        # Create .kb/investigations/simple/
        kb_inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        kb_inv_dir.mkdir(parents=True)
        inv_file = kb_inv_dir / "test-workspace.md"
        inv_file.write_text("# Investigation")

        result = find_investigation_file("test-workspace", tmp_path)

        assert result is not None
        assert result == inv_file

    def test_finds_file_in_orch_directory_fallback(self, tmp_path):
        """Should fall back to .orch/investigations/ when .kb/ doesn't exist."""
        # Create .orch/investigations/simple/
        orch_inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        orch_inv_dir.mkdir(parents=True)
        inv_file = orch_inv_dir / "test-workspace.md"
        inv_file.write_text("# Investigation")

        result = find_investigation_file("test-workspace", tmp_path)

        assert result is not None
        assert result == inv_file

    def test_prefers_kb_over_orch_when_both_exist(self, tmp_path):
        """When file exists in both locations, .kb/ should take precedence."""
        # Create file in both locations
        kb_inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        kb_inv_dir.mkdir(parents=True)
        kb_file = kb_inv_dir / "test-workspace.md"
        kb_file.write_text("# KB Investigation")

        orch_inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        orch_inv_dir.mkdir(parents=True)
        orch_file = orch_inv_dir / "test-workspace.md"
        orch_file.write_text("# Orch Investigation")

        result = find_investigation_file("test-workspace", tmp_path)

        assert result is not None
        assert result == kb_file
        assert ".kb" in str(result)

    def test_searches_subdirectories(self, tmp_path):
        """Should search in subdirectories (simple, design, etc.)."""
        # Create in design subdirectory
        design_dir = tmp_path / ".kb" / "investigations" / "design"
        design_dir.mkdir(parents=True)
        inv_file = design_dir / "test-workspace.md"
        inv_file.write_text("# Design Investigation")

        result = find_investigation_file("test-workspace", tmp_path)

        assert result is not None
        assert result == inv_file

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when file doesn't exist in either location."""
        # Create empty directories
        (tmp_path / ".kb" / "investigations").mkdir(parents=True)
        (tmp_path / ".orch" / "investigations").mkdir(parents=True)

        result = find_investigation_file("nonexistent", tmp_path)

        assert result is None

    def test_returns_none_when_no_investigations_dir(self, tmp_path):
        """Should return None when neither investigations dir exists."""
        result = find_investigation_file("test-workspace", tmp_path)

        assert result is None


class TestSpawnPromptKbPaths:
    """Tests for spawn_prompt.py using .kb/ paths for new investigations."""

    def test_spawn_prompt_tells_agent_to_create_in_kb(self, tmp_path):
        """Spawn prompt should tell agents to create files in .kb/investigations/."""
        from orch.spawn_prompt import build_spawn_prompt
        from orch.spawn import SpawnConfig

        config = SpawnConfig(
            task="test task",
            project=str(tmp_path),
            skill_name="investigation",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            investigation_type="simple",
            requires_workspace=False,
        )

        prompt = build_spawn_prompt(config)

        # Should mention .kb/ path for new investigation files
        assert ".kb/investigations/" in prompt or "kb create investigation" in prompt
