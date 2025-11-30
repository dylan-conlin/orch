"""
Tests for orch instructions module.

Tests orchestrator instruction management including:
- Template directory discovery
- Available/current/missing instruction detection
- Content parsing and insertion points
- Marker formatting and migration
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from orch.instructions import (
    get_templates_directory,
    get_available_instructions,
    get_current_instructions,
    get_missing_instructions,
    find_insertion_point,
    format_instruction_marker,
    validate_instruction_exists,
    get_project_claude_md_path,
    get_project_agents_md_path,
    get_project_gemini_md_path,
    get_project_context_files,
    create_empty_instruction_block,
    migrate_markers_to_instruction,
    remove_instruction_from_content,
)


class TestGetTemplatesDirectory:
    """Tests for get_templates_directory function."""

    def test_returns_home_orch_templates_orchestrator(self):
        """Should return ~/.orch/templates/orchestrator path."""
        result = get_templates_directory()
        assert result == Path.home() / '.orch' / 'templates' / 'orchestrator'


class TestGetAvailableInstructions:
    """Tests for get_available_instructions function."""

    def test_returns_empty_when_directory_not_exists(self, tmp_path):
        """Should return empty list when templates directory doesn't exist."""
        with patch('orch.instructions.get_templates_directory', return_value=tmp_path / 'nonexistent'):
            result = get_available_instructions()
            assert result == []

    def test_finds_markdown_files(self, tmp_path):
        """Should find all .md files in templates directory."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()

        (templates_dir / 'instruction-one.md').write_text('# Instruction One\nContent')
        (templates_dir / 'instruction-two.md').write_text('# Instruction Two\nContent')
        (templates_dir / 'not-markdown.txt').write_text('Should be ignored')

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            result = get_available_instructions()
            names = [r['name'] for r in result]
            assert 'instruction-one' in names
            assert 'instruction-two' in names
            assert 'not-markdown' not in names

    def test_extracts_description_from_heading(self, tmp_path):
        """Should extract description from first heading."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()

        (templates_dir / 'with-heading.md').write_text('# My Instruction Description\nContent')

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            result = get_available_instructions()
            instruction = next(r for r in result if r['name'] == 'with-heading')
            assert instruction['description'] == 'My Instruction Description'

    def test_skips_comment_for_description(self, tmp_path):
        """Should skip HTML comments when looking for description."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()

        content = """<!-- This is a comment -->
# Real Heading
Content
"""
        (templates_dir / 'with-comment.md').write_text(content)

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            result = get_available_instructions()
            instruction = next(r for r in result if r['name'] == 'with-comment')
            assert instruction['description'] == 'Real Heading'

    def test_returns_sorted_by_name(self, tmp_path):
        """Should return instructions sorted by name."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()

        (templates_dir / 'z-instruction.md').write_text('# Z')
        (templates_dir / 'a-instruction.md').write_text('# A')
        (templates_dir / 'm-instruction.md').write_text('# M')

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            result = get_available_instructions()
            names = [r['name'] for r in result]
            assert names == ['a-instruction', 'm-instruction', 'z-instruction']


class TestGetCurrentInstructions:
    """Tests for get_current_instructions function."""

    def test_returns_empty_when_claude_md_not_exists(self, tmp_path):
        """Should return empty list when .orch/CLAUDE.md doesn't exist."""
        result = get_current_instructions(str(tmp_path))
        assert result == []

    def test_parses_orch_template_markers(self, tmp_path):
        """Should parse ORCH-TEMPLATE markers."""
        claude_md = tmp_path / '.orch' / 'CLAUDE.md'
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("""
<!-- ORCH-TEMPLATE: instruction-one -->
Content
<!-- /ORCH-TEMPLATE -->

<!-- ORCH-TEMPLATE: instruction-two -->
More content
<!-- /ORCH-TEMPLATE -->
""")
        result = get_current_instructions(str(tmp_path))
        assert 'instruction-one' in result
        assert 'instruction-two' in result

    def test_parses_orch_instruction_markers(self, tmp_path):
        """Should parse ORCH-INSTRUCTION markers."""
        claude_md = tmp_path / '.orch' / 'CLAUDE.md'
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("""
<!-- ORCH-INSTRUCTION: new-style-one -->
Content
<!-- /ORCH-INSTRUCTION -->

<!-- ORCH-INSTRUCTION: new-style-two -->
More content
<!-- /ORCH-INSTRUCTION -->
""")
        result = get_current_instructions(str(tmp_path))
        assert 'new-style-one' in result
        assert 'new-style-two' in result

    def test_returns_unique_names_in_order(self, tmp_path):
        """Should return unique instruction names in order of appearance."""
        claude_md = tmp_path / '.orch' / 'CLAUDE.md'
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("""
<!-- ORCH-TEMPLATE: first -->
<!-- /ORCH-TEMPLATE -->
<!-- ORCH-TEMPLATE: second -->
<!-- /ORCH-TEMPLATE -->
<!-- ORCH-TEMPLATE: first -->
<!-- /ORCH-TEMPLATE -->
""")
        result = get_current_instructions(str(tmp_path))
        assert result == ['first', 'second']


