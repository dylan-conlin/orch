import re
import subprocess
import fcntl
import time
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set, List, Dict
from datetime import datetime, timezone
from enum import Enum
from jinja2 import Template

from orch.frontmatter import extract_phase


# Custom exceptions
class WorkspaceValidationError(Exception):
    """Raised when workspace validation fails."""
    pass


# ===== Workspace Naming Constants =====

# Common abbreviations for workspace naming
ABBREVIATIONS = {
    'investigate': 'inv',
    'investigation': 'inv',
    'implement': 'impl',
    'implementation': 'impl',
    'collection': 'coll',
    'debugging': 'debug',
    'configuration': 'config',
    'authentication': 'auth',
    'authorization': 'authz'
}


# ===== Workspace Naming Utilities =====

def apply_abbreviations(words: List[str], abbrev_dict: Dict[str, str] = None) -> List[str]:
    """
    Apply abbreviations to word list.

    Args:
        words: List of words to abbreviate
        abbrev_dict: Dictionary of abbreviations (defaults to ABBREVIATIONS)

    Returns:
        List of words with abbreviations applied

    Example:
        >>> apply_abbreviations(["investigate", "timeout"], ABBREVIATIONS)
        ['inv', 'timeout']
    """
    if abbrev_dict is None:
        abbrev_dict = ABBREVIATIONS

    result = []
    for word in words:
        # Check for abbreviation (case-insensitive)
        lower_word = word.lower()
        if lower_word in abbrev_dict:
            result.append(abbrev_dict[lower_word])
        else:
            result.append(word)

    return result


def truncate_at_word_boundary(text: str, max_length: int) -> str:
    """
    Truncate text at word boundary (last hyphen before max_length).

    Args:
        text: Text to truncate (kebab-case workspace name)
        max_length: Maximum length

    Returns:
        Truncated text at last hyphen before max_length, or text unchanged if under limit

    Examples:
        >>> truncate_at_word_boundary("explore-websocket-patterns-for-dashboard", 30)
        'explore-websocket-patterns'
        >>> truncate_at_word_boundary("short-name", 50)
        'short-name'
    """
    if len(text) <= max_length:
        return text

    # Find last hyphen before max_length
    truncated = text[:max_length]

    # Split at last hyphen and take first part
    if '-' in truncated:
        truncated = truncated.rsplit('-', 1)[0]
    else:
        # No hyphens found - truncate at max_length
        truncated = text[:max_length]

    return truncated


# ===== Safe File Reading with Locking =====

def read_workspace_safe(
    workspace_path: Path,
    stability_window: float = 0.5,
    max_wait: float = 5.0,
    check_stability: bool = True
) -> str:
    """
    Read workspace file safely with fcntl locking and stability check.

    Prevents race conditions when the orchestrator reads WORKSPACE.md while
    an agent may be writing to it. Uses two strategies:

    1. fcntl shared locking - ensures atomic read
    2. Stability check - waits if file was recently modified

    Args:
        workspace_path: Path to WORKSPACE.md file
        stability_window: Seconds the file must be unmodified before reading (default 0.5s)
        max_wait: Maximum seconds to wait for file to stabilize (default 5.0s)
        check_stability: If True, wait for file to stabilize before reading

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file doesn't exist
        TimeoutError: If file doesn't stabilize within max_wait (only with check_stability=True)

    Example:
        >>> content = read_workspace_safe(Path(".orch/workspace/my-workspace/WORKSPACE.md"))
        >>> # Content is guaranteed to be from a stable, complete write
    """
    workspace_path = Path(workspace_path).expanduser()

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace file not found: {workspace_path}")

    start_time = time.time()

    while True:
        # Check file stability before reading
        if check_stability:
            try:
                mtime = workspace_path.stat().st_mtime
                time_since_modify = time.time() - mtime
            except OSError:
                # File might have been deleted - re-check existence
                if not workspace_path.exists():
                    raise FileNotFoundError(f"Workspace file not found: {workspace_path}")
                raise

            # If file was modified recently, wait for it to stabilize
            if time_since_modify < stability_window:
                if time.time() - start_time > max_wait:
                    # Timeout - read anyway but file might be incomplete
                    # This is a fallback to prevent infinite waiting
                    break
                time.sleep(0.1)  # Wait 100ms and check again
                continue

        # File is stable (or check_stability=False), read with lock
        break

    # Read with shared lock (allows concurrent reads, blocks during write)
    with open(workspace_path, 'r') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            content = f.read()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return content


