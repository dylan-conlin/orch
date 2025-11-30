"""
Session tracking for orchestrator.

Tracks when the current orchestration session started to help distinguish
fresh vs stale agent completions.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class SessionTracker:
    """Track orchestrator session start time."""

    def __init__(self, session_file: Path = None):
        if session_file is None:
            session_file = Path.home() / '.orch' / 'current-session.json'
        self.session_file = Path(session_file)
        self._session_data = None

    def get_session_start(self, tmux_session: str) -> datetime:
        """
        Get session start time, creating new session if needed.

        Args:
            tmux_session: Name of tmux session (e.g., "workers")

        Returns:
            Session start datetime
        """
        # Load existing session data
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    self._session_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupted file, start fresh
                self._session_data = None

        # Check if we need to start a new session
        start_new = False

        if not self._session_data:
            # No existing session data
            start_new = True
        elif self._session_data.get('tmux_session') != tmux_session:
            # Different tmux session
            start_new = True
        else:
            # Check if session is too old (> 8 hours means likely a new session)
            try:
                session_start = datetime.fromisoformat(self._session_data['started_at'])
                age_hours = (datetime.now() - session_start).total_seconds() / 3600
                if age_hours > 8:
                    start_new = True
            except (KeyError, ValueError):
                start_new = True

        if start_new:
            # Start new session
            self._session_data = {
                'tmux_session': tmux_session,
                'started_at': datetime.now().isoformat()
            }
            self._save()

        return datetime.fromisoformat(self._session_data['started_at'])

    def _save(self):
        """Save session data to disk."""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump(self._session_data, f, indent=2)

    def reset_session(self, tmux_session: str):
        """Force start of a new session."""
        self._session_data = {
            'tmux_session': tmux_session,
            'started_at': datetime.now().isoformat()
        }
        self._save()


def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time string.

    Args:
        dt: Datetime to format

    Returns:
        Relative time string like "5m ago", "3h ago", "2d ago"

    Examples:
        >>> now = datetime.now()
        >>> format_relative_time(now)
        'just now'
        >>> format_relative_time(now - timedelta(minutes=5))
        '5m ago'
        >>> format_relative_time(now - timedelta(hours=3))
        '3h ago'
        >>> format_relative_time(now - timedelta(days=2))
        '2d ago'
    """
    from datetime import timedelta

    delta = datetime.now() - dt

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}m ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = int(delta.total_seconds() / 86400)
        return f"{days}d ago"


def is_stale(dt: datetime, threshold_hours: int = 4) -> bool:
    """
    Check if datetime is stale (older than threshold).

    Args:
        dt: Datetime to check
        threshold_hours: Staleness threshold in hours (default: 4)

    Returns:
        True if stale, False otherwise
    """
    from datetime import timedelta

    delta = datetime.now() - dt
    return delta > timedelta(hours=threshold_hours)