class TestGetMissingInstructions:
    """Tests for get_missing_instructions function."""

    def test_returns_available_minus_current(self, tmp_path):
        """Should return instructions that are available but not in project."""
        # Setup available instructions
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        (templates_dir / 'available-one.md').write_text('# One')
        (templates_dir / 'available-two.md').write_text('# Two')
        (templates_dir / 'available-three.md').write_text('# Three')

        # Setup project with some instructions
        project = tmp_path / 'project'
        claude_md = project / '.orch' / 'CLAUDE.md'
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("""
<!-- ORCH-TEMPLATE: available-one -->
Content
<!-- /ORCH-TEMPLATE -->
""")

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            result = get_missing_instructions(str(project))
            names = [r['name'] for r in result]
            assert 'available-one' not in names
            assert 'available-two' in names
            assert 'available-three' in names


class TestFindInsertionPoint:
    """Tests for find_insertion_point function."""

    def test_after_last_template_marker(self):
        """Should find insertion point after last template marker."""
        content = """
<!-- ORCH-TEMPLATE: one -->
Content
<!-- /ORCH-TEMPLATE -->

<!-- ORCH-TEMPLATE: two -->
More content
<!-- /ORCH-TEMPLATE -->

## Other section
"""
        index, reason = find_insertion_point(content)
        assert reason == "after_last_template"
        # Should be after the second closing marker
        assert content[index:index+10].strip() in ['', '## Other']

    def test_after_last_instruction_marker(self):
        """Should find insertion point after last instruction marker."""
        content = """
<!-- ORCH-INSTRUCTION: one -->
Content
<!-- /ORCH-INSTRUCTION -->
"""
        index, reason = find_insertion_point(content)
        assert reason == "after_last_template"

    def test_before_project_specific_marker(self):
        """Should find insertion point before PROJECT-SPECIFIC-START."""
        content = """
# Header

Some content

<!-- PROJECT-SPECIFIC-START -->
Project specific stuff
"""
        index, reason = find_insertion_point(content)
        assert reason == "before_project_section"

    def test_before_reference_section(self):
        """Should find insertion point before Reference section."""
        content = """
# Header

Some content

## Reference
- Link 1
"""
        index, reason = find_insertion_point(content)
        assert reason == "before_reference_section"

    def test_end_of_file_fallback(self):
        """Should insert at end of file if no markers found."""
        content = """# Simple content
No markers here
"""
        index, reason = find_insertion_point(content)
        assert reason == "end_of_file"
        assert index == len(content)


class TestFormatInstructionMarker:
    """Tests for format_instruction_marker function."""

    def test_creates_marker_block(self):
        """Should create properly formatted marker block."""
        result = format_instruction_marker('test-instruction', 'Content here')
        assert '<!-- ORCH-INSTRUCTION: test-instruction -->' in result
        assert '<!-- /ORCH-INSTRUCTION -->' in result
        assert 'Content here' in result
        assert result.endswith('---\n\n')

    def test_adds_spacing(self):
        """Should add proper spacing around content."""
        result = format_instruction_marker('test', 'Content')
        # Content should have newline before and after
        assert '\nContent\n' in result


class TestValidateInstructionExists:
    """Tests for validate_instruction_exists function."""

    def test_returns_true_when_exists(self, tmp_path):
        """Should return True when template file exists."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()
        (templates_dir / 'existing.md').write_text('Content')

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            assert validate_instruction_exists('existing') is True

    def test_returns_false_when_not_exists(self, tmp_path):
        """Should return False when template file doesn't exist."""
        templates_dir = tmp_path / 'orchestrator'
        templates_dir.mkdir()

        with patch('orch.instructions.get_templates_directory', return_value=templates_dir):
            assert validate_instruction_exists('nonexistent') is False


class TestGetProjectPaths:
    """Tests for path getter functions."""

    def test_get_project_claude_md_path(self, tmp_path):
        """Should return .orch/CLAUDE.md path."""
        result = get_project_claude_md_path(str(tmp_path))
        assert result == tmp_path / '.orch' / 'CLAUDE.md'

    def test_get_project_agents_md_path(self, tmp_path):
        """Should return .orch/AGENTS.md path."""
        result = get_project_agents_md_path(str(tmp_path))
        assert result == tmp_path / '.orch' / 'AGENTS.md'

    def test_get_project_gemini_md_path(self, tmp_path):
        """Should return .orch/GEMINI.md path."""
        result = get_project_gemini_md_path(str(tmp_path))
        assert result == tmp_path / '.orch' / 'GEMINI.md'


