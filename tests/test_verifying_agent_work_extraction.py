"""
Test: Verifying Agent Work section extraction from CLAUDE.md

TDD: These tests define what "successfully extracted" means.
They will fail initially (RED phase), then pass after implementation (GREEN phase).
"""

import os
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def test_extracted_doc_exists():
    """Test that docs/verifying-agent-work.md exists after extraction."""
    doc_path = PROJECT_ROOT / "docs" / "verifying-agent-work.md"
    assert doc_path.exists(), f"Expected {doc_path} to exist after extraction"


def test_extracted_doc_contains_verification_principles():
    """Test that extracted doc contains the verification principles."""
    doc_path = PROJECT_ROOT / "docs" / "verifying-agent-work.md"
    content = doc_path.read_text()

    # Check for key sections that should be in the extracted content
    assert "Trust by default" in content, "Should contain verification principles"
    assert "Deep verification when:" in content, "Should contain verification triggers"
    assert "Example Violations & Responses" in content, "Should contain examples"
    assert "Responsibility Framing" in content, "Should contain responsibility section"


def test_extracted_doc_has_proper_heading():
    """Test that extracted doc starts with proper H1 heading."""
    doc_path = PROJECT_ROOT / "docs" / "verifying-agent-work.md"
    content = doc_path.read_text()

    # Should start with H1 (single #)
    lines = content.strip().split('\n')
    assert lines[0].startswith('# '), "First line should be H1 heading"
    assert "Verifying Agent Work" in lines[0], "Heading should mention Verifying Agent Work"


def test_claude_md_references_new_doc():
    """Test that CLAUDE.md now references the extracted doc instead of containing full content."""
    claude_md_path = PROJECT_ROOT / "CLAUDE.md"
    content = claude_md_path.read_text()

    # Should contain a reference to the new doc
    assert "docs/verifying-agent-work.md" in content, "CLAUDE.md should reference the new doc location"


def test_claude_md_no_longer_contains_full_section():
    """Test that CLAUDE.md no longer contains the full verification section."""
    claude_md_path = PROJECT_ROOT / "CLAUDE.md"
    content = claude_md_path.read_text()

    # Should NOT contain the detailed examples (these should be in the extracted doc)
    # We check for a specific example detail that should only be in the extracted doc
    assert "Agent skipped update_status calls" not in content, \
        "CLAUDE.md should not contain example details (should be in extracted doc)"


def test_extracted_doc_contains_all_examples():
    """Test that extracted doc contains all three example violations."""
    doc_path = PROJECT_ROOT / "docs" / "verifying-agent-work.md"
    content = doc_path.read_text()

    # All three examples should be present
    assert "Example 1: Agent skipped update_status calls" in content
    assert "Example 2: Agent marked Phase: Complete before validation" in content
    assert "Example 3: Agent created workspace in wrong location" in content


def test_extracted_doc_preserves_formatting():
    """Test that extracted doc preserves markdown formatting (lists, bold, etc)."""
    doc_path = PROJECT_ROOT / "docs" / "verifying-agent-work.md"
    content = doc_path.read_text()

    # Check that formatting is preserved
    assert "**Deep verification when:**" in content, "Should preserve bold formatting"
    assert "- ⚠️" in content, "Should preserve list items with emoji"
    assert "**Observed:**" in content, "Should preserve bold in examples"
    assert "- ✅" in content, "Should preserve checkmarks in lists"