@dataclass
class WorkspaceSignal:
    """Represents a signal found in workspace."""
    has_signal: bool = False
    signal_type: Optional[str] = None  # 'blocked' or 'question'
    message: Optional[str] = None
    phase: Optional[str] = None
    awaiting_validation: bool = False  # True if Status contains AWAITING_VALIDATION


@dataclass
class CheckboxItem:
    """Represents a checkbox item in markdown."""
    checked: bool
    text: str
    line_number: int


@dataclass
class TestResult:
    """Represents test execution results."""
    passed: bool
    total: int
    failed: int
    output: str


@dataclass
class WorkspaceVerificationData:
    """Enhanced workspace data with verification information."""
    # Original fields
    phase: Optional[str] = None
    has_signal: bool = False
    signal_type: Optional[str] = None
    message: Optional[str] = None

    # Verification fields
    verification_complete: bool = False
    verification_items: List[CheckboxItem] = None
    next_actions: List[CheckboxItem] = None
    has_pending_actions: bool = False
    test_results: Optional[TestResult] = None

    def __post_init__(self):
        """Initialize list fields if None."""
        if self.verification_items is None:
            self.verification_items = []
        if self.next_actions is None:
            self.next_actions = []


# ===== Verification Parsing Helpers =====

def get_section(content: str, heading: str) -> Optional[str]:
    """
    Extract markdown section by heading.

    Finds content between '## Heading' and the next '##' or end of file.

    Args:
        content: Full markdown content
        heading: Section heading to find (without ##)

    Returns:
        Section content (without heading) or None if not found

    Example:
        >>> content = "## Summary\\nText here\\n## Next\\nMore"
        >>> get_section(content, "Summary")
        'Text here'
    """
    # Escape heading for regex
    escaped_heading = re.escape(heading)

    # Match ## Heading (with optional whitespace) until next ## or end
    pattern = rf'^##\s+{escaped_heading}\s*$(.*?)(?=^##|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return None

    return match.group(1).strip()


def _strip_html_comments(text: str) -> str:
    """
    Remove HTML comments from text.

    Removes both single-line and multi-line HTML comments:
    <!-- comment -->
    <!-- multi
         line
         comment -->

    Args:
        text: Text that may contain HTML comments

    Returns:
        Text with HTML comments removed

    Example:
        >>> text = "Real\\n<!-- Example -->\\nAlso real"
        >>> _strip_html_comments(text)
        'Real\\n\\nAlso real'
    """
    if not text:
        return text

    # Remove HTML comments (both single-line and multi-line)
    # Use re.DOTALL to make . match newlines
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)


def parse_checkboxes(section: str) -> List[CheckboxItem]:
    """
    Extract checkbox items from markdown section.

    Parses lines like:
    - [ ] Unchecked item
    - [x] Checked item
    - [X] Also checked

    Ignores checkbox items within HTML comments (<!-- ... -->).

    Args:
        section: Markdown section content

    Returns:
        List of CheckboxItem objects

    Example:
        >>> text = "- [ ] Todo\\n- [x] Done"
        >>> items = parse_checkboxes(text)
        >>> len(items)
        2
        >>> items[0].checked
        False
        >>> items[1].checked
        True
    """
    if not section:
        return []

    # Strip HTML comments first (template examples, etc.)
    section = _strip_html_comments(section)

    items = []
    lines = section.split('\n')

    for line_num, line in enumerate(lines, 1):
        # Match checkbox pattern: - [ ] or - [x] or - [X]
        match = re.match(r'^\s*-\s*\[([x\sX])\]\s*(.+)$', line)
        if match:
            checkbox_state = match.group(1)
            text = match.group(2).strip()

            checked = checkbox_state.lower() == 'x'
            items.append(CheckboxItem(
                checked=checked,
                text=text,
                line_number=line_num
            ))

    return items


def all_checked(items: List[CheckboxItem]) -> bool:
    """
    Check if all checkbox items are checked.

    Args:
        items: List of CheckboxItem objects

    Returns:
        True if all items are checked, False otherwise
        Returns True for empty list (vacuous truth)
    """
    if not items:
        return True

    return all(item.checked for item in items)


def has_unchecked_items(items: List[CheckboxItem]) -> bool:
    """
    Check if any checkbox items are unchecked.

    Args:
        items: List of CheckboxItem objects

    Returns:
        True if any items are unchecked, False otherwise
    """
    return any(not item.checked for item in items)


