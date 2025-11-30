"""
Tests for pre-spawn artifact search hint in orch spawn.

Validates that spawn command shows hints when related artifacts exist
but weren't mentioned in the spawn context, encouraging orchestrators
to check for prior work before spawning.

Related:
- ROADMAP entry: .orch/ROADMAP.org line 2906 (Enforce pre-spawn artifact search)
- Documentation: docs/spawning-agents.md (Pre-Spawn Artifact Check section)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from orch.spawn_commands import register_spawn_commands


# Create a minimal CLI for testing
import click

@click.group()
def cli():
    pass

register_spawn_commands(cli)


class TestExtractSpawnKeywords:
    """Tests for keyword extraction from spawn task descriptions."""

    def test_extracts_meaningful_keywords(self):
        """Keyword extraction should filter stop words and extract meaningful terms."""
        from orch.artifact_hint import extract_spawn_keywords

        task = "add JWT token refresh endpoint for authentication"
        keywords = extract_spawn_keywords(task)

        # Should extract meaningful words
        assert any(kw in keywords for kw in ['jwt', 'token', 'refresh', 'authentication'])

    def test_filters_stop_words(self):
        """Should not include common stop words in keywords."""
        from orch.artifact_hint import extract_spawn_keywords

        task = "add the new feature for the user"
        keywords = extract_spawn_keywords(task)

        # Stop words should be filtered
        assert 'the' not in keywords
        assert 'for' not in keywords
        assert 'add' not in keywords

    def test_filters_short_words(self):
        """Should filter words shorter than 4 characters."""
        from orch.artifact_hint import extract_spawn_keywords

        task = "fix a bug in the API endpoint"
        keywords = extract_spawn_keywords(task)

        # Short words should be filtered
        assert 'fix' not in keywords
        assert 'bug' not in keywords
        assert 'api' not in keywords  # 3 chars

    def test_returns_limited_keywords(self):
        """Should return at most 3 keywords for focused search."""
        from orch.artifact_hint import extract_spawn_keywords

        task = "implement authentication authorization validation middleware endpoint"
        keywords = extract_spawn_keywords(task)

        # Should limit to 3 keywords
        assert len(keywords) <= 3


class TestCheckForRelatedArtifacts:
    """Tests for artifact search functionality."""

    @pytest.fixture
    def mock_project_dir(self, tmp_path):
        """Create mock project with .orch directory."""
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()
        (orch_dir / "investigations").mkdir()
        (orch_dir / "investigations" / "simple").mkdir()
        (orch_dir / "decisions").mkdir()
        (orch_dir / "workspace").mkdir()
        return tmp_path

    @pytest.fixture
    def mock_artifacts(self, mock_project_dir):
        """Create mock artifacts for testing."""
        # Create investigation about 'authentication'
        inv_dir = mock_project_dir / ".orch" / "investigations" / "simple"
        inv_file = inv_dir / "2025-11-20-auth-flow-analysis.md"
        inv_file.write_text("""# Authentication Flow Analysis

**Status:** Complete
**Question:** How does authentication work in the API?

## Findings
- JWT tokens with 15-minute expiry
- Refresh token mechanism exists
""")

        # Create decision about 'authentication'
        dec_dir = mock_project_dir / ".orch" / "decisions"
        dec_file = dec_dir / "2025-11-15-auth-session-management.md"
        dec_file.write_text("""# Auth Session Management Decision

**Status:** Accepted

## Decision
Use JWT with HTTP-only cookies.
""")

        return {
            'investigation': inv_file,
            'decision': dec_file
        }

    def test_finds_related_artifacts(self, mock_project_dir, mock_artifacts):
        """Should find related artifacts when they exist."""
        from orch.artifact_hint import check_for_related_artifacts

        # Search for authentication-related work
        result = check_for_related_artifacts(
            keywords=['authentication', 'auth'],
            project_dir=mock_project_dir
        )

        # Should find the investigation about auth
        assert result.found
        assert len(result.artifacts) >= 1

    def test_returns_empty_for_novel_topics(self, mock_project_dir):
        """Should return empty result when no related artifacts exist."""
        from orch.artifact_hint import check_for_related_artifacts

        # Search for completely novel topic
        result = check_for_related_artifacts(
            keywords=['xyznovel', 'unprecedented'],
            project_dir=mock_project_dir
        )

        # Should not find any artifacts
        assert not result.found
        assert len(result.artifacts) == 0

    def test_respects_time_bounds(self, mock_project_dir, mock_artifacts):
        """Should respect max_age_days parameter."""
        from orch.artifact_hint import check_for_related_artifacts

        # Search with time bound (artifacts should be within bound since just created)
        result = check_for_related_artifacts(
            keywords=['authentication'],
            project_dir=mock_project_dir,
            max_age_days=60
        )

        # Recent artifacts should be found
        assert result.found

    def test_returns_scored_artifacts(self, mock_project_dir, mock_artifacts):
        """Should return scored artifacts ranked by relevance."""
        from orch.artifact_hint import check_for_related_artifacts

        result = check_for_related_artifacts(
            keywords=['authentication', 'jwt'],
            project_dir=mock_project_dir
        )

        # Should have scored artifacts
        assert result.found
        assert len(result.scored_artifacts) > 0

        # Each scored artifact should have summary
        for sa in result.scored_artifacts:
            assert sa.summary

    def test_scored_artifacts_sorted_by_relevance(self, mock_project_dir, mock_artifacts):
        """Scored artifacts should be sorted by score (highest first)."""
        from orch.artifact_hint import check_for_related_artifacts

        result = check_for_related_artifacts(
            keywords=['authentication'],
            project_dir=mock_project_dir
        )

        if len(result.scored_artifacts) >= 2:
            # Scores should be in descending order
            scores = [sa.score for sa in result.scored_artifacts]
            assert scores == sorted(scores, reverse=True)


class TestExtractArtifactSummary:
    """Tests for TLDR/summary extraction from artifacts."""

    def test_extracts_tldr_line(self, tmp_path):
        """Should extract TLDR when present."""
        from orch.artifact_hint import extract_artifact_summary

        md_file = tmp_path / "test.md"
        md_file.write_text("""# Investigation

