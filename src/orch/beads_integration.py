"""Beads issue tracker integration for orch CLI.

Provides a wrapper around the `bd` CLI for fetching and updating beads issues.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional


class BeadsCLINotFoundError(Exception):
    """Raised when the bd CLI is not installed or not in PATH."""

    def __init__(self, message: str = "bd CLI not found. Install beads or check PATH."):
        super().__init__(message)


class BeadsIssueNotFoundError(Exception):
    """Raised when a beads issue is not found."""

    def __init__(self, issue_id: str):
        self.issue_id = issue_id
        super().__init__(f"Beads issue '{issue_id}' not found")


@dataclass
class BeadsIssue:
    """Represents a beads issue."""

    id: str
    title: str
    description: str
    status: str
    priority: int
    notes: Optional[str] = None


class BeadsIntegration:
    """Wrapper around the beads (bd) CLI."""

    def __init__(self, cli_path: str = "bd"):
        """Initialize BeadsIntegration.

        Args:
            cli_path: Path to the bd CLI executable. Defaults to "bd".
        """
        self.cli_path = cli_path

    def get_issue(self, issue_id: str) -> BeadsIssue:
        """Get a beads issue by ID.

        Args:
            issue_id: The beads issue ID (e.g., "orch-cli-ltv")

        Returns:
            BeadsIssue with the issue details

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                [self.cli_path, "show", issue_id, "--json"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

        try:
            issues = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise BeadsIssueNotFoundError(issue_id)

        if not issues or len(issues) == 0:
            raise BeadsIssueNotFoundError(issue_id)

        issue_data = issues[0]
        return BeadsIssue(
            id=issue_data.get("id", issue_id),
            title=issue_data.get("title", ""),
            description=issue_data.get("description", ""),
            status=issue_data.get("status", ""),
            priority=issue_data.get("priority", 0),
            notes=issue_data.get("notes"),
        )

    def update_issue_notes(self, issue_id: str, notes: str) -> None:
        """Update the notes field of a beads issue.

        Args:
            issue_id: The beads issue ID
            notes: The new notes content

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                [self.cli_path, "update", issue_id, "--notes", notes],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

    def add_workspace_link(self, issue_id: str, workspace_path: str) -> None:
        """Add a workspace link to an issue's notes.

        Args:
            issue_id: The beads issue ID
            workspace_path: Path to the workspace directory

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        notes = f"workspace: {workspace_path}"
        self.update_issue_notes(issue_id, notes)

    def update_issue_status(self, issue_id: str, status: str) -> None:
        """Update the status of a beads issue.

        Args:
            issue_id: The beads issue ID
            status: The new status (e.g., "in_progress", "open", "closed")

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                [self.cli_path, "update", issue_id, "--status", status],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

    def close_issue(self, issue_id: str, reason: Optional[str] = None) -> None:
        """Close a beads issue with an optional reason.

        Args:
            issue_id: The beads issue ID
            reason: Optional reason for closing. Defaults to "Resolved via orch complete".

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        if reason is None:
            reason = "Resolved via orch complete"

        try:
            result = subprocess.run(
                [self.cli_path, "close", issue_id, "--reason", reason],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)