def extract_test_results(text: str) -> Optional[TestResult]:
    """
    Find and parse test result lines.

    Looks for patterns like:
    - Result: 8/8 tests passed
    - Result: All 8 tests passed
    - Result: 5/8 failed (3 passed)
    - Result: FAILED - 2/10 tests failed

    Args:
        text: Text content to search

    Returns:
        TestResult object or None if no results found

    Example:
        >>> text = "Result: 8/8 tests passed"
        >>> result = extract_test_results(text)
        >>> result.passed
        True
        >>> result.total
        8
    """
    if not text:
        return None

    # Pattern 1: X/Y tests passed
    match = re.search(r'Result:\s*(\d+)/(\d+)\s+tests?\s+passed', text, re.IGNORECASE)
    if match:
        passed_count = int(match.group(1))
        total = int(match.group(2))
        return TestResult(
            passed=(passed_count == total),
            total=total,
            failed=(total - passed_count),
            output=match.group(0)
        )

    # Pattern 2: All X tests passed
    match = re.search(r'Result:\s*All\s+(\d+)\s+tests?\s+passed', text, re.IGNORECASE)
    if match:
        total = int(match.group(1))
        return TestResult(
            passed=True,
            total=total,
            failed=0,
            output=match.group(0)
        )

    # Pattern 3: X/Y failed
    match = re.search(r'Result:.*?(\d+)/(\d+)\s+(?:tests?\s+)?failed', text, re.IGNORECASE)
    if match:
        failed_count = int(match.group(1))
        total = int(match.group(2))
        return TestResult(
            passed=False,
            total=total,
            failed=failed_count,
            output=match.group(0)
        )

    # Pattern 4: FAILED keyword (no specific counts)
    if re.search(r'Result:.*?FAILED', text, re.IGNORECASE):
        return TestResult(
            passed=False,
            total=0,
            failed=0,
            output="Test failed (no counts available)"
        )

    return None


def parse_workspace(workspace_path: Path) -> WorkspaceSignal:
    """
    Parse workspace file for signals and status.

    Args:
        workspace_path: Path to WORKSPACE.md file or directory (supports ~ expansion)

    Returns:
        WorkspaceSignal with extracted information
    """
    # Expand ~ in path and convert to Path object
    workspace_path = Path(workspace_path).expanduser()

    # Handle both file path and directory path
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        return WorkspaceSignal()

    # Use safe read with stability check to prevent race conditions
    # when agents are writing to the workspace
    try:
        content = read_workspace_safe(workspace_path, check_stability=True)
    except (FileNotFoundError, TimeoutError):
        # File disappeared or didn't stabilize - return empty signal
        return WorkspaceSignal()

    signal = WorkspaceSignal()

    # Extract Phase - try YAML frontmatter first, then fall back to inline regex
    phase = extract_phase(content)
    if phase:
        signal.phase = phase
    else:
        # Fallback: inline format (handles **Phase:**, Phase:, and **Status:** Phase: formats)
        phase_match = re.search(r'^\*\*Phase:\*\*\s*(\w+)|^Phase:\s*(\w+)|^\*\*Status:\*\*\s+Phase:\s*(\w+)', content, re.MULTILINE)
        if phase_match:
            # Group 1: **Phase:** format, Group 2: Phase: format, Group 3: **Status:** Phase: format
            signal.phase = phase_match.group(1) or phase_match.group(2) or phase_match.group(3)

    # Check for BLOCKED signal
    blocked_match = re.search(r'BLOCKED:\s*(.+?)(?:\n|$)', content, re.MULTILINE)
    if blocked_match:
        signal.has_signal = True
        signal.signal_type = 'blocked'
        signal.message = blocked_match.group(1).strip()
        return signal

    # Check for QUESTION signal
    question_match = re.search(r'QUESTION:\s*(.+?)(?:\n|$)', content, re.MULTILINE)
    if question_match:
        signal.has_signal = True
        signal.signal_type = 'question'
        signal.message = question_match.group(1).strip()
        return signal

    # Check for AWAITING_VALIDATION status (multi-phase validation pattern)
    # Matches: **Status:** AWAITING_VALIDATION or Status: AWAITING_VALIDATION
    awaiting_validation_match = re.search(r'^\*\*Status:\*\*\s+.*AWAITING_VALIDATION|^Status:\s+.*AWAITING_VALIDATION', content, re.MULTILINE)
    if awaiting_validation_match:
        signal.awaiting_validation = True

    return signal


