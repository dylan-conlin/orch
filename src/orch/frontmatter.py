"""
Frontmatter parsing module for markdown metadata extraction.

This module provides functions to extract metadata from markdown files
that use YAML frontmatter, with fallback to inline markdown parsing.

YAML frontmatter format:
---
phase: Implementation
status: Active
started: 2025-11-30
---

Inline markdown format (fallback):
**Phase:** Implementation
**Status:** Active
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List, Any
from pathlib import Path

try:
    import frontmatter
except ImportError:
    frontmatter = None  # Graceful degradation if python-frontmatter not installed


@dataclass
class MetadataResult:
    """
    Container for extracted metadata from markdown files.

    Attributes:
        phase: Workflow phase (e.g., "Implementation", "Complete")
        status: Current status (e.g., "Active", "Blocked")
        started: Start date (YYYY-MM-DD format)
        last_updated: Last update timestamp
        completed: Completion date
        resumed_at: Resume timestamp
        tags: List of tags
        topic: Topic/subject
        scope: Scope definition
        context: Context information
        source: Source reference
        dimension: Dimension (for audit files)
        confidence: Confidence level (e.g., "High", "Medium", "Low")
        from_frontmatter: True if extracted from YAML frontmatter, False if from inline
    """
    phase: Optional[str] = None
    status: Optional[str] = None
    started: Optional[str] = None
    last_updated: Optional[str] = None
    completed: Optional[str] = None
    resumed_at: Optional[str] = None
    tags: Optional[List[str]] = None
    topic: Optional[str] = None
    scope: Optional[str] = None
    context: Optional[str] = None
    source: Optional[str] = None
    dimension: Optional[str] = None
    confidence: Optional[str] = None
    from_frontmatter: bool = False


def has_frontmatter(content: str) -> bool:
    """
    Check if content has valid YAML frontmatter.

    Frontmatter must:
    - Start at the very beginning of the file (no leading whitespace/newlines)
    - Be delimited by --- on its own line

    Args:
        content: Markdown content string

    Returns:
        True if valid frontmatter is detected, False otherwise
    """
    if not content:
        return False

    # Frontmatter must start at the very beginning
    if not content.startswith('---'):
        return False

    # Find the closing ---
    lines = content.split('\n')
    if len(lines) < 2:
        return False

    # First line must be exactly '---'
    if lines[0].strip() != '---':
        return False

    # Find closing delimiter (must be on its own line after first line)
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            return True

    return False


def _is_template_placeholder(value: str) -> bool:
    """
    Check if a value looks like a template placeholder rather than an actual value.

    Template placeholders contain:
    - Pipe characters with spaces: 'Active | Complete'
    - Brackets: '[Investigating/Complete]'

    Args:
        value: Value to check

    Returns:
        True if value appears to be a placeholder
    """
    if not value:
        return True

    value_str = str(value)

    # Pipe-separated choices: 'Active | Complete'
    if ' | ' in value_str:
        return True

    # Bracket placeholders: '[Option1/Option2]'
    if value_str.startswith('[') and value_str.endswith(']'):
        return True

    return False


def _extract_frontmatter(content: str) -> Optional[dict]:
    """
    Extract YAML frontmatter from content.

    Args:
        content: Markdown content string

    Returns:
        Dictionary of frontmatter fields, or None if not present/invalid
    """
    if frontmatter is None:
        return None

    if not has_frontmatter(content):
        return None

    try:
        post = frontmatter.loads(content)
        return dict(post.metadata)
    except Exception:
        # Malformed YAML - return None to trigger fallback
        return None


def _get_case_insensitive(data: dict, key: str) -> Any:
    """
    Get a value from dict with case-insensitive key matching.

    Args:
        data: Dictionary to search
        key: Key to find (case-insensitive)

    Returns:
        Value if found, None otherwise
    """
    key_lower = key.lower()
    for k, v in data.items():
        if k.lower() == key_lower:
            return v
    return None


def _extract_inline_field(content: str, field_name: str) -> Optional[str]:
    """
    Extract a field value from inline markdown format.

    Matches patterns like:
    - **Field:** value
    - Field: value

    Args:
        content: Markdown content string
        field_name: Name of field to extract

    Returns:
        Field value if found, None otherwise
    """
    # Match **Field:** value or Field: value
    pattern = rf'\*\*{field_name}:\*\*\s*([^\n]+)|^{field_name}:\s*([^\n]+)'
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

    if match:
        value = (match.group(1) or match.group(2)).strip()
        if value:
            return value

    return None


def extract_metadata(content: str) -> MetadataResult:
    """
    Extract all metadata from markdown content.

    Tries YAML frontmatter first, falls back to inline markdown extraction.

    Args:
        content: Markdown content string

    Returns:
        MetadataResult with extracted fields
    """
    result = MetadataResult()

    # Try frontmatter first
    fm_data = _extract_frontmatter(content)

    if fm_data is not None:
        # Extract from frontmatter (case-insensitive key matching)
        result.phase = _get_case_insensitive(fm_data, 'phase')
        result.status = _get_case_insensitive(fm_data, 'status')
        result.started = _get_case_insensitive(fm_data, 'started')
        result.last_updated = _get_case_insensitive(fm_data, 'last_updated')
        result.completed = _get_case_insensitive(fm_data, 'completed')
        result.resumed_at = _get_case_insensitive(fm_data, 'resumed_at')
        result.tags = _get_case_insensitive(fm_data, 'tags')
        result.topic = _get_case_insensitive(fm_data, 'topic')
        result.scope = _get_case_insensitive(fm_data, 'scope')
        result.context = _get_case_insensitive(fm_data, 'context')
        result.source = _get_case_insensitive(fm_data, 'source')
        result.dimension = _get_case_insensitive(fm_data, 'dimension')
        result.confidence = _get_case_insensitive(fm_data, 'confidence')
        result.from_frontmatter = True

        # Filter out template placeholders
        if _is_template_placeholder(result.phase):
            result.phase = None
        if _is_template_placeholder(result.status):
            result.status = None

        return result

    # Fall back to inline extraction
    result.phase = _extract_inline_field(content, 'Phase')
    result.status = _extract_inline_field(content, 'Status')
    result.started = _extract_inline_field(content, 'Started')
    result.last_updated = _extract_inline_field(content, 'Last Updated')
    result.completed = _extract_inline_field(content, 'Completed')
    result.confidence = _extract_inline_field(content, 'Confidence')
    result.from_frontmatter = False

    # Filter out template placeholders
    if _is_template_placeholder(result.phase):
        result.phase = None
    if _is_template_placeholder(result.status):
        result.status = None

    return result


def extract_phase(content: str) -> Optional[str]:
    """
    Extract Phase field from content.

    Convenience function that extracts only the phase.

    Args:
        content: Markdown content string

    Returns:
        Phase value if found, None otherwise
    """
    result = extract_metadata(content)
    return result.phase


def extract_status(content: str) -> Optional[str]:
    """
    Extract Status field from content.

    Convenience function that extracts only the status.

    Args:
        content: Markdown content string

    Returns:
        Status value if found, None otherwise
    """
    result = extract_metadata(content)
    return result.status


def extract_phase_from_file(path: Path) -> Optional[str]:
    """
    Extract Phase from a file.

    Args:
        path: Path to markdown file

    Returns:
        Phase value if found, None otherwise
    """
    if not path:
        return None

    path = Path(path).expanduser()
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding='utf-8')
        return extract_phase(content)
    except Exception:
        return None


def extract_metadata_from_file(path: Path) -> MetadataResult:
    """
    Extract all metadata from a file.

    Args:
        path: Path to markdown file

    Returns:
        MetadataResult with extracted fields
    """
    if not path:
        return MetadataResult()

    path = Path(path).expanduser()
    if not path.exists():
        return MetadataResult()

    try:
        content = path.read_text(encoding='utf-8')
        return extract_metadata(content)
    except Exception:
        return MetadataResult()
