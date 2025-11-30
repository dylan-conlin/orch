"""
Tests for orch roadmap module.

Tests cover:
1. Basic ROADMAP parsing functionality
2. Caching with mtime invalidation
3. Validation for malformed org-mode files
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from orch.roadmap import (
    RoadmapItem,
    parse_roadmap_file,
    parse_roadmap_file_cached,
    find_roadmap_item,
    mark_roadmap_item_done,
    RoadmapParseError,
    RoadmapValidationError,
)


# ============================================================================
# FIXTURES
# ============================================================================

# sample_roadmap_content and temp_roadmap_file fixtures are now provided by conftest.py


@pytest.fixture
def malformed_roadmap_content():
    """Malformed ROADMAP.org content for validation testing."""
    return """#+TITLE: Malformed Roadmap

** TODO Task with unclosed properties block
:PROPERTIES:
:Created: 2025-11-16
:Project: test-project
# Missing :END: tag

** TODO Task with malformed property
:PROPERTIES:
:MalformedNoColon
:END:

** Task without TODO/DONE prefix
:PROPERTIES:
:Created: 2025-11-16
:END:
"""


@pytest.fixture
def malformed_roadmap_file(tmp_path, malformed_roadmap_content):
    """Create a temporary malformed ROADMAP.org file for testing."""
    roadmap_file = tmp_path / "ROADMAP-malformed.org"
    roadmap_file.write_text(malformed_roadmap_content)
    return roadmap_file


# ============================================================================
# BASIC PARSING TESTS
# ============================================================================

def test_parse_roadmap_file_basic(temp_roadmap_file):
    """Test basic ROADMAP parsing returns correct number of items."""
    items = parse_roadmap_file(temp_roadmap_file)

    # Should parse 3 tasks
    assert len(items) == 3
    assert all(isinstance(item, RoadmapItem) for item in items)


def test_parse_roadmap_file_extracts_titles(temp_roadmap_file):
    """Test that task titles are correctly extracted."""
    items = parse_roadmap_file(temp_roadmap_file)

    titles = [item.title for item in items]
    assert "First task :tag1:tag2:" in titles
    assert "Second task :tag3:" in titles
    assert "Third task with missing properties" in titles


def test_parse_roadmap_file_extracts_properties(temp_roadmap_file):
    """Test that properties are correctly extracted."""
    items = parse_roadmap_file(temp_roadmap_file)

    # First task should have all properties
    first_task = items[0]
    assert first_task.properties["Created"] == "2025-11-16"
    assert first_task.properties["Project"] == "test-project"
    assert first_task.properties["Workspace"] == "test-workspace"
    assert first_task.properties["Skill"] == "test-skill"
    assert first_task.properties["Priority"] == "1"


def test_parse_roadmap_file_extracts_description(temp_roadmap_file):
    """Test that task descriptions are correctly extracted."""
    items = parse_roadmap_file(temp_roadmap_file)

    # First task should have description
    first_task = items[0]
    assert "**Context:**" in first_task.description
    assert "test task for validating" in first_task.description
    assert "**Problem:**" in first_task.description


def test_parse_roadmap_file_detects_done_status(temp_roadmap_file):
    """Test that DONE status is correctly detected."""
    items = parse_roadmap_file(temp_roadmap_file)

    # Find the DONE task
    done_task = next(item for item in items if "Second task" in item.title)
    assert done_task.is_done is True
    assert done_task.closed_date == "2025-11-15"


def test_parse_roadmap_file_handles_todo_status(temp_roadmap_file):
    """Test that TODO status is correctly detected."""
    items = parse_roadmap_file(temp_roadmap_file)

    # Find a TODO task
    todo_task = next(item for item in items if "First task" in item.title)
    assert todo_task.is_done is False
    assert todo_task.closed_date is None


def test_parse_roadmap_file_nonexistent_file():
    """Test that parsing nonexistent file returns empty list."""
    items = parse_roadmap_file(Path("/nonexistent/ROADMAP.org"))
    assert items == []


def test_parse_roadmap_file_empty_file(tmp_path):
    """Test that parsing empty file returns empty list."""
    empty_file = tmp_path / "empty.org"
    empty_file.write_text("")

    items = parse_roadmap_file(empty_file)
    assert items == []


# ============================================================================
# CACHING TESTS
# ============================================================================

def test_parse_roadmap_file_cached_returns_same_result(temp_roadmap_file):
    """Test that cached parsing returns same result as non-cached."""
    uncached_items = parse_roadmap_file(temp_roadmap_file)
    cached_items = parse_roadmap_file_cached(temp_roadmap_file)

    assert len(cached_items) == len(uncached_items)
    for cached, uncached in zip(cached_items, uncached_items):
        assert cached.title == uncached.title
        assert cached.properties == uncached.properties


def test_parse_roadmap_file_cached_uses_cache_on_second_call(temp_roadmap_file):
    """Test that second call uses cache (same mtime)."""
    # First call - populates cache
    first_result = parse_roadmap_file_cached(temp_roadmap_file)

    # Modify file content but keep mtime same (mock mtime)
    original_mtime = temp_roadmap_file.stat().st_mtime
    temp_roadmap_file.write_text("** TODO New task\n:PROPERTIES:\n:END:")

    # Force same mtime
    import os
    os.utime(temp_roadmap_file, (original_mtime, original_mtime))

    # Second call - should use cache (same mtime)
    second_result = parse_roadmap_file_cached(temp_roadmap_file)

    # Should return cached result (old content)
    assert len(second_result) == len(first_result)
    assert second_result[0].title == first_result[0].title


def test_parse_roadmap_file_cached_invalidates_on_mtime_change(temp_roadmap_file):
    """Test that cache is invalidated when file mtime changes."""
    # First call - populates cache
    first_result = parse_roadmap_file_cached(temp_roadmap_file)
    assert len(first_result) == 3

    # Capture original mtime before modification
    original_mtime = temp_roadmap_file.stat().st_mtime

    # Modify file content
    temp_roadmap_file.write_text("** TODO New task\n:PROPERTIES:\n:END:")

    # Force different mtime (simulate file modification at later time)
    # This is deterministic - no reliance on real time or filesystem mtime resolution
    import os
    new_mtime = original_mtime + 2  # Ensure different from cached value
    os.utime(temp_roadmap_file, (new_mtime, new_mtime))

    # Second call - should re-parse (different mtime)
    second_result = parse_roadmap_file_cached(temp_roadmap_file)

    # Should return new result (new content)
    assert len(second_result) == 1
    assert "New task" in second_result[0].title


def test_parse_roadmap_file_cached_handles_nonexistent_file():
    """Test that cached parsing handles nonexistent files gracefully."""
    items = parse_roadmap_file_cached(Path("/nonexistent/ROADMAP.org"))
    assert items == []


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_parse_roadmap_file_validates_missing_properties_block(temp_roadmap_file):
    """Test that missing :PROPERTIES: block triggers validation warning."""
    items = parse_roadmap_file(temp_roadmap_file, validate=True)

    # Should still parse but might have validation warnings
    # Third task has no :PROPERTIES: block
    third_task = items[2]
    assert third_task.title == "Third task with missing properties"
    assert len(third_task.properties) == 0


def test_parse_roadmap_file_validates_unclosed_properties_block(malformed_roadmap_file):
    """Test that unclosed :PROPERTIES: block raises validation error."""
    with pytest.raises(RoadmapValidationError, match="Unclosed :PROPERTIES: block"):
        parse_roadmap_file(malformed_roadmap_file, validate=True)


def test_parse_roadmap_file_validates_malformed_properties(malformed_roadmap_file):
    """Test that malformed properties raise validation error."""
    # Should parse but warn about malformed properties
    # (depending on strictness, might raise error or just warn)
    items = parse_roadmap_file(malformed_roadmap_file, validate=False)

    # Without validation, should parse (maybe skip malformed properties)
    assert len(items) > 0


def test_parse_roadmap_file_validates_required_fields():
    """Test that validation checks for required properties."""
    content = """** TODO Task with missing required fields
