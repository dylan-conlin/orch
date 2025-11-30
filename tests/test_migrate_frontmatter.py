"""
Tests for frontmatter migration module.

TDD approach: Tests written first.
"""
import pytest
from pathlib import Path
from orch.migrate_frontmatter import (
    convert_to_frontmatter,
    detect_file_type,
    extract_inline_metadata,
    FileType,
)


class TestDetectFileType:
    """Test file type detection."""

    def test_detects_workspace_file(self, tmp_path):
        """Should detect workspace files."""
        workspace = tmp_path / ".orch" / "workspace" / "test" / "WORKSPACE.md"
        workspace.parent.mkdir(parents=True)
        workspace.write_text("# Workspace: test")
        assert detect_file_type(workspace) == FileType.WORKSPACE

    def test_detects_simple_investigation(self, tmp_path):
        """Should detect simple investigation files."""
        inv = tmp_path / ".orch" / "investigations" / "simple" / "2025-01-01-test.md"
        inv.parent.mkdir(parents=True)
        inv.write_text("# Test Investigation")
        assert detect_file_type(inv) == FileType.SIMPLE_INVESTIGATION

    def test_detects_decision_file(self, tmp_path):
        """Should detect decision files."""
        dec = tmp_path / ".orch" / "decisions" / "2025-01-01-test-decision.md"
        dec.parent.mkdir(parents=True)
        dec.write_text("# Decision: Test")
        assert detect_file_type(dec) == FileType.DECISION

    def test_detects_audit_file(self, tmp_path):
        """Should detect audit investigation files."""
        audit = tmp_path / ".orch" / "investigations" / "audits" / "test.md"
        audit.parent.mkdir(parents=True)
        audit.write_text("# Audit Investigation")
        assert detect_file_type(audit) == FileType.AUDIT


class TestExtractInlineMetadata:
    """Test inline metadata extraction."""

    def test_extracts_workspace_metadata(self):
        """Should extract workspace metadata fields."""
        content = """# Workspace: test

**Owner:** Dylan
**Started:** 2025-11-30
**Last Updated:** 2025-11-30 13:45
**Phase:** Implementation
**Status:** Active
**Template-Version:** v3-slim

**TLDR:** Test workspace.

## Summary
"""
        metadata = extract_inline_metadata(content, FileType.WORKSPACE)

        assert metadata["owner"] == "Dylan"
        assert metadata["started"] == "2025-11-30"
        assert metadata["last_updated"] == "2025-11-30 13:45"
        assert metadata["phase"] == "Implementation"
        assert metadata["status"] == "Active"
        assert metadata["template_version"] == "v3-slim"

    def test_extracts_simple_investigation_metadata(self):
        """Should extract simple investigation metadata."""
        content = """# Test Topic

**Date:** 2025-11-30
**Status:** Complete

**TLDR:** Test finding.
"""
        metadata = extract_inline_metadata(content, FileType.SIMPLE_INVESTIGATION)

        assert metadata["date"] == "2025-11-30"
        assert metadata["status"] == "Complete"

    def test_extracts_decision_metadata(self):
        """Should extract decision file metadata."""
        content = """# Decision: Test

**Date:** 2025-11-30
**Status:** Accepted
**Topic:** test-topic
**Context:** Test context
**Scope:** Test scope
**Source:** Manual decision

## Problem
"""
        metadata = extract_inline_metadata(content, FileType.DECISION)

        assert metadata["date"] == "2025-11-30"
        assert metadata["status"] == "Accepted"
        assert metadata["topic"] == "test-topic"
        assert metadata["context"] == "Test context"
        assert metadata["scope"] == "Test scope"
        assert metadata["source"] == "Manual decision"

    def test_handles_missing_fields(self):
        """Should handle missing fields gracefully."""
        content = """# Workspace: test

**Phase:** Complete

## Summary
"""
        metadata = extract_inline_metadata(content, FileType.WORKSPACE)

        assert metadata["phase"] == "Complete"
        assert "owner" not in metadata or metadata["owner"] is None


