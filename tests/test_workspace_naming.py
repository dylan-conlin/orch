"""Tests for workspace naming improvements (abbreviations and truncation)."""

import pytest
from pathlib import Path
from orch.workspace import apply_abbreviations, ABBREVIATIONS
from orch.workspace_naming import create_workspace_adhoc, abbreviate_project_name


class TestAbbreviations:
    """Test abbreviation application to word lists."""

    def test_apply_abbreviations_single_word(self):
        """Apply abbreviation to a single word."""
        words = ["investigate", "timeout"]
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == ["inv", "timeout"]

    def test_apply_abbreviations_multiple_words(self):
        """Apply abbreviations to multiple words."""
        words = ["implement", "authentication", "configuration"]
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == ["impl", "auth", "config"]

    def test_apply_abbreviations_preserves_non_matching(self):
        """Words without abbreviations pass through unchanged."""
        words = ["fix", "urgent", "bug"]
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == ["fix", "urgent", "bug"]

    def test_apply_abbreviations_case_insensitive(self):
        """Abbreviation matching should be case-insensitive."""
        words = ["Investigate", "DEBUGGING", "Collection"]
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == ["inv", "debug", "coll"]

    def test_apply_abbreviations_empty_list(self):
        """Handle empty word list."""
        words = []
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == []

    def test_apply_abbreviations_mixed_case_preserved_when_no_match(self):
        """Preserve original case for words without abbreviations."""
        words = ["FixBug", "QuickWin"]
        result = apply_abbreviations(words, ABBREVIATIONS)
        assert result == ["FixBug", "QuickWin"]


class TestConstants:
    """Test that required constants are defined."""

    def test_abbreviations_dict_exists(self):
        """ABBREVIATIONS constant should be defined."""
        assert isinstance(ABBREVIATIONS, dict)
        assert len(ABBREVIATIONS) > 0

    def test_abbreviations_contain_expected_terms(self):
        """ABBREVIATIONS should contain expected terms."""
        expected_keys = {'investigate', 'implement', 'debugging', 'configuration'}
        assert expected_keys.issubset(ABBREVIATIONS.keys())

    def test_abbreviations_values_are_shorter(self):
        """Abbreviation values should be shorter than keys."""
        for key, value in ABBREVIATIONS.items():
            assert len(value) < len(key), f"Abbreviation '{value}' not shorter than '{key}'"


class TestProjectPrefixWorkspaceNames:
    """Test that workspace names include project prefix for global uniqueness."""

    def test_different_projects_get_different_names(self, tmp_path):
        """Same task in different projects should generate different workspace names."""
        task = "bug handling analysis"
        proj_a = tmp_path / "project-a"
        proj_b = tmp_path / "orch-cli"
        proj_a.mkdir()
        proj_b.mkdir()

        name_a = create_workspace_adhoc(task, skill_name="investigation", project_dir=proj_a)
        name_b = create_workspace_adhoc(task, skill_name="investigation", project_dir=proj_b)

        assert name_a != name_b, "Different projects should have different workspace names"
        assert name_a.startswith("pa-"), f"Expected project-a prefix 'pa-', got: {name_a}"
        assert name_b.startswith("oc-"), f"Expected orch-cli prefix 'oc-', got: {name_b}"

    def test_workspace_name_includes_project_prefix(self, tmp_path):
        """Workspace names should start with abbreviated project name."""
        proj = tmp_path / "price-watch"
        proj.mkdir()

        name = create_workspace_adhoc("fix authentication", skill_name="feature-impl", project_dir=proj)

        assert name.startswith("pw-"), f"Expected 'pw-' prefix for price-watch, got: {name}"
        assert "feat" in name, "Should include skill prefix"

    def test_workspace_name_without_project_dir(self):
        """Workspace names without project_dir should work (no prefix)."""
        name = create_workspace_adhoc("fix something", skill_name="investigation")

        assert name.startswith("inv-"), "Should start with skill prefix when no project"
        assert len(name) <= 35, "Name should be within max length"

    def test_workspace_name_respects_max_length(self, tmp_path):
        """Workspace names with project prefix should still be <= 35 chars."""
        proj = tmp_path / "super-long-project-name"
        proj.mkdir()

        name = create_workspace_adhoc(
            "very long task description with many words that should be truncated properly",
            skill_name="investigation",
            project_dir=proj
        )

        assert len(name) <= 35, f"Name too long: {name} ({len(name)} chars)"

    def test_single_word_project_name(self, tmp_path):
        """Single word projects should use the full name if short."""
        proj = tmp_path / "beads"
        proj.mkdir()

        name = create_workspace_adhoc("fix issue", skill_name="investigation", project_dir=proj)

        assert name.startswith("beads-"), f"Expected 'beads-' prefix, got: {name}"

    def test_abbreviate_project_name_examples(self):
        """Test project name abbreviation function directly."""
        assert abbreviate_project_name("price-watch") == "pw"
        assert abbreviate_project_name("orch-cli") == "oc"
        assert abbreviate_project_name("beads") == "beads"  # Short single word
        assert abbreviate_project_name("kb-cli") == "kc"
