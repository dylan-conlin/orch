"""
Tests for orch synthesis module.

Tests synthesis promotion workflow for closing the synthesis→action loop.
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from orch.synthesis import (
    parse_synthesis_file,
    create_decision_document,
    create_roadmap_item,
    mark_investigations_superseded,
    update_synthesis_status,
    update_synthesis_resolution_status,
)


class TestParseSynthesisFile:
    """Tests for parse_synthesis_file function."""

    def test_raises_when_file_not_exists(self, tmp_path):
        """Should raise FileNotFoundError when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            parse_synthesis_file(tmp_path / 'nonexistent.md')

    def test_parses_status(self, tmp_path):
        """Should extract Status field."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("**Status:** Pending")
        result = parse_synthesis_file(synthesis_file)
        assert result['status'] == 'Pending'

    def test_parses_decision_link(self, tmp_path):
        """Should extract Decision field with backtick format."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("**Decision:** `my-decision-file`")
        result = parse_synthesis_file(synthesis_file)
        assert result['decision'] == 'my-decision-file'

    def test_parses_title(self, tmp_path):
        """Should extract title from Pattern Synthesis heading."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("# Pattern Synthesis: Test Topic\n\nContent")
        result = parse_synthesis_file(synthesis_file)
        assert result['title'] == 'Test Topic'

    def test_uses_filename_as_fallback_title(self, tmp_path):
        """Should use filename stem when no title heading found."""
        synthesis_file = tmp_path / 'my-topic.md'
        synthesis_file.write_text("Content without title heading")
        result = parse_synthesis_file(synthesis_file)
        assert result['title'] == 'my-topic'

    def test_parses_recommendation_section(self, tmp_path):
        """Should extract Recommendation section content."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("""
### Recommendation

Do this thing.
It has multiple lines.

## Next Section
""")
        result = parse_synthesis_file(synthesis_file)
        assert 'Do this thing' in result['recommendation']
        assert 'multiple lines' in result['recommendation']

    def test_parses_source_investigations(self, tmp_path):
        """Should extract investigation file references."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("""
Some content referencing [investigation](investigations/simple/2025-01-01-topic.md)
and another [one](investigations/audits/2025-01-02-audit.md).
""")
        result = parse_synthesis_file(synthesis_file)
        assert len(result['source_investigations']) == 2
        assert 'investigations/simple/2025-01-01-topic.md' in result['source_investigations']


class TestCreateDecisionDocument:
    """Tests for create_decision_document function."""

    def test_generates_decision_path(self, tmp_path):
        """Should generate decision path with date prefix."""
        synthesis_path = tmp_path / '2025-01-15-topic.md'
        synthesis_data = {
            'title': 'Test Decision',
            'recommendation': 'Do this',
            'source_investigations': [],
        }

        decision_path, content = create_decision_document(
            synthesis_data, synthesis_path, tmp_path
        )

        assert decision_path.parent.name == 'decisions'
        assert 'topic.md' in decision_path.name

    def test_generates_decision_content(self, tmp_path):
        """Should generate decision document content."""
        synthesis_path = tmp_path / '2025-01-15-topic.md'
        synthesis_data = {
            'title': 'Test Decision',
            'recommendation': 'Implement feature X',
            'source_investigations': ['investigations/simple/inv1.md'],
        }

        decision_path, content = create_decision_document(
            synthesis_data, synthesis_path, tmp_path
        )

        assert '# Decision: Test Decision' in content
        assert 'Implement feature X' in content
        assert 'investigations/simple/inv1.md' in content


class TestCreateRoadmapItem:
    """Tests for create_roadmap_item function."""

    def test_generates_roadmap_text(self, tmp_path):
        """Should generate formatted ROADMAP item."""
        synthesis_data = {
            'title': 'Implement Feature',
            'source_investigations': ['investigations/simple/inv1.md'],
        }
        decision_path = tmp_path / 'decisions' / '2025-01-15-feature.md'

        result = create_roadmap_item(synthesis_data, decision_path)

        assert '** TODO' in result
        assert 'Implement Feature' in result
        assert ':synthesis:' in result
        assert 'investigations/simple/inv1.md' in result


class TestMarkInvestigationsSuperseded:
    """Tests for mark_investigations_superseded function."""

    def test_updates_complete_investigations(self, tmp_path):
        """Should update Status to Superseded for complete investigations."""
        # Create project structure
        inv_dir = tmp_path / '.orch' / 'investigations' / 'simple'
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / '2025-01-01-topic.md'
        inv_file.write_text("**Status:** Complete\n\nContent")

        synthesis_path = tmp_path / 'synthesis.md'
        inv_paths = ['investigations/simple/2025-01-01-topic.md']

        updated = mark_investigations_superseded(inv_paths, synthesis_path, tmp_path)

        assert len(updated) == 1
        assert 'Superseded' in inv_file.read_text()

    def test_skips_already_superseded(self, tmp_path):
        """Should skip investigations already marked as superseded."""
        inv_dir = tmp_path / '.orch' / 'investigations' / 'simple'
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / '2025-01-01-topic.md'
        inv_file.write_text("**Status:** Superseded\n\nContent")

        synthesis_path = tmp_path / 'synthesis.md'
        inv_paths = ['investigations/simple/2025-01-01-topic.md']

        updated = mark_investigations_superseded(inv_paths, synthesis_path, tmp_path)

        assert len(updated) == 0

    def test_skips_missing_files(self, tmp_path):
        """Should skip investigations that don't exist."""
        synthesis_path = tmp_path / 'synthesis.md'
        inv_paths = ['investigations/simple/nonexistent.md']

        updated = mark_investigations_superseded(inv_paths, synthesis_path, tmp_path)

        assert len(updated) == 0


class TestUpdateSynthesisStatus:
    """Tests for update_synthesis_status function."""

    def test_updates_status_field(self, tmp_path):
        """Should update Status field value."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("**Status:** Pending\n\nContent")

        update_synthesis_status(synthesis_file, 'Accepted')

        content = synthesis_file.read_text()
        assert '**Status:** Accepted' in content
        assert '**Status:** Pending' not in content

    def test_adds_decision_link(self, tmp_path):
        """Should add Decision field when provided."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("**Status:** Pending\n\nContent")
        decision_path = Path('.orch/decisions/my-decision.md')

        update_synthesis_status(synthesis_file, 'Accepted', decision_path)

        content = synthesis_file.read_text()
        assert '**Decision:**' in content
        assert 'my-decision.md' in content

    def test_adds_accepted_date(self, tmp_path):
        """Should add Accepted date when status is Accepted."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("**Status:** Pending\n**Decision:** `test`\n\nContent")
        decision_path = Path('.orch/decisions/my-decision.md')

        update_synthesis_status(synthesis_file, 'Accepted', decision_path)

        content = synthesis_file.read_text()
        assert '**Accepted:**' in content


class TestUpdateSynthesisResolutionStatus:
    """Tests for update_synthesis_resolution_status function."""

    def test_updates_checkboxes(self, tmp_path):
        """Should check off resolution status checkboxes."""
        synthesis_file = tmp_path / 'synthesis.md'
        synthesis_file.write_text("""
## Resolution Status

- [ ] Recommendation accepted
- [ ] Decision document created
- [ ] ROADMAP item created
""")

        update_synthesis_resolution_status(synthesis_file)

        content = synthesis_file.read_text()
        assert '- [x] Recommendation accepted' in content
        assert '- [x] Decision document created' in content
        assert '- [x] ROADMAP item created' in content
