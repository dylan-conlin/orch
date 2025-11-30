"""Tests for artifact search with reference counting."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from orch.artifact_search import (
    ArtifactReference,
    ArtifactSearcher,
    ReferenceCache,
    SearchResult,
    extract_artifact_metadata,
    format_time_ago,
)


class TestReferenceCache:
    """Test reference cache management."""

    def test_cache_initialization(self, tmp_path):
        """Test cache initializes with correct structure."""
        cache_path = tmp_path / "test-cache.json"
        cache = ReferenceCache(cache_path)

        assert cache.cache_path == cache_path
        assert cache._data == {}
        assert cache._last_updated is None

    def test_cache_save_and_load(self, tmp_path):
        """Test cache can be saved and loaded."""
        cache_path = tmp_path / "test-cache.json"
        cache = ReferenceCache(cache_path)

        # Add some data
        cache._data = {
            "/path/to/artifact.md": ArtifactReference(
                reference_count=5,
                last_referenced="2025-11-15T10:00:00",
                referenced_by=["/path/to/workspace.md"]
            )
        }

        # Save cache
        cache.save()
        assert cache_path.exists()

        # Load cache in new instance
        cache2 = ReferenceCache(cache_path)
        cache2.load()

        assert "/path/to/artifact.md" in cache2._data
        ref = cache2._data["/path/to/artifact.md"]
        assert ref.reference_count == 5
        assert ref.last_referenced == "2025-11-15T10:00:00"
        assert ref.referenced_by == ["/path/to/workspace.md"]

    def test_cache_version_validation(self, tmp_path):
        """Test cache rejects incompatible versions."""
        cache_path = tmp_path / "test-cache.json"

        # Write cache with wrong version
        with open(cache_path, 'w') as f:
            json.dump({"cache_version": "99.0", "artifacts": {}}, f)

        cache = ReferenceCache(cache_path)
        cache.load()

        # Should have empty data (version mismatch)
        assert cache._data == {}

    def test_needs_rebuild_no_update(self):
        """Test needs_rebuild returns True when never updated."""
        cache = ReferenceCache()
        assert cache.needs_rebuild() is True

    def test_needs_rebuild_old_cache(self):
        """Test needs_rebuild returns True for old cache."""
        cache = ReferenceCache()
        cache._last_updated = datetime.now() - timedelta(days=10)

        assert cache.needs_rebuild(max_age=timedelta(days=7)) is True
        assert cache.needs_rebuild(max_age=timedelta(days=14)) is False

    def test_rebuild_finds_artifacts(self, tmp_path):
        """Test rebuild finds and tracks artifacts."""
        # Create test structure
        project_dir = tmp_path / "test-project"
        orch_dir = project_dir / ".orch"
        inv_dir = orch_dir / "investigations"
        dec_dir = orch_dir / "decisions"
        workspace_dir = orch_dir / "workspace" / "test-ws"

        inv_dir.mkdir(parents=True)
        dec_dir.mkdir(parents=True)
        workspace_dir.mkdir(parents=True)

        # Create artifacts
        inv_file = inv_dir / "test-investigation.md"
        inv_file.write_text("# Test Investigation\n\nSome content")

        dec_file = dec_dir / "test-decision.md"
        dec_file.write_text("# Test Decision\n\nSome content")

        # Create workspace that references investigation
        ws_file = workspace_dir / "WORKSPACE.md"
        ws_file.write_text(f"""# Workspace

See investigation: {inv_file}
Also see test-investigation.md
""")

        # Rebuild cache
        cache_path = tmp_path / "cache.json"
        cache = ReferenceCache(cache_path)
        cache.rebuild([project_dir])

        # Check artifacts were found
        assert str(inv_file) in cache._data
        assert str(dec_file) in cache._data

        # Check references were counted
        inv_ref = cache.get(str(inv_file))
        assert inv_ref is not None
        assert inv_ref.reference_count == 2  # Referenced twice by workspace (full path + filename)
        assert str(ws_file) in inv_ref.referenced_by

        dec_ref = cache.get(str(dec_file))
        assert dec_ref is not None
        assert dec_ref.reference_count == 0  # Not referenced


class TestArtifactSearcher:
    """Test artifact search functionality."""

    def test_detect_project_dir_in_project(self, tmp_path, monkeypatch):
        """Test project directory detection when in .orch project."""
        project_dir = tmp_path / "test-project"
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir(parents=True)

        # Change to subdirectory
        work_dir = project_dir / "subdir"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        searcher = ArtifactSearcher()
        detected = searcher._detect_project_dir()

        assert detected == project_dir

    def test_detect_project_dir_no_project(self, tmp_path, monkeypatch):
        """Test project directory detection when not in project."""
        work_dir = tmp_path / "not-a-project"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        searcher = ArtifactSearcher()
        detected = searcher._detect_project_dir()

        assert detected is None

    def test_get_glob_patterns(self):
        """Test glob pattern generation for different types."""
        searcher = ArtifactSearcher()

        inv_patterns = searcher._get_glob_patterns("investigations")
        assert inv_patterns == ["**/.orch/investigations/**/*.md", "investigations/**/*.md"]

        dec_patterns = searcher._get_glob_patterns("decisions")
        assert dec_patterns == ["**/.orch/decisions/*.md", "decisions/*.md"]

        all_patterns = searcher._get_glob_patterns("all")
        assert "**/.orch/investigations/**/*.md" in all_patterns
        assert "investigations/**/*.md" in all_patterns
        assert "**/.orch/decisions/*.md" in all_patterns
        assert "decisions/*.md" in all_patterns
        assert "**/.orch/knowledge/*.md" in all_patterns
        assert "knowledge/*.md" in all_patterns

    def test_search_file_matches(self, tmp_path):
        """Test file search finds matching lines."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""Line 1
