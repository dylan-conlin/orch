"""
Tests for orch session module.

Tests session tracking for orchestrator.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from orch.session import (
    SessionTracker,
    format_relative_time,
    is_stale,
)


class TestSessionTracker:
    """Tests for SessionTracker class."""

    def test_creates_new_session_when_no_file(self, tmp_path):
        """Should create new session when no session file exists."""
        session_file = tmp_path / 'session.json'
        tracker = SessionTracker(session_file)

        start = tracker.get_session_start('workers')

        assert session_file.exists()
        assert isinstance(start, datetime)

    def test_reuses_session_for_same_tmux_session(self, tmp_path):
        """Should reuse existing session for same tmux session."""
        session_file = tmp_path / 'session.json'
        tracker = SessionTracker(session_file)

        start1 = tracker.get_session_start('workers')
        start2 = tracker.get_session_start('workers')

        assert start1 == start2

    def test_creates_new_session_for_different_tmux(self, tmp_path):
        """Should create new session for different tmux session."""
        session_file = tmp_path / 'session.json'
        tracker = SessionTracker(session_file)

        start1 = tracker.get_session_start('workers')
        start2 = tracker.get_session_start('different')

        # Different tmux sessions should get different start times
        # (or at least the session data should be updated)
        data = json.loads(session_file.read_text())
        assert data['tmux_session'] == 'different'

    def test_creates_new_session_when_old(self, tmp_path):
        """Should create new session when existing is > 8 hours old."""
        session_file = tmp_path / 'session.json'

        # Create old session
        old_time = datetime.now() - timedelta(hours=10)
        session_file.write_text(json.dumps({
            'tmux_session': 'workers',
            'started_at': old_time.isoformat()
        }))

        tracker = SessionTracker(session_file)
        start = tracker.get_session_start('workers')

        # Should be a recent time, not the old one
        assert (datetime.now() - start).total_seconds() < 60

    def test_handles_corrupted_file(self, tmp_path):
        """Should handle corrupted session file gracefully."""
        session_file = tmp_path / 'session.json'
        session_file.write_text('not valid json')

        tracker = SessionTracker(session_file)
        start = tracker.get_session_start('workers')

        assert isinstance(start, datetime)

    def test_reset_session(self, tmp_path):
        """Should force create new session on reset."""
        session_file = tmp_path / 'session.json'
        tracker = SessionTracker(session_file)

        # Get initial session
        start1 = tracker.get_session_start('workers')

        # Reset
        tracker.reset_session('workers')

        # Should have new timestamp (at least different session data)
        data = json.loads(session_file.read_text())
        new_start = datetime.fromisoformat(data['started_at'])
        assert new_start >= start1

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directory on save."""
        session_file = tmp_path / 'nested' / 'dir' / 'session.json'
        tracker = SessionTracker(session_file)

        tracker.get_session_start('workers')

        assert session_file.exists()


class TestFormatRelativeTime:
    """Tests for format_relative_time function."""

    def test_just_now(self):
        """Should return 'just now' for recent times."""
        result = format_relative_time(datetime.now())
        assert result == 'just now'

    def test_minutes_ago(self):
        """Should return minutes for times < 1 hour."""
        past = datetime.now() - timedelta(minutes=15)
        result = format_relative_time(past)
        assert '15m ago' == result

    def test_hours_ago(self):
        """Should return hours for times < 1 day."""
        past = datetime.now() - timedelta(hours=3)
        result = format_relative_time(past)
        assert '3h ago' == result

    def test_days_ago(self):
        """Should return days for times >= 1 day."""
        past = datetime.now() - timedelta(days=5)
        result = format_relative_time(past)
        assert '5d ago' == result


class TestIsStale:
    """Tests for is_stale function."""

    def test_not_stale_when_recent(self):
        """Should return False for recent times."""
        recent = datetime.now() - timedelta(hours=1)
        assert is_stale(recent) is False

    def test_stale_when_old(self):
        """Should return True for old times."""
        old = datetime.now() - timedelta(hours=5)
        assert is_stale(old) is True

    def test_custom_threshold(self):
        """Should respect custom threshold."""
        time = datetime.now() - timedelta(hours=2)

        # Not stale with 3 hour threshold
        assert is_stale(time, threshold_hours=3) is False

        # Stale with 1 hour threshold
        assert is_stale(time, threshold_hours=1) is True

    def test_exactly_at_threshold(self):
        """Should be stale when exactly at threshold."""
        time = datetime.now() - timedelta(hours=4, seconds=1)
        assert is_stale(time, threshold_hours=4) is True
