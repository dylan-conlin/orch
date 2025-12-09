"""Tests for error logging module."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from orch.error_logging import (
    ErrorEntry,
    ErrorLogger,
    ErrorType,
    log_error,
    get_error_stats,
    get_recent_errors,
    reset_default_logger,
)


class TestErrorEntry:
    """Tests for ErrorEntry dataclass."""

    def test_error_entry_creation(self):
        """Test creating an ErrorEntry with required fields."""
        entry = ErrorEntry(
            timestamp="2025-12-09T10:42:00Z",
            command="orch complete pw-k2r",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Agent 'pw-k2r' not found in registry",
        )
        assert entry.command == "orch complete pw-k2r"
        assert entry.subcommand == "complete"
        assert entry.error_type == ErrorType.AGENT_NOT_FOUND
        assert entry.message == "Agent 'pw-k2r' not found in registry"
        assert entry.context is None
        assert entry.stack_trace is None
        assert entry.duration_ms is None

    def test_error_entry_with_context(self):
        """Test creating an ErrorEntry with context dict."""
        entry = ErrorEntry(
            timestamp="2025-12-09T10:42:00Z",
            command="orch complete pw-k2r",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Agent 'pw-k2r' not found in registry",
            context={"attempted_lookup": "pw-k2r", "registry_count": 2},
        )
        assert entry.context == {"attempted_lookup": "pw-k2r", "registry_count": 2}

    def test_error_entry_to_dict(self):
        """Test serializing ErrorEntry to dict."""
        entry = ErrorEntry(
            timestamp="2025-12-09T10:42:00Z",
            command="orch complete pw-k2r",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Agent 'pw-k2r' not found in registry",
            context={"attempted_lookup": "pw-k2r"},
            duration_ms=45,
        )
        result = entry.to_dict()
        assert result["timestamp"] == "2025-12-09T10:42:00Z"
        assert result["command"] == "orch complete pw-k2r"
        assert result["error_type"] == "AGENT_NOT_FOUND"
        assert result["error_code"] == "AGENT_NOT_FOUND"  # Matches error_type
        assert result["context"] == {"attempted_lookup": "pw-k2r"}
        assert result["duration_ms"] == 45


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_error_types_exist(self):
        """Test that required error types exist."""
        assert ErrorType.AGENT_NOT_FOUND
        assert ErrorType.VERIFICATION_FAILED
        assert ErrorType.INVESTIGATION_NOT_FOUND
        assert ErrorType.SPAWN_FAILED
        assert ErrorType.REGISTRY_LOCKED
        assert ErrorType.BEADS_ERROR
        assert ErrorType.UNEXPECTED_ERROR


class TestErrorLogger:
    """Tests for ErrorLogger class."""

    def test_logger_creates_error_file(self, tmp_path):
        """Test that logger creates errors.jsonl file."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        logger.log_error(
            command="orch complete test-agent",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Agent not found",
        )

        assert error_file.exists()
        lines = error_file.read_text().strip().split('\n')
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["error_type"] == "AGENT_NOT_FOUND"
        assert entry["message"] == "Agent not found"

    def test_logger_appends_multiple_errors(self, tmp_path):
        """Test that logger appends errors to file."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        logger.log_error(
            command="orch complete a1",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="First error",
        )
        logger.log_error(
            command="orch complete a2",
            subcommand="complete",
            error_type=ErrorType.VERIFICATION_FAILED,
            message="Second error",
        )

        lines = error_file.read_text().strip().split('\n')
        assert len(lines) == 2

    def test_logger_with_stack_trace(self, tmp_path):
        """Test logging error with stack trace."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        logger.log_error(
            command="orch spawn skill task",
            subcommand="spawn",
            error_type=ErrorType.UNEXPECTED_ERROR,
            message="Unexpected error occurred",
            stack_trace="Traceback (most recent call last):\n  File...",
        )

        lines = error_file.read_text().strip().split('\n')
        entry = json.loads(lines[0])
        assert "stack_trace" in entry
        assert "Traceback" in entry["stack_trace"]

    def test_logger_rotation_on_size_limit(self, tmp_path):
        """Test that logger respects max entries limit."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file, max_entries=5)

        # Log 10 entries
        for i in range(10):
            logger.log_error(
                command=f"orch complete agent-{i}",
                subcommand="complete",
                error_type=ErrorType.AGENT_NOT_FOUND,
                message=f"Error {i}",
            )

        # Should only have 5 most recent entries
        lines = error_file.read_text().strip().split('\n')
        assert len(lines) == 5
        # Most recent should be last
        last_entry = json.loads(lines[-1])
        assert "Error 9" in last_entry["message"]


class TestGetErrorStats:
    """Tests for get_error_stats function."""

    def test_get_error_stats_empty(self, tmp_path):
        """Test stats with no errors."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        stats = logger.get_error_stats(days=7)

        assert stats["total"] == 0
        assert stats["by_type"] == {}
        assert stats["by_command"] == {}

    def test_get_error_stats_by_type(self, tmp_path):
        """Test stats aggregated by error type."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        # Add errors of different types
        for _ in range(3):
            logger.log_error(
                command="orch complete x",
                subcommand="complete",
                error_type=ErrorType.AGENT_NOT_FOUND,
                message="Not found",
            )
        for _ in range(2):
            logger.log_error(
                command="orch complete x",
                subcommand="complete",
                error_type=ErrorType.VERIFICATION_FAILED,
                message="Verification failed",
            )

        stats = logger.get_error_stats(days=7)

        assert stats["total"] == 5
        assert stats["by_type"]["AGENT_NOT_FOUND"] == 3
        assert stats["by_type"]["VERIFICATION_FAILED"] == 2

    def test_get_error_stats_by_command(self, tmp_path):
        """Test stats aggregated by subcommand."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        for _ in range(4):
            logger.log_error(
                command="orch complete x",
                subcommand="complete",
                error_type=ErrorType.AGENT_NOT_FOUND,
                message="Error",
            )
        for _ in range(2):
            logger.log_error(
                command="orch spawn skill task",
                subcommand="spawn",
                error_type=ErrorType.SPAWN_FAILED,
                message="Error",
            )

        stats = logger.get_error_stats(days=7)

        assert stats["by_command"]["complete"] == 4
        assert stats["by_command"]["spawn"] == 2

    def test_get_error_stats_filters_by_days(self, tmp_path):
        """Test that stats filters by date range."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        # Write entries with different timestamps directly
        now = datetime.now()
        old_date = (now - timedelta(days=10)).isoformat() + "Z"
        recent_date = now.isoformat() + "Z"

        # Old entry
        with open(error_file, 'a') as f:
            f.write(json.dumps({
                "timestamp": old_date,
                "command": "orch complete old",
                "subcommand": "complete",
                "error_type": "AGENT_NOT_FOUND",
                "error_code": "AGENT_NOT_FOUND",
                "message": "Old error",
            }) + '\n')

        # Recent entry
        with open(error_file, 'a') as f:
            f.write(json.dumps({
                "timestamp": recent_date,
                "command": "orch complete new",
                "subcommand": "complete",
                "error_type": "AGENT_NOT_FOUND",
                "error_code": "AGENT_NOT_FOUND",
                "message": "New error",
            }) + '\n')

        # Stats for last 7 days should only include recent
        stats = logger.get_error_stats(days=7)
        assert stats["total"] == 1


class TestGetRecentErrors:
    """Tests for get_recent_errors function."""

    def test_get_recent_errors_empty(self, tmp_path):
        """Test with no errors."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        errors = logger.get_recent_errors(limit=10)

        assert errors == []

    def test_get_recent_errors_returns_list(self, tmp_path):
        """Test that recent errors returns list of dicts."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        logger.log_error(
            command="orch complete agent-1",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Error 1",
        )

        errors = logger.get_recent_errors(limit=10)

        assert len(errors) == 1
        assert errors[0]["message"] == "Error 1"

    def test_get_recent_errors_respects_limit(self, tmp_path):
        """Test that limit parameter works."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        for i in range(10):
            logger.log_error(
                command=f"orch complete agent-{i}",
                subcommand="complete",
                error_type=ErrorType.AGENT_NOT_FOUND,
                message=f"Error {i}",
            )

        errors = logger.get_recent_errors(limit=5)

        assert len(errors) == 5

    def test_get_recent_errors_most_recent_first(self, tmp_path):
        """Test that errors are returned most recent first."""
        error_file = tmp_path / "errors.jsonl"
        logger = ErrorLogger(error_file=error_file)

        logger.log_error(
            command="orch complete a",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="First",
        )
        logger.log_error(
            command="orch complete b",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Second",
        )

        errors = logger.get_recent_errors(limit=10)

        # Most recent (Second) should be first
        assert errors[0]["message"] == "Second"
        assert errors[1]["message"] == "First"


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_log_error_uses_default_path(self, tmp_path, monkeypatch):
        """Test that log_error uses default ~/.orch/errors.jsonl."""
        # Reset singleton to pick up new HOME
        reset_default_logger()

        # Redirect home to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create .orch directory
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()

        log_error(
            command="orch complete test",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Test error",
        )

        error_file = orch_dir / "errors.jsonl"
        assert error_file.exists()

    def test_get_error_stats_convenience(self, tmp_path, monkeypatch):
        """Test get_error_stats convenience function."""
        # Reset singleton to pick up new HOME
        reset_default_logger()

        monkeypatch.setenv("HOME", str(tmp_path))
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()

        log_error(
            command="orch complete test",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Test error",
        )

        stats = get_error_stats(days=7)
        assert stats["total"] == 1

    def test_get_recent_errors_convenience(self, tmp_path, monkeypatch):
        """Test get_recent_errors convenience function."""
        # Reset singleton to pick up new HOME
        reset_default_logger()

        monkeypatch.setenv("HOME", str(tmp_path))
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()

        log_error(
            command="orch complete test",
            subcommand="complete",
            error_type=ErrorType.AGENT_NOT_FOUND,
            message="Test error",
        )

        errors = get_recent_errors(limit=10)
        assert len(errors) == 1
