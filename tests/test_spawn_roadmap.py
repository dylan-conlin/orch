"""
Tests for ROADMAP.org parsing functionality in orch spawn.

Tests the ROADMAP parsing mechanism including:
- Parsing ROADMAP.org files for TODO items
- Finding ROADMAP items by title (exact and substring match)
- Extracting properties from ROADMAP entries
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import find_roadmap_item


class TestRoadmapParsing:
    """Tests for ROADMAP.org parsing functionality."""

    def test_parse_roadmap_file(self, tmp_path):
        """Test parsing ROADMAP.org file."""
        from orch.roadmap import parse_roadmap_file

        # Create test ROADMAP.org
        roadmap_file = tmp_path / "ROADMAP.org"
        roadmap_file.write_text("""* Phase 1

** TODO Implement Authentication
:PROPERTIES:
:Created: 2025-11-07
:Phase: Phase 1
:Project: test-app
:Workspace: auth-implementation
:Skill: implement-feature
:Effort: 4-6 hours
:END:

Implement JWT-based authentication with refresh tokens.
See ADR-001 for context.

** DONE Fix Database Bug
:PROPERTIES:
:Created: 2025-11-06
:Phase: Phase 1
:Project: test-app
:Workspace: debug-db-bug
:Skill: systematic-debugging
:END:

Database was not persisting sessions correctly.

* Phase 2

** TODO Add Email Notifications
:PROPERTIES:
:Created: 2025-11-08
:Phase: Phase 2
:Project: test-app
:Workspace: email-notifications
:END:

Send email notifications for important events.
""")

        items = parse_roadmap_file(roadmap_file)

        assert len(items) == 3

        # Check first item
        assert items[0].title == "Implement Authentication"
        assert items[0].properties['Project'] == "test-app"
        assert items[0].properties['Workspace'] == "auth-implementation"
        assert items[0].properties['Skill'] == "implement-feature"
        assert "JWT-based authentication" in items[0].description

        # Check second item
        assert items[1].title == "Fix Database Bug"
        assert items[1].properties['Skill'] == "systematic-debugging"

        # Check third item
        assert items[2].title == "Add Email Notifications"
        assert items[2].properties['Project'] == "test-app"

    def test_find_roadmap_item_exact_match(self, tmp_path):
        """Test finding ROADMAP item by exact title match."""
        # Create test ROADMAP.org
        roadmap_file = tmp_path / "ROADMAP.org"
        roadmap_file.write_text("""** TODO Test Item
:PROPERTIES:
:Project: test
:Workspace: test-workspace
:END:

Test description.
""")

        item = find_roadmap_item("Test Item", roadmap_path=roadmap_file)

        assert item is not None
        assert item.title == "Test Item"
        assert item.properties['Project'] == "test"

    def test_find_roadmap_item_substring_match(self, tmp_path):
        """Test finding ROADMAP item by substring match."""
        # Create test ROADMAP.org
        roadmap_file = tmp_path / "ROADMAP.org"
        roadmap_file.write_text("""** TODO Implement User Authentication System
:PROPERTIES:
:Project: test
:Workspace: auth-system
:END:

Description.
""")

        item = find_roadmap_item("Authentication", roadmap_path=roadmap_file)

        assert item is not None
        assert "Authentication" in item.title

    def test_find_roadmap_item_not_found(self, tmp_path):
        """Test finding nonexistent ROADMAP item."""
        # Create empty ROADMAP.org
        roadmap_file = tmp_path / "ROADMAP.org"
        roadmap_file.write_text("")

        item = find_roadmap_item("Nonexistent", roadmap_path=roadmap_file)

        assert item is None
