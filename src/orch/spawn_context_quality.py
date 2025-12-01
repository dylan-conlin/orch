"""
Spawn context quality validation.

Validates spawn contexts for completeness and quality indicators as defined in:
.orch/decisions/2025-11-19-spawn-context-first-class-orchestrator-artifact.md

Phase 2 implementation of SPAWN_CONTEXT.md as first-class artifact feature.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# Minimum line count for spawn context - contexts below this threshold
# are likely incomplete/insufficient and should fail fast
MINIMUM_LINE_COUNT = 100


class SpawnContextTooShortError(Exception):
    """Raised when spawn context is below minimum line count."""

    def __init__(self, line_count: int, min_lines: int = MINIMUM_LINE_COUNT, workspace_name: str = None):
        self.line_count = line_count
        self.min_lines = min_lines
        self.workspace_name = workspace_name
        workspace_info = f" for workspace '{workspace_name}'" if workspace_name else ""
        super().__init__(
            f"Spawn context{workspace_info} has only {line_count} lines "
            f"(minimum {min_lines} required). "
            f"This usually indicates insufficient context for the agent to work effectively. "
            f"Check that skill content is being loaded and all template sections are filled."
        )


@dataclass
class QualityIndicator:
    """A single quality indicator (warning or check result)."""
    message: str
    severity: str  # "critical", "warning", "info"
    section: str   # Which section this relates to


@dataclass
class SpawnContextQuality:
    """Result of spawn context quality validation."""
    is_complete: bool
    warnings: List[QualityIndicator]
    score: int  # 0-100 percentage
    sections_present: List[str] = field(default_factory=list)
    sections_missing: List[str] = field(default_factory=list)
    line_count: int = 0  # Number of lines in context


# Define required sections with their patterns and severities
# Pattern, display name, severity if missing, required for completeness
REQUIRED_SECTIONS = [
    {
        "name": "TASK",
        "pattern": r"^TASK:\s*\S",
        "severity": "critical",
        "required": True,
        "weight": 20,
    },
    {
        "name": "SCOPE",
        "pattern": r"^SCOPE:\s*\n.*-\s*IN:",
        "severity": "critical",
        "required": True,
        "weight": 20,
    },
    {
        "name": "SESSION SCOPE",
        "pattern": r"^SESSION SCOPE:\s*\S",
        "severity": "warning",
        "required": True,
        "weight": 15,
    },
    {
        "name": "AUTHORITY",
        "pattern": r"^AUTHORITY:|You have authority to decide:",
        "severity": "warning",
        "required": True,
        "weight": 15,
    },
    {
        "name": "DELIVERABLES",
        "pattern": r"^DELIVERABLES.*:|ADDITIONAL DELIVERABLES:",
        "severity": "critical",
        "required": True,
        "weight": 20,
    },
    {
        "name": "VERIFICATION",
        "pattern": r"^VERIFICATION REQUIRED:|VERIFICATION:",
        "severity": "info",
        "required": False,
        "weight": 10,
    },
]

# Placeholder patterns that indicate unfilled template values
PLACEHOLDER_PATTERNS = [
    r"\[One sentence description\]",
    r"\[Agent to define based on task\]",
    r"\[What's in scope\]",
    r"\[What's explicitly out of scope\]",
    r"\[Small/Medium/Large\]",
]


def _check_section_present(content: str, section: dict) -> bool:
    """Check if a section is present in the content."""
    pattern = section["pattern"]
    return bool(re.search(pattern, content, re.MULTILINE))


def _check_placeholder(content: str, section_name: str) -> Optional[str]:
    """Check if section contains placeholder text."""
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, content):
            return f"{section_name} contains placeholder text"
    return None


def _get_task_text(content: str) -> Optional[str]:
    """Extract the TASK line text."""
    match = re.search(r"^TASK:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def validate_spawn_context_quality(content: str) -> SpawnContextQuality:
    """
    Validate spawn context for completeness and quality.

    Checks for:
    - Required sections (TASK, SCOPE, SESSION SCOPE, AUTHORITY, DELIVERABLES)
    - Optional sections (VERIFICATION)
    - Placeholder text that wasn't filled in
    - Quality indicators

    Args:
        content: The spawn context content to validate

    Returns:
        SpawnContextQuality with is_complete, warnings, score, and section lists
    """
    warnings: List[QualityIndicator] = []
    sections_present: List[str] = []
    sections_missing: List[str] = []
    total_weight = 0
    earned_weight = 0

    # Check each required section
    for section in REQUIRED_SECTIONS:
        total_weight += section["weight"]

        if _check_section_present(content, section):
            sections_present.append(section["name"])
            earned_weight += section["weight"]
        else:
            sections_missing.append(section["name"])
            if section["required"]:
                warnings.append(QualityIndicator(
                    message=f"Missing {section['name']} section",
                    severity=section["severity"],
                    section=section["name"]
                ))

    # Check for placeholder text in TASK
    task_text = _get_task_text(content)
    if task_text:
        for pattern in PLACEHOLDER_PATTERNS:
            if re.search(pattern, task_text):
                warnings.append(QualityIndicator(
                    message="TASK contains placeholder text (not filled in)",
                    severity="critical",
                    section="TASK"
                ))
                # Remove earned weight for unfilled TASK
                if "TASK" in sections_present:
                    earned_weight -= 20
                    sections_present.remove("TASK")
                    sections_missing.append("TASK")
                break

    # Calculate line count
    line_count = len(content.split('\n')) if content else 0

    # Check minimum line count
    if line_count < MINIMUM_LINE_COUNT:
        warnings.append(QualityIndicator(
            message=f"Context has only {line_count} lines (minimum {MINIMUM_LINE_COUNT} required)",
            severity="critical",
            section="LINE_COUNT"
        ))

    # Calculate score
    score = int((earned_weight / total_weight) * 100) if total_weight > 0 else 0

    # Determine if complete (all required sections present and no critical issues)
    required_section_names = [s["name"] for s in REQUIRED_SECTIONS if s["required"]]
    has_all_required = all(name in sections_present for name in required_section_names)
    has_critical_warnings = any(w.severity == "critical" for w in warnings)
    is_complete = has_all_required and not has_critical_warnings

    return SpawnContextQuality(
        is_complete=is_complete,
        warnings=warnings,
        score=score,
        sections_present=sections_present,
        sections_missing=sections_missing,
        line_count=line_count
    )


def format_quality_for_human(quality: SpawnContextQuality) -> str:
    """
    Format spawn context quality for human-readable output.

    Used by `orch check` command to display quality indicators.

    Args:
        quality: The SpawnContextQuality result to format

    Returns:
        Formatted string for CLI output
    """
    lines = []

    # Header
    if quality.is_complete:
        lines.append("✅ Spawn Context Quality: Complete")
    else:
        lines.append(f"⚠️  Spawn Context Quality: {quality.score}%")

    # Show line count
    lines.append(f"  Lines: {quality.line_count} (minimum: {MINIMUM_LINE_COUNT})")

    # Show present sections with checkmarks
    for section in quality.sections_present:
        lines.append(f"  ✓ {section} defined")

    # Show warnings
    for warning in quality.warnings:
        icon = "❌" if warning.severity == "critical" else "⚠️"
        lines.append(f"  {icon} {warning.message}")

    return "\n".join(lines)


def validate_spawn_context_length(
    content: str,
    min_lines: int = MINIMUM_LINE_COUNT,
    workspace_name: str = None
) -> None:
    """
    Validate that spawn context meets minimum line count.

    This is a "fail fast" check that should be called before spawning an agent.
    Contexts below the minimum are likely incomplete and will cause agents to
    ask clarifying questions or make incorrect assumptions.

    Args:
        content: The spawn context content to validate
        min_lines: Minimum number of lines required (default: MINIMUM_LINE_COUNT)
        workspace_name: Optional workspace name for error message context

    Raises:
        SpawnContextTooShortError: If content has fewer than min_lines lines
    """
    line_count = len(content.split('\n')) if content else 0
    if line_count < min_lines:
        raise SpawnContextTooShortError(line_count, min_lines, workspace_name)


def format_quality_for_json(quality: SpawnContextQuality) -> dict:
    """
    Format spawn context quality for JSON output.

    Used by `orch check --format json` command.

    Args:
        quality: The SpawnContextQuality result to format

    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "is_complete": quality.is_complete,
        "score": quality.score,
        "line_count": quality.line_count,
        "sections_present": quality.sections_present,
        "sections_missing": quality.sections_missing,
        "warnings": [
            {
                "message": w.message,
                "severity": w.severity,
                "section": w.section
            }
            for w in quality.warnings
        ]
    }