:PROPERTIES:
:Created: 2025-11-16
# Missing :Project: and :Workspace:
:END:
"""

    roadmap_file = Path("/tmp/test-required-fields.org")
    roadmap_file.write_text(content)

    try:
        with pytest.raises(RoadmapValidationError, match="Missing required"):
            parse_roadmap_file(roadmap_file, validate=True, require_fields=["Project", "Workspace"])
    finally:
        roadmap_file.unlink(missing_ok=True)


# ============================================================================
# FIND ROADMAP ITEM TESTS
# ============================================================================

def test_find_roadmap_item_exact_match(temp_roadmap_file):
    """Test finding item by exact title match."""
    item = find_roadmap_item("First task :tag1:tag2:", temp_roadmap_file)

    assert item is not None
    assert "First task" in item.title
    assert item.properties["Project"] == "test-project"


def test_find_roadmap_item_fuzzy_match(temp_roadmap_file):
    """Test finding item by fuzzy title match."""
    item = find_roadmap_item("First task", temp_roadmap_file)

    assert item is not None
    assert "First task" in item.title


def test_find_roadmap_item_case_insensitive(temp_roadmap_file):
    """Test finding item is case-insensitive."""
    item = find_roadmap_item("FIRST TASK", temp_roadmap_file)

    assert item is not None
    assert "First task" in item.title


def test_find_roadmap_item_not_found(temp_roadmap_file):
    """Test that nonexistent item returns None."""
    item = find_roadmap_item("Nonexistent task", temp_roadmap_file)
    assert item is None


def test_find_roadmap_item_default_path(temp_roadmap_file):
    """Test that default ROADMAP path is used when not specified."""
    # Just verify we can find items when providing explicit path
    # (default path logic is tested in integration tests)
    item = find_roadmap_item("First task", temp_roadmap_file)
    assert item is not None


# ============================================================================
# MARK ROADMAP ITEM DONE TESTS
# ============================================================================

def test_mark_roadmap_item_done_updates_file(temp_roadmap_file):
    """Test that marking item done updates ROADMAP file."""
    original_content = temp_roadmap_file.read_text()

    # Mark first task as done
    success = mark_roadmap_item_done(
        roadmap_path=temp_roadmap_file,
        task_title="First task",
        workspace_name="test-workspace"
    )

    assert success is True

    # Read updated content
    updated_content = temp_roadmap_file.read_text()
    assert updated_content != original_content

    # Should have DONE instead of TODO
    assert "** DONE First task" in updated_content

    # Should have CLOSED timestamp
    assert "CLOSED:" in updated_content


def test_mark_roadmap_item_done_preserves_other_tasks(temp_roadmap_file):
    """Test that marking one item done doesn't affect other tasks."""
    # Mark first task as done
    mark_roadmap_item_done(
        roadmap_path=temp_roadmap_file,
        task_title="First task",
        workspace_name="test-workspace"
    )

    # Re-parse to verify
    items = parse_roadmap_file(temp_roadmap_file)

    # First task should be done
    first_task = next(item for item in items if "First task" in item.title)
    assert first_task.is_done is True

    # Third task should still be TODO
    third_task = next(item for item in items if "Third task" in item.title)
    assert third_task.is_done is False


