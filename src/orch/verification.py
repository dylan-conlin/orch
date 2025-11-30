"""
Agent work verification module.

Handles:
- Verification of agent work completion requirements
- Deliverable existence checks
- Test result validation
- Investigation artifact verification
"""

from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field
import re
import subprocess


@dataclass
class VerificationResult:
    """Result of agent work verification."""
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _get_skill_deliverables(skill_name: str) -> List[str]:
    """
    Get deliverables from skill SKILL.md frontmatter.

    Args:
        skill_name: Name of skill (e.g., 'systematic-debugging')

    Returns:
        List of deliverable types (e.g., ['workspace', 'investigation'])
    """
    from orch.spawn import discover_skills

    # Discover all skills and get metadata for the requested skill
    skills = discover_skills()

    if skill_name not in skills:
        return []

    skill_metadata = skills[skill_name]

    # Extract deliverable types from metadata (SkillDeliverable objects)
    deliverables = skill_metadata.deliverables

    # Return list of REQUIRED deliverable types only
    # Note: Phase-conditional deliverables (investigation when investigation phase
    # included) are marked required=false in skill metadata and filtered here.
    # Future: Could parse workspace to determine which phases were configured.
    return [d.type for d in deliverables if d.required] if deliverables else []


def _check_deliverable_exists(
    deliverable: str,
    workspace_path: Path,
    project_dir: Path,
    agent_info: Optional[Dict] = None
) -> bool:
    """
    Check if deliverable exists.

    Args:
        deliverable: Deliverable type ('workspace', 'investigation', 'decision', etc.)
        workspace_path: Path to workspace directory
        project_dir: Path to project directory

    Returns:
        True if deliverable exists, False otherwise
    """
    workspace_name = workspace_path.name

    # Handle investigation separately (requires recursive search)
    if deliverable == 'investigation':
        if agent_info and agent_info.get('primary_artifact'):
            primary_path = Path(agent_info['primary_artifact']).expanduser()
            if not primary_path.is_absolute():
                primary_path = (project_dir / primary_path).resolve()
            return primary_path.exists()

        investigations_dir = project_dir / ".orch" / "investigations"

        if not investigations_dir.exists():
            return False

        # Search recursively in investigation subdirectories
        # Subdirectories: systems/, feasibility/, audits/, agent-failures/, performance/
        pattern = f"**/{workspace_name}.md"
        matching_files = list(investigations_dir.glob(pattern))

        return len(matching_files) > 0

    # Deliverable types and their expected locations (flat structure)
    deliverable_paths = {
        'workspace': workspace_path / "WORKSPACE.md",
        'decision': project_dir / ".orch" / "decisions" / f"{workspace_name}.md",
        'knowledge': project_dir / ".orch" / "knowledge" / f"{workspace_name}.md",
    }

    # Check specific deliverable type
    if deliverable in deliverable_paths:
        return deliverable_paths[deliverable].exists()

    # For 'commits', check git log (special case)
    if deliverable == 'commits':
        return _has_commits_in_workspace(workspace_path, project_dir)

    # Unknown deliverable type - assume satisfied (don't block)
    return True


def _has_commits_in_workspace(workspace_path: Path, project_dir: Path) -> bool:
    """
    Check if workspace has associated git commits.

    Looks for commits with workspace name in commit message.

    Args:
        workspace_path: Path to workspace directory
        project_dir: Path to project directory

    Returns:
        True if commits found, False otherwise
    """
    workspace_name = workspace_path.name

    try:
        # Search git log for workspace name in commit messages
        result = subprocess.run(
            ['git', 'log', '--all', '--grep', workspace_name, '--oneline'],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False
        )

        # If any commits found, return True
        return bool(result.stdout.strip())
    except Exception:
        # Git command failed - assume no commits
        return False


