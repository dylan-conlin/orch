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
class BeadsDependency:
    """Represents a dependency relationship between beads issues."""

    id: str
    title: str
    status: str
    dependency_type: str  # "blocks" or "parent-child"


@dataclass
class BeadsIssue:
    """Represents a beads issue."""

    id: str
    title: str
    description: str
    status: str
    priority: int
    notes: Optional[str] = None
    dependencies: Optional[list] = None  # List of BeadsDependency


class BeadsIntegration:
    """Wrapper around the beads (bd) CLI."""

    def __init__(self, cli_path: str = "bd", db_path: Optional[str] = None):
        """Initialize BeadsIntegration.

        Args:
            cli_path: Path to the bd CLI executable. Defaults to "bd".
            db_path: Optional absolute path to beads database. If provided,
                     all bd commands will include --db flag for cross-repo access.
        """
        self.cli_path = cli_path
        self.db_path = db_path

    def _build_command(self, *args) -> list:
        """Build command with optional --db flag.

        Args:
            *args: Command arguments to pass to bd CLI.

        Returns:
            List of command arguments including cli_path and optional --db flag.
        """
        cmd = [self.cli_path]
        if self.db_path:
            cmd.extend(["--db", self.db_path])
        cmd.extend(args)
        return cmd

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
                self._build_command("show", issue_id, "--json"),
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

        # Parse dependencies if present
        dependencies = None
        deps_data = issue_data.get("dependencies")
        if deps_data is not None:
            dependencies = [
                BeadsDependency(
                    id=dep.get("id", ""),
                    title=dep.get("title", ""),
                    status=dep.get("status", ""),
                    dependency_type=dep.get("dependency_type", "")
                )
                for dep in deps_data
            ]

        return BeadsIssue(
            id=issue_data.get("id", issue_id),
            title=issue_data.get("title", ""),
            description=issue_data.get("description", ""),
            status=issue_data.get("status", ""),
            priority=issue_data.get("priority", 0),
            notes=issue_data.get("notes"),
            dependencies=dependencies,
        )

    def get_open_blockers(self, issue_id: str) -> list:
        """Get list of open blockers for an issue.

        Returns dependencies that have:
        - dependency_type == "blocks"
        - status == "open"

        Args:
            issue_id: The beads issue ID

        Returns:
            List of BeadsDependency objects that are open blockers.
            Empty list if no open blockers exist.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        issue = self.get_issue(issue_id)
        if issue.dependencies is None:
            return []

        return [
            dep for dep in issue.dependencies
            if dep.dependency_type == "blocks" and dep.status == "open"
        ]

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
                self._build_command("update", issue_id, "--notes", notes),
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
                self._build_command("update", issue_id, "--status", status),
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
                self._build_command("close", issue_id, "--reason", reason),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

    def get_phase_from_comments(self, issue_id: str) -> Optional[str]:
        """Extract the latest phase from beads issue comments.

        Agents report progress via comments like:
          bd comment <id> "Phase: Implementing - working on feature X"

        This method parses comments to find the most recent "Phase: ..." line.

        Args:
            issue_id: The beads issue ID

        Returns:
            The phase string (e.g., "Implementing", "Complete") or None if no phase found.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                self._build_command("comments", issue_id, "--json"),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

        try:
            comments = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

        if not comments:
            return None

        # Find the latest "Phase: ..." comment (comments are chronologically ordered)
        import re
        latest_phase = None
        for comment in comments:
            text = comment.get("text", "")
            # Match "Phase: <phase>" at start of comment
            match = re.match(r"Phase:\s*(\w+)", text)
            if match:
                latest_phase = match.group(1)

        return latest_phase

    def has_phase_complete(self, issue_id: str) -> bool:
        """Check if issue has a "Phase: Complete" comment.

        Used by orch complete to verify agent reported completion before closing.

        Args:
            issue_id: The beads issue ID

        Returns:
            True if a "Phase: Complete" comment exists, False otherwise.
        """
        phase = self.get_phase_from_comments(issue_id)
        return phase is not None and phase.lower() == "complete"

    def get_investigation_path_from_comments(self, issue_id: str) -> Optional[str]:
        """Extract the investigation_path from beads issue comments.

        Agents report their investigation file path via comments like:
          bd comment <id> "investigation_path: /path/to/file.md"

        This method parses comments to find the most recent "investigation_path: ..." line.

        Args:
            issue_id: The beads issue ID

        Returns:
            The investigation file path or None if no investigation_path found.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                self._build_command("comments", issue_id, "--json"),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

        try:
            comments = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

        if not comments:
            return None

        # Find the latest "investigation_path: ..." comment (comments are chronologically ordered)
        import re
        latest_path = None
        for comment in comments:
            text = comment.get("text", "")
            # Match "investigation_path: <path>" at start of comment
            match = re.match(r"investigation_path:\s*(.+)", text)
            if match:
                latest_path = match.group(1).strip()

        return latest_path

    def add_comment(self, issue_id: str, comment: str) -> None:
        """Add a comment to a beads issue.

        Args:
            issue_id: The beads issue ID
            comment: The comment text to add

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                self._build_command("comment", issue_id, comment),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

    def add_agent_metadata(
        self,
        issue_id: str,
        agent_id: str,
        window_id: str,
        skill: Optional[str] = None,
        project_dir: Optional[str] = None
    ) -> None:
        """Store agent metadata in beads comments for registry-less operation.

        This is Phase 1 of registry removal: store agent metadata in beads
        so we can later look up agents without the JSON registry file.

        The metadata is stored as a structured comment:
          agent_metadata: {"agent_id": "...", "window_id": "...", "skill": "...", "project_dir": "..."}

        Args:
            issue_id: The beads issue ID
            agent_id: Agent identifier (workspace name)
            window_id: Tmux window ID (e.g., "@123")
            skill: Optional skill name
            project_dir: Optional project directory path

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        metadata = {
            "agent_id": agent_id,
            "window_id": window_id,
        }
        if skill:
            metadata["skill"] = skill
        if project_dir:
            metadata["project_dir"] = project_dir

        comment = f"agent_metadata: {json.dumps(metadata)}"
        self.add_comment(issue_id, comment)

    def get_agent_metadata(self, issue_id: str) -> Optional[dict]:
        """Extract agent metadata from beads issue comments.

        Looks for the most recent "agent_metadata: {...}" comment.

        Args:
            issue_id: The beads issue ID

        Returns:
            Dict with agent metadata (agent_id, window_id, skill, project_dir)
            or None if no metadata found.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        try:
            result = subprocess.run(
                self._build_command("comments", issue_id, "--json"),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            raise BeadsIssueNotFoundError(issue_id)

        try:
            comments = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

        if not comments:
            return None

        # Find the latest "agent_metadata: {...}" comment
        import re
        latest_metadata = None
        for comment in comments:
            text = comment.get("text", "")
            # Match "agent_metadata: {...}" at start of comment
            match = re.match(r"agent_metadata:\s*(\{.+\})", text)
            if match:
                try:
                    latest_metadata = json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        return latest_metadata

    def list_active_agents(self) -> list:
        """List active agents by querying beads issues with in_progress status.

        This is part of Phase 2 of registry removal: use beads to find
        active agents instead of reading from agent-registry.json.

        Returns:
            List of dicts with agent metadata for active issues.
            Each dict has keys: beads_id, title, agent_id, window_id, skill, project_dir

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
        """
        try:
            result = subprocess.run(
                self._build_command("list", "--status=in_progress", "--json"),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise BeadsCLINotFoundError()

        if result.returncode != 0:
            return []

        try:
            issues = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        agents = []
        for issue in issues:
            issue_id = issue.get("id")
            if not issue_id:
                continue

            # Get agent metadata from comments
            try:
                metadata = self.get_agent_metadata(issue_id)
            except (BeadsCLINotFoundError, BeadsIssueNotFoundError):
                metadata = None

            agent_info = {
                "beads_id": issue_id,
                "title": issue.get("title", ""),
                "status": issue.get("status", ""),
            }

            if metadata:
                agent_info.update(metadata)

            agents.append(agent_info)

        return agents

    def get_agent_notes(self, issue_id: str) -> Optional[dict]:
        """Get agent metadata from the notes field as a JSON dict.

        The notes field stores a JSON object with agent metadata including:
        agent_id, window_id, phase, skill, project_dir, investigation_path, updated_at.

        Args:
            issue_id: The beads issue ID

        Returns:
            Dict with agent metadata or None if notes is empty/not JSON.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        issue = self.get_issue(issue_id)
        if not issue.notes:
            return None

        try:
            return json.loads(issue.notes)
        except json.JSONDecodeError:
            return None

    def update_agent_notes(
        self,
        issue_id: str,
        agent_id: Optional[str] = None,
        window_id: Optional[str] = None,
        phase: Optional[str] = None,
        skill: Optional[str] = None,
        project_dir: Optional[str] = None,
        investigation_path: Optional[str] = None,
    ) -> None:
        """Update agent metadata in the notes field as JSON.

        This method merges new values with existing notes content,
        preserving fields that aren't being updated.

        Args:
            issue_id: The beads issue ID
            agent_id: Agent identifier (workspace name)
            window_id: Tmux window ID (e.g., "@123")
            phase: Current phase (e.g., "Planning", "Implementing", "Complete")
            skill: Skill name (e.g., "feature-impl", "investigation")
            project_dir: Project directory path
            investigation_path: Path to investigation file

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        from datetime import datetime, timezone

        # Get existing notes and merge
        existing = {}
        try:
            existing = self.get_agent_notes(issue_id) or {}
        except BeadsIssueNotFoundError:
            # Issue doesn't exist yet, start fresh
            pass

        # Build update dict with only provided values
        updates = {}
        if agent_id is not None:
            updates["agent_id"] = agent_id
        if window_id is not None:
            updates["window_id"] = window_id
        if phase is not None:
            updates["phase"] = phase
        if skill is not None:
            updates["skill"] = skill
        if project_dir is not None:
            updates["project_dir"] = project_dir
        if investigation_path is not None:
            updates["investigation_path"] = investigation_path

        # Merge existing with updates
        merged = {**existing, **updates}

        # Always update timestamp
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Write to notes field
        self.update_issue_notes(issue_id, json.dumps(merged))

    def get_phase_from_notes(self, issue_id: str) -> Optional[str]:
        """Get the phase from the notes field.

        Args:
            issue_id: The beads issue ID

        Returns:
            The phase string or None if not found.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        notes = self.get_agent_notes(issue_id)
        if notes is None:
            return None
        return notes.get("phase")

    def get_investigation_path_from_notes(self, issue_id: str) -> Optional[str]:
        """Get the investigation_path from the notes field.

        Args:
            issue_id: The beads issue ID

        Returns:
            The investigation file path or None if not found.

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        notes = self.get_agent_notes(issue_id)
        if notes is None:
            return None
        return notes.get("investigation_path")

    def update_phase(self, issue_id: str, phase: str) -> None:
        """Update just the phase in the notes field.

        Convenience method for updating phase without specifying other fields.

        Args:
            issue_id: The beads issue ID
            phase: The new phase (e.g., "Planning", "Implementing", "Complete")

        Raises:
            BeadsCLINotFoundError: If bd CLI is not installed
            BeadsIssueNotFoundError: If the issue doesn't exist
        """
        self.update_agent_notes(issue_id, phase=phase)
