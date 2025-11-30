"""
Tests for frontmatter parsing module.

TDD approach: These tests are written first, before the implementation.
They define the expected behavior of the frontmatter parser.
"""
import pytest
from pathlib import Path
from typing import Optional


# This import will fail until we create the module (TDD RED phase)
from orch.frontmatter import (
    extract_metadata,
    extract_phase,
    extract_status,
    has_frontmatter,
    MetadataResult,
)


class TestHasFrontmatter:
    """Test detection of YAML frontmatter in markdown files."""

    def test_detects_valid_frontmatter(self):
        """File with valid YAML frontmatter should return True."""
        content = """---
phase: Implementation
status: Active
started: 2025-11-30
---

# Title

Content here.
"""
        assert has_frontmatter(content) is True

    def test_no_frontmatter(self):
        """File without frontmatter should return False."""
        content = """# Title

**Phase:** Implementation
**Status:** Active
"""
        assert has_frontmatter(content) is False

    def test_frontmatter_must_start_at_beginning(self):
        """Frontmatter must start at line 1, not later."""
        content = """
---
phase: Implementation
---
"""
        # Leading newline means it's not at the start
        assert has_frontmatter(content) is False

    def test_empty_frontmatter(self):
        """Empty frontmatter block is still valid frontmatter."""
        content = """---
---

Content
"""
        assert has_frontmatter(content) is True


class TestExtractMetadata:
    """Test extraction of all metadata fields from frontmatter."""

    def test_extracts_all_fields(self):
        """Should extract all standard metadata fields."""
        content = """---
phase: Implementation
status: Active
started: "2025-11-30"
last_updated: "2025-11-30T13:45:00Z"
tags:
  - debugging
  - orch-cli
confidence: High
---

# Title
"""
        result = extract_metadata(content)

        assert result.phase == "Implementation"
        assert result.status == "Active"
        # Dates are parsed as strings when quoted in YAML
        assert result.started == "2025-11-30"
        assert result.last_updated == "2025-11-30T13:45:00Z"
        assert result.tags == ["debugging", "orch-cli"]
        assert result.confidence == "High"

    def test_missing_fields_return_none(self):
        """Fields not present in frontmatter should return None."""
        content = """---
phase: Complete
---

Content
"""
        result = extract_metadata(content)

        assert result.phase == "Complete"
        assert result.status is None
        assert result.started is None
        assert result.tags is None

    def test_fallback_to_inline_when_no_frontmatter(self):
        """When no frontmatter, fall back to inline markdown extraction."""
        content = """# Workspace: test

**Phase:** Implementation
**Status:** Active
**Started:** 2025-11-30

Content here.
"""
        result = extract_metadata(content)

        assert result.phase == "Implementation"
        assert result.status == "Active"
        assert result.started == "2025-11-30"
        assert result.from_frontmatter is False

    def test_frontmatter_takes_precedence(self):
        """Frontmatter values should take precedence over inline."""
        content = """---
phase: Complete
status: Active
---

**Phase:** Implementation
**Status:** Blocked
"""
        result = extract_metadata(content)

        assert result.phase == "Complete"  # From frontmatter
        assert result.status == "Active"  # From frontmatter
        assert result.from_frontmatter is True


class TestExtractPhase:
    """Test extraction of Phase field specifically."""

    def test_extracts_from_frontmatter(self):
        """Phase should be extracted from frontmatter."""
        content = """---
phase: Implementation
---

Content
"""
        assert extract_phase(content) == "Implementation"

    def test_extracts_from_inline_markdown(self):
        """Phase should be extracted from inline markdown as fallback."""
        content = """# Title

**Phase:** Testing
"""
        assert extract_phase(content) == "Testing"

    def test_handles_case_insensitivity_in_frontmatter(self):
        """Frontmatter keys should be case-insensitive."""
        content = """---
Phase: Implementation
---
"""
        assert extract_phase(content) == "Implementation"

    def test_filters_template_placeholders(self):
        """Template placeholders like 'Active | Complete' should be filtered."""
        content = """---
phase: Active | Complete
---
"""
        # This is a template placeholder, not a real value
        assert extract_phase(content) is None

    def test_filters_bracket_placeholders(self):
        """Bracket placeholders like '[Investigating/Complete]' should be filtered."""
        content = """---
phase: "[Investigating/Complete]"
---
"""
        assert extract_phase(content) is None

    def test_returns_none_for_missing_phase(self):
        """Missing phase should return None."""
        content = """---
status: Active
---
"""
        assert extract_phase(content) is None


