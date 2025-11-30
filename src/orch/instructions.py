"""Orchestrator instruction management for orch.

Provides utilities for discovering, listing, and managing orchestrator instructions
(template markers in .orch/CLAUDE.md files).

Key functions:
- get_available_instructions() - List all instructions in ~/.orch/templates/orchestrator/
- get_current_instructions(project_path) - Parse existing markers from CLAUDE.md
- get_missing_instructions(project_path) - Diff of available vs current
- find_insertion_point(content) - Determine where to insert new markers
- add_instruction_marker(project_path, instruction_name) - Add marker to CLAUDE.md
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def get_templates_directory() -> Path:
    """Get path to orchestrator templates directory."""
    return Path.home() / '.orch' / 'templates' / 'orchestrator'


def get_available_instructions() -> List[Dict[str, str]]:
    """
    Get list of all available orchestrator instructions.

    Returns:
        List of dicts with keys: 'name' (template filename without .md),
        'path' (full path to template file), 'description' (first line or empty)
    """
    templates_dir = get_templates_directory()

    if not templates_dir.exists():
        return []

    instructions = []
    for template_file in sorted(templates_dir.glob('*.md')):
        name = template_file.stem  # filename without .md extension

        # Try to extract description from first line of file
        description = ''
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                # Skip markdown comments
                if first_line.startswith('<!--'):
                    first_line = f.readline().strip()
                # Extract heading text
                if first_line.startswith('#'):
                    description = first_line.lstrip('#').strip()
        except Exception:
            pass

        instructions.append({
            'name': name,
            'path': str(template_file),
            'description': description
        })

    return instructions


def get_current_instructions(project_path: str) -> List[str]:
    """
    Parse existing instruction markers from project's .orch/CLAUDE.md.

    Args:
        project_path: Path to project root directory

    Returns:
        List of instruction names (template names without .md extension)
    """
    claude_md_path = Path(project_path) / '.orch' / 'CLAUDE.md'

    if not claude_md_path.exists():
        return []

    try:
        with open(claude_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    # Match both ORCH-TEMPLATE (current) and ORCH-INSTRUCTION (future) markers
    pattern = r'<!--\s*ORCH-(?:TEMPLATE|INSTRUCTION):\s*([a-zA-Z0-9_-]+)\s*-->'
    matches = re.findall(pattern, content)

    # Return unique instruction names in order
    seen = set()
    instructions = []
    for name in matches:
        if name not in seen:
            seen.add(name)
            instructions.append(name)

    return instructions


def get_missing_instructions(project_path: str) -> List[Dict[str, str]]:
    """
    Get list of instructions that are available but not in project.

    Args:
        project_path: Path to project root directory

    Returns:
        List of dicts with keys: 'name', 'path', 'description' (same as get_available_instructions)
    """
    available = get_available_instructions()
    current = set(get_current_instructions(project_path))

    missing = [inst for inst in available if inst['name'] not in current]

    return missing


def find_insertion_point(content: str) -> Tuple[Optional[int], str]:
    """
    Find insertion point for new instruction marker in CLAUDE.md content.

    Uses priority order:
    1. After last existing <!-- /ORCH-TEMPLATE --> or <!-- /ORCH-INSTRUCTION --> marker
    2. Before <!-- PROJECT-SPECIFIC-START --> marker
    3. None (fallback - caller should handle)

    Args:
        content: Full content of CLAUDE.md file

    Returns:
        Tuple of (insertion_index, reason):
        - insertion_index: Character index where to insert, or None if no good location found
        - reason: Human-readable explanation of where we're inserting ("after_last_template", "before_project_section", "not_found")
    """
    # Priority 1: After last existing template marker
    pattern = r'<!--\s*/ORCH-(?:TEMPLATE|INSTRUCTION)\s*-->'
    matches = list(re.finditer(pattern, content))

    if matches:
        last_match = matches[-1]
        # Find the end of the line after the closing marker
        insertion_point = content.find('\n', last_match.end())
        if insertion_point != -1:
            # Insert after the newline
            return (insertion_point + 1, "after_last_template")

    # Priority 2: Before PROJECT-SPECIFIC-START marker
    project_marker = '<!-- PROJECT-SPECIFIC-START -->'
    project_index = content.find(project_marker)
    if project_index != -1:
        # Find start of line containing the marker
        line_start = content.rfind('\n', 0, project_index)
        if line_start != -1:
            return (line_start + 1, "before_project_section")
        else:
            # Marker is at start of file
            return (project_index, "before_project_section")

    # Priority 3: Before "## Reference" section if present (common footer)
    reference_index = content.find('\n## Reference')
    if reference_index != -1:
        line_start = content.rfind('\n', 0, reference_index)
        if line_start != -1:
            return (line_start + 1, "before_reference_section")
        else:
            return (reference_index, "before_reference_section")

    # Priority 4: Fallback to end of file (append)
    if content:
        return (len(content), "end_of_file")

    return (0, "end_of_file")


def format_instruction_marker(instruction_name: str, content: str) -> str:
    """
    Format a complete instruction marker block with content.

    Args:
        instruction_name: Name of the instruction (template filename without .md)
        content: Content to place between markers

    Returns:
        Formatted marker block with surrounding markers and content
    """
    # Phase 1b: Prefer ORCH-INSTRUCTION markers going forward.
    marker_start = f"<!-- ORCH-INSTRUCTION: {instruction_name} -->"
    marker_end = "<!-- /ORCH-INSTRUCTION -->"

    # Ensure content has proper spacing
    if not content.startswith('\n'):
        content = '\n' + content
    if not content.endswith('\n'):
        content = content + '\n'

    return f"{marker_start}{content}{marker_end}\n\n---\n\n"


def validate_instruction_exists(instruction_name: str) -> bool:
    """
    Check if an instruction template file exists.

    Args:
        instruction_name: Name of the instruction

    Returns:
        True if template file exists, False otherwise
    """
    template_path = get_templates_directory() / f"{instruction_name}.md"
    return template_path.exists()


def get_project_claude_md_path(project_path: str) -> Path:
    """
    Get path to project's .orch/CLAUDE.md file.

    Args:
        project_path: Path to project root directory

    Returns:
        Path object for .orch/CLAUDE.md
    """
    return Path(project_path) / '.orch' / 'CLAUDE.md'


def get_project_agents_md_path(project_path: str) -> Path:
    """
    Get path to project's .orch/AGENTS.md file.

    Args:
        project_path: Path to project root directory

    Returns:
        Path object for .orch/AGENTS.md
    """
    return Path(project_path) / '.orch' / 'AGENTS.md'


def get_project_gemini_md_path(project_path: str) -> Path:
    """
    Get path to project's .orch/GEMINI.md file.

    Args:
        project_path: Path to project root directory

    Returns:
        Path object for .orch/GEMINI.md
    """
    return Path(project_path) / '.orch' / 'GEMINI.md'


def get_project_context_files(project_path: str) -> List[Tuple[str, Path]]:
    """
    Get list of existing context files (CLAUDE.md, GEMINI.md, and/or AGENTS.md) in project.

    Args:
        project_path: Path to project root directory

    Returns:
        List of tuples (file_type, path) for existing context files.
        file_type is one of: 'CLAUDE.md', 'GEMINI.md', 'AGENTS.md'
    """
    files: List[Tuple[str, Path]] = []

    claude_path = get_project_claude_md_path(project_path)
    if claude_path.exists():
        files.append(('CLAUDE.md', claude_path))

    gemini_path = get_project_gemini_md_path(project_path)
    if gemini_path.exists():
        files.append(('GEMINI.md', gemini_path))

    agents_path = get_project_agents_md_path(project_path)
    if agents_path.exists():
        files.append(('AGENTS.md', agents_path))

    return files


def create_empty_instruction_block(instruction_name: str) -> str:
    """
    Create an empty instruction marker block for a given instruction name.

    This is used when adding markers via CLI before the build system injects
    actual content from templates.
    """
    marker_start = f"<!-- ORCH-INSTRUCTION: {instruction_name} -->"
    marker_end = "<!-- /ORCH-INSTRUCTION -->"
    return (
        f"{marker_start}\n"
        "<!-- Auto-generated content will be injected here by build -->\n"
        f"{marker_end}\n\n---\n\n"
    )


def migrate_markers_to_instruction(content: str) -> Tuple[str, bool]:
    """
    Migrate legacy ORCH-TEMPLATE markers to ORCH-INSTRUCTION markers in content.

    Converts:
      <!-- ORCH-TEMPLATE: name -->        → <!-- ORCH-INSTRUCTION: name -->
      <!-- /ORCH-TEMPLATE -->             → <!-- /ORCH-INSTRUCTION -->

    Returns:
        Tuple of (new_content, changed_flag)
    """
    changed = False

    # Migrate opening markers
    def replace_open(match: re.Match) -> str:
        nonlocal changed
        changed = True
        name = match.group(1)
        return f"<!-- ORCH-INSTRUCTION: {name} -->"

    new_content, open_count = re.subn(
        r'<!--\s*ORCH-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->',
        replace_open,
        content,
    )

    # Migrate closing markers
    new_content, close_count = re.subn(
        r'<!--\s*/ORCH-TEMPLATE\s*-->',
        '<!-- /ORCH-INSTRUCTION -->',
        new_content,
    )

    if open_count or close_count:
        changed = True

    return new_content, changed


def remove_instruction_from_content(content: str, instruction_name: str) -> Tuple[str, bool]:
    """
    Remove an instruction block (marker + content + trailing separator) from content.

    Handles both ORCH-TEMPLATE and ORCH-INSTRUCTION markers and removes the
    following '---' separator block when present.

    Returns:
        Tuple of (new_content, removed_flag)
    """
    # Pattern matches:
    #   optional leading newlines
    #   opening marker with given name (TEMPLATE or INSTRUCTION)
    #   any content up to the closing marker
    #   optional trailing newlines and '---' separator
    pattern = (
        r'\n*<!--\s*ORCH-(?:TEMPLATE|INSTRUCTION):\s*'
        + re.escape(instruction_name)
        + r'\s*-->(?:.*?)<!--\s*/ORCH-(?:TEMPLATE|INSTRUCTION)\s*-->\n*'
        r'(?:-{3}\s*\n*)?'
    )

    new_content, count = re.subn(pattern, '\n', content, flags=re.DOTALL)

    # Normalize multiple blank lines that may have been created
    if count:
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    return new_content, bool(count)
