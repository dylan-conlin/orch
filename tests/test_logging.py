"""Tests for orch logging module."""
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import time_machine
from orch.logging import OrchLogger


class TestOrchLogger:
    """Test suite for OrchLogger class."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self, temp_log_dir):
        """Create logger instance with temp directory."""
        return OrchLogger(log_dir=temp_log_dir)

    def test_log_directory_creation(self, temp_log_dir):
        """Test that log directory is created if it doesn't exist."""
        log_dir = temp_log_dir / "subdir" / "logs"
        assert not log_dir.exists()

        logger = OrchLogger(log_dir=log_dir)
        logger.log_event("test", "test message", {})

        assert log_dir.exists()

    @time_machine.travel("2025-11-10 15:30:45")
    def test_monthly_log_file_naming(self, temp_log_dir):
        """Test that log files are named with YYYY-MM format."""
        logger = OrchLogger(log_dir=temp_log_dir)
        logger.log_event("test", "test message", {})

        expected_file = temp_log_dir / "orch-2025-11.log"
        assert expected_file.exists()

    @time_machine.travel("2025-11-10 15:30:45")
    def test_hybrid_format_structure(self, logger, temp_log_dir):
        """Test that log entries follow hybrid format: readable | JSON."""
        logger.log_event("spawn", "Agent spawned successfully", {
            "agent_id": "test-agent",
            "window": "orchestrator:5",
            "duration_ms": 714
        })

        log_file = temp_log_dir / "orch-2025-11.log"
        log_line = log_file.read_text().strip()

        # Check format: YYYY-MM-DD HH:MM:SS LEVEL [command] message | {json}
        assert log_line.startswith("2025-11-10 15:30:45 INFO")
        assert "[spawn]" in log_line
        assert "Agent spawned successfully" in log_line
        assert " | " in log_line

        # Extract and verify JSON part
        json_part = log_line.split(" | ", 1)[1]
        data = json.loads(json_part)
        assert data["agent_id"] == "test-agent"
        assert data["window"] == "orchestrator:5"
        assert data["duration_ms"] == 714

    def test_log_levels(self, logger, temp_log_dir):
        """Test different log levels."""
        logger.log_event("test", "debug message", {}, level="DEBUG")
        logger.log_event("test", "info message", {}, level="INFO")
        logger.log_event("test", "warning message", {}, level="WARNING")
        logger.log_event("test", "error message", {}, level="ERROR")

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        lines = log_file.read_text().strip().split("\n")

        assert len(lines) == 4
        assert " DEBUG " in lines[0]
        assert " INFO  " in lines[1]
        assert " WARNING " in lines[2]
        assert " ERROR " in lines[3]

    def test_json_escaping(self, logger, temp_log_dir):
        """Test that special characters in JSON are properly escaped."""
        logger.log_event("test", "Message with \"quotes\"", {
            "field_with_quotes": "value \"with\" quotes",
            "field_with_newline": "value\nwith\nnewlines"
        })

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        log_line = log_file.read_text().strip()

        # Extract and parse JSON to verify it's valid
        json_part = log_line.split(" | ", 1)[1]
        data = json.loads(json_part)
        assert data["field_with_quotes"] == "value \"with\" quotes"
        assert data["field_with_newline"] == "value\nwith\nnewlines"

    def test_log_command_start(self, logger, temp_log_dir):
        """Test log_command_start convenience method."""
        logger.log_command_start("spawn", {
            "task": "debug bug",
            "project": "test-project",
            "workspace": "test-workspace"
        })

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        log_line = log_file.read_text().strip()

        assert "[spawn]" in log_line
        assert "Starting command" in log_line
        assert "debug bug" in log_line

    def test_log_command_complete(self, logger, temp_log_dir):
        """Test log_command_complete convenience method."""
        logger.log_command_complete("spawn", 714, {
            "agent_id": "test-agent",
            "window": "orchestrator:5"
        })

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        log_line = log_file.read_text().strip()

        assert "[spawn]" in log_line
        assert "Command complete" in log_line
        assert "(714ms)" in log_line
        assert "test-agent" in log_line

    def test_log_error(self, logger, temp_log_dir):
        """Test log_error convenience method."""
        logger.log_error("spawn", "Validation failed", {
            "reason": "workspace already exists",
            "workspace": "test-workspace"
        })

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        log_line = log_file.read_text().strip()

        assert " ERROR " in log_line
        assert "[spawn]" in log_line
        assert "Validation failed" in log_line
        assert "workspace already exists" in log_line

    @time_machine.travel("2025-11-10 15:30:45")
    def test_multiple_log_entries(self, logger, temp_log_dir):
        """Test that multiple log entries are appended correctly."""
        logger.log_event("spawn", "First entry", {"id": 1})
        logger.log_event("clean", "Second entry", {"id": 2})
        logger.log_event("status", "Third entry", {"id": 3})

        log_file = temp_log_dir / "orch-2025-11.log"
        lines = log_file.read_text().strip().split("\n")

        assert len(lines) == 3
        assert "First entry" in lines[0]
        assert "Second entry" in lines[1]
        assert "Third entry" in lines[2]

    def test_default_log_directory(self):
        """Test that default log directory is ~/.orch/logs/."""
        logger = OrchLogger()
        expected_dir = Path.home() / ".orch" / "logs"
        assert logger.log_dir == expected_dir

    def test_empty_structured_data(self, logger, temp_log_dir):
        """Test logging with empty structured data dict."""
        logger.log_event("test", "Message with no data", {})

        log_file = temp_log_dir / f"orch-{datetime.now().strftime('%Y-%m')}.log"
        log_line = log_file.read_text().strip()

        # Should still have pipe separator and empty JSON object
        assert " | {}" in log_line

    def test_read_logs_returns_newest_entries_first(self, logger, temp_log_dir):
        """Test that read_logs returns newest entries when limit is less than total entries."""
        # Create 100 log entries with timestamps spanning from oldest to newest
        timestamps = [
            "2025-11-01 10:00:00",
            "2025-11-02 10:00:00",
            "2025-11-03 10:00:00",
            "2025-11-04 10:00:00",
            "2025-11-05 10:00:00",
        ]

        # Write entries directly to log file (oldest first, as they're written over time)
        log_file = temp_log_dir / "orch-2025-11.log"
        with open(log_file, 'w') as f:
            for i, timestamp in enumerate(timestamps):
                # Write in format: YYYY-MM-DD HH:MM:SS LEVEL [command] message | {json}
                f.write(f"{timestamp} INFO  [test] Entry {i+1} | {{}}\n")

        # Read logs with limit of 3
        entries = logger.read_logs(limit=3)

        # Should return the 3 newest entries (Nov 5, 4, 3), not oldest (Nov 1, 2, 3)
        assert len(entries) == 3
        assert "2025-11-05" in entries[0]['timestamp']
        assert "2025-11-04" in entries[1]['timestamp']
        assert "2025-11-03" in entries[2]['timestamp']

        # Should NOT contain oldest entries (Nov 1, 2)
        timestamps_returned = [e['timestamp'] for e in entries]
        assert not any("2025-11-01" in ts for ts in timestamps_returned)
        assert not any("2025-11-02" in ts for ts in timestamps_returned)

    def test_read_logs_with_large_file_returns_recent_entries(self, logger, temp_log_dir):
        """Test that read_logs correctly handles large log files with many old entries."""
        # Simulate the actual bug scenario: many old entries + some new entries
        log_file = temp_log_dir / "orch-2025-11.log"
        with open(log_file, 'w') as f:
            # Write 100 old entries (simulating Nov 1-10)
            for i in range(100):
                f.write(f"2025-11-01 10:00:00 INFO  [test] Old entry {i+1} | {{}}\n")

            # Write 10 recent entries (simulating Nov 11)
            for i in range(10):
                f.write(f"2025-11-11 10:00:00 INFO  [test] Recent entry {i+1} | {{}}\n")

        # Read logs with default limit (50)
        entries = logger.read_logs(limit=50)

        # Should return 50 entries (respecting limit)
        assert len(entries) == 50

        # First 10 entries should be from Nov 11 (the most recent)
        for i in range(10):
            assert "2025-11-11" in entries[i]['timestamp'], \
                f"Expected first 10 entries to be from Nov 11, but entry {i} is {entries[i]['timestamp']}"

        # Remaining entries can be from Nov 1 (to fill up to limit)
        # The key is that Nov 11 comes FIRST, not buried after old entries
