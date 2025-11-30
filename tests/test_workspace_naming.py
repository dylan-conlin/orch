"""Tests for workspace naming improvements (abbreviations and truncation)."""

import pytest
from orch.workspace import apply_abbreviations, ABBREVIATIONS


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
