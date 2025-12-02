from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from orch.workspace import parse_workspace, parse_workspace_verification
from orch.frontmatter import extract_phase as fm_extract_phase, extract_metadata
import re
from orch.patterns import check_patterns
from orch.context import ContextInfo
from orch.git_utils import CommitInfo
from orch.beads_integration import BeadsIntegration, BeadsCLINotFoundError, BeadsIssueNotFoundError


class Scenario(Enum):
    """Completion scenarios for agent workflow."""
    WORKING = "working"              # Phase not Complete, agent still working
    INTERACTIVE = "interactive"      # Interactive session (manual completion)
    BLOCKED = "blocked"              # Verification incomplete
    ACTION_NEEDED = "action_needed"  # Next-actions require decisions
    READY_COMPLETE = "ready_complete"  # ROADMAP work ready for orch complete
    READY_CLEAN = "ready_clean"      # Investigation complete, ready to clean


@dataclass
class AgentStatus:
    """Status of an agent."""
    agent_id: str
    needs_attention: bool = False
    priority: str = 'ok'  # 'critical', 'warning', 'info', 'ok'
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    phase: str = 'Unknown'
    violations: List[Any] = field(default_factory=list)
    context_info: Optional[ContextInfo] = None
    last_commit: Optional[CommitInfo] = None
    commits_since_spawn: int = 0

    # Phase 2: Completion scenario detection
    scenario: Optional[Scenario] = None
    recommendation: Optional[str] = None

    # Phase 2.5: Session awareness
    completed_at: Optional[datetime] = None
    age_str: Optional[str] = None
    is_stale: bool = False


def _is_template_placeholder(value: str) -> bool:
    """
    Check if a value looks like a template placeholder rather than an actual phase.

    Template placeholders contain:
    - Pipe characters with spaces: 'Active | Complete'
    - Brackets: '[Investigating/Complete]'
    """
    if not value:
        return True
    # Pipe-separated choices: 'Active | Complete'
    if ' | ' in value:
        return True
    # Bracket placeholders: '[Option1/Option2]'
    if value.startswith('[') and value.endswith(']'):
        return True
    return False


def extract_phase_from_file(path: Path) -> Optional[str]:
    """
    Extract Phase value from a coordination artifact (workspace or investigation file).

    Uses YAML frontmatter if present, falls back to inline markdown extraction.

    Args:
        path: Path to file containing '**Phase:**' style metadata or YAML frontmatter

    Returns:
        Phase string if found, else None
    """
    if not path:
        return None

    path = Path(path).expanduser()
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Use new frontmatter module (handles both frontmatter and inline with fallback)
    phase = fm_extract_phase(content)
    if phase:
        return phase

    # Legacy fallback: regex extraction for edge cases the frontmatter module might miss
    match = re.search(
        r'\*\*Phase:\*\*\s*([^\n]+)|^Phase:\s*([^\n]+)|^\*\*Status:\*\*\s+Phase:\s*([^\n]+)|\*\*Status:\*\*\s*([^\n]+)',
        content,
        re.MULTILINE
    )
    if match:
        phase = (match.group(1) or match.group(2) or match.group(3) or match.group(4)).strip()
        # Filter out template placeholder values like 'Active | Complete'
        if _is_template_placeholder(phase):
            return None
        return phase

    return None