def parse_workspace_verification(workspace_path: Path) -> WorkspaceVerificationData:
    """
    Enhanced workspace parsing with verification and next-actions support.

    Parses workspace file for:
    - Phase field
    - BLOCKED/QUESTION signals
    - Verification Required section (checkboxes and test results)
    - Next-Actions section (checkboxes)

    Args:
        workspace_path: Path to WORKSPACE.md file or directory (supports ~ expansion)

    Returns:
        WorkspaceVerificationData with all parsed information

    Example:
        >>> data = parse_workspace_verification("/path/to/workspace")
        >>> data.phase
        'Complete'
        >>> data.verification_complete
        True
        >>> len(data.verification_items)
        3
    """
    # Expand ~ in path and convert to Path object
    workspace_path = Path(workspace_path).expanduser()

    # Handle both file path and directory path
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        return WorkspaceVerificationData()

    # Use safe read with stability check to prevent race conditions
    # when agents are writing to the workspace
    try:
        content = read_workspace_safe(workspace_path, check_stability=True)
    except (FileNotFoundError, TimeoutError):
        # File disappeared or didn't stabilize - return empty data
        return WorkspaceVerificationData()

    # Initialize result
    data = WorkspaceVerificationData()

    # Extract Phase (handles **Phase:**, Phase:, and **Status:** Phase: formats)
    phase_match = re.search(r'^\*\*Phase:\*\*\s*(\w+)|^Phase:\s*(\w+)|^\*\*Status:\*\*\s+Phase:\s*(\w+)', content, re.MULTILINE)
    if phase_match:
        # Group 1: **Phase:** format, Group 2: Phase: format, Group 3: **Status:** Phase: format
        data.phase = phase_match.group(1) or phase_match.group(2) or phase_match.group(3)

    # Check for BLOCKED signal
    blocked_match = re.search(r'BLOCKED:\s*(.+?)(?:\n|$)', content, re.MULTILINE)
    if blocked_match:
        data.has_signal = True
        data.signal_type = 'blocked'
        data.message = blocked_match.group(1).strip()
        # Don't return early - continue parsing verification data

    # Check for QUESTION signal
    if not data.has_signal:  # Only check if not already blocked
        question_match = re.search(r'QUESTION:\s*(.+?)(?:\n|$)', content, re.MULTILINE)
        if question_match:
            data.has_signal = True
            data.signal_type = 'question'
            data.message = question_match.group(1).strip()

    # Parse Verification Required section
    verification_section = get_section(content, "Verification Required")
    if verification_section:
        data.verification_items = parse_checkboxes(verification_section)
        data.verification_complete = all_checked(data.verification_items)

        # Extract test results from verification section
        data.test_results = extract_test_results(verification_section)
    else:
        # No verification section means verification is N/A (complete by default)
        data.verification_complete = True

    # Parse Next-Actions section
    next_actions_section = get_section(content, "Next-Actions")
    if next_actions_section:
        data.next_actions = parse_checkboxes(next_actions_section)
        data.has_pending_actions = has_unchecked_items(data.next_actions)
    else:
        # No next-actions section means no pending actions
        data.has_pending_actions = False

    return data


def extract_tldr(workspace_path: Path) -> Optional[str]:
    """
    Extract TLDR section from workspace file.

    Looks for content between '**TLDR:**' and the next '---' separator.
    Returns None if TLDR not found or if it's an unmodified template placeholder.

    Args:
        workspace_path: Path to WORKSPACE.md file or directory

    Returns:
        TLDR text (stripped) or None if not found/invalid
    """
    # Expand ~ in path and convert to Path object
    workspace_path = Path(workspace_path).expanduser()

    # Handle both file path and directory path
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        return None

    # Use safe read with stability check to prevent race conditions
    try:
        content = read_workspace_safe(workspace_path, check_stability=True)
    except (FileNotFoundError, TimeoutError):
        return None

    # Find TLDR section
    tldr_match = re.search(r'\*\*TLDR:\*\*\s*(.+?)(?=\n---|\Z)', content, re.DOTALL)
    if not tldr_match:
        return None

    tldr_text = tldr_match.group(1).strip()

    # Check if TLDR is a template placeholder
    # Template TLDR starts with '[' or contains guideline text
    if (tldr_text.startswith('[') or
        'One sentence describing' in tldr_text or
        'Example TLDR:' in tldr_text or
        len(tldr_text) < 10):  # Too short to be meaningful
        return None

    return tldr_text


