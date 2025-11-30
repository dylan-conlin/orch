"""
Frontmatter migration module.

Converts markdown files from inline metadata format to YAML frontmatter.

Usage:
    orch migrate frontmatter --dry-run  # Preview changes
    orch migrate frontmatter            # Execute migration
"""
import re
from pathlib import Path
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass

try:
    import frontmatter
except ImportError:
    frontmatter = None


class FileType(Enum):
    """Types of orchestration files that can be migrated."""
    WORKSPACE = "workspace"
    SIMPLE_INVESTIGATION = "simple_investigation"
    DECISION = "decision"
    AUDIT = "audit"
    UNKNOWN = "unknown"


# Fields to extract for each file type
FILE_TYPE_FIELDS = {
    FileType.WORKSPACE: [
        ("owner", "Owner"),
        ("started", "Started"),
        ("last_updated", "Last Updated"),
        ("phase", "Phase"),
        ("status", "Status"),
        ("template_version", "Template-Version"),
    ],
    FileType.SIMPLE_INVESTIGATION: [
        ("date", "Date"),
        ("status", "Status"),
    ],
    FileType.DECISION: [
        ("date", "Date"),
        ("status", "Status"),
        ("topic", "Topic"),
        ("context", "Context"),
        ("scope", "Scope"),
        ("source", "Source"),
    ],
    FileType.AUDIT: [
        ("started", "Started"),
        ("status", "Status"),
        ("confidence", "Confidence"),
        ("dimension", "Dimension"),
        ("project", "Project"),
        ("auditor", "Auditor"),
        ("owner", "Owner"),
        ("phase", "Phase"),
    ],
}


def detect_file_type(path: Path) -> FileType:
    """
    Detect the type of orchestration file.

    Args:
        path: Path to the file

    Returns:
        FileType enum value
    """
    path_str = str(path)

    if "workspace" in path_str.lower() and "WORKSPACE.md" in path_str:
        return FileType.WORKSPACE

    if "investigations" in path_str:
        if "simple" in path_str:
            return FileType.SIMPLE_INVESTIGATION
        if "audit" in path_str.lower():
            return FileType.AUDIT
        # Default to simple for other investigation types
        return FileType.SIMPLE_INVESTIGATION

    if "decisions" in path_str:
        return FileType.DECISION

    return FileType.UNKNOWN


def has_frontmatter(content: str) -> bool:
    """
    Check if content already has YAML frontmatter.

    Args:
        content: File content

    Returns:
        True if frontmatter exists
    """
    if not content:
        return False
    return content.strip().startswith("---")


def extract_inline_metadata(content: str, file_type: FileType) -> Dict[str, Optional[str]]:
    """
    Extract inline metadata fields from content.

    Args:
        content: File content
        file_type: Type of file being processed

    Returns:
        Dictionary of extracted field values
    """
    metadata = {}

    if file_type == FileType.UNKNOWN:
        return metadata

    fields = FILE_TYPE_FIELDS.get(file_type, [])

    for field_key, field_name in fields:
        # Match **Field:** value or Field: value patterns
        pattern = rf'\*\*{re.escape(field_name)}:\*\*\s*([^\n]+)|^{re.escape(field_name)}:\s*([^\n]+)'
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

        if match:
            value = (match.group(1) or match.group(2)).strip()
            if value:
                metadata[field_key] = value

    return metadata


def _remove_inline_metadata(content: str, file_type: FileType) -> str:
    """
    Remove inline metadata fields from content.

    Args:
        content: File content
        file_type: Type of file being processed

    Returns:
        Content with inline metadata removed
    """
    if file_type == FileType.UNKNOWN:
        return content

    fields = FILE_TYPE_FIELDS.get(file_type, [])
    result = content

    for _, field_name in fields:
        # Remove **Field:** value lines
        pattern = rf'^\*\*{re.escape(field_name)}:\*\*\s*[^\n]*\n?'
        result = re.sub(pattern, '', result, flags=re.MULTILINE | re.IGNORECASE)

        # Remove Field: value lines (without bold)
        pattern = rf'^{re.escape(field_name)}:\s*[^\n]*\n?'
        result = re.sub(pattern, '', result, flags=re.MULTILINE | re.IGNORECASE)

    # Clean up multiple consecutive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result


