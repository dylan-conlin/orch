"""
Tests for skill build system.

Tests skill template parsing and SKILL.md generation from source templates.
"""

import pytest
import re
from pathlib import Path


class TestSkillTemplateParsing:
    """Test skill template marker parsing."""

    def test_parse_skill_template_markers_simple(self):
        """Should find and parse simple skill template markers."""
        content = """# My Skill

<!-- SKILL-TEMPLATE: investigation -->
<!-- /SKILL-TEMPLATE -->

## Other Content
"""

        # Pattern for skill template markers (similar to orchestrator)
        pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'

        matches = re.findall(pattern, content, flags=re.DOTALL)

        assert len(matches) == 1
        assert matches[0][0] == 'investigation'  # Template name
        assert matches[0][1].strip() == ''  # Empty content (not yet replaced)

    def test_parse_skill_template_markers_multiple(self):
        """Should find multiple template markers in one file."""
        content = """# Feature Implementation

<!-- SKILL-TEMPLATE: design -->
<!-- /SKILL-TEMPLATE -->

## Implementation

<!-- SKILL-TEMPLATE: implementation-tdd -->
<!-- /SKILL-TEMPLATE -->

<!-- SKILL-TEMPLATE: validation -->
<!-- /SKILL-TEMPLATE -->
"""

        pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'
        matches = re.findall(pattern, content, flags=re.DOTALL)

        assert len(matches) == 3
        assert matches[0][0] == 'design'
        assert matches[1][0] == 'implementation-tdd'
        assert matches[2][0] == 'validation'

    def test_replace_skill_template_markers(self):
        """Should replace template markers with phase content."""
        content = """# Feature Implementation

<!-- SKILL-TEMPLATE: investigation -->
<!-- /SKILL-TEMPLATE -->
"""

        # Mock templates
        templates = {
            'investigation': '# Investigation Phase\n\nExplore the codebase.'
        }

        def replace_template(match):
            template_name = match.group(1)
            if template_name not in templates:
                return match.group(0)

            template_content = templates[template_name]
            replacement = f'<!-- SKILL-TEMPLATE: {template_name} -->\n'
            replacement += f'<!-- Auto-generated from phase file -->\n\n'
            replacement += template_content.strip()
            replacement += '\n\n<!-- /SKILL-TEMPLATE -->'
            return replacement

        pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'
        new_content = re.sub(pattern, replace_template, content, flags=re.DOTALL)

        assert '# Investigation Phase' in new_content
        assert 'Explore the codebase' in new_content
        assert '<!-- Auto-generated from phase file -->' in new_content


class TestSkillDiscovery:
    """Test finding skill template files."""

    def test_find_skill_templates_pattern(self):
        """Should match */src/SKILL.md.template pattern."""
        # Test that our glob pattern matches the expected structure
        test_paths = [
            Path('~/.claude/skills/worker/feature-impl/src/SKILL.md.template'),
            Path('~/.claude/skills/worker/systematic-debugging/src/SKILL.md.template'),
            Path('~/.claude/skills/orchestrator/coord/src/SKILL.md.template'),
        ]

        # Check each path matches our expected pattern
        for path in test_paths:
            # Pattern: any path ending in /src/SKILL.md.template
            assert path.name == 'SKILL.md.template'
            assert path.parent.name == 'src'

    def test_phase_file_discovery_pattern(self):
        """Should find phase files in src/phases/ directory."""
        test_paths = [
            Path('~/.claude/skills/worker/feature-impl/src/phases/investigation.md'),
            Path('~/.claude/skills/worker/feature-impl/src/phases/design.md'),
            Path('~/.claude/skills/worker/feature-impl/src/phases/implementation-tdd.md'),
        ]

        for path in test_paths:
            assert path.parent.name == 'phases'
            assert path.parent.parent.name == 'src'
            assert path.suffix == '.md'