def check_agent_status(agent_info: Dict[str, Any], check_context: bool = False, check_git: bool = False) -> AgentStatus:
    """
    Check status of an agent.

    Args:
        agent_info: Agent dict from registry (id, project_dir, workspace, window)
        check_context: If True, check context usage via /context command
        check_git: If True, check git commit history

    Returns:
        AgentStatus with alerts and priority
    """
    status = AgentStatus(agent_id=agent_info['id'])
    project_dir = Path(agent_info['project_dir'])
    workspace_path = agent_info['workspace']

    # Phase 3: Prefer beads-based phase detection when agent has beads_id
    beads_id = agent_info.get('beads_id')
    beads_phase = None
    if beads_id:
        try:
            beads = BeadsIntegration()
            beads_phase = beads.get_phase_from_comments(beads_id)
        except (BeadsCLINotFoundError, BeadsIssueNotFoundError):
            pass  # Fallback to workspace-based detection

    # Parse workspace for signals (workspace_file may not exist for investigation-only agents)
    workspace_file = project_dir / workspace_path / 'WORKSPACE.md'
    signal = parse_workspace(workspace_file)

    primary_artifact = agent_info.get('primary_artifact')
    primary_artifact_path = None
    if primary_artifact:
        primary_artifact_path = Path(primary_artifact).expanduser()
        if not primary_artifact_path.is_absolute():
            primary_artifact_path = (project_dir / primary_artifact_path).resolve()

    coordination_file = primary_artifact_path or workspace_file

    # Determine phase: beads > workspace > fallback
    if beads_phase:
        status.phase = beads_phase
    elif signal.phase:
        status.phase = signal.phase
    else:
        # Fallback completion detection when workspace phase is Unknown
        inferred_phase = _detect_completion_fallback(agent_info, project_dir)
        if inferred_phase:
            status.phase = inferred_phase

    # For investigation-oriented skills, prefer Phase from investigation file if available
    skill_name = agent_info.get('skill')
    if primary_artifact_path:
        artifact_phase = extract_phase_from_file(primary_artifact_path)
        if artifact_phase:
            status.phase = artifact_phase
    elif skill_name in ("investigation", "systematic-debugging", "codebase-audit"):
        investigations_dir = project_dir / ".orch" / "investigations"
        if investigations_dir.exists():
            workspace_name = Path(workspace_path).name
            try:
                matches = list(investigations_dir.rglob(f"{workspace_name}.md"))
            except Exception:
                matches = []
            if matches:
                inv_file = matches[0]
                try:
                    content = inv_file.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                if content:
                    phase_match = re.search(r"\*\*Phase:\*\*\s*([^\n]+)", content)
                    if phase_match:
                        phase = phase_match.group(1).strip()
                        # Filter out template placeholder values like 'Active | Complete'
                        if not _is_template_placeholder(phase):
                            status.phase = phase

    # Priority 1: Explicit signals (BLOCKED/QUESTION)
    if signal.has_signal:
        status.needs_attention = True
        status.priority = 'critical'
        status.alerts.append({
            'type': signal.signal_type,
            'message': signal.message,
            'level': 'critical'
        })
        return status  # Critical takes precedence

    # Priority 2: Context usage (if requested)
    if check_context:
        from orch.context import get_context_info
        context_info = get_context_info(agent_info)
        status.context_info = context_info

        if context_info and context_info.is_high_usage:
            status.needs_attention = True
            # Don't override 'critical' priority if already set
            if status.priority == 'ok':
                status.priority = 'warning'
            status.alerts.append({
                'type': 'context',
                'message': f'High context usage: {context_info.percentage:.1f}%',
                'level': 'warning'
            })

    # Priority 2.5: Git tracking (if requested)
    if check_git:
        from orch.git_utils import get_last_commit, count_commits_since

        # Get last commit
        last_commit = get_last_commit(project_dir)
        status.last_commit = last_commit

        # Count commits since agent spawned
        spawn_time_str = agent_info.get('spawned_at')
        if spawn_time_str:
            try:
                spawn_time = datetime.fromisoformat(spawn_time_str)
                commits_count = count_commits_since(project_dir, spawn_time)
                status.commits_since_spawn = commits_count

                # Flag implementation agents with no commits after 30 min
                time_running = datetime.now() - spawn_time
                if time_running > timedelta(minutes=30) and commits_count == 0:
                    # Check if agent is in implementation phase
                    if status.phase in ['Implementing', 'Implementation']:
                        status.needs_attention = True
                        if status.priority == 'ok':
                            status.priority = 'warning'
                        status.alerts.append({
                            'type': 'git',
                            'message': f'No commits after {int(time_running.total_seconds() / 60)} min (implementation phase)',
                            'level': 'warning'
                        })
            except (ValueError, TypeError):
                pass  # Invalid spawn time, skip git checking

    # Priority 2.75: AWAITING_VALIDATION detection (multi-phase validation pattern)
    if signal.awaiting_validation:
        status.needs_attention = True
        if status.priority == 'ok':
            status.priority = 'info'
        status.alerts.append({
            'type': 'validation',
            'message': '⏸️  Agent awaiting validation – run manual tests before starting next phase',
            'level': 'info'
        })

    # Priority 3: Pattern violations
    skip_workspace_checks = primary_artifact_path is not None
    violations = check_patterns(project_dir, workspace_path) if not skip_workspace_checks else []
    status.violations = violations

    # Check for critical violations
    critical_violations = [v for v in violations if v.severity == 'critical']
    if critical_violations:
        status.needs_attention = True
        status.priority = 'warning'  # Not as urgent as BLOCKED
        status.alerts.append({
            'type': 'pattern',
            'message': f'{len(critical_violations)} critical violations',
            'level': 'warning'
        })

    # Priority 4: Workspace population check
    from orch.workspace import is_unmodified_template
    if not skip_workspace_checks and is_unmodified_template(workspace_file):
        status.needs_attention = True
        if status.priority == 'ok':
            status.priority = 'warning'
        status.alerts.append({
            'type': 'workspace',
            'message': 'Workspace appears unpopulated (template placeholders still present)',
            'level': 'warning'
        })

    # Phase 2: Detect completion scenario
    # Pass the phase we determined (including inferred) to detect_completion_scenario
    scenario, recommendation = detect_completion_scenario(
        agent_info, coordination_file, primary_artifact_path,
        phase_override=status.phase if status.phase != 'Unknown' else None
    )
    status.scenario = scenario
    status.recommendation = recommendation

    # Phase 2.5: Add age tracking for completed agents
    if agent_info.get('completed_at'):
        from orch.session import format_relative_time, is_stale
        try:
            completed_dt = datetime.fromisoformat(agent_info['completed_at'])
            status.completed_at = completed_dt
            status.age_str = format_relative_time(completed_dt)
            status.is_stale = is_stale(completed_dt)

            # Add staleness warning to recommendation if stale
            if status.is_stale and recommendation:
                status.recommendation = f"⏰ {recommendation} (completed {status.age_str})\n      ⚠️  Stale completion - review workspace before completing"
            elif status.is_stale:
                status.recommendation = f"⏰ Completed {status.age_str} (stale - review before completing)"
        except (ValueError, TypeError):
            # Invalid timestamp, skip age tracking
            pass

    return status


