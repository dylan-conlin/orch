"""Investigation template management."""

import os
from pathlib import Path
from typing import Optional
from datetime import date


class InvestigationError(Exception):
    """Base exception for investigation operations."""
    pass


# Map investigation types to template filenames
# Two active types: simple (default) and audits (comprehensive)
# Legacy types kept for backward compatibility with existing files
TEMPLATE_MAP = {
    # Active types (offered in CLI)
    'simple': 'SIMPLE.md',  # Default: minimal, test-focused
    'audits': 'AUDIT.md',   # Comprehensive multi-hour reviews
    # Legacy/frozen types (existing files still work, but CLI won't offer these)
    # See decision: .orch/decisions/2025-11-28-investigation-directory-organization.md
    'systems': 'SYSTEM_EXPLORATION.md',
    'feasibility': 'FEASIBILITY.md',
    'performance': 'PERFORMANCE.md',
    'agent-failures': 'AGENT_FAILURE.md'
}

DEFAULT_TYPE = 'simple'


def detect_project_dir(project_dir: Optional[Path] = None) -> Path:
    """
    Detect project directory from cwd, CLAUDE_PROJECT env, or explicit path.

    Priority order (first match wins):
    1. Explicit project_dir argument (--project flag)
    2. Current working directory (via find_orch_root)
    3. CLAUDE_PROJECT environment variable (fallback)

    The cwd takes precedence over CLAUDE_PROJECT because when a user
    explicitly cd's to another project, they expect commands to operate
    on that project, not on whatever CLAUDE_PROJECT was set to.

    Args:
        project_dir: Explicit project directory (default: auto-detect)

    Returns:
        Path to project directory containing .orch/

    Raises:
        InvestigationError: If no .orch directory found
    """
    # Use explicit project_dir if provided
    if project_dir:
        project_path = project_dir.resolve()
        if not (project_path / '.orch').exists():
            raise InvestigationError(f"No .orch directory found in {project_path}")
        return project_path

    # Try cwd-based detection first (user's current location takes priority)
    from orch.path_utils import find_orch_root
    orch_root = find_orch_root()
    if orch_root:
        return Path(orch_root)

    # Fallback to CLAUDE_PROJECT environment variable
    if 'CLAUDE_PROJECT' in os.environ:
        project_path = Path(os.environ['CLAUDE_PROJECT']).resolve()
        if not (project_path / '.orch').exists():
            raise InvestigationError(f"CLAUDE_PROJECT points to {project_path} but no .orch directory found")
        return project_path

    raise InvestigationError(
        "No .orch directory found. Either:\n"
        "  1. Run from within a project directory containing .orch/\n"
        "  2. Set CLAUDE_PROJECT environment variable\n"
        "  3. Use --project flag to specify project path"
    )


def create_investigation(
    slug: str,
    investigation_type: str,
    project_dir: Optional[Path] = None
) -> dict:
    """
    Create investigation file from template.

    Args:
        slug: Investigation topic in kebab-case
        investigation_type: One of systems, feasibility, audits, performance, agent-failures
        project_dir: Project directory (default: auto-detect)

    Returns:
        dict with keys: file_path, investigation_type, template_name, date

    Raises:
        InvestigationError: If template not found, project invalid, or file exists
    """
    # Validate slug (no path traversal)
    if '..' in slug or slug.startswith('/') or '/' in slug:
        raise InvestigationError(f"Invalid slug: {slug} (must be kebab-case filename without slashes)")

    # Detect project directory
    project_path = detect_project_dir(project_dir)

    # Build file path
    today = date.today().strftime('%Y-%m-%d')
    inv_dir = project_path / '.orch' / 'investigations' / investigation_type
    file_path = inv_dir / f"{today}-{slug}.md"

    # Check if file already exists
    if file_path.exists():
        raise InvestigationError(
            f"File already exists: {file_path}\n"
            f"Choose a different slug or remove the existing file"
        )

    # Get template
    template_name = TEMPLATE_MAP[investigation_type]
    template_path = Path.home() / '.orch' / 'templates' / 'investigations' / template_name

    if not template_path.exists():
        raise InvestigationError(
            f"Template not found: {template_path}\n"
            f"Ensure orchestration templates are installed at ~/.orch/templates/"
        )

    # Create directory
    inv_dir.mkdir(parents=True, exist_ok=True)

    # Copy template and substitute placeholders
    content = template_path.read_text()

    # Replace date placeholders in various formats found in templates
    content = content.replace('YYYY-MM-DD', today)
    content = content.replace('[YYYY-MM-DD]', today)
    content = content.replace('[2025-11-24]', today)  # Specific date format in templates

    # Write file
    file_path.write_text(content)

    return {
        'file_path': str(file_path),
        'investigation_type': investigation_type,
        'template_name': template_name,
        'date': today
    }


def validate_investigation(file_path: Path, investigation_type: str = 'simple') -> bool:
    """
    Validate investigation file has required fields.

    Args:
        file_path: Path to investigation file
        investigation_type: Type of investigation (simple templates have minimal requirements)

    Returns:
        True if validation passes

    Raises:
        InvestigationError: If validation fails

    Note: Resolution-Status is no longer required in investigation files.
    Problem resolution status is now tracked in backlog.json.
    See: .orch/decisions/2025-11-28-backlog-investigation-separation.md
    """
    if not file_path.exists():
        raise InvestigationError(f"Investigation file not found: {file_path}")

    content = file_path.read_text()

    # Simple template: just check it exists and has the test section
    if investigation_type == 'simple':
        if '## Test performed' not in content:
            raise InvestigationError(
                f"Investigation missing 'Test performed' section: {file_path}\n"
                f"This is the key discipline - you must document what you tested."
            )
        return True

    # For all other investigation types, just check the file is readable
    # (Resolution-Status is no longer required - tracked in backlog.json instead)
    return True


def mark_investigation_resolved(file_path: Path) -> None:
    """
    DEPRECATED: This function is deprecated.

    Resolution status is now tracked in backlog.json, not in investigation files.
    To mark a problem as resolved, complete the associated backlog item with a
    resolution value (fix or workaround).

    See: .orch/decisions/2025-11-28-backlog-investigation-separation.md

    Args:
        file_path: Path to investigation file

    Raises:
        InvestigationError: Always raises to indicate deprecation
    """
    import warnings
    warnings.warn(
        "mark_investigation_resolved() is deprecated. "
        "Resolution status is now tracked in backlog.json, not in investigation files. "
        "Complete the associated backlog item to mark the problem as resolved.",
        DeprecationWarning,
        stacklevel=2
    )

    raise InvestigationError(
        "This function is deprecated. Resolution status is now tracked in backlog.json.\n"
        "To mark a problem as resolved:\n"
        "  1. Find the backlog item that references this investigation\n"
        "  2. Set the item's 'resolution' field to 'fix' or 'workaround'\n"
        "  3. Complete the backlog item via 'orch complete'\n"
        "\n"
        f"Investigation: {file_path}"
    )