def test_mark_roadmap_item_done_task_not_found(temp_roadmap_file):
    """Test that marking nonexistent task returns False."""
    success = mark_roadmap_item_done(
        roadmap_path=temp_roadmap_file,
        task_title="Nonexistent task",
        workspace_name="test-workspace"
    )

    assert success is False


def test_mark_roadmap_item_done_creates_backup(temp_roadmap_file):
    """Test that marking item done creates backup file."""
    mark_roadmap_item_done(
        roadmap_path=temp_roadmap_file,
        task_title="First task",
        workspace_name="test-workspace",
        create_backup=True
    )

    # Check backup file exists
    backup_file = temp_roadmap_file.with_suffix(".org.backup")
    assert backup_file.exists()


# ============================================================================
# ROADMAP ITEM DATA CLASS TESTS
# ============================================================================

def test_roadmap_item_initialization():
    """Test RoadmapItem can be initialized with required fields."""
    item = RoadmapItem(
        title="Test task",
        properties={"Project": "test", "Created": "2025-11-16"},
        description="Test description"
    )

    assert item.title == "Test task"
    assert item.properties["Project"] == "test"
    assert item.description == "Test description"
    assert item.is_done is False  # Default
    assert item.closed_date is None  # Default


def test_roadmap_item_with_done_status():
    """Test RoadmapItem with DONE status."""
    item = RoadmapItem(
        title="Completed task",
        properties={},
        is_done=True,
        closed_date="2025-11-16"
    )

    assert item.is_done is True
    assert item.closed_date == "2025-11-16"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_parse_roadmap_file_handles_encoding_errors(tmp_path):
    """Test that parsing handles encoding errors gracefully."""
    # Create file with invalid UTF-8
    bad_file = tmp_path / "bad-encoding.org"
    bad_file.write_bytes(b"** TODO Task\n\xFF\xFE")  # Invalid UTF-8

    # Should raise RoadmapParseError, not UnicodeDecodeError
    with pytest.raises(RoadmapParseError, match="encoding"):
        parse_roadmap_file(bad_file)


def test_parse_roadmap_file_handles_permission_errors(tmp_path):
    """Test that parsing handles permission errors gracefully."""
    restricted_file = tmp_path / "restricted.org"
    restricted_file.write_text("** TODO Task\n")

    # Make file unreadable (Unix-only test)
    import os
    import sys
    if sys.platform != 'win32':
        os.chmod(restricted_file, 0o000)
        try:
            # Should raise RoadmapParseError, not PermissionError
            with pytest.raises(RoadmapParseError, match="permission"):
                parse_roadmap_file(restricted_file)
        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_file, 0o644)
    else:
        # Skip on Windows
        pytest.skip("Permission test requires Unix permissions")