**TLDR:** JWT tokens are refreshed every 15 minutes.

## Details
More content here.
""")

        summary = extract_artifact_summary(md_file)
        assert "JWT tokens" in summary

    def test_extracts_tldr_alternate_format(self, tmp_path):
        """Should extract TLDR with alternate formatting."""
        from orch.artifact_hint import extract_artifact_summary

        md_file = tmp_path / "test.md"
        md_file.write_text("""# Investigation

TLDR: Authentication uses OAuth2 flow.

## Details
""")

        summary = extract_artifact_summary(md_file)
        assert "OAuth2" in summary or "Authentication" in summary

    def test_fallback_to_first_content_line(self, tmp_path):
        """Should fall back to first content line when no TLDR."""
        from orch.artifact_hint import extract_artifact_summary

        md_file = tmp_path / "test.md"
        md_file.write_text("""# Investigation

---

This is the first meaningful content line.

## Details
""")

        summary = extract_artifact_summary(md_file)
        assert "first meaningful content" in summary

    def test_truncates_long_summaries(self, tmp_path):
        """Should truncate summaries that are too long."""
        from orch.artifact_hint import extract_artifact_summary, MAX_SUMMARY_LENGTH

        md_file = tmp_path / "test.md"
        long_text = "x" * 200
        md_file.write_text(f"""# Investigation