def _format_frontmatter_value(value: str) -> str:
    """
    Format a value for YAML frontmatter.

    Args:
        value: Value to format

    Returns:
        Properly quoted YAML string
    """
    # Always quote to be safe with special characters
    # Escape any existing quotes
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def convert_to_frontmatter(content: str, file_type: FileType) -> str:
    """
    Convert content from inline metadata to frontmatter format.

    Args:
        content: File content with inline metadata
        file_type: Type of file being processed

    Returns:
        Content with YAML frontmatter
    """
    if not content or not content.strip():
        return content

    # Skip if already has frontmatter
    if has_frontmatter(content):
        return content

    if file_type == FileType.UNKNOWN:
        return content

    # Extract metadata
    metadata = extract_inline_metadata(content, file_type)

    if not metadata:
        return content

    # Build frontmatter block
    frontmatter_lines = ["---"]

    # Get fields in order
    fields = FILE_TYPE_FIELDS.get(file_type, [])
    for field_key, _ in fields:
        if field_key in metadata and metadata[field_key]:
            value = _format_frontmatter_value(metadata[field_key])
            frontmatter_lines.append(f"{field_key}: {value}")

    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    frontmatter_block = "\n".join(frontmatter_lines)

    # Remove inline metadata from content
    content_without_metadata = _remove_inline_metadata(content, file_type)

    # Combine frontmatter with cleaned content
    return frontmatter_block + content_without_metadata.lstrip()


@dataclass
class MigrationResult:
    """Result of migrating a single file."""
    path: Path
    success: bool
    skipped: bool = False
    skip_reason: Optional[str] = None
    error: Optional[str] = None


def migrate_file(path: Path, dry_run: bool = True) -> MigrationResult:
    """
    Migrate a single file to frontmatter format.

    Args:
        path: Path to file
        dry_run: If True, don't write changes

    Returns:
        MigrationResult with outcome
    """
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        return MigrationResult(path=path, success=False, error=str(e))

    # Skip if already has frontmatter
    if has_frontmatter(content):
        return MigrationResult(
            path=path, success=True, skipped=True,
            skip_reason="Already has frontmatter"
        )

    # Detect file type
    file_type = detect_file_type(path)

    if file_type == FileType.UNKNOWN:
        return MigrationResult(
            path=path, success=True, skipped=True,
            skip_reason="Unknown file type"
        )

    # Convert
    converted = convert_to_frontmatter(content, file_type)

    # Check if anything changed
    if converted == content:
        return MigrationResult(
            path=path, success=True, skipped=True,
            skip_reason="No metadata to migrate"
        )

    # Write if not dry run
    if not dry_run:
        try:
            path.write_text(converted, encoding='utf-8')
        except Exception as e:
            return MigrationResult(path=path, success=False, error=str(e))

    return MigrationResult(path=path, success=True)


def find_files_to_migrate(project_dir: Path) -> List[Path]:
    """
    Find all files that could be migrated.

    Args:
        project_dir: Project root directory

    Returns:
        List of file paths
    """
    orch_dir = project_dir / ".orch"
    files = []

    # Workspace files
    workspace_dir = orch_dir / "workspace"
    if workspace_dir.exists():
        files.extend(workspace_dir.rglob("WORKSPACE.md"))

    # Investigation files
    inv_dir = orch_dir / "investigations"
    if inv_dir.exists():
        files.extend(inv_dir.rglob("*.md"))

    # Decision files
    dec_dir = orch_dir / "decisions"
    if dec_dir.exists():
        files.extend(dec_dir.rglob("*.md"))

    return files


def migrate_project(project_dir: Path, dry_run: bool = True) -> List[MigrationResult]:
    """
    Migrate all files in a project to frontmatter format.

    Args:
        project_dir: Project root directory
        dry_run: If True, don't write changes

    Returns:
        List of MigrationResult for each file
    """
    files = find_files_to_migrate(project_dir)
    results = []

    for file_path in files:
        result = migrate_file(file_path, dry_run=dry_run)
        results.append(result)

    return results