class TestConvertToFrontmatter:
    """Test content conversion to frontmatter format."""

    def test_converts_workspace_to_frontmatter(self):
        """Should convert workspace file to frontmatter format."""
        content = """<!-- Pattern comment -->

**TLDR:** Test workspace.

---

# Workspace: test

**Owner:** Dylan
**Started:** 2025-11-30
**Last Updated:** 2025-11-30 13:45
**Phase:** Implementation
**Status:** Active
**Template-Version:** v3-slim

---

## Summary
"""
        converted = convert_to_frontmatter(content, FileType.WORKSPACE)

        # Should have frontmatter at start
        assert converted.startswith("---\n")
        # Should have extracted values in frontmatter
        assert 'owner: "Dylan"' in converted
        assert 'phase: "Implementation"' in converted
        assert 'status: "Active"' in converted
        # Should preserve TLDR inline
        assert "**TLDR:** Test workspace." in converted
        # Should remove inline metadata (no duplicate)
        assert "**Owner:** Dylan" not in converted
        assert "**Phase:** Implementation" not in converted

    def test_converts_simple_investigation_to_frontmatter(self):
        """Should convert simple investigation to frontmatter format."""
        content = """# Test Topic

**Date:** 2025-11-30
**Status:** Complete

**TLDR:** Test finding.

## Question
"""
        converted = convert_to_frontmatter(content, FileType.SIMPLE_INVESTIGATION)

        assert converted.startswith("---\n")
        assert 'date: "2025-11-30"' in converted
        assert 'status: "Complete"' in converted
        # Date and Status removed from inline
        assert "**Date:** 2025-11-30" not in converted
        assert "**Status:** Complete" not in converted
        # TLDR preserved
        assert "**TLDR:** Test finding." in converted

    def test_skips_files_with_existing_frontmatter(self):
        """Should skip files that already have frontmatter."""
        content = """---
phase: Complete
status: Active
---

# Workspace: test

**TLDR:** Already migrated.
"""
        converted = convert_to_frontmatter(content, FileType.WORKSPACE)

        # Should return unchanged
        assert converted == content

    def test_preserves_content_after_metadata(self):
        """Should preserve all content after metadata section."""
        content = """# Test Topic

**Date:** 2025-11-30
**Status:** Complete

**TLDR:** Test.

## Question

What is this?

## What I tried

- Thing 1
- Thing 2
"""
        converted = convert_to_frontmatter(content, FileType.SIMPLE_INVESTIGATION)

        # All sections should be preserved
        assert "## Question" in converted
        assert "What is this?" in converted
        assert "## What I tried" in converted
        assert "- Thing 1" in converted
        assert "- Thing 2" in converted


class TestMigrationEdgeCases:
    """Test edge cases in migration."""

    def test_handles_template_placeholders(self):
        """Should handle template placeholder values."""
        content = """# Workspace: [workspace-name]

**Owner:** [Owner name]
**Started:** [YYYY-MM-DD]
**Phase:** [Planning/Implementation/Testing/Complete]
**Status:** [Active/Blocked/Paused/Complete]
"""
        converted = convert_to_frontmatter(content, FileType.WORKSPACE)

        # Should preserve placeholders as strings
        assert 'owner: "[Owner name]"' in converted
        assert 'phase: "[Planning/Implementation/Testing/Complete]"' in converted

    def test_handles_empty_content(self):
        """Should handle empty content gracefully."""
        content = ""
        converted = convert_to_frontmatter(content, FileType.WORKSPACE)
        # Should return as-is or minimal frontmatter
        assert converted == content or converted.startswith("---")

    def test_handles_special_characters_in_values(self):
        """Should properly quote values with special characters."""
        content = """# Workspace: test

**Owner:** Dylan: The Developer
**Started:** 2025-11-30
**Phase:** Implementation
**Status:** Active
"""
        converted = convert_to_frontmatter(content, FileType.WORKSPACE)

        # Should quote value with colon
        assert 'owner: "Dylan: The Developer"' in converted