class TestExtractStatus:
    """Test extraction of Status field specifically."""

    def test_extracts_from_frontmatter(self):
        """Status should be extracted from frontmatter."""
        content = """---
status: Blocked
---
"""
        assert extract_status(content) == "Blocked"

    def test_extracts_from_inline_markdown(self):
        """Status should be extracted from inline markdown as fallback."""
        content = """# Title

**Status:** Active
"""
        assert extract_status(content) == "Active"

    def test_detects_awaiting_validation(self):
        """AWAITING_VALIDATION status should be properly extracted."""
        content = """---
status: AWAITING_VALIDATION
---
"""
        assert extract_status(content) == "AWAITING_VALIDATION"


class TestMetadataResult:
    """Test the MetadataResult dataclass."""

    def test_default_values(self):
        """Default MetadataResult should have all None values."""
        result = MetadataResult()
        assert result.phase is None
        assert result.status is None
        assert result.started is None
        assert result.last_updated is None
        assert result.completed is None
        assert result.tags is None
        assert result.confidence is None
        assert result.from_frontmatter is False

    def test_fields_can_be_set(self):
        """All fields should be settable."""
        result = MetadataResult(
            phase="Complete",
            status="Active",
            started="2025-11-30",
            tags=["test"],
            from_frontmatter=True,
        )
        assert result.phase == "Complete"
        assert result.status == "Active"
        assert result.started == "2025-11-30"
        assert result.tags == ["test"]
        assert result.from_frontmatter is True


class TestFileBasedExtraction:
    """Test extraction from actual files."""

    def test_extract_from_file_with_frontmatter(self, tmp_path):
        """Should extract metadata from file with frontmatter."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
phase: Implementation
status: Active
---

# Test File
""")
        result = extract_metadata(test_file.read_text())
        assert result.phase == "Implementation"
        assert result.from_frontmatter is True

    def test_extract_from_file_with_inline(self, tmp_path):
        """Should extract metadata from file with inline markdown."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""# Test File

**Phase:** Complete
**Status:** Active
""")
        result = extract_metadata(test_file.read_text())
        assert result.phase == "Complete"
        assert result.from_frontmatter is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_content(self):
        """Empty content should return empty result."""
        result = extract_metadata("")
        assert result.phase is None
        assert result.from_frontmatter is False

    def test_malformed_frontmatter(self):
        """Malformed YAML should fall back to inline extraction."""
        # Use duplicate keys at different indent levels to trigger YAML error
        content = """---
mapping:
  nested: value
nested: duplicate
  broken: indent
---

**Phase:** Fallback
"""
        # Should gracefully fall back to inline
        result = extract_metadata(content)
        assert result.phase == "Fallback"
        assert result.from_frontmatter is False

    def test_frontmatter_with_special_characters(self):
        """Frontmatter with special characters should be handled."""
        content = """---
phase: "Implementation: Phase 1"
status: "Active"
---
"""
        result = extract_metadata(content)
        assert result.phase == "Implementation: Phase 1"

    def test_multiline_values_in_frontmatter(self):
        """Multiline values should be handled correctly."""
        content = """---
phase: Implementation
tags:
  - tag1
  - tag2
  - tag3
---
"""
        result = extract_metadata(content)
        assert result.tags == ["tag1", "tag2", "tag3"]

    def test_boolean_values(self):
        """Boolean values in YAML should be preserved."""
        content = """---
phase: Complete
archived: true
---
"""
        result = extract_metadata(content)
        # archived isn't a standard field, but shouldn't break parsing
        assert result.phase == "Complete"