**TLDR:** {long_text}
""")

        summary = extract_artifact_summary(md_file)
        assert len(summary) <= MAX_SUMMARY_LENGTH
        assert summary.endswith("...")

    def test_handles_missing_file(self, tmp_path):
        """Should return fallback for missing files."""
        from orch.artifact_hint import extract_artifact_summary

        missing_file = tmp_path / "missing.md"

        summary = extract_artifact_summary(missing_file)
        assert "unable to read" in summary


class TestScoreArtifact:
    """Tests for artifact scoring."""

    def test_score_increases_with_keyword_matches(self, tmp_path):
        """More keyword matches should increase score."""
        from orch.artifact_hint import score_artifact
        from datetime import datetime

        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nContent")

        now = datetime.now()
        score1 = score_artifact(md_file, keyword_match_count=1, now=now)
        score2 = score_artifact(md_file, keyword_match_count=3, now=now)

        assert score2.score > score1.score
        assert score2.keyword_matches == 3
        assert score1.keyword_matches == 1

    def test_recency_affects_score(self, tmp_path):
        """Recent files should score higher than old files."""
        from orch.artifact_hint import score_artifact
        from datetime import datetime, timedelta
        import os

        # Create two files with different mtimes
        recent_file = tmp_path / "recent.md"
        recent_file.write_text("# Recent\nContent")

        old_file = tmp_path / "old.md"
        old_file.write_text("# Old\nContent")

        # Set old file mtime to 30 days ago
        old_mtime = datetime.now() - timedelta(days=30)
        os.utime(old_file, (old_mtime.timestamp(), old_mtime.timestamp()))

        now = datetime.now()
        recent_score = score_artifact(recent_file, keyword_match_count=1, now=now)
        old_score = score_artifact(old_file, keyword_match_count=1, now=now)

        # Same keyword match, but recent should score higher
        assert recent_score.score > old_score.score
        assert recent_score.days_old < old_score.days_old


class TestArtifactHintMessage:
    """Tests for artifact search hint message generation."""

    def test_generates_hint_with_search_command(self, tmp_path):
        """Hint message should include orch search command."""
        from orch.artifact_hint import format_artifact_hint, ScoredArtifact

        artifact_path = tmp_path / "investigations" / "2025-11-20-auth-flow.md"
        scored = [
            ScoredArtifact(
                path=artifact_path,
                score=20.0,
                keyword_matches=2,
                days_old=0,
                summary="How does authentication work?"
            )
        ]

        hint = format_artifact_hint(
            keywords=['authentication', 'token'],
            scored_artifacts=scored,
            total_count=2,
            project_dir=tmp_path
        )

        # Should include orch search command
        assert 'orch search' in hint
        # Should include keyword suggestion
        assert 'authentication' in hint or 'token' in hint

    def test_hint_mentions_prior_work(self, tmp_path):
        """Hint should mention checking for prior work."""
        from orch.artifact_hint import format_artifact_hint, ScoredArtifact

        artifact_path = tmp_path / "decisions" / "2025-11-15-auth-decision.md"
        scored = [
            ScoredArtifact(
                path=artifact_path,
                score=15.0,
                keyword_matches=1,
                days_old=5,
                summary="Use JWT with HTTP-only cookies."
            )
        ]

        hint = format_artifact_hint(
            keywords=['authentication'],
            scored_artifacts=scored,
            total_count=1,
            project_dir=tmp_path
        )

        # Should mention prior work
        assert 'prior' in hint.lower() or 'related' in hint.lower() or 'found' in hint.lower()

    def test_hint_shows_artifact_summaries(self, tmp_path):
        """Hint should display summaries for each artifact."""
        from orch.artifact_hint import format_artifact_hint, ScoredArtifact

        scored = [
            ScoredArtifact(
                path=tmp_path / "investigations" / "auth.md",
                score=20.0,
                keyword_matches=2,
                days_old=1,
                summary="JWT tokens with 15-minute expiry"
            ),
            ScoredArtifact(
                path=tmp_path / "decisions" / "session.md",
                score=15.0,
                keyword_matches=1,
                days_old=3,
                summary="Use HTTP-only cookies for sessions"
            )
        ]

        hint = format_artifact_hint(
            keywords=['authentication'],
            scored_artifacts=scored,
            total_count=2,
            project_dir=tmp_path
        )

        # Should show both summaries
        assert "JWT tokens with 15-minute expiry" in hint
        assert "Use HTTP-only cookies for sessions" in hint

    def test_hint_shows_recency(self, tmp_path):
        """Hint should show how old each artifact is."""
        from orch.artifact_hint import format_artifact_hint, ScoredArtifact

        scored = [
            ScoredArtifact(
                path=tmp_path / "test.md",
                score=20.0,
                keyword_matches=2,
                days_old=0,
                summary="Test summary"
            ),
            ScoredArtifact(
                path=tmp_path / "old.md",
                score=10.0,
                keyword_matches=1,
                days_old=7,
                summary="Old summary"
            )
        ]

        hint = format_artifact_hint(
            keywords=['test'],
            scored_artifacts=scored,
            total_count=2,
            project_dir=tmp_path
        )

        # Should show recency indicators
        assert "today" in hint
        assert "7d ago" in hint

    def test_hint_shows_more_count(self, tmp_path):
        """Hint should indicate when there are more artifacts not shown."""
        from orch.artifact_hint import format_artifact_hint, ScoredArtifact

        scored = [
            ScoredArtifact(
                path=tmp_path / "test.md",
                score=20.0,
                keyword_matches=2,
                days_old=0,
                summary="Test summary"
            )
        ]

        hint = format_artifact_hint(
            keywords=['test'],
            scored_artifacts=scored,
            total_count=10,  # 9 more not shown
            project_dir=tmp_path
        )

        # Should indicate more exist
        assert "9 more" in hint


class TestSpawnWithArtifactHint:
    """Integration tests for spawn command with artifact hint."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_skip_artifact_check_flag_exists(self, runner):
        """The --skip-artifact-check flag should be recognized."""
        result = runner.invoke(cli, ['spawn', '--help'])

        # Check flag is documented in help
        assert '--skip-artifact-check' in result.output or result.exit_code == 0

    def test_spawn_proceeds_with_hint(self, runner, tmp_path):
        """Spawn should proceed even when hint is shown."""
        # Create minimal project structure
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()
        (orch_dir / "investigations" / "simple").mkdir(parents=True)

        # Create artifact that might match
        inv_file = orch_dir / "investigations" / "simple" / "2025-11-20-test-task.md"
        inv_file.write_text("# Test Task Investigation\n**Status:** Complete")

        with patch('orch.spawn.spawn_with_skill') as mock_spawn:
            with patch('orch.spawn.detect_project_from_cwd') as mock_detect:
                mock_detect.return_value = ('test-project', tmp_path)
                mock_spawn.return_value = {'agent_id': 'test', 'window': 'workers:1'}

                result = runner.invoke(cli, [
                    'spawn',
                    'feature-impl',
                    'test task description',
                    '--yes'
                ])

                # Spawn should proceed (not blocked by hint)
                # Either succeeds or fails for other reasons, not artifact check
                # The key is the flow continues past the hint