def detect_completion_scenario(
    agent_info: Dict[str, Any],
    coordination_file: Path,
    primary_artifact: Optional[Path] = None,
    phase_override: Optional[str] = None
) -> tuple[Scenario, Optional[str]]:
    """
    Detect completion scenario for an agent.

    Args:
        agent_info: Agent dict from registry
        coordination_file: Path to coordination artifact (workspace or investigation file)
        primary_artifact: Investigation file path if agent is workspace-less
        phase_override: Optional phase determined by fallback detection (e.g., "Complete (inferred)")

    Returns:
        Tuple of (Scenario, recommendation_text)
    """
    # Investigation-first workflow: use investigation file instead of workspace
    if primary_artifact:
        primary_artifact = Path(primary_artifact).expanduser()
        if primary_artifact.exists():
            phase = extract_phase_from_file(primary_artifact)
            if not phase or phase.lower() != 'complete':
                return (Scenario.WORKING, None)
            return (
                Scenario.READY_CLEAN,
                "✅ Ready: Investigation complete, no next-actions, ready to clean"
            )
        # Investigation file missing → treat as still working
        return (Scenario.WORKING, None)

    # Parse workspace with verification data
    data = parse_workspace_verification(coordination_file)

    # Determine effective phase: use override if provided, otherwise use workspace phase
    effective_phase = phase_override or data.phase

    # Scenario 1: Not complete yet - agent still working
    # Check for both "complete" and "complete (inferred)" patterns
    is_complete = effective_phase and 'complete' in effective_phase.lower()
    if not is_complete:
        return (Scenario.WORKING, None)

    # Scenario 1.5: Inferred completion (no workspace but detected complete via fallback signals)
    is_inferred = phase_override and 'inferred' in phase_override.lower()
    if is_inferred:
        # Workspace doesn't exist, so we can't verify - recommend manual check
        return (
            Scenario.READY_COMPLETE,
            "✅ Ready: Completion inferred (no workspace, but tmux closed), run `orch check` to verify"
        )

    # Scenario 2: Interactive session - manual completion required
    # Check if agent was spawned with --interactive flag
    is_interactive = agent_info.get('is_interactive', False)
    if is_interactive:
        return (Scenario.INTERACTIVE, "⚪ Interactive session (manual completion required)")

    # Scenario 3: Verification incomplete - blocked
    if not data.verification_complete:
        # Find first unchecked item
        unchecked = [item for item in data.verification_items if not item.checked]
        if unchecked:
            first_unchecked = unchecked[0].text[:60]  # Truncate long text
            return (
                Scenario.BLOCKED,
                f"❌ Blocked: Verification incomplete\n      {first_unchecked}"
            )
        else:
            # No verification items at all but verification_complete is False
            # This shouldn't happen with current logic, but handle gracefully
            return (Scenario.BLOCKED, "❌ Blocked: Verification incomplete")

    # Scenario 4: Next-actions require decisions
    if data.has_pending_actions:
        # Get first unchecked next-action
        unchecked_actions = [item for item in data.next_actions if not item.checked]
        if unchecked_actions:
            first_action = unchecked_actions[0].text[:60]
            return (
                Scenario.ACTION_NEEDED,
                f"⚠️  Action needed: {first_action}"
            )

    # At this point: Phase Complete, verification complete, no pending actions
    # Determine if this is ROADMAP work or investigation

    # Check if agent has ROADMAP reference
    has_roadmap_ref = agent_info.get('from_roadmap', False) or agent_info.get('roadmap_item')

    # Check if investigation file exists
    project_dir = Path(agent_info['project_dir'])
    workspace_path = agent_info['workspace']

    # Look for investigation files
    investigation_patterns = [
        project_dir / ".orch" / "investigations" / "*.md",
        project_dir / workspace_path / "investigation.md"
    ]

    has_investigation = False
    for pattern in investigation_patterns:
        if pattern.exists() or list(pattern.parent.glob(pattern.name)) if '*' in str(pattern) else False:
            has_investigation = True
            break

    # Scenario 5: ROADMAP work ready for completion
    if has_roadmap_ref:
        # Check if tests passed (if there were any)
        if data.test_results:
            if data.test_results.passed:
                return (
                    Scenario.READY_COMPLETE,
                    f"✅ Ready: Tests passed ({data.test_results.total}), ready for `orch complete`"
                )
            else:
                # Tests failed - this is actually a blocker
                return (
                    Scenario.BLOCKED,
                    f"❌ Blocked: Tests failed ({data.test_results.failed}/{data.test_results.total})"
                )
        else:
            # No test results, but verification complete
            return (
                Scenario.READY_COMPLETE,
                "✅ Ready: Verification complete, ready for `orch complete`"
            )

    # Scenario 6: Investigation complete, ready to clean
    if has_investigation:
        return (
            Scenario.READY_CLEAN,
            "✅ Ready: Investigation complete, no next-actions, ready to clean"
        )

    # Default: Work complete (no ROADMAP or investigation, but verified)
    return (
        Scenario.READY_COMPLETE,
        "✅ Ready: Work complete, ready for `orch complete`"
    )