def is_unmodified_template(workspace_path: Path) -> bool:
    """
    Check if workspace file is an unmodified template.

    Detects common placeholder patterns that indicate the workspace
    hasn't been filled in yet by the agent.

    Args:
        workspace_path: Path to WORKSPACE.md file

    Returns:
        True if workspace appears to be unmodified template, False otherwise
    """
    # Expand ~ in path and convert to Path object
    workspace_path = Path(workspace_path).expanduser()

    # Handle both file path and directory path
    if workspace_path.is_dir():
        workspace_path = workspace_path / 'WORKSPACE.md'

    if not workspace_path.exists():
        return False

    # Use safe read with stability check to prevent race conditions
    try:
        content = read_workspace_safe(workspace_path, check_stability=True)
    except (FileNotFoundError, TimeoutError):
        return False

    # Template placeholder patterns that indicate unmodified content
    # Based on current template format (.orch/templates/WORKSPACE.md)
    template_patterns = [
        r'\[workspace-name\]',                  # Workspace title placeholder
        r'\[Owner name\]',                      # Owner field placeholder
        r'\[YYYY-MM-DD\]',                      # Date placeholders (appears multiple times)
        r'\[Description\]',                     # Task description placeholders
        r'\[Phase Name\]',                      # Phase name in progress tracking
        r'\[Example:',                          # Example text in checkpoint markers
        r'\[What led to this work\?\]',        # Context section placeholder
        r'\[Impact/value point',                # "Why this matters" section
        r'\[Link to ROADMAP',                   # ROADMAP reference placeholder
        r'\[What needs to exist',               # Dependencies section
        r'\[Background needed',                 # Alternative context placeholder
        r'^\*\*TLDR:\*\*\s*\[',                 # Unpopulated TLDR (starts with [)
        r'\[One sentence describing',           # TLDR guideline text still present
    ]

    # Count how many placeholder patterns are still present
    placeholder_count = 0
    for pattern in template_patterns:
        if re.search(pattern, content, re.MULTILINE):
            placeholder_count += 1

    # If 5 or more placeholders remain, consider it an unmodified template
    # This threshold allows for some minor edits while still catching templates
    return placeholder_count >= 5


# ===== Validation Functions (Task 1) =====

def validate_workspace_name(name: str) -> None:
    """
    Validate workspace name follows kebab-case format and length constraints.

    Args:
        name: Workspace name to validate

    Raises:
        WorkspaceValidationError: If name is invalid
    """
    # Check kebab-case format: lowercase, numbers, hyphens only
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        raise WorkspaceValidationError(
            f"Invalid workspace name: '{name}'\n"
            "Must be kebab-case: lowercase, numbers, hyphens only\n"
            "Example: 'feature-name'"
        )

    # Check length (max 70 chars - modern terminals handle this well)
    if len(name) > 70:
        raise WorkspaceValidationError(
            f"Workspace name too long: {len(name)} chars (max 70)\n"
            "Long names break tab completion and tmux window display"
        )


def validate_workspace_type(workspace_type: str) -> None:
    """
    Validate workspace type is one of the allowed values.

    Args:
        workspace_type: Type to validate

    Raises:
        WorkspaceValidationError: If type is invalid
    """
    valid_types = ["planning", "implementation", "investigation"]
    if workspace_type not in valid_types:
        raise WorkspaceValidationError(
            f"Invalid workspace type: '{workspace_type}'\n"
            f"Must be one of: {', '.join(valid_types)}"
        )


def validate_environment(project_dir: Path) -> None:
    """
    Validate project environment is set up for workspace creation.

    Checks for .orch directory and template file. Auto-creates
    workspace subdirectory if missing.

    Args:
        project_dir: Project root directory

    Raises:
        WorkspaceValidationError: If environment is not set up correctly
    """
    # Check .orch directory exists
    orch_dir = project_dir / ".orch"
    if not orch_dir.exists():
        raise WorkspaceValidationError(
            f".orch/ directory not found in {project_dir}\n"
            f"Are you in the project root? (Current: {project_dir})\n"
            f"Run: mkdir -p {orch_dir}/workspace"
        )

    # Auto-create workspace directory if missing
    workspace_dir = orch_dir / "workspace"
    workspace_dir.mkdir(exist_ok=True)

    # Check template exists
    template_file = Path.home() / ".orch/templates/WORKSPACE.md"
    if not template_file.exists():
        raise WorkspaceValidationError(
            f"Workspace template not found: {template_file}\n"
            "Run: orch sync-templates"
        )


