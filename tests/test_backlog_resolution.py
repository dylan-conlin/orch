"""Tests for backlog resolution status lookup."""

import json
import pytest
from pathlib import Path

from orch.backlog_resolution import (
    BacklogResolver,
    get_investigation_resolution,
    ResolutionStatus,
)


class TestBacklogResolver:
    """Test BacklogResolver class."""

    def test_load_backlog_success(self, tmp_path):
        """Test loading backlog.json successfully."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-login-bug",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-login-bug.md",
                    "resolution": "fix"
                }
            ]
        }))

        resolver = BacklogResolver(project)
        assert resolver.backlog is not None
        assert len(resolver.backlog["features"]) == 1

    def test_load_backlog_missing_file(self, tmp_path):
        """Test graceful handling when backlog.json doesn't exist."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)
        # No backlog.json file

        resolver = BacklogResolver(project)
        assert resolver.backlog is None

    def test_get_resolution_for_investigation_resolved(self, tmp_path):
        """Test getting resolution status for an investigation with resolved backlog item."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-login-bug",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-login-bug.md",
                    "resolution": "fix"
                }
            ]
        }))

        resolver = BacklogResolver(project)

        # Query by investigation path
        inv_path = ".kb/investigations/simple/2025-11-28-login-bug.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        assert resolution == ResolutionStatus.FIX

    def test_get_resolution_for_investigation_workaround(self, tmp_path):
        """Test getting resolution status for an investigation with workaround resolution."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "handle-timeout",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-timeout-issue.md",
                    "resolution": "workaround"
                }
            ]
        }))

        resolver = BacklogResolver(project)
        inv_path = ".kb/investigations/simple/2025-11-28-timeout-issue.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        assert resolution == ResolutionStatus.WORKAROUND

    def test_get_resolution_for_investigation_unresolved(self, tmp_path):
        """Test getting resolution status when investigation has no resolution yet."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "debug-memory-leak",
                    "status": "in_progress",
                    "investigation": ".kb/investigations/simple/2025-11-28-memory-leak.md",
                    "resolution": None
                }
            ]
        }))

        resolver = BacklogResolver(project)
        inv_path = ".kb/investigations/simple/2025-11-28-memory-leak.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        assert resolution == ResolutionStatus.UNRESOLVED

    def test_get_resolution_for_investigation_not_in_backlog(self, tmp_path):
        """Test getting resolution status when investigation not in backlog."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": []
        }))

        resolver = BacklogResolver(project)
        inv_path = ".kb/investigations/simple/2025-11-28-unknown.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        # Not in backlog = no associated problem tracking = unknown
        assert resolution == ResolutionStatus.UNKNOWN

    def test_get_resolution_multiple_items_same_investigation(self, tmp_path):
        """Test when multiple backlog items reference same investigation."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-part-1",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-auth-bug.md",
                    "resolution": "fix"
                },
                {
                    "id": "fix-part-2",
                    "status": "in_progress",
                    "investigation": ".kb/investigations/simple/2025-11-28-auth-bug.md",
                    "resolution": None
                }
            ]
        }))

        resolver = BacklogResolver(project)
        inv_path = ".kb/investigations/simple/2025-11-28-auth-bug.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        # If any item is unresolved, the overall problem is unresolved
        assert resolution == ResolutionStatus.UNRESOLVED

    def test_get_resolution_multiple_items_all_resolved(self, tmp_path):
        """Test when multiple backlog items all resolved."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-part-1",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-auth-bug.md",
                    "resolution": "fix"
                },
                {
                    "id": "fix-part-2",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-auth-bug.md",
                    "resolution": "fix"
                }
            ]
        }))

        resolver = BacklogResolver(project)
        inv_path = ".kb/investigations/simple/2025-11-28-auth-bug.md"
        resolution = resolver.get_resolution_for_investigation(inv_path)

        # All resolved = overall resolved
        assert resolution == ResolutionStatus.FIX

    def test_get_resolution_with_absolute_path(self, tmp_path):
        """Test matching investigation by absolute path."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        inv_dir = orch_dir / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        # Create investigation file
        inv_file = inv_dir / "2025-11-28-test-inv.md"
        inv_file.write_text("# Test Investigation")

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "test-fix",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-test-inv.md",
                    "resolution": "fix"
                }
            ]
        }))

        resolver = BacklogResolver(project)

        # Query with absolute path
        resolution = resolver.get_resolution_for_investigation(str(inv_file))
        assert resolution == ResolutionStatus.FIX


class TestHelperFunction:
    """Test the convenience function."""

    def test_get_investigation_resolution(self, tmp_path):
        """Test convenience function for getting resolution."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)

        backlog_file = orch_dir / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [
                {
                    "id": "fix-issue",
                    "status": "complete",
                    "investigation": ".kb/investigations/simple/2025-11-28-issue.md",
                    "resolution": "fix"
                }
            ]
        }))

        inv_path = ".kb/investigations/simple/2025-11-28-issue.md"
        resolution = get_investigation_resolution(inv_path, project)

        assert resolution == ResolutionStatus.FIX

    def test_get_investigation_resolution_no_backlog(self, tmp_path):
        """Test convenience function when no backlog exists."""
        project = tmp_path / "test-project"
        orch_dir = project / ".orch"
        orch_dir.mkdir(parents=True)
        # No backlog.json

        inv_path = ".kb/investigations/simple/2025-11-28-issue.md"
        resolution = get_investigation_resolution(inv_path, project)

        assert resolution == ResolutionStatus.UNKNOWN


class TestResolutionStatusEnum:
    """Test ResolutionStatus enum values and methods."""

    def test_resolution_status_values(self):
        """Test enum values exist."""
        assert ResolutionStatus.FIX is not None
        assert ResolutionStatus.WORKAROUND is not None
        assert ResolutionStatus.UNRESOLVED is not None
        assert ResolutionStatus.UNKNOWN is not None

    def test_resolution_status_is_resolved(self):
        """Test is_resolved() method."""
        assert ResolutionStatus.FIX.is_resolved() is True
        assert ResolutionStatus.WORKAROUND.is_resolved() is True
        assert ResolutionStatus.UNRESOLVED.is_resolved() is False
        assert ResolutionStatus.UNKNOWN.is_resolved() is False