def _detect_completion_fallback(agent_info: Dict[str, Any], project_dir: Path) -> Optional[str]:
    """
    Detect agent completion through fallback signals when workspace phase is Unknown.

    Uses multiple signals to infer completion:
    1. Deliverable exists (investigation file for investigation skill)
    2. Commits exist since agent spawn time
    3. Agent registry status is 'completed' (set by reconcile when window closes)

    Args:
        agent_info: Agent dict from registry
        project_dir: Project directory path

    Returns:
        Inferred phase string (e.g., "Complete (inferred)") or None
    """
    skill_name = agent_info.get('skill')
    workspace_path = agent_info.get('workspace', '')

    # Signal 1: Check registry status (set by reconcile when tmux window closes)
    # If registry says 'completed', agent is done regardless of workspace state
    if agent_info.get('status') == 'completed':
        return "Complete (inferred)"

    # Signal 2: Check for deliverable based on skill type
    if skill_name == 'investigation':
        # Look for investigation file in .orch/investigations/
        investigations_dir = project_dir / ".orch" / "investigations"
        if investigations_dir.exists():
            # Check for matching investigation file based on workspace name or date
            workspace_name = Path(workspace_path).name if workspace_path else ''

            # Try to find investigation files that match workspace pattern
            # Workspace names often follow: YYYY-MM-DD-inv-topic or inv-topic
            try:
                for inv_type_dir in investigations_dir.iterdir():
                    if inv_type_dir.is_dir():
                        for inv_file in inv_type_dir.glob("*.md"):
                            # Check if investigation file matches workspace name
                            if workspace_name and workspace_name in inv_file.stem:
                                # Found matching investigation - check its phase
                                phase = extract_phase_from_file(inv_file)
                                if phase and phase.lower() == 'complete':
                                    return "Complete (inferred)"
            except (OSError, PermissionError):
                pass  # Ignore file system errors

    # Signal 3: Check for commits since spawn (indicates work was done)
    spawn_time_str = agent_info.get('spawned_at')
    if spawn_time_str:
        try:
            from orch.git_utils import count_commits_since
            spawn_time = datetime.fromisoformat(spawn_time_str)
            commits_count = count_commits_since(project_dir, spawn_time)

            # If there are commits and the window is closed (status would be 'completed'),
            # we can infer completion. This is a weaker signal on its own.
            if commits_count > 0 and agent_info.get('status') == 'completed':
                return "Complete (inferred)"
        except (ValueError, TypeError, ImportError):
            pass

    # No fallback signals detected
    return None


def get_status_emoji(priority: str) -> str:
    """Get emoji for priority level."""
    return {
        'critical': '🔴',
        'warning': '🟡',
        'info': '⚪',
        'ok': '🟢'
    }.get(priority, '⚪')
