"""
Tests for Markdown ROADMAP parser.

Tests cover:
1. Basic Markdown ROADMAP parsing
2. Priority extraction from [P0], [P1], [P2]
3. Tag extraction from backtick blocks
4. Metadata parsing from inline format
5. Item marking as done
6. Format detection and integration
"""

import pytest
from pathlib import Path
from orch.roadmap_markdown import (
    RoadmapItem,
    parse_roadmap_markdown,
    find_roadmap_item_for_workspace,
    mark_roadmap_item_done,
)
from orch.roadmap_utils import (
    detect_roadmap_format,
    parse_roadmap,
    find_roadmap_file,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_markdown_roadmap():
    """Sample ROADMAP.md content for testing."""
    return """# Meta-Orchestration Roadmap

**Stats:** 3 active items (1 P0, 1 P1, 1 P2)

This roadmap is priority-sorted: highest priority items first.

---

## Active Work

### [P0] Critical bug blocking production

**Tags:** `phase-3` `tool` `bug`

**Metadata:**
- Project: orch-knowledge
- Workspace: fix-critical-bug
- Skill: systematic-debugging
- Effort: 2-4h
- Created: 2025-11-15

**Description:**

Problem: orch spawn fails when git has uncommitted changes
Impact: Blocking all spawns requiring clean git state

---

### [P1] SPAWN_CONTEXT.md as first-class artifact

**Tags:** `phase-3` `infrastructure`

**Metadata:**
- Project: orch-knowledge
- Workspace: spawn-context-first-class
- Skill: feature-impl
- Effort: 4-6h
- Created: 2025-11-17

**Description:**

Elevate SPAWN_CONTEXT.md from display bug workaround to strategic orchestrator artifact.

---

### [P2] Improve error messages

**Tags:** `phase-3` `tool` `ux`

**Metadata:**
- Project: orch-knowledge
- Workspace: improve-error-messages
- Skill: feature-impl
- Effort: 1-2h

**Description:**

Add actionable suggestions to error messages.

---

## Completed Work

### ✅ [P0] Fix tmux window tracking

**Completed:** 2025-11-12

**Tags:** `phase-3` `tool` `bug`

**Metadata:**
- Project: orch-knowledge
- Workspace: fix-tmux-registry-tracking
- Skill: systematic-debugging
- Effort: 3h
- Created: 2025-11-10

**Description:**

Investigation findings show no actual bug.

---

## Phase Reference

**Phase 3: Current Work**
- Focus: Critical bug fixes, infrastructure improvements
- Items: See `phase-3` tag in Active Work above
"""


@pytest.fixture
def temp_markdown_roadmap(tmp_path, sample_markdown_roadmap):
    """Create a temporary ROADMAP.md file for testing."""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(sample_markdown_roadmap)
    return roadmap_file


# ============================================================================
# PARSING TESTS
# ============================================================================

def test_parse_markdown_basic(temp_markdown_roadmap):
    """Test basic Markdown parsing functionality."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    assert len(items) == 4  # 3 active + 1 completed
    assert all(isinstance(item, RoadmapItem) for item in items)


def test_parse_markdown_priority_extraction(temp_markdown_roadmap):
    """Test priority extraction from [P0], [P1], [P2] syntax."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    # Find items by title
    critical_bug = next(item for item in items if "Critical bug" in item.title)
    spawn_context = next(item for item in items if "SPAWN_CONTEXT" in item.title)
    error_messages = next(item for item in items if "error messages" in item.title)

    assert critical_bug.priority == 0
    assert spawn_context.priority == 1
    assert error_messages.priority == 2


def test_parse_markdown_tags(temp_markdown_roadmap):
    """Test tag extraction from backtick blocks."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    critical_bug = next(item for item in items if "Critical bug" in item.title)
    assert "phase-3" in critical_bug.tags
    assert "tool" in critical_bug.tags
    assert "bug" in critical_bug.tags


def test_parse_markdown_metadata(temp_markdown_roadmap):
    """Test metadata extraction from inline format."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    critical_bug = next(item for item in items if "Critical bug" in item.title)
    assert critical_bug.properties["Project"] == "orch-knowledge"
    assert critical_bug.properties["Workspace"] == "fix-critical-bug"
    assert critical_bug.properties["Skill"] == "systematic-debugging"
    assert critical_bug.properties["Effort"] == "2-4h"
    assert critical_bug.properties["Created"] == "2025-11-15"


def test_parse_markdown_description(temp_markdown_roadmap):
    """Test description extraction."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    critical_bug = next(item for item in items if "Critical bug" in item.title)
    assert "orch spawn fails" in critical_bug.description
    assert "Blocking all spawns" in critical_bug.description


def test_parse_markdown_completed_items(temp_markdown_roadmap):
    """Test parsing of completed items."""
    items = parse_roadmap_markdown(temp_markdown_roadmap)

    completed = [item for item in items if item.is_done]
    assert len(completed) == 1

    done_item = completed[0]
    assert "Fix tmux window tracking" in done_item.title
    assert done_item.closed_date == "2025-11-12"
    assert done_item.priority == 0


# ============================================================================
# QUERY TESTS
# ============================================================================

def test_find_item_for_workspace(temp_markdown_roadmap):
    """Test finding items by workspace name."""
    item = find_roadmap_item_for_workspace("fix-critical-bug", temp_markdown_roadmap)

    assert item is not None
    assert "Critical bug" in item.title
    assert item.properties["Workspace"] == "fix-critical-bug"


def test_find_item_for_workspace_not_found(temp_markdown_roadmap):
    """Test finding non-existent workspace."""
    item = find_roadmap_item_for_workspace("nonexistent-workspace", temp_markdown_roadmap)
    assert item is None


# ============================================================================
# UPDATE TESTS
# ============================================================================

def test_mark_item_done_by_workspace(temp_markdown_roadmap):
    """Test marking item done by workspace name."""
    success = mark_roadmap_item_done(
        temp_markdown_roadmap,
        workspace_name="spawn-context-first-class"
    )

    assert success

    # Verify item was marked done
    items = parse_roadmap_markdown(temp_markdown_roadmap)
    done_item = next(item for item in items if "SPAWN_CONTEXT" in item.title)

    assert done_item.is_done
    assert done_item.closed_date is not None  # Should have today's date


def test_mark_item_done_not_found(temp_markdown_roadmap):
    """Test marking non-existent item done."""
    success = mark_roadmap_item_done(
        temp_markdown_roadmap,
        workspace_name="nonexistent-workspace"
    )

    assert not success


# ============================================================================
# FORMAT DETECTION TESTS
# ============================================================================

def test_detect_markdown_format(temp_markdown_roadmap):
    """Test format detection for .md files."""
    format_type = detect_roadmap_format(temp_markdown_roadmap)
    assert format_type == "markdown"


def test_detect_org_format(tmp_path):
    """Test format detection for .org files."""
    org_file = tmp_path / "ROADMAP.org"
    org_file.write_text("#+TITLE: Test")

    format_type = detect_roadmap_format(org_file)
    assert format_type == "org"


def test_parse_roadmap_auto_detect_markdown(temp_markdown_roadmap):
    """Test auto-detection and parsing of Markdown format."""
    items = parse_roadmap(temp_markdown_roadmap)

    assert len(items) == 4
    assert all(isinstance(item, RoadmapItem) for item in items)


def test_find_roadmap_file_prefers_org_by_default(tmp_path, sample_markdown_roadmap):
    """Test that find_roadmap_file prefers .org over .md by default (no config)."""
    # Create both formats
    md_file = tmp_path / "ROADMAP.md"
    md_file.write_text(sample_markdown_roadmap)

    org_file = tmp_path / "ROADMAP.org"
    org_file.write_text("#+TITLE: Test")

    # Mock no config (default behavior)
    from unittest.mock import patch
    with patch('orch.roadmap_utils.get_roadmap_format', return_value='org'):
        found = find_roadmap_file(tmp_path)
        assert found == org_file  # Should prefer org by default


def test_find_roadmap_file_falls_back_to_org(tmp_path):
    """Test that find_roadmap_file falls back to .org if .md doesn't exist."""
    org_file = tmp_path / "ROADMAP.org"
    org_file.write_text("#+TITLE: Test")

    found = find_roadmap_file(tmp_path)

    assert found == org_file


def test_find_roadmap_file_returns_none(tmp_path):
    """Test that find_roadmap_file returns None if neither format exists."""
    found = find_roadmap_file(tmp_path)
    assert found is None


def test_find_roadmap_file_respects_config_markdown(tmp_path, sample_markdown_roadmap):
    """Test that find_roadmap_file respects config preference for markdown."""
    # Create both formats
    md_file = tmp_path / "ROADMAP.md"
    md_file.write_text(sample_markdown_roadmap)

    org_file = tmp_path / "ROADMAP.org"
    org_file.write_text("#+TITLE: Test")

    # Mock config set to markdown
    from unittest.mock import patch
    with patch('orch.roadmap_utils.get_roadmap_format', return_value='markdown'):
        found = find_roadmap_file(tmp_path)
        assert found == md_file  # Should prefer markdown when config says so


def test_find_roadmap_file_respects_config_org(tmp_path, sample_markdown_roadmap):
    """Test that find_roadmap_file respects config preference for org."""
    # Create both formats
    md_file = tmp_path / "ROADMAP.md"
    md_file.write_text(sample_markdown_roadmap)

    org_file = tmp_path / "ROADMAP.org"
    org_file.write_text("#+TITLE: Test")

    # Mock config set to org
    from unittest.mock import patch
    with patch('orch.roadmap_utils.get_roadmap_format', return_value='org'):
        found = find_roadmap_file(tmp_path)
        assert found == org_file  # Should prefer org when config says so


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

def test_parse_empty_file(tmp_path):
    """Test parsing empty Markdown file."""
    empty_file = tmp_path / "ROADMAP.md"
    empty_file.write_text("")

    items = parse_roadmap_markdown(empty_file)
    assert items == []


def test_parse_no_items(tmp_path):
    """Test parsing file with sections but no items."""
    content = """# Roadmap

## Active Work

## Completed Work
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(content)

    items = parse_roadmap_markdown(roadmap_file)
    assert items == []


def test_parse_item_without_metadata(tmp_path):
    """Test parsing item without metadata section."""
    content = """# Roadmap

## Active Work

### [P1] Simple task

**Description:**

Just a description.

---
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(content)

    items = parse_roadmap_markdown(roadmap_file)
    assert len(items) == 1
    assert items[0].title == "Simple task"
    assert items[0].priority == 1
    assert items[0].properties == {}  # No metadata


def test_parse_item_without_tags(tmp_path):
    """Test parsing item without tags."""
    content = """# Roadmap

## Active Work

### [P1] Untagged task

**Description:**

No tags here.

---
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(content)

    items = parse_roadmap_markdown(roadmap_file)
    assert len(items) == 1
    assert items[0].tags == []  # No tags