class TestSkillBuildWorkflow:
    """Test end-to-end skill building workflow."""

    def test_build_skill_from_template(self, tmp_path):
        """Should build SKILL.md from template and phase files."""
        # Create test structure
        skill_dir = tmp_path / 'worker' / 'feature-impl'
        src_dir = skill_dir / 'src'
        phases_dir = src_dir / 'phases'
        phases_dir.mkdir(parents=True)

        # Create phase file
        investigation_phase = phases_dir / 'investigation.md'
        investigation_phase.write_text('# Investigation Phase\n\nExplore first.')

        # Create template
        template_file = src_dir / 'SKILL.md.template'
        template_content = """---
name: feature-impl
audience: worker
---

# Feature Implementation

<!-- SKILL-TEMPLATE: investigation -->
<!-- /SKILL-TEMPLATE -->
"""
        template_file.write_text(template_content)

        # Load phase files
        phase_templates = {}
        for phase_file in phases_dir.glob('*.md'):
            phase_name = phase_file.stem
            phase_templates[phase_name] = phase_file.read_text()

        # Build SKILL.md
        template = template_file.read_text()

        def replace_template(match):
            template_name = match.group(1)
            if template_name not in phase_templates:
                return match.group(0)

            content = phase_templates[template_name]
            replacement = f'<!-- SKILL-TEMPLATE: {template_name} -->\n'
            replacement += content.strip()
            replacement += '\n<!-- /SKILL-TEMPLATE -->'
            return replacement

        pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'
        built_content = re.sub(pattern, replace_template, template, flags=re.DOTALL)

        # Write SKILL.md
        output_file = skill_dir / 'SKILL.md'
        output_file.write_text(built_content)

        # Verify
        assert output_file.exists()
        content = output_file.read_text()
        assert '# Investigation Phase' in content
        assert 'Explore first' in content
        assert '<!-- SKILL-TEMPLATE: investigation -->' in content


class TestClarifyingQuestionsPhase:
    """Test the clarifying-questions phase is properly integrated."""

    def test_clarifying_questions_phase_file_exists(self):
        """Should have a clarifying-questions.md phase file in feature-impl skill."""
        phase_file = Path(__file__).parent.parent / 'skills' / 'src' / 'worker' / 'feature-impl' / 'src' / 'phases' / 'clarifying-questions.md'
        assert phase_file.exists(), f"Missing phase file: {phase_file}"

    def test_clarifying_questions_template_marker_exists(self):
        """Should have SKILL-TEMPLATE marker for clarifying-questions in template."""
        template_file = Path(__file__).parent.parent / 'skills' / 'src' / 'worker' / 'feature-impl' / 'src' / 'SKILL.md.template'
        content = template_file.read_text()
        assert '<!-- SKILL-TEMPLATE: clarifying-questions -->' in content, "Missing clarifying-questions template marker"

    def test_clarifying_questions_comes_after_investigation(self):
        """Clarifying questions should come AFTER investigation but BEFORE design."""
        template_file = Path(__file__).parent.parent / 'skills' / 'src' / 'worker' / 'feature-impl' / 'src' / 'SKILL.md.template'
        content = template_file.read_text()

        investigation_pos = content.find('<!-- SKILL-TEMPLATE: investigation -->')
        clarifying_pos = content.find('<!-- SKILL-TEMPLATE: clarifying-questions -->')
        design_pos = content.find('<!-- SKILL-TEMPLATE: design -->')

        assert investigation_pos != -1, "Missing investigation template marker"
        assert clarifying_pos != -1, "Missing clarifying-questions template marker"
        assert design_pos != -1, "Missing design template marker"

        assert investigation_pos < clarifying_pos < design_pos, \
            "Phase order must be: investigation → clarifying-questions → design"

    def test_clarifying_questions_phase_has_required_sections(self):
        """Clarifying questions phase should have workflow, completion criteria."""
        phase_file = Path(__file__).parent.parent / 'skills' / 'src' / 'worker' / 'feature-impl' / 'src' / 'phases' / 'clarifying-questions.md'
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()

        # Required sections
        assert '## Workflow' in content, "Missing Workflow section"
        assert '## Completion Criteria' in content, "Missing Completion Criteria section"
        assert 'AskUserQuestion' in content, "Should reference AskUserQuestion tool"

    def test_clarifying_questions_blocks_design_progression(self):
        """Phase should explicitly block progression to design until questions answered."""
        phase_file = Path(__file__).parent.parent / 'skills' / 'src' / 'worker' / 'feature-impl' / 'src' / 'phases' / 'clarifying-questions.md'
        if not phase_file.exists():
            pytest.skip("Phase file doesn't exist yet")

        content = phase_file.read_text()

        # Should have explicit guidance about blocking progression
        assert 'design' in content.lower(), "Should reference design phase"
        # Should have checkpoint/blocking behavior
        assert any(term in content.lower() for term in ['wait', 'block', 'checkpoint', 'approval', 'proceed']), \
            "Should have blocking/checkpoint behavior"