# ===== Template Rendering Functions (Task 2) =====

def get_owner() -> str:
    """
    Get owner name from git config or fall back to 'Agent'.

    Returns:
        Owner name (git user.name or 'Agent')
    """
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return 'Agent'


def get_phase_from_type(workspace_type: str) -> str:
    """
    Map workspace type to initial phase.

    Args:
        workspace_type: Type of workspace (planning|implementation|investigation)

    Returns:
        Initial phase name
    """
    phase_map = {
        'planning': 'Planning',
        'implementation': 'Implementing',
        'investigation': 'Investigating'
    }
    return phase_map.get(workspace_type, 'Planning')


def get_orchestrator_from_type(workspace_type: str) -> str:
    """
    Map workspace type to orchestrator skill reference.

    Args:
        workspace_type: Type of workspace

    Returns:
        Orchestrator file path or empty string
    """
    if workspace_type == 'investigation':
        return 'file://~/.claude/skills/systematic-debugging/SKILL.md'
    return ''


def render_template(
    workspace_name: str,
    owner: str,
    phase: str,
    orchestrator: str
) -> str:
    """
    Render workspace template with provided values using Jinja2.

    Args:
        workspace_name: Name of the workspace (kebab-case)
        owner: Owner name
        phase: Initial phase
        orchestrator: Orchestrator skill reference

    Returns:
        Rendered template content

    Raises:
        WorkspaceValidationError: If template file not found
    """
    # Locate template file
    template_file = Path.home() / ".orch/templates/WORKSPACE.md"
    if not template_file.exists():
        raise WorkspaceValidationError(
            f"Workspace template not found: {template_file}\n"
            "Run: orch sync-templates"
        )

    # Read template
    template_content = template_file.read_text()

    # Create Jinja2 template
    template = Template(template_content)

    # Generate timestamps
    now = datetime.now()
    started = now.strftime("%Y-%m-%d")
    last_updated = now.strftime("%Y-%m-%d %H:%M")
    resumed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Render template
    rendered = template.render(
        workspace_name=workspace_name,
        owner=owner,
        started=started,
        last_updated=last_updated,
        phase=phase,
        orchestrator=orchestrator,
        resumed_at=resumed_at
    )

    return rendered


# ===== Workspace State Detection (Task 3) =====

class WorkspaceState(Enum):
    """Represents the state of a workspace."""
    MISSING = "missing"      # No directory or file exists
    PARTIAL = "partial"      # Directory exists, no WORKSPACE.md (THE BUG)
    EMPTY = "empty"          # Template exists but unmodified
    ACTIVE = "active"        # Work in progress
    COMPLETED = "completed"  # Phase: Complete


def detect_workspace_state(workspace_path: Path) -> WorkspaceState:
    """
    Detect the current state of a workspace.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        WorkspaceState enum value

    States:
        - MISSING: Directory doesn't exist
        - PARTIAL: Directory exists but no WORKSPACE.md (the bug we're fixing)
        - EMPTY: WORKSPACE.md exists but is unmodified template
        - ACTIVE: WORKSPACE.md exists with real content and phase != Complete
        - COMPLETED: WORKSPACE.md exists and phase is Complete
    """
    workspace_path = Path(workspace_path)
    workspace_file = workspace_path / "WORKSPACE.md"

    # State 1: MISSING - Directory doesn't exist
    if not workspace_path.exists():
        return WorkspaceState.MISSING

    # State 2: PARTIAL - Directory exists but no WORKSPACE.md (THE BUG)
    if not workspace_file.exists():
        return WorkspaceState.PARTIAL

    # State 3: EMPTY - Template exists but unmodified
    if is_unmodified_template(workspace_file):
        return WorkspaceState.EMPTY

    # State 4: COMPLETED - Phase is Complete
    signal = parse_workspace(workspace_file)
    if signal.phase and signal.phase.lower() == 'complete':
        return WorkspaceState.COMPLETED

    # State 5: ACTIVE - Has real content, work in progress
    return WorkspaceState.ACTIVE


# ===== Core Workspace Creation (Task 4) =====

