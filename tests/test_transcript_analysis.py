"""
Tests for orch transcript_analysis module.

Tests transcript analysis for detecting Skill tool usage in Claude Code sessions.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta

from orch.transcript_analysis import (
    SkillToolUse,
    TranscriptSkillStats,
    parse_transcript_file,
    scan_transcripts_for_skills,
    aggregate_transcript_skill_stats,
    format_transcript_skill_analytics,
)


class TestSkillToolUse:
    """Tests for SkillToolUse dataclass."""

    def test_creates_with_all_fields(self, tmp_path):
        """Should create SkillToolUse with all fields."""
        use = SkillToolUse(
            skill_name='investigation',
            session_id='session-123',
            project_path='/path/to/project',
            timestamp=datetime.now(),
            transcript_file=tmp_path / 'transcript.jsonl'
        )
        assert use.skill_name == 'investigation'
        assert use.session_id == 'session-123'


class TestTranscriptSkillStats:
    """Tests for TranscriptSkillStats dataclass."""

    def test_creates_with_defaults(self):
        """Should create with empty sessions and projects by default."""
        stats = TranscriptSkillStats(skill_name='test')
        assert stats.total_uses == 0
        assert stats.sessions == []
        assert stats.projects == set()

    def test_creates_with_values(self):
        """Should accept provided values."""
        stats = TranscriptSkillStats(
            skill_name='test',
            total_uses=5,
            sessions=['s1', 's2'],
            projects={'p1', 'p2'}
        )
        assert stats.total_uses == 5
        assert len(stats.sessions) == 2


class TestParseTranscriptFile:
    """Tests for parse_transcript_file function."""

    def test_returns_empty_when_file_not_exists(self, tmp_path):
        """Should return empty list when file doesn't exist."""
        result = parse_transcript_file(tmp_path / 'nonexistent.jsonl')
        assert result == []

    def test_parses_skill_tool_use(self, tmp_path):
        """Should extract Skill tool usage from transcript."""
        transcript = tmp_path / 'transcript.jsonl'
        entry = {
            'sessionId': 'test-session',
            'cwd': '/test/project',
            'timestamp': '2025-01-15T10:00:00Z',
            'message': {
                'content': [
                    {
                        'type': 'tool_use',
                        'name': 'Skill',
                        'input': {'skill': 'investigation'}
                    }
                ]
            }
        }
        transcript.write_text(json.dumps(entry) + '\n')

        result = parse_transcript_file(transcript)

        assert len(result) == 1
        assert result[0].skill_name == 'investigation'
        assert result[0].session_id == 'test-session'

    def test_ignores_non_skill_tools(self, tmp_path):
        """Should ignore tool_use entries that aren't Skill."""
        transcript = tmp_path / 'transcript.jsonl'
        entry = {
            'sessionId': 'test-session',
            'cwd': '/test/project',
            'message': {
                'content': [
                    {
                        'type': 'tool_use',
                        'name': 'Read',  # Not Skill
                        'input': {'path': '/file.txt'}
                    }
                ]
            }
        }
        transcript.write_text(json.dumps(entry) + '\n')

        result = parse_transcript_file(transcript)
        assert result == []

    def test_handles_malformed_json(self, tmp_path):
        """Should skip malformed JSON lines."""
        transcript = tmp_path / 'transcript.jsonl'
        transcript.write_text("not valid json\n{\"valid\": true}\n")

        result = parse_transcript_file(transcript)
        # Should not raise, just skip bad lines
        assert result == []

    def test_handles_missing_content(self, tmp_path):
        """Should handle entries without message content."""
        transcript = tmp_path / 'transcript.jsonl'
        transcript.write_text('{"sessionId": "s1"}\n')

        result = parse_transcript_file(transcript)
        assert result == []


class TestScanTranscriptsForSkills:
    """Tests for scan_transcripts_for_skills function."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path):
        """Should return empty list when projects directory doesn't exist."""
        result = scan_transcripts_for_skills(tmp_path / 'nonexistent')
        assert result == []

    def test_scans_all_jsonl_files(self, tmp_path):
        """Should scan all .jsonl files recursively."""
        projects_dir = tmp_path / 'projects'
        (projects_dir / 'project1').mkdir(parents=True)
        (projects_dir / 'project2').mkdir(parents=True)

        # Create transcripts
        entry = {
            'sessionId': 's1',
            'cwd': '/project1',
            'message': {
                'content': [
                    {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'investigation'}}
                ]
            }
        }

        (projects_dir / 'project1' / 'transcript.jsonl').write_text(json.dumps(entry) + '\n')

        result = scan_transcripts_for_skills(projects_dir)
        assert len(result) >= 1

    def test_filters_by_project(self, tmp_path):
        """Should filter results by project path."""
        projects_dir = tmp_path / 'projects'
        (projects_dir / 'project1').mkdir(parents=True)

        entry = {
            'sessionId': 's1',
            'cwd': '/different/project',  # Won't match filter
            'message': {
                'content': [
                    {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'test'}}
                ]
            }
        }

        (projects_dir / 'project1' / 'transcript.jsonl').write_text(json.dumps(entry) + '\n')

        result = scan_transcripts_for_skills(projects_dir, project_filter='/wanted/project')
        assert len(result) == 0


class TestAggregateTranscriptSkillStats:
    """Tests for aggregate_transcript_skill_stats function."""

    def test_aggregates_by_skill_name(self, tmp_path):
        """Should aggregate uses by skill name."""
        uses = [
            SkillToolUse('skill1', 's1', '/p1', datetime.now(), tmp_path),
            SkillToolUse('skill1', 's2', '/p1', datetime.now(), tmp_path),
            SkillToolUse('skill2', 's1', '/p1', datetime.now(), tmp_path),
        ]

        stats = aggregate_transcript_skill_stats(uses)

        assert 'skill1' in stats
        assert stats['skill1'].total_uses == 2
        assert len(stats['skill1'].sessions) == 2
        assert 'skill2' in stats
        assert stats['skill2'].total_uses == 1

    def test_tracks_unique_sessions(self, tmp_path):
        """Should track unique sessions per skill."""
        uses = [
            SkillToolUse('skill1', 's1', '/p1', datetime.now(), tmp_path),
            SkillToolUse('skill1', 's1', '/p1', datetime.now(), tmp_path),  # Same session
        ]

        stats = aggregate_transcript_skill_stats(uses)

        assert len(stats['skill1'].sessions) == 1

    def test_tracks_unique_projects(self, tmp_path):
        """Should track unique projects per skill."""
        uses = [
            SkillToolUse('skill1', 's1', '/project1', datetime.now(), tmp_path),
            SkillToolUse('skill1', 's2', '/project2', datetime.now(), tmp_path),
        ]

        stats = aggregate_transcript_skill_stats(uses)

        assert len(stats['skill1'].projects) == 2


class TestFormatTranscriptSkillAnalytics:
    """Tests for format_transcript_skill_analytics function."""

    def test_formats_with_usage_data(self):
        """Should format analytics with skill usage data."""
        stats = {
            'investigation': TranscriptSkillStats(
                skill_name='investigation',
                total_uses=5,
                sessions=['s1', 's2'],
                projects={'/p1'}
            )
        }

        result = format_transcript_skill_analytics(stats, total_sessions_scanned=10)

        assert 'INTERACTIVE SKILL USAGE' in result
        assert 'investigation' in result
        assert '5 use' in result
        assert '10' in result

    def test_formats_empty_stats(self):
        """Should handle empty stats gracefully."""
        result = format_transcript_skill_analytics({}, total_sessions_scanned=5)

        assert 'No Skill tool usage found' in result
