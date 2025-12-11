"""Agentlog integration for orch CLI.

Provides a wrapper around the `agentlog` CLI for fetching error context.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import List, Optional


class AgentlogCLINotFoundError(Exception):
    """Raised when the agentlog CLI is not installed or not in PATH."""

    def __init__(self, message: str = "agentlog CLI not found. Install agentlog or check PATH."):
        super().__init__(message)


@dataclass
class ErrorEntry:
    """Represents an error entry from agentlog."""

    timestamp: str
    error_type: str
    message: str
    source: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    stack_trace: Optional[str] = None


@dataclass
class PrimeSummary:
    """Represents the prime context summary from agentlog."""

    total_errors: int
    last_24h_errors: int
    last_hour_errors: int
    top_error_types: Optional[List[dict]] = None
    top_sources: Optional[List[dict]] = None
    actionable_tip: Optional[str] = None
    generated_at: Optional[str] = None
    no_log_file: bool = False


class AgentlogIntegration:
    """Wrapper around the agentlog CLI."""

    def __init__(self, cli_path: str = "agentlog"):
        """Initialize AgentlogIntegration.

        Args:
            cli_path: Path to the agentlog CLI executable. Defaults to "agentlog".
        """
        self.cli_path = cli_path

    def is_available(self) -> bool:
        """Check if agentlog CLI is available.

        Returns:
            True if agentlog is installed and accessible, False otherwise.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def prime(self) -> str:
        """Get context summary for AI agent injection.

        Returns:
            Human-readable summary string from agentlog prime.

        Raises:
            AgentlogCLINotFoundError: If agentlog CLI is not installed.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "prime"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise AgentlogCLINotFoundError()
        except subprocess.TimeoutExpired:
            return ""

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    def prime_json(self) -> PrimeSummary:
        """Get structured context summary for AI agent injection.

        Returns:
            PrimeSummary with error statistics and tips.

        Raises:
            AgentlogCLINotFoundError: If agentlog CLI is not installed.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "prime", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise AgentlogCLINotFoundError()
        except subprocess.TimeoutExpired:
            return PrimeSummary(
                total_errors=0,
                last_24h_errors=0,
                last_hour_errors=0,
                no_log_file=True,
            )

        if result.returncode != 0:
            return PrimeSummary(
                total_errors=0,
                last_24h_errors=0,
                last_hour_errors=0,
                no_log_file=True,
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return PrimeSummary(
                total_errors=0,
                last_24h_errors=0,
                last_hour_errors=0,
                no_log_file=True,
            )

        return PrimeSummary(
            total_errors=data.get("total_errors", 0),
            last_24h_errors=data.get("last_24h_errors", 0),
            last_hour_errors=data.get("last_hour_errors", 0),
            top_error_types=data.get("top_error_types"),
            top_sources=data.get("top_sources"),
            actionable_tip=data.get("actionable_tip"),
            generated_at=data.get("generated_at"),
            no_log_file=data.get("no_log_file", False),
        )

    def get_recent_errors(self, limit: int = 10) -> List[ErrorEntry]:
        """Get recent errors from agentlog.

        Args:
            limit: Maximum number of errors to return. Defaults to 10.

        Returns:
            List of ErrorEntry objects.

        Raises:
            AgentlogCLINotFoundError: If agentlog CLI is not installed.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "errors", "--limit", str(limit), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise AgentlogCLINotFoundError()
        except subprocess.TimeoutExpired:
            return []

        if result.returncode != 0:
            return []

        try:
            errors = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(errors, list):
            return []

        return [
            ErrorEntry(
                timestamp=err.get("timestamp", ""),
                error_type=err.get("type", err.get("error_type", "")),
                message=err.get("message", ""),
                source=err.get("source"),
                file=err.get("file"),
                line=err.get("line"),
                stack_trace=err.get("stack_trace"),
            )
            for err in errors
        ]

    def get_errors_by_type(self, error_type: str, limit: int = 10) -> List[ErrorEntry]:
        """Get errors filtered by type.

        Args:
            error_type: Error type to filter by (e.g., "DATABASE_ERROR").
            limit: Maximum number of errors to return. Defaults to 10.

        Returns:
            List of ErrorEntry objects matching the type.

        Raises:
            AgentlogCLINotFoundError: If agentlog CLI is not installed.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "errors", "--type", error_type, "--limit", str(limit), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise AgentlogCLINotFoundError()
        except subprocess.TimeoutExpired:
            return []

        if result.returncode != 0:
            return []

        try:
            errors = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(errors, list):
            return []

        return [
            ErrorEntry(
                timestamp=err.get("timestamp", ""),
                error_type=err.get("type", err.get("error_type", "")),
                message=err.get("message", ""),
                source=err.get("source"),
                file=err.get("file"),
                line=err.get("line"),
                stack_trace=err.get("stack_trace"),
            )
            for err in errors
        ]

    def get_errors_by_source(self, source: str, limit: int = 10) -> List[ErrorEntry]:
        """Get errors filtered by source.

        Args:
            source: Source to filter by (e.g., "frontend", "backend", "cli").
            limit: Maximum number of errors to return. Defaults to 10.

        Returns:
            List of ErrorEntry objects from the source.

        Raises:
            AgentlogCLINotFoundError: If agentlog CLI is not installed.
        """
        try:
            result = subprocess.run(
                [self.cli_path, "errors", "--source", source, "--limit", str(limit), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise AgentlogCLINotFoundError()
        except subprocess.TimeoutExpired:
            return []

        if result.returncode != 0:
            return []

        try:
            errors = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(errors, list):
            return []

        return [
            ErrorEntry(
                timestamp=err.get("timestamp", ""),
                error_type=err.get("type", err.get("error_type", "")),
                message=err.get("message", ""),
                source=err.get("source"),
                file=err.get("file"),
                line=err.get("line"),
                stack_trace=err.get("stack_trace"),
            )
            for err in errors
        ]
