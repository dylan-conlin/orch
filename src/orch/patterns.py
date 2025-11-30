from pathlib import Path
from dataclasses import dataclass
from typing import List
from orch.workspace import parse_workspace

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

    Args:
        project_dir: Project directory path
        workspace_path: Relative path to workspace (e.g., '.orch/workspace/agent/')

    Returns:
        List of violations found
    """
    violations = []
    project_dir = Path(project_dir)
    full_workspace_path = project_dir / workspace_path

    # Check 1: Workspace directory exists
    if not full_workspace_path.exists():
        violations.append(PatternViolation(
            type='missing_workspace',
            severity='critical',
            message='Workspace directory does not exist'
        ))
        return violations  # Can't check further if workspace missing

    # Check 2: WORKSPACE.md exists
    workspace_file = full_workspace_path / 'WORKSPACE.md'
    if not workspace_file.exists():
        violations.append(PatternViolation(
            type='missing_workspace_file',
            severity='critical',
            message='WORKSPACE.md file missing'
        ))
        return violations

    # Check 3: Phase field present
    signal = parse_workspace(workspace_file)
    if not signal.phase:
        violations.append(PatternViolation(
            type='missing_phase',
            severity='warning',
            message='Phase field missing or not parseable'
        ))
    elif signal.phase == 'Planning':
        # Still on Planning might indicate agent hasn't progressed
        violations.append(PatternViolation(
            type='stuck_on_planning',
            severity='info',
            message='Agent still in Planning phase'
        ))

    return violations
