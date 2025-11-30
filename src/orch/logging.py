"""Logging module for orch commands with hybrid format.

Logs are written in hybrid format:
    YYYY-MM-DD HH:MM:SS LEVEL [command] Human message | {"json": "data"}

This provides both human readability (left side) and machine parseability (right side).
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class OrchLogger:
    """Logger for orch commands with hybrid format output.

    Logs are written to monthly files: orch-YYYY-MM.log
    Default location: ~/.orch/logs/
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize logger with log directory.

        Args:
            log_dir: Directory for log files. Defaults to ~/.orch/logs/
        """
        if log_dir is None:
            log_dir = Path.home() / ".orch" / "logs"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self) -> Path:
        """Get current month's log file path."""
        month_str = datetime.now().strftime("%Y-%m")
        return self.log_dir / f"orch-{month_str}.log"

    def _format_log_line(
        self,
        level: str,
        command: str,
        message: str,
        data: Dict[str, Any]
    ) -> str:
        """Format log line in hybrid format.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            command: Command name (spawn, clean, status, etc.)
            message: Human-readable message
            data: Structured data as dict

        Returns:
            Formatted log line with newline
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Pad level to 5 characters for alignment
        level_padded = level.ljust(5)

        # Format: YYYY-MM-DD HH:MM:SS LEVEL [command] message | {json}
        json_str = json.dumps(data, ensure_ascii=False)
        return f"{timestamp} {level_padded} [{command}] {message} | {json_str}\n"

    def log_event(
        self,
        command: str,
        message: str,
        data: Dict[str, Any],
        level: str = "INFO"
    ) -> None:
        """Log an event with hybrid format.

        Args:
            command: Command name (spawn, clean, status, etc.)
            message: Human-readable message
            data: Structured data as dict
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        log_line = self._format_log_line(level, command, message, data)
        log_file = self._get_log_file()

        with open(log_file, "a") as f:
            f.write(log_line)

    def log_command_start(self, command: str, data: Dict[str, Any]) -> None:
        """Log command start event.

        Args:
            command: Command name
            data: Command parameters and context
        """
        # Extract key info for human-readable message
        task = data.get("task", "")
        message = f"Starting command"
        if task:
            message = f"Starting command: {task}"

        self.log_event(command, message, data, level="INFO")

    def log_command_complete(
        self,
        command: str,
        duration_ms: int,
        data: Dict[str, Any]
    ) -> None:
        """Log command completion event.

        Args:
            command: Command name
            duration_ms: Command duration in milliseconds
            data: Result data
        """
        # Extract key info for human-readable message
        agent_id = data.get("agent_id", "")
        message = f"Command complete ({duration_ms}ms)"
        if agent_id:
            message = f"Command complete: {agent_id} ({duration_ms}ms)"

        # Add duration to data if not already present
        if "duration_ms" not in data:
            data = {**data, "duration_ms": duration_ms}

        self.log_event(command, message, data, level="INFO")

    def log_error(
        self,
        command: str,
        message: str,
        data: Dict[str, Any]
    ) -> None:
        """Log error event.

        Args:
            command: Command name
            message: Error message
            data: Error details
        """
        # Include reason in message if available
        reason = data.get("reason", "")
        if reason:
            full_message = f"{message}: {reason}"
        else:
            full_message = message

        self.log_event(command, full_message, data, level="ERROR")

    def get_log_files(self, months_back: int = 6) -> list[Path]:
        """Get list of available log files (most recent first).

        Args:
            months_back: Number of months to look back

        Returns:
            List of log file paths, sorted newest first
        """
        log_files = []
        for file in self.log_dir.glob("orch-*.log"):
            log_files.append(file)

        # Sort by filename (which includes YYYY-MM) descending
        return sorted(log_files, reverse=True)[:months_back]

    def read_logs(
        self,
        limit: int = 50,
        command_filter: str = None,
        level_filter: str = None
    ) -> list[dict]:
        """Read and parse log entries with optional filtering.

        Args:
            limit: Maximum number of entries to return
            command_filter: Only return entries for this command
            level_filter: Only return entries with this log level

        Returns:
            List of parsed log entries (dicts with timestamp, level, command, message, data)
        """
        entries = []
        log_files = self.get_log_files()

        for log_file in log_files:
            if not log_file.exists():
                continue

            # Read file in reverse to get newest entries first
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    entry = self._parse_log_line(line)
                    if not entry:
                        continue

                    # Apply filters
                    if command_filter and entry['command'] != command_filter:
                        continue
                    if level_filter and entry['level'] != level_filter:
                        continue

                    entries.append(entry)

                    # Stop if we've reached limit
                    if len(entries) >= limit:
                        return entries

        return entries

    def _parse_log_line(self, line: str) -> dict | None:
        """Parse a log line into structured format.

        Args:
            line: Raw log line in hybrid format

        Returns:
            Dict with parsed fields or None if parse fails
        """
        try:
            # Format: YYYY-MM-DD HH:MM:SS LEVEL [command] message | {json}
            parts = line.split(' | ', 1)
            if len(parts) != 2:
                return None

            left_part = parts[0]
            json_part = parts[1].strip()

            # Parse left side
            tokens = left_part.split(None, 3)  # Split on whitespace, max 4 parts
            if len(tokens) < 4:
                return None

            timestamp = f"{tokens[0]} {tokens[1]}"
            level = tokens[2].strip()
            # Command is in brackets: [command]
            command_and_message = tokens[3]
            if not command_and_message.startswith('['):
                return None

            # Extract command and message
            bracket_end = command_and_message.index(']')
            command = command_and_message[1:bracket_end]
            message = command_and_message[bracket_end + 2:].strip()  # +2 to skip "] "

            # Parse JSON data
            data = json.loads(json_part)

            return {
                'timestamp': timestamp,
                'level': level,
                'command': command,
                'message': message,
                'data': data
            }
        except (ValueError, IndexError, json.JSONDecodeError):
            return None