def create_workspace(
    workspace_name: str,
    project_dir: Path,
    workspace_type: str = "planning",
    owner: Optional[str] = None,
    resume: bool = False
) -> dict:
    """
    Create a new workspace with validation, state detection, and template rendering.

    Args:
        workspace_name: Name of workspace (kebab-case)
        project_dir: Project root directory
        workspace_type: Type of workspace (planning|implementation|investigation)
        owner: Owner name (defaults to git config or 'Agent')
        resume: Allow resuming existing workspaces

    Returns:
        dict with workspace info:
            - workspace_file: Relative path to WORKSPACE.md
            - workspace_dir: Relative path to workspace directory
            - workspace_name: Workspace name
            - phase: Initial phase
            - owner: Owner name
            - started: Start date (YYYY-MM-DD)

    Raises:
        WorkspaceValidationError: If validation fails or workspace exists without resume
    """
    # Convert to Path object
    project_dir = Path(project_dir)

    # Step 1: Validate inputs
    validate_workspace_name(workspace_name)
    validate_workspace_type(workspace_type)
    validate_environment(project_dir)

    # Step 2: Detect workspace state
    workspace_path = project_dir / ".orch" / "workspace" / workspace_name
    state = detect_workspace_state(workspace_path)

    # Step 3: Handle different states
    if state == WorkspaceState.ACTIVE or state == WorkspaceState.COMPLETED:
        if not resume:
            raise WorkspaceValidationError(
                f"Workspace '{workspace_name}' already exists\n"
                f"State: {state.value}\n"
                "Use resume=True to resume existing workspace"
            )
        # If resuming, just return info about existing workspace
        workspace_file = workspace_path / "WORKSPACE.md"
        signal = parse_workspace(workspace_file)
        started = datetime.now().strftime("%Y-%m-%d")  # Placeholder
        owner_name = owner or get_owner()

        return _build_result_dict(
            workspace_file=workspace_file,
            workspace_name=workspace_name,
            phase=signal.phase or get_phase_from_type(workspace_type),
            owner=owner_name,
            started=started,
            project_dir=project_dir
        )

    # Step 4: Get or default owner
    owner_name = owner or get_owner()

    # Step 5: Map type to phase and orchestrator
    phase = get_phase_from_type(workspace_type)
    orchestrator = get_orchestrator_from_type(workspace_type)

    # Step 6: Create workspace directory if needed (handles MISSING and PARTIAL states)
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Step 7: Render and write WORKSPACE.md
    workspace_file = workspace_path / "WORKSPACE.md"
    content = render_template(
        workspace_name=workspace_name,
        owner=owner_name,
        phase=phase,
        orchestrator=orchestrator
    )
    workspace_file.write_text(content)

    # Explicit sync to ensure file is visible to other processes immediately
    # This reduces the race condition window between write and agent spawn
    try:
        # Force filesystem sync by touching the parent directory
        workspace_path.stat()  # Touch directory to force sync
    except Exception:
        pass  # Sync is defensive; don't fail if it doesn't work

    # Step 8: Get started date
    started = datetime.now().strftime("%Y-%m-%d")

    # Step 9: Build and return result dict
    return _build_result_dict(
        workspace_file=workspace_file,
        workspace_name=workspace_name,
        phase=phase,
        owner=owner_name,
        started=started,
        project_dir=project_dir
    )


def _build_result_dict(
    workspace_file: Path,
    workspace_name: str,
    phase: str,
    owner: str,
    started: str,
    project_dir: Path
) -> dict:
    """
    Build result dictionary matching bash script JSON output format.

    Args:
        workspace_file: Absolute path to WORKSPACE.md
        workspace_name: Workspace name
        phase: Current phase
        owner: Owner name
        started: Start date
        project_dir: Project directory

    Returns:
        dict with workspace info
    """
    # Make paths relative to project .orch directory
    orch_dir = project_dir / ".orch"

    try:
        rel_workspace_file = workspace_file.relative_to(orch_dir)
        rel_workspace_dir = workspace_file.parent.relative_to(orch_dir)
    except ValueError:
        # If relative path fails, use as-is
        rel_workspace_file = workspace_file
        rel_workspace_dir = workspace_file.parent

    return {
        "workspace_file": str(rel_workspace_file),
        "workspace_dir": str(rel_workspace_dir),
        "workspace_name": workspace_name,
        "phase": phase,
        "owner": owner,
        "started": started
    }
