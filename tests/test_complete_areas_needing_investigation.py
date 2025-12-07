"""
Tests for parsing and surfacing "Areas needing further investigation" sections.

Defense-in-depth pattern (kn-57afc0): Even if agents don't proactively create
beads issues during work, orchestrator is prompted to create follow-up issues
from investigation files.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestExtractAreasNeedingInvestigation:
    """Tests for extracting 'Areas needing further investigation' from investigation files."""

    def test_extract_areas_from_bold_subsection(self, tmp_path):
        """Test extracting from **Areas needing further investigation:** format."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Implementation Recommendations

**What to implement first:**
- Add the feature

**Things to watch out for:**
- Edge cases

**Areas needing further investigation:**
- How does the auth system handle token refresh?
- What are the rate limiting implications?
- Are there race conditions in the queue processing?

**Success criteria:**
- Tests pass
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        assert len(result) == 3
        assert "How does the auth system handle token refresh?" in result
        assert "What are the rate limiting implications?" in result
        assert "Are there race conditions in the queue processing?" in result

    def test_extract_areas_from_h2_section(self, tmp_path):
        """Test extracting from ## Areas Needing Further Investigation format."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

## Areas Needing Further Investigation

- Explore the webhook retry mechanism
- Check database connection pooling behavior
- Investigate memory usage under load

## References

- Doc 1
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        assert len(result) == 3
        assert "Explore the webhook retry mechanism" in result
        assert "Check database connection pooling behavior" in result
        assert "Investigate memory usage under load" in result

    def test_extract_areas_handles_empty_section(self, tmp_path):
        """Test returns empty list when section exists but has no items."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

**Areas needing further investigation:**

**Success criteria:**
- Tests pass
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        assert len(result) == 0

    def test_extract_areas_returns_none_when_section_missing(self, tmp_path):
        """Test returns None when no areas section exists."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

## Recommendations

Do X.
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is None

    def test_extract_areas_handles_missing_file(self, tmp_path):
        """Test returns None when file doesn't exist."""
        investigation_file = tmp_path / "nonexistent.md"

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is None

    def test_extract_areas_handles_numbered_list(self, tmp_path):
        """Test extracts items from numbered list format."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

**Areas needing further investigation:**
1. First area to explore
2. Second area to explore
3. Third area to explore

**Success criteria:**
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        assert len(result) == 3
        assert "First area to explore" in result
        assert "Second area to explore" in result
        assert "Third area to explore" in result

    def test_extract_areas_strips_list_markers(self, tmp_path):
        """Test that list markers (-, *, 1.) are stripped from items."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

**Areas needing further investigation:**
- Item with dash
* Item with asterisk
1. Item with number

**Next section:**
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        for item in result:
            # Items should not start with markers
            assert not item.startswith('-')
            assert not item.startswith('*')
            assert not item.startswith('1.')

    def test_extract_areas_at_end_of_file(self, tmp_path):
        """Test extracting when section is at end of file."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

**Areas needing further investigation:**
- Last item at end of file
- Another final item
""")

        from orch.complete import extract_areas_needing_investigation
        result = extract_areas_needing_investigation(investigation_file)

        assert result is not None
        assert len(result) == 2
        assert "Last item at end of file" in result


class TestSurfaceAreasNeedingInvestigation:
    """Tests for surfacing areas during agent completion."""

    def test_surface_areas_returns_items_for_investigation_skill(self, tmp_path):
        """Test that investigation skill surfaces areas needing investigation."""
        # Setup investigation file
        inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "2025-12-06-test-investigation.md"
        inv_file.write_text("""# Investigation: Test

## Findings

Found something.

**Areas needing further investigation:**
- How does X work?
- What about Y?
""")

        mock_agent = {
            'id': '2025-12-06-test-investigation',
            'workspace': '.orch/workspace/2025-12-06-test-investigation',
            'skill': 'investigation',
            'primary_artifact': str(inv_file)
        }

        from orch.complete import surface_areas_needing_investigation
        result = surface_areas_needing_investigation(mock_agent, tmp_path)

        assert result is not None
        assert 'areas' in result
        assert len(result['areas']) == 2
        assert "How does X work?" in result['areas']

    def test_surface_areas_returns_none_for_non_investigation_skill(self, tmp_path):
        """Test that feature-impl skill does not surface areas."""
        mock_agent = {
            'id': 'test-feature',
            'workspace': '.orch/workspace/test-feature',
            'skill': 'feature-impl',
        }

        from orch.complete import surface_areas_needing_investigation
        result = surface_areas_needing_investigation(mock_agent, tmp_path)

        assert result is None

    def test_surface_areas_returns_none_when_no_areas_section(self, tmp_path):
        """Test returns None when investigation has no areas section."""
        inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "2025-12-06-no-areas.md"
        inv_file.write_text("""# Investigation: Test

## Findings

Found something.

## Recommendations

Do X.
""")

        mock_agent = {
            'id': '2025-12-06-no-areas',
            'workspace': '.orch/workspace/2025-12-06-no-areas',
            'skill': 'investigation',
            'primary_artifact': str(inv_file)
        }

        from orch.complete import surface_areas_needing_investigation
        result = surface_areas_needing_investigation(mock_agent, tmp_path)

        assert result is None


class TestAreasInCompleteFlow:
    """Tests for areas surfacing integration in complete_agent_work flow."""

    def test_complete_agent_surfaces_areas_needing_investigation(self, tmp_path, capsys):
        """Test that completing investigation surfaces areas needing follow-up."""
        workspace_name = "2025-12-06-test-inv"

        # Setup workspace
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-inv
**Phase:** Complete
""")

        # Setup investigation file with areas
        inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_path_abs = str(inv_file.resolve())
        inv_file.write_text("""# Investigation: Test

## Findings

Found something.

**Areas needing further investigation:**
- Explore caching behavior
- Check auth edge cases

## Recommendations

Do X.
""")

        # Setup git repo
        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active',
            'primary_artifact': inv_path_abs
        }

        from orch.complete import complete_agent_work

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                    )

        assert result['success'] is True

        # Check that areas were output
        captured = capsys.readouterr()
        assert "Areas needing further investigation" in captured.out
        assert "Explore caching behavior" in captured.out
        assert "bd create" in captured.out or "beads" in captured.out.lower()

    def test_complete_agent_includes_areas_in_result(self, tmp_path):
        """Test that areas are included in complete result dict."""
        workspace_name = "2025-12-06-test-areas"

        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Complete\n")

        inv_dir = tmp_path / ".kb" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_path_abs = str(inv_file.resolve())
        inv_file.write_text("""# Investigation

**Areas needing further investigation:**
- Area 1
- Area 2
""")

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active',
            'primary_artifact': inv_path_abs
        }

        from orch.complete import complete_agent_work

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                    )

        assert 'areas_needing_investigation' in result
        assert len(result['areas_needing_investigation']['areas']) == 2