Line 2 with KEYWORD
Line 3
Line 4 with keyword again
""")

        searcher = ArtifactSearcher()
        matches = searcher._search_file(test_file, "keyword")

        assert len(matches) == 2
        line_nums = [m[0] for m in matches]
        assert 2 in line_nums
        assert 4 in line_nums

    def test_search_integration(self, tmp_path, monkeypatch):
        """Test full search workflow with reference tracking."""
        # Create test structure
        project_dir = tmp_path / "test-project"
        orch_dir = project_dir / ".orch"
        inv_dir = orch_dir / "investigations"
        workspace_dir = orch_dir / "workspace" / "test-ws"

        inv_dir.mkdir(parents=True)
        workspace_dir.mkdir(parents=True)

        # Create investigation
        inv_file = inv_dir / "authentication-analysis.md"
        inv_file.write_text("""# Authentication Analysis

This investigation covers authentication patterns.

## Findings

Found several authentication issues.
""")

        # Create workspace referencing it
        ws_file = workspace_dir / "WORKSPACE.md"
        ws_file.write_text(f"""# Workspace

Related: {inv_file.name}
See authentication-analysis.md for details.
""")

        # Create searcher with custom cache
        cache_path = tmp_path / "cache.json"
        cache = ReferenceCache(cache_path)
        searcher = ArtifactSearcher(cache)

        # Mock _get_search_paths to only search test directory
        def mock_get_search_paths(global_search):
            return [project_dir]

        monkeypatch.setattr(searcher, '_get_search_paths', mock_get_search_paths)

        # Perform search with cache rebuild
        results = searcher.search(
            query="authentication",
            artifact_type="all",
            project=None,
            global_search=False,
            rebuild_cache=True
        )

        # Should find the investigation
        assert len(results) == 1
        result = results[0]
        assert str(inv_file) in result.file_path
        assert len(result.matches) > 0

        # Check reference info
        assert result.reference_info is not None
        assert result.reference_info.reference_count == 1
        assert str(ws_file) in result.reference_info.referenced_by


class TestFormatTimeAgo:
    """Test time ago formatting."""

    def test_format_none(self):
        """Test formatting None returns never."""
        assert format_time_ago(None) == "never"

    def test_format_just_now(self):
        """Test recent timestamp formats as just now."""
        now = datetime.now()
        iso = now.isoformat()
        assert format_time_ago(iso) == "just now"

    def test_format_minutes(self):
        """Test minutes ago."""
        past = datetime.now() - timedelta(minutes=30)
        iso = past.isoformat()
        result = format_time_ago(iso)
        assert "m ago" in result

    def test_format_hours(self):
        """Test hours ago."""
        past = datetime.now() - timedelta(hours=5)
        iso = past.isoformat()
        result = format_time_ago(iso)
        assert "h ago" in result

    def test_format_days(self):
        """Test days ago."""
        past = datetime.now() - timedelta(days=10)
        iso = past.isoformat()
        result = format_time_ago(iso)
        assert "d ago" in result

    def test_format_months(self):
        """Test months ago."""
        past = datetime.now() - timedelta(days=60)
        iso = past.isoformat()
        result = format_time_ago(iso)
        assert "mo ago" in result

    def test_format_years(self):
        """Test years ago."""
        past = datetime.now() - timedelta(days=400)
        iso = past.isoformat()
        result = format_time_ago(iso)
        assert "y ago" in result

    def test_format_invalid(self):
        """Test invalid timestamp returns unknown."""
        assert format_time_ago("not-a-timestamp") == "unknown"


class TestExtractArtifactMetadata:
    """Test metadata extraction from artifact files."""

    def test_extract_tldr_with_heading(self, tmp_path):
        """Test extracting TLDR from ## TLDR heading format."""
        test_file = tmp_path / ".orch" / "investigations" / "2025-11-20-test-investigation.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""# Investigation: Test Topic

**Question:** What is this about?
**Started:** 2025-11-20

