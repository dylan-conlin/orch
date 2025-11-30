"""
Transcript analysis for detecting Skill tool usage in Claude Code sessions.

Scans JSONL transcript files to detect when agents use the Skill tool,
providing visibility into interactive skill usage that isn't tracked via
workspace markers.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from datetime import datetime
from collections import defaultdict


@dataclass
class SkillToolUse:
    """Represents a single use of the Skill tool in a transcript."""
    skill_name: str
    session_id: str
    project_path: str
    timestamp: datetime
    transcript_file: Path


@dataclass
class TranscriptSkillStats:
    """Aggregated statistics for skill tool usage from transcripts."""
    skill_name: str
    total_uses: int = 0
    sessions: List[str] = None
    projects: Set[str] = None

    def __post_init__(self):
        if self.sessions is None:
            self.sessions = []
        if self.projects is None:
            self.projects = set()


def parse_transcript_file(transcript_path: Path) -> List[SkillToolUse]:
    """
    Parse a single JSONL transcript file for Skill tool usage.

    Args:
        transcript_path: Path to .jsonl transcript file

    Returns:
        List of SkillToolUse objects found in transcript
    """
    skill_uses = []

    if not transcript_path.exists():
        return skill_uses

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)

                    # Extract session and project info
                    session_id = entry.get('sessionId', 'unknown')
                    project_path = entry.get('cwd', 'unknown')
                    timestamp_str = entry.get('timestamp')

                    # Parse timestamp
                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            pass

                    # Look for Skill tool usage in message content
                    message = entry.get('message', {})
                    content = message.get('content', [])

                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                if item.get('name') == 'Skill':
                                    skill_input = item.get('input', {})
                                    skill_name = skill_input.get('skill')

                                    if skill_name:
                                        skill_uses.append(SkillToolUse(
                                            skill_name=skill_name,
                                            session_id=session_id,
                                            project_path=project_path,
                                            timestamp=timestamp or datetime.now(),
                                            transcript_file=transcript_path
                                        ))

                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue
                except Exception:
                    # Skip lines that cause other errors
                    continue

    except Exception:
        # Skip files that can't be read
        pass

    return skill_uses


def scan_transcripts_for_skills(
    claude_projects_dir: Path = None,
    project_filter: Optional[str] = None,
    days: Optional[int] = None
) -> List[SkillToolUse]:
    """
    Scan all transcript files for Skill tool usage.

    Args:
        claude_projects_dir: Path to ~/.claude/projects/ directory
        project_filter: Optional project path to filter by
        days: Optional number of days to look back

    Returns:
        List of SkillToolUse objects found across all transcripts
    """
    if claude_projects_dir is None:
        claude_projects_dir = Path.home() / '.claude' / 'projects'

    if not claude_projects_dir.exists():
        return []

    skill_uses = []
    cutoff_date = None

    if days:
        # Make cutoff_date timezone-aware (UTC) to match transcript timestamps
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Scan all transcript files
    for transcript_file in claude_projects_dir.rglob('*.jsonl'):
        # Parse transcript
        uses = parse_transcript_file(transcript_file)

        for use in uses:
            # Apply project filter if specified
            if project_filter and project_filter not in use.project_path:
                continue

            # Apply date filter if specified
            if cutoff_date and use.timestamp < cutoff_date:
                continue

            skill_uses.append(use)

    return skill_uses


def aggregate_transcript_skill_stats(skill_uses: List[SkillToolUse]) -> Dict[str, TranscriptSkillStats]:
    """
    Aggregate skill tool usage into statistics by skill name.

    Args:
        skill_uses: List of SkillToolUse objects

    Returns:
        Dictionary mapping skill name to TranscriptSkillStats
    """
    stats_map: Dict[str, TranscriptSkillStats] = {}

    for use in skill_uses:
        skill_name = use.skill_name

        if skill_name not in stats_map:
            stats_map[skill_name] = TranscriptSkillStats(
                skill_name=skill_name,
                sessions=[],
                projects=set()
            )

        stats = stats_map[skill_name]
        stats.total_uses += 1

        if use.session_id not in stats.sessions:
            stats.sessions.append(use.session_id)

        stats.projects.add(use.project_path)

    return stats_map


def format_transcript_skill_analytics(
    stats_map: Dict[str, TranscriptSkillStats],
    total_sessions_scanned: int
) -> str:
    """
    Format transcript skill analytics for human-readable output.

    Args:
        stats_map: Dictionary of skill name to stats
        total_sessions_scanned: Total number of sessions scanned

    Returns:
        Formatted string for display
    """
    lines = []

    # Header with context clarification
    lines.append("\n" + "=" * 70)
    lines.append("📝 INTERACTIVE SKILL USAGE (Skill Tool Invocations)")
    lines.append("=" * 70)
    lines.append("\n💡 Context: These are interactive sessions where you used the Skill tool")
    lines.append("   directly. This is DIFFERENT from spawned agents (which get skills")
    lines.append("   embedded in SPAWN_CONTEXT.md).")
    lines.append("")
    lines.append("   Decision: .orch/decisions/2025-11-22-skill-system-hybrid-architecture.md")

    lines.append(f"\n📈 Sessions scanned: {total_sessions_scanned}")

    if stats_map:
        total_skill_uses = sum(s.total_uses for s in stats_map.values())
        sessions_with_skills = len(set(session for s in stats_map.values() for session in s.sessions))

        lines.append(f"Sessions with Skill tool usage: {sessions_with_skills}")
        lines.append(f"Total Skill tool calls: {total_skill_uses}")

        # Skill breakdown
        lines.append(f"\n🎯 Skills Used (via Skill tool):")

        # Sort by usage count (descending)
        sorted_skills = sorted(
            stats_map.values(),
            key=lambda s: s.total_uses,
            reverse=True
        )

        for stats in sorted_skills:
            session_count = len(stats.sessions)
            project_count = len(stats.projects)

            lines.append(
                f"  • {stats.skill_name}: {stats.total_uses} use{'s' if stats.total_uses != 1 else ''} "
                f"across {session_count} session{'s' if session_count != 1 else ''}"
            )

            if project_count > 1:
                lines.append(f"      ({project_count} different projects)")
    else:
        lines.append("\n⚠️  No Skill tool usage found in transcripts.")
        lines.append("This means the Skill tool was not used in interactive sessions.")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


# Add missing import
from datetime import timedelta
