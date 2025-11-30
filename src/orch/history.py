"""
Skill usage tracking and analytics for orch history command.

Analyzes workspace files to extract skill usage patterns, measure adoption rates,
and identify gaps where skills could be applied but weren't.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
import re


@dataclass
class SkillUsage:
    """Represents usage of a specific skill in a workspace."""
    skill_name: str
    workspace_name: str
    workspace_path: Path
    phase: Optional[str] = None
    started: Optional[datetime] = None
    completed: Optional[datetime] = None
    success: bool = False  # True if Phase: Complete


@dataclass
class SkillStats:
    """Aggregated statistics for a skill."""
    skill_name: str
    total_uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    workspaces: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_uses == 0:
            return 0.0
        return (self.successful_uses / self.total_uses) * 100


@dataclass
class SkillAnalytics:
    """Complete analytics for skill usage."""
    stats_by_skill: Dict[str, SkillStats]
    total_workspaces: int
    workspaces_with_skills: int
    workspaces_without_skills: int
    date_range: tuple[Optional[datetime], Optional[datetime]]

    @property
    def skill_adoption_rate(self) -> float:
        """Percentage of workspaces that used skills."""
        if self.total_workspaces == 0:
            return 0.0
        return (self.workspaces_with_skills / self.total_workspaces) * 100


def extract_skill_from_workspace(workspace_path: Path) -> Optional[SkillUsage]:
    """
    Extract skill usage information from a workspace file.

    Args:
        workspace_path: Path to workspace directory or WORKSPACE.md file

    Returns:
        SkillUsage object if skill found, None otherwise
    """
    # Handle both directory and file paths
    if workspace_path.is_dir():
        workspace_file = workspace_path / 'WORKSPACE.md'
        workspace_name = workspace_path.name
    else:
        workspace_file = workspace_path
        workspace_name = workspace_path.parent.name

    if not workspace_file.exists():
        return None

    try:
        content = workspace_file.read_text()
    except Exception:
        return None

    # Pattern to match skill references (case-insensitive)
    # Matches multiple formats:
    # - "**Skill:** skill-name"
    # - "- Skill: skill-name"
    # - "Skill: skill-name"
    # - "Using skill-name skill:"
    skill_name = None

    # Try format 1: "**Skill:**", "- Skill:", "Skill:"
    skill_pattern_1 = r'(?:^|\n)(?:\*\*|\-\s+)?[Ss]kill:(?:\*\*)?\s*([a-z0-9-]+)'
    skill_match_1 = re.search(skill_pattern_1, content)
    if skill_match_1:
        skill_name = skill_match_1.group(1).strip()

    # Try format 2: "Using skill-name skill:"
    if not skill_name:
        skill_pattern_2 = r'Using\s+([a-z0-9-]+)\s+skill:'
        skill_match_2 = re.search(skill_pattern_2, content, re.IGNORECASE)
        if skill_match_2:
            skill_name = skill_match_2.group(1).strip()

    if not skill_name:
        return None

    # Extract phase
    phase = None
    phase_match = re.search(r'^\*\*Phase:\*\*\s*(\w+)', content, re.MULTILINE)
    if phase_match:
        phase = phase_match.group(1)

    # Extract started date
    started = None
    started_match = re.search(r'^\*\*Started:\*\*\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
    if started_match:
        try:
            started = datetime.strptime(started_match.group(1), '%Y-%m-%d')
        except ValueError:
            pass

    # Extract completion (check if phase is Complete)
    success = False
    completed = None
    if phase and phase.lower() == 'complete':
        success = True
        # Try to extract completion timestamp (could be from git or Last Updated)
        updated_match = re.search(r'^\*\*Last Updated:\*\*\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
        if updated_match:
            try:
                completed = datetime.strptime(updated_match.group(1), '%Y-%m-%d')
            except ValueError:
                pass

    return SkillUsage(
        skill_name=skill_name,
        workspace_name=workspace_name,
        workspace_path=workspace_path,
        phase=phase,
        started=started,
        completed=completed,
        success=success
    )


def scan_workspaces_for_skills(
    workspace_dir: Path,
    days: Optional[int] = None
) -> List[SkillUsage]:
    """
    Scan workspace directory for skill usage.

    Args:
        workspace_dir: Path to .orch/workspace directory
        days: Optional number of days to look back (filters by started date)

    Returns:
        List of SkillUsage objects
    """
    if not workspace_dir.exists():
        return []

    skill_usages = []
    cutoff_date = None

    if days:
        cutoff_date = datetime.now() - timedelta(days=days)

    # Scan all workspace directories
    for workspace_path in workspace_dir.iterdir():
        if not workspace_path.is_dir():
            continue

        # Skip special directories
        if workspace_path.name.startswith('.'):
            continue

        skill_usage = extract_skill_from_workspace(workspace_path)

        if skill_usage:
            # Apply date filter if specified
            if cutoff_date and skill_usage.started:
                if skill_usage.started < cutoff_date:
                    continue

            skill_usages.append(skill_usage)

    return skill_usages


def aggregate_skill_stats(skill_usages: List[SkillUsage]) -> Dict[str, SkillStats]:
    """
    Aggregate skill usage into statistics by skill name.

    Args:
        skill_usages: List of SkillUsage objects

    Returns:
        Dictionary mapping skill name to SkillStats
    """
    stats_map: Dict[str, SkillStats] = {}

    for usage in skill_usages:
        skill_name = usage.skill_name

        if skill_name not in stats_map:
            stats_map[skill_name] = SkillStats(skill_name=skill_name)

        stats = stats_map[skill_name]
        stats.total_uses += 1
        stats.workspaces.append(usage.workspace_name)

        if usage.success:
            stats.successful_uses += 1
        else:
            stats.failed_uses += 1

    return stats_map


def analyze_skill_usage(
    project_dir: Path,
    days: int = 30
) -> SkillAnalytics:
    """
    Analyze skill usage across all workspaces in a project.

    Args:
        project_dir: Project root directory
        days: Number of days to analyze (default: 30)

    Returns:
        SkillAnalytics object with complete analytics
    """
    workspace_dir = project_dir / '.orch' / 'workspace'

    # Scan for skill usages
    skill_usages = scan_workspaces_for_skills(workspace_dir, days=days)

    # Aggregate statistics
    stats_by_skill = aggregate_skill_stats(skill_usages)

    # Count total workspaces
    total_workspaces = 0
    if workspace_dir.exists():
        total_workspaces = sum(1 for p in workspace_dir.iterdir()
                              if p.is_dir() and not p.name.startswith('.'))

    workspaces_with_skills = len(skill_usages)
    workspaces_without_skills = total_workspaces - workspaces_with_skills

    # Calculate date range
    min_date = None
    max_date = None
    if skill_usages:
        dates = [u.started for u in skill_usages if u.started]
        if dates:
            min_date = min(dates)
            max_date = max(dates)

    return SkillAnalytics(
        stats_by_skill=stats_by_skill,
        total_workspaces=total_workspaces,
        workspaces_with_skills=workspaces_with_skills,
        workspaces_without_skills=workspaces_without_skills,
        date_range=(min_date, max_date)
    )


def format_skill_analytics(analytics: SkillAnalytics) -> str:
    """
    Format skill analytics for human-readable output.

    Args:
        analytics: SkillAnalytics object

    Returns:
        Formatted string for display
    """
    lines = []

    # Header with context clarification
    lines.append("\n" + "=" * 70)
    lines.append("📊 SPAWNED AGENT SKILL USAGE (Workspace Markers)")
    lines.append("=" * 70)
    lines.append("\n💡 Context: These are spawned agents created via 'orch spawn {skill}'.")
    lines.append("   Skills are embedded in SPAWN_CONTEXT.md (not invoked via Skill tool).")
    lines.append("")
    lines.append("   Note: Low markers may indicate agents not documenting skills in workspaces,")
    lines.append("   NOT that skills aren't being used. See --include-transcripts for interactive")
    lines.append("   Skill tool usage.")
    lines.append("")
    lines.append("   Decision: .orch/decisions/2025-11-22-skill-system-hybrid-architecture.md")

    # Date range
    if analytics.date_range[0] and analytics.date_range[1]:
        lines.append(f"\n📅 Date Range: {analytics.date_range[0].strftime('%Y-%m-%d')} to {analytics.date_range[1].strftime('%Y-%m-%d')}")

    # Overall statistics
    lines.append(f"\n📈 Overall Statistics:")
    lines.append(f"  Total workspaces: {analytics.total_workspaces}")
    lines.append(f"  Workspaces with skill markers: {analytics.workspaces_with_skills}")
    lines.append(f"  Workspaces without skill markers: {analytics.workspaces_without_skills}")
    lines.append(f"  Skill marker rate: {analytics.skill_adoption_rate:.1f}% (documentation, not usage)")

    # Skill breakdown
    if analytics.stats_by_skill:
        lines.append(f"\n🎯 Skill Usage Breakdown:")

        # Sort by usage count (descending)
        sorted_skills = sorted(
            analytics.stats_by_skill.values(),
            key=lambda s: s.total_uses,
            reverse=True
        )

        for stats in sorted_skills:
            success_rate_str = f"{stats.success_rate:.0f}% success" if stats.total_uses > 0 else "N/A"
            lines.append(
                f"  • {stats.skill_name}: {stats.total_uses} use{'s' if stats.total_uses != 1 else ''} "
                f"({success_rate_str})"
            )

            # Show workspace list if not too many
            if len(stats.workspaces) <= 5:
                for workspace in stats.workspaces:
                    lines.append(f"      - {workspace}")
    else:
        lines.append("\n⚠️  No skill usage found in the specified time period.")

    # Pattern gaps section
    if analytics.workspaces_without_skills > 0:
        lines.append(f"\n⚡ Documentation Gap (Not Usage Gap):")
        lines.append(f"  {analytics.workspaces_without_skills} workspace(s) without skill markers in WORKSPACE.md")
        lines.append(f"  This indicates missing documentation, not that skills weren't used.")
        lines.append(f"  Most spawned agents have skills embedded but don't document in workspace.")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def export_skill_analytics_json(analytics: SkillAnalytics) -> dict:
    """
    Export skill analytics as JSON-serializable dictionary.

    Args:
        analytics: SkillAnalytics object

    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "total_workspaces": analytics.total_workspaces,
        "workspaces_with_skills": analytics.workspaces_with_skills,
        "workspaces_without_skills": analytics.workspaces_without_skills,
        "skill_adoption_rate": round(analytics.skill_adoption_rate, 1),
        "date_range": {
            "start": analytics.date_range[0].isoformat() if analytics.date_range[0] else None,
            "end": analytics.date_range[1].isoformat() if analytics.date_range[1] else None
        },
        "skills": [
            {
                "name": stats.skill_name,
                "total_uses": stats.total_uses,
                "successful_uses": stats.successful_uses,
                "failed_uses": stats.failed_uses,
                "success_rate": round(stats.success_rate, 1),
                "workspaces": stats.workspaces
            }
            for stats in sorted(
                analytics.stats_by_skill.values(),
                key=lambda s: s.total_uses,
                reverse=True
            )
        ]
    }