## TLDR

This is a concise summary of the investigation findings.

## Findings

Some detailed findings here.
""")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["tldr"] == "This is a concise summary of the investigation findings."
        assert metadata["date"] == "2025-11-20"
        assert metadata["type"] == "investigation"

    def test_extract_tldr_with_bold_format(self, tmp_path):
        """Test extracting TLDR from **TLDR:** inline format."""
        test_file = tmp_path / ".orch" / "workspace" / "test-ws" / "WORKSPACE.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""**TLDR:** Adding JSON output format to orch search command.

---

# Workspace: test-feature

**Owner:** Claude
""")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["tldr"] == "Adding JSON output format to orch search command."
        assert metadata["type"] == "workspace"

    def test_extract_resolution_status_from_backlog(self, tmp_path):
        """Test extracting resolution status from backlog.json.

        Note: Resolution status is now looked up from backlog.json, not from the
        investigation file itself. See decision:
        .orch/decisions/2025-11-28-backlog-investigation-separation.md
        """
        import json

        # Create proper .orch directory structure
        project_dir = tmp_path / "test-project"
        orch_dir = project_dir / ".orch"
        inv_dir = orch_dir / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        # Create investigation file
        test_file = inv_dir / "2025-11-20-test-investigation.md"
        test_file.write_text("""# Investigation

**Question:** What?
**Started:** 2025-11-20

## Findings

Content here.
""")

        # Create backlog.json with investigation linked and resolved
        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-test-issue",
                    "status": "complete",
                    "investigation": ".orch/investigations/simple/2025-11-20-test-investigation.md",
                    "resolution": "fix"
                }
            ]
        }))

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["status"] == "Resolved"

    def test_extract_resolution_status_not_in_backlog(self, tmp_path):
        """Test that status is empty when investigation not in backlog."""
        # Create proper .orch directory structure
        project_dir = tmp_path / "test-project"
        orch_dir = project_dir / ".orch"
        inv_dir = orch_dir / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        # Create investigation file
        test_file = inv_dir / "2025-11-20-test-investigation.md"
        test_file.write_text("""# Investigation

**Question:** What?

## Findings

Content here.
""")

        # Create empty backlog.json
        import json
        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": []
        }))

        metadata = extract_artifact_metadata(str(test_file))

        # Not in backlog = no status
        assert metadata["status"] == ""

    def test_extract_date_from_filename(self, tmp_path):
        """Test extracting date from YYYY-MM-DD filename prefix."""
        test_file = tmp_path / "2025-11-24-test-decision.md"
        test_file.write_text("# Decision\n\nContent")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["date"] == "2025-11-24"

    def test_extract_type_from_path_investigation_systems(self, tmp_path):
        """Test extracting type from .orch/investigations/systems/ path."""
        test_file = tmp_path / ".orch" / "investigations" / "systems" / "2025-11-20-test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# Investigation\n\nContent")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["type"] == "investigation-systems"

    def test_extract_type_from_path_investigation_feasibility(self, tmp_path):
        """Test extracting type from .orch/investigations/feasibility/ path."""
        test_file = tmp_path / ".orch" / "investigations" / "feasibility" / "2025-11-20-test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# Investigation\n\nContent")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["type"] == "investigation-feasibility"

    def test_extract_type_from_path_decision(self, tmp_path):
        """Test extracting type from .orch/decisions/ path."""
        test_file = tmp_path / ".orch" / "decisions" / "2025-11-20-test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# Decision\n\nContent")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["type"] == "decision"

    def test_extract_type_from_path_knowledge(self, tmp_path):
        """Test extracting type from .orch/knowledge/ path."""
        test_file = tmp_path / ".orch" / "knowledge" / "patterns" / "2025-11-20-test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# Knowledge\n\nContent")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["type"] == "knowledge"

    def test_extract_metadata_missing_fields(self, tmp_path):
        """Test graceful handling of missing metadata fields."""
        test_file = tmp_path / "no-date-file.md"
        test_file.write_text("# Some File\n\nNo TLDR or status here.")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["tldr"] == ""
        assert metadata["status"] == ""
        assert metadata["date"] == ""
        assert metadata["type"] == "unknown"

    def test_extract_metadata_file_not_found(self):
        """Test handling of non-existent file."""
        metadata = extract_artifact_metadata("/nonexistent/file.md")

        assert metadata["tldr"] == ""
        assert metadata["status"] == ""
        assert metadata["date"] == ""
        assert metadata["type"] == "unknown"

    def test_extract_metadata_malformed_tldr(self, tmp_path):
        """Test handling of malformed TLDR section."""
        test_file = tmp_path / "2025-11-20-test.md"
        test_file.write_text("""# Investigation

## TLDR


## Next Section
""")

        metadata = extract_artifact_metadata(str(test_file))

        assert metadata["tldr"] == ""
        assert metadata["date"] == "2025-11-20"
