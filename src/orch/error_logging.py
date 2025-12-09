"""Error logging module for orch CLI with local analytics.

Logs errors to ~/.orch/errors.jsonl for local pattern detection.
Provides aggregated stats and recent error retrieval.

Entry schema:
{
    "timestamp": "2025-12-09T10:42:00Z",
    "command": "orch complete pw-k2r",
    "subcommand": "complete",
    "error_type": "AgentNotFound",
    "error_code": "AGENT_NOT_FOUND",
    "message": "Agent 'pw-k2r' not found in registry",
    "context": {"attempted_lookup": "pw-k2r", "registry_count": 2},
    "stack_trace": "...",  // optional, for unexpected errors
    "duration_ms": 45
}
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ErrorType(Enum):
    """Error taxonomy for orch CLI errors."""

    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INVESTIGATION_NOT_FOUND = "INVESTIGATION_NOT_FOUND"
    SPAWN_FAILED = "SPAWN_FAILED"
    REGISTRY_LOCKED = "REGISTRY_LOCKED"
    BEADS_ERROR = "BEADS_ERROR"
    TMUX_ERROR = "TMUX_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass
class ErrorEntry:
    """Represents a single error log entry."""

    timestamp: str
    command: str
    subcommand: str
    error_type: ErrorType
    message: str
    context: Optional[dict[str, Any]] = None
    stack_trace: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        result = {
            "timestamp": self.timestamp,
            "command": self.command,
            "subcommand": self.subcommand,
            "error_type": self.error_type.value,
            "error_code": self.error_type.value,  # Alias for compatibility
            "message": self.message,
        }
        if self.context is not None:
            result["context"] = self.context
        if self.stack_trace is not None:
            result["stack_trace"] = self.stack_trace
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        return result


class ErrorLogger:
    """Logger for error telemetry to JSONL file.

    Logs errors to ~/.orch/errors.jsonl with automatic rotation.
    """

    DEFAULT_MAX_ENTRIES = 10000

    def __init__(
        self,
        error_file: Optional[Path] = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """Initialize error logger.

        Args:
            error_file: Path to errors.jsonl file. Defaults to ~/.orch/errors.jsonl
            max_entries: Maximum entries to keep (older entries are removed)
        """
        if error_file is None:
            error_file = Path.home() / ".orch" / "errors.jsonl"

        self.error_file = Path(error_file)
        self.max_entries = max_entries

        # Ensure parent directory exists
        self.error_file.parent.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        command: str,
        subcommand: str,
        error_type: ErrorType,
        message: str,
        context: Optional[dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Log an error to the JSONL file.

        Args:
            command: Full command string (e.g., "orch complete pw-k2r")
            subcommand: Subcommand name (e.g., "complete")
            error_type: ErrorType enum value
            message: Human-readable error message
            context: Optional context dict with error details
            stack_trace: Optional stack trace for unexpected errors
            duration_ms: Optional command duration in milliseconds
        """
        entry = ErrorEntry(
            timestamp=datetime.now().isoformat() + "Z",
            command=command,
            subcommand=subcommand,
            error_type=error_type,
            message=message,
            context=context,
            stack_trace=stack_trace,
            duration_ms=duration_ms,
        )

        # Append to file
        with open(self.error_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        # Check if rotation needed
        self._rotate_if_needed()

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max_entries."""
        if not self.error_file.exists():
            return

        lines = self.error_file.read_text().strip().split("\n")
        if len(lines) > self.max_entries:
            # Keep only the most recent entries
            keep_lines = lines[-self.max_entries :]
            self.error_file.write_text("\n".join(keep_lines) + "\n")

    def get_error_stats(self, days: int = 7) -> dict[str, Any]:
        """Get aggregated error statistics.

        Args:
            days: Number of days to include in stats

        Returns:
            Dict with total, by_type, by_command aggregations
        """
        cutoff = datetime.now() - timedelta(days=days)
        entries = self._read_entries(cutoff=cutoff)

        stats = {
            "total": len(entries),
            "by_type": {},
            "by_command": {},
        }

        for entry in entries:
            # Count by type
            error_type = entry.get("error_type", "UNKNOWN")
            stats["by_type"][error_type] = stats["by_type"].get(error_type, 0) + 1

            # Count by subcommand
            subcommand = entry.get("subcommand", "unknown")
            stats["by_command"][subcommand] = (
                stats["by_command"].get(subcommand, 0) + 1
            )

        return stats

    def get_recent_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent error entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of error entry dicts, most recent first
        """
        entries = self._read_entries()

        # Return most recent first (file is chronological, so reverse)
        return list(reversed(entries[-limit:]))

    def _read_entries(
        self, cutoff: Optional[datetime] = None
    ) -> list[dict[str, Any]]:
        """Read and parse all entries from the log file.

        Args:
            cutoff: Optional datetime - only include entries after this time

        Returns:
            List of parsed entry dicts
        """
        if not self.error_file.exists():
            return []

        entries = []
        for line in self.error_file.read_text().strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)

                # Filter by cutoff if provided
                if cutoff:
                    ts_str = entry.get("timestamp", "")
                    if ts_str:
                        # Parse ISO timestamp (remove Z suffix if present)
                        ts_str = ts_str.rstrip("Z")
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts < cutoff:
                                continue
                        except ValueError:
                            continue

                entries.append(entry)
            except json.JSONDecodeError:
                continue

        return entries


# Module-level singleton and convenience functions
_default_logger: Optional[ErrorLogger] = None


def _get_default_logger() -> ErrorLogger:
    """Get or create the default ErrorLogger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = ErrorLogger()
    return _default_logger


def log_error(
    command: str,
    subcommand: str,
    error_type: ErrorType,
    message: str,
    context: Optional[dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Log an error using the default logger.

    Convenience function that uses ~/.orch/errors.jsonl.

    Args:
        command: Full command string
        subcommand: Subcommand name
        error_type: ErrorType enum value
        message: Human-readable error message
        context: Optional context dict
        stack_trace: Optional stack trace
        duration_ms: Optional command duration
    """
    logger = _get_default_logger()
    logger.log_error(
        command=command,
        subcommand=subcommand,
        error_type=error_type,
        message=message,
        context=context,
        stack_trace=stack_trace,
        duration_ms=duration_ms,
    )


def get_error_stats(days: int = 7) -> dict[str, Any]:
    """Get error statistics using the default logger.

    Args:
        days: Number of days to include

    Returns:
        Stats dict with total, by_type, by_command
    """
    logger = _get_default_logger()
    return logger.get_error_stats(days=days)


def get_recent_errors(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent errors using the default logger.

    Args:
        limit: Maximum entries to return

    Returns:
        List of error entries, most recent first
    """
    logger = _get_default_logger()
    return logger.get_recent_errors(limit=limit)


def reset_default_logger() -> None:
    """Reset the default logger (for testing)."""
    global _default_logger
    _default_logger = None
