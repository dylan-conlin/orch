"""
Agent work verification module.

Handles:
- Verification of agent work completion requirements
- Deliverable existence checks
- Test result validation
- Investigation artifact verification

Note: WORKSPACE.md is no longer used. Agent state is tracked via beads comments.
Phase verification happens via `bd show` (beads comments contain "Phase: <state>").
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

        # Check .kb/ first (new location), then .orch/ (legacy fallback)
        for base_dir in [".kb", ".orch"]:
            investigations_dir = project_dir / base_dir / "investigations"
            if investigations_dir.exists():
                # Search recursively in investigation subdirectories
                pattern = f"**/{workspace_name}.md"
                matching_files = list(investigations_dir.glob(pattern))
                if matching_files:
                    return True

        return False

    # Skip workspace deliverable check - beads is now source of truth
    # WORKSPACE.md is no longer created (see investigation 2025-12-05-investigate-where-workspace-files-still.md)
    if deliverable == 'workspace':
        return True  # Always pass - workspace tracking replaced by beads

    # Deliverable types and their expected locations
    # Check .kb/ first (new location), then .orch/ (legacy fallback)
    deliverable_subdirs = {
        'decision': 'decisions',
        'knowledge': 'knowledge',
    }

    if deliverable in deliverable_subdirs:
        subdir = deliverable_subdirs[deliverable]
        for base_dir in [".kb", ".orch"]:
            path = project_dir / base_dir / subdir / f"{workspace_name}.md"
            if path.exists():
                return True
        return False

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

    Primary verification is via beads comments (agent reports "Phase: Complete").
    WORKSPACE.md is no longer used - all agent state is in beads.

    Checks:
    - Beads phase is Complete (verified separately in close_beads_issue())
    - Deliverables exist (from skill metadata)
    - Git commits present (if git repo)

    For investigation skills with primary_artifact, verifies the artifact exists
    and has Phase: Complete.

    Args:
        workspace_path: Path to workspace directory
        project_dir: Path to project directory
        agent_info: Optional agent registry info (for skill metadata lookup)
        skip_test_check: Skip test verification check (unused - kept for API compat)

    Returns:
        VerificationResult with passed status and any errors
    """
    from orch.logging import OrchLogger

    logger = OrchLogger()
    errors: List[str] = []
    warnings: List[str] = []

    # Check for primary_artifact (investigation skills)
    primary_artifact_path = None
    if agent_info and agent_info.get('primary_artifact'):
        primary_artifact_path = Path(agent_info['primary_artifact']).expanduser()
        if not primary_artifact_path.is_absolute():
            primary_artifact_path = (project_dir / primary_artifact_path).resolve()

    # Path 1: Investigation skills with primary_artifact
    # Verify the investigation file exists and has Phase: Complete
    if primary_artifact_path:
        logger.log_event("verify", "Verifying investigation artifact", {
            "workspace": str(workspace_path),
            "artifact": str(primary_artifact_path)
        }, level="INFO")
        return _verify_investigation_artifact(
            primary_artifact_path,
            workspace_path,
            project_dir,
            agent_info
        )

    # Path 2: Beads-tracked agents (primary path)
    # Phase verification happens in close_beads_issue() - just check deliverables here
    if agent_info and agent_info.get('beads_id'):
        logger.log_event("verify", "Using beads as source of truth", {
            "workspace": str(workspace_path),
            "beads_id": agent_info.get('beads_id')
        }, level="INFO")

        # Verify required deliverables exist
        if agent_info.get('skill'):
            skill_name = agent_info['skill']
            deliverables = _get_skill_deliverables(skill_name)
            for deliverable in deliverables:
                if not _check_deliverable_exists(deliverable, workspace_path, project_dir, agent_info):
                    errors.append(f"Missing deliverable: {deliverable}")
                    logger.log_event("verify", "Missing deliverable", {
                        "deliverable": deliverable,
                        "skill": skill_name
                    })

        # Check git commits present (warning only)
        git_dir = project_dir / ".git"
        if git_dir.exists():
            if not _has_commits_in_workspace(workspace_path, project_dir):
                warnings.append("No commits found in workspace - agent may not have committed work")

        if errors:
            return VerificationResult(passed=False, errors=errors, warnings=warnings)
        return VerificationResult(passed=True, errors=[], warnings=warnings)

    # Path 3: Ad-hoc spawns (no beads_id)
    # Allow completion when commits exist since spawn time
    if agent_info and agent_info.get('spawned_at'):
        spawned_at = agent_info['spawned_at']
        logger.log_event("verify", "Checking commits since spawn time for ad-hoc spawn", {
            "workspace": str(workspace_path),
            "spawned_at": spawned_at
        }, level="INFO")

        try:
            # Check if any commits exist since spawn time
            result = subprocess.run(
                ['git', 'log', f'--since={spawned_at}', '--oneline'],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0 and result.stdout.strip():
                # Commits exist - allow completion
                logger.log_event("verify", "Ad-hoc spawn verified via commits", {
                    "workspace": str(workspace_path),
                    "commits_found": len(result.stdout.strip().split('\n'))
                }, level="INFO")
                warnings.append("Ad-hoc spawn verified via git commits since spawn time")
                return VerificationResult(passed=True, errors=[], warnings=warnings)
        except Exception as e:
            logger.log_event("verify", "Git log check failed", {
                "error": str(e)
            }, level="WARNING")

    # No verification method available
    errors.append("Cannot verify agent work: no beads_id, no primary_artifact, and no commits since spawn")
    return VerificationResult(passed=False, errors=errors, warnings=warnings)


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