def verify_agent_work(
    workspace_path: Path,
    project_dir: Path,
    agent_info: Optional[Dict] = None,
    skip_test_check: bool = False
) -> VerificationResult:
    """
    Verify agent work meets completion requirements.

    Checks (Phase 4 enhanced):
    - Workspace exists
    - Phase is Complete
    - Verification requirements complete (from workspace)
    - No pending next-actions
    - Test results (if present)
    - Deliverables exist (if specified)
    - Git commits present (if git repo)

    Args:
        workspace_path: Path to workspace directory
        project_dir: Path to project directory
        agent_info: Optional agent registry info (for skill metadata lookup)
        skip_test_check: Skip test verification check (use when pre-existing test failures block completion)

    Returns:
        VerificationResult with passed status and any errors
    """
    from orch.workspace import parse_workspace_verification
    from orch.logging import OrchLogger

    logger = OrchLogger()
    errors = []
    warnings = []
    primary_artifact_path = None
    if agent_info and agent_info.get('primary_artifact'):
        primary_artifact_path = Path(agent_info['primary_artifact']).expanduser()
        if not primary_artifact_path.is_absolute():
            primary_artifact_path = (project_dir / primary_artifact_path).resolve()

    # Check workspace exists
    workspace_file = workspace_path / "WORKSPACE.md"
    if not workspace_file.exists():
        if primary_artifact_path:
            logger.log_event("verify", "Workspace missing - verifying investigation artifact", {
                "workspace": str(workspace_path),
                "artifact": str(primary_artifact_path)
            }, level="INFO")
            return _verify_investigation_artifact(
                primary_artifact_path,
                workspace_path,
                project_dir,
                agent_info
            )

        errors.append(f"Workspace file not found: {workspace_file}")
        return VerificationResult(passed=False, errors=errors, warnings=warnings)

    logger.log_event("verify", "Parsing workspace verification data", {
        "workspace_file": str(workspace_file)
    })

    # Phase 4: Parse workspace with verification data
    data = parse_workspace_verification(workspace_file)

    # Check Phase: Complete
    if not data.phase:
        errors.append("Phase field not found in workspace")
    elif data.phase.lower() != "complete":
        errors.append(f"Phase is '{data.phase}', must be 'Complete'")

    # Phase 4: Check verification requirements complete
    if not data.verification_complete:
        # List unchecked items for clarity
        unchecked = [item.text for item in data.verification_items if not item.checked]
        if unchecked:
            errors.append(f"Verification incomplete. Unchecked items:\n  - " + "\n  - ".join(unchecked[:3]))
        else:
            # Verification section exists but no items found
            warnings.append("No verification items found in workspace")

    # Phase 4: Check for pending next-actions
    if data.has_pending_actions:
        # List first few pending actions
        pending = [item.text for item in data.next_actions if not item.checked]
        if pending:
            errors.append(f"Next-Actions incomplete. Pending items:\n  - " + "\n  - ".join(pending[:3]))

    # Phase 4: Check test results (if present and not skipped)
    if data.test_results and not skip_test_check:
        if not data.test_results.passed:
            errors.append(f"Tests failed: {data.test_results.output}")
            logger.log_event("verify", "Test failure detected", {
                "total": data.test_results.total,
                "failed": data.test_results.failed
            })

    # Phase 4: Check deliverables exist (from skill metadata)
    if agent_info and agent_info.get('skill'):
        skill_name = agent_info['skill']
        deliverables = _get_skill_deliverables(skill_name)

        if deliverables:
            for deliverable in deliverables:
                if not _check_deliverable_exists(deliverable, workspace_path, project_dir, agent_info):
                    errors.append(f"Missing deliverable: {deliverable}")
                    logger.log_event("verify", "Missing deliverable", {
                        "deliverable": deliverable,
                        "skill": skill_name
                    })

    # Phase 4: Check git commits present (if git repo)
    git_dir = project_dir / ".git"
    if git_dir.exists():
        if not _has_commits_in_workspace(workspace_path, project_dir):
            warnings.append("No commits found in workspace - agent may not have committed work")

    # If errors, return early
    if errors:
        return VerificationResult(passed=False, errors=errors, warnings=warnings)

    # All checks passed
    return VerificationResult(passed=True, errors=[], warnings=warnings)


def _verify_investigation_artifact(
    primary_artifact: Path,
    workspace_path: Path,
    project_dir: Path,
    agent_info: Optional[Dict]
) -> VerificationResult:
    """
    Verification path for workspace-less investigation agents.
    """
    errors: List[str] = []
    warnings: List[str] = []

    primary_artifact = Path(primary_artifact).expanduser()
    if not primary_artifact.exists():
        errors.append(f"Investigation file not found: {primary_artifact}")
        return VerificationResult(passed=False, errors=errors, warnings=warnings)

    phase = _extract_investigation_phase(primary_artifact)
    if not phase:
        errors.append("Phase field not found in investigation file")
    elif phase.lower() != "complete":
        errors.append(f"Phase is '{phase}', must be 'Complete'")

    if agent_info:
        if not _check_deliverable_exists('investigation', workspace_path, project_dir, agent_info):
            errors.append("Missing deliverable: investigation")

    return VerificationResult(passed=(len(errors) == 0), errors=errors, warnings=warnings)


def _extract_investigation_phase(path: Path) -> Optional[str]:
    """Extract Phase value from an investigation file."""
    path = Path(path).expanduser()
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    match = re.search(
        r'\*\*Phase:\*\*\s*([^\n]+)|^Phase:\s*([^\n]+)|^\*\*Status:\*\*\s+Phase:\s*([^\n]+)',
        content,
        re.MULTILINE
    )
    if match:
        return (match.group(1) or match.group(2) or match.group(3)).strip()

    return None


def _extract_section(content: str, section_header: str) -> Optional[str]:
    """
    Extract content between a section header and the next section.

    Args:
        content: Full markdown content
        section_header: Section header to find (e.g., "## Handoff Notes")

    Returns:
        Section content or None if not found
    """
    lines = content.split('\n')
    in_section = False
    section_lines = []

    for line in lines:
        if line.strip() == section_header:
            in_section = True
            continue

        if in_section:
            # Stop at next section header (##)
            if line.startswith('##'):
                break
            section_lines.append(line)

    return '\n'.join(section_lines) if section_lines else None