class TestGetProjectContextFiles:
    """Tests for get_project_context_files function."""

    def test_returns_empty_when_no_context_files(self, tmp_path):
        """Should return empty list when no context files exist."""
        (tmp_path / '.orch').mkdir()
        result = get_project_context_files(str(tmp_path))
        assert result == []

    def test_returns_existing_files(self, tmp_path):
        """Should return list of existing context files."""
        orch_dir = tmp_path / '.orch'
        orch_dir.mkdir()
        (orch_dir / 'CLAUDE.md').write_text('Claude content')
        (orch_dir / 'GEMINI.md').write_text('Gemini content')

        result = get_project_context_files(str(tmp_path))
        types = [r[0] for r in result]
        assert 'CLAUDE.md' in types
        assert 'GEMINI.md' in types
        assert 'AGENTS.md' not in types

    def test_includes_all_context_file_types(self, tmp_path):
        """Should include CLAUDE.md, GEMINI.md, and AGENTS.md."""
        orch_dir = tmp_path / '.orch'
        orch_dir.mkdir()
        (orch_dir / 'CLAUDE.md').write_text('C')
        (orch_dir / 'GEMINI.md').write_text('G')
        (orch_dir / 'AGENTS.md').write_text('A')

        result = get_project_context_files(str(tmp_path))
        types = [r[0] for r in result]
        assert len(types) == 3
        assert 'CLAUDE.md' in types
        assert 'GEMINI.md' in types
        assert 'AGENTS.md' in types


class TestCreateEmptyInstructionBlock:
    """Tests for create_empty_instruction_block function."""

    def test_creates_block_with_placeholder(self):
        """Should create block with placeholder content."""
        result = create_empty_instruction_block('test-instruction')
        assert '<!-- ORCH-INSTRUCTION: test-instruction -->' in result
        assert '<!-- /ORCH-INSTRUCTION -->' in result
        assert 'Auto-generated content will be injected' in result


class TestMigrateMarkersToInstruction:
    """Tests for migrate_markers_to_instruction function."""

    def test_migrates_opening_markers(self):
        """Should migrate ORCH-TEMPLATE to ORCH-INSTRUCTION."""
        content = '<!-- ORCH-TEMPLATE: test -->'
        new_content, changed = migrate_markers_to_instruction(content)
        assert '<!-- ORCH-INSTRUCTION: test -->' in new_content
        assert 'ORCH-TEMPLATE' not in new_content
        assert changed is True

    def test_migrates_closing_markers(self):
        """Should migrate closing markers."""
        content = '<!-- /ORCH-TEMPLATE -->'
        new_content, changed = migrate_markers_to_instruction(content)
        assert '<!-- /ORCH-INSTRUCTION -->' in new_content
        assert '/ORCH-TEMPLATE' not in new_content
        assert changed is True

    def test_returns_unchanged_when_no_templates(self):
        """Should return unchanged content when no template markers."""
        content = '# Just markdown\nNo markers here'
        new_content, changed = migrate_markers_to_instruction(content)
        assert new_content == content
        assert changed is False

    def test_migrates_multiple_markers(self):
        """Should migrate multiple markers in one pass."""
        content = """
<!-- ORCH-TEMPLATE: one -->
Content
<!-- /ORCH-TEMPLATE -->
<!-- ORCH-TEMPLATE: two -->
More
<!-- /ORCH-TEMPLATE -->
"""
        new_content, changed = migrate_markers_to_instruction(content)
        assert changed is True
        assert new_content.count('ORCH-INSTRUCTION') == 4  # 2 open + 2 close
        assert 'ORCH-TEMPLATE' not in new_content


class TestRemoveInstructionFromContent:
    """Tests for remove_instruction_from_content function."""

    def test_removes_template_block(self):
        """Should remove ORCH-TEMPLATE block."""
        content = """
# Header

<!-- ORCH-TEMPLATE: to-remove -->
Content to remove
<!-- /ORCH-TEMPLATE -->

---

## Footer
"""
        new_content, removed = remove_instruction_from_content(content, 'to-remove')
        assert removed is True
        assert 'to-remove' not in new_content
        assert 'Content to remove' not in new_content
        assert '# Header' in new_content
        assert '## Footer' in new_content

    def test_removes_instruction_block(self):
        """Should remove ORCH-INSTRUCTION block."""
        content = """
<!-- ORCH-INSTRUCTION: to-remove -->
Content
<!-- /ORCH-INSTRUCTION -->

---
"""
        new_content, removed = remove_instruction_from_content(content, 'to-remove')
        assert removed is True
        assert 'to-remove' not in new_content

    def test_returns_unchanged_when_not_found(self):
        """Should return unchanged when instruction not found."""
        content = "# No markers\nJust content"
        new_content, removed = remove_instruction_from_content(content, 'nonexistent')
        assert removed is False
        assert new_content == content

    def test_removes_trailing_separator(self):
        """Should remove trailing --- separator."""
        content = """<!-- ORCH-TEMPLATE: test -->
Content
<!-- /ORCH-TEMPLATE -->

---

## Next section
"""
        new_content, removed = remove_instruction_from_content(content, 'test')
        assert removed is True
        # Should not have multiple blank lines
        assert '\n\n\n' not in new_content

    def test_normalizes_blank_lines(self):
        """Should normalize multiple blank lines after removal."""
        content = """
<!-- ORCH-TEMPLATE: test -->
Content
<!-- /ORCH-TEMPLATE -->



Next content
"""
        new_content, removed = remove_instruction_from_content(content, 'test')
        assert removed is True
        # Should have at most 2 consecutive newlines
        assert '\n\n\n' not in new_content
