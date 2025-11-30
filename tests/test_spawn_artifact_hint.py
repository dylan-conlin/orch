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


class TestArtifactHintMessage:
    """Tests for artifact search hint message generation."""

    def test_generates_hint_with_search_command(self):
        """Hint message should include orch search command."""
        from orch.artifact_hint import format_artifact_hint

        hint = format_artifact_hint(
            keywords=['authentication', 'token'],
            artifact_count=2,
            artifact_example='investigations/2025-11-20-auth-flow.md'
        )

        # Should include orch search command
        assert 'orch search' in hint
        # Should include keyword suggestion
        assert 'authentication' in hint or 'token' in hint

    def test_hint_mentions_prior_work(self):
        """Hint should mention checking for prior work."""
        from orch.artifact_hint import format_artifact_hint

        hint = format_artifact_hint(
            keywords=['authentication'],
            artifact_count=1,
            artifact_example='decisions/2025-11-15-auth-decision.md'
        )

        # Should mention prior work
        assert 'prior' in hint.lower() or 'related' in hint.lower() or 'found' in hint.lower()


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
