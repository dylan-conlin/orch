"""
CDD pattern checking (deprecated).

WORKSPACE.md is no longer used for agent state tracking.
Beads is now the source of truth.

This module is kept for backward compatibility but pattern checking
is effectively a no-op.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class PatternViolation:
    """Represents a CDD pattern violation."""
    type: str
    severity: str  # 'critical', 'warning', 'info'
    message: str


def check_patterns(
    project_dir: Path | str,
    workspace_path: str
) -> List[PatternViolation]:
    """
    Check for CDD pattern violations.

    DEPRECATED: WORKSPACE.md is no longer used for agent state tracking.
    Beads is now the source of truth. This function always returns an empty list.

    Args:
        project_dir: Project directory path
        workspace_path: Relative path to workspace (e.g., '.orch/workspace/agent/')

    Returns:
        Empty list (pattern checking deprecated)
    """
    # WORKSPACE.md pattern checking removed - beads is source of truth
    return []
