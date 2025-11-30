"""Backlog resolution status lookup.

This module provides functionality to look up problem resolution status
from backlog.json instead of Resolution-Status fields in investigation files.

Per decision: .orch/decisions/2025-11-28-backlog-investigation-separation.md
- Investigations are pure documents (answer questions)
- Problem status is tracked in backlog.json via the `resolution` field
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class ResolutionStatus(Enum):
    """Resolution status for a problem tracked in backlog.json.

    Values match the backlog.json `resolution` field:
    - FIX: Problem was properly fixed
    - WORKAROUND: Problem has a workaround applied
    - UNRESOLVED: Problem not yet resolved (resolution=null with backlog item)
    - UNKNOWN: Investigation not tracked in backlog (no associated problem)
    """
    FIX = "fix"
    WORKAROUND = "workaround"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"

    def is_resolved(self) -> bool:
        """Check if this status represents a resolved problem."""
        return self in (ResolutionStatus.FIX, ResolutionStatus.WORKAROUND)


class BacklogResolver:
    """Resolve problem status by checking backlog.json.

    Usage:
        resolver = BacklogResolver(project_dir)
        status = resolver.get_resolution_for_investigation(inv_path)
        if status.is_resolved():
            print("Problem is resolved")
    """

    def __init__(self, project_dir: Path):
        """Initialize resolver for a project.

        Args:
            project_dir: Path to project root (containing .orch/)
        """
        self.project_dir = Path(project_dir)
        self.backlog: Optional[Dict] = None
        self._load_backlog()

    def _load_backlog(self) -> None:
        """Load backlog.json from project."""
        backlog_path = self.project_dir / ".orch" / "backlog.json"
        if not backlog_path.exists():
            return

        try:
            with open(backlog_path, 'r', encoding='utf-8') as f:
                self.backlog = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    def _normalize_path(self, path: str) -> str:
        """Normalize investigation path for comparison.

        Handles both absolute paths and relative paths (.orch/...).

        Args:
            path: Investigation path (absolute or relative)

        Returns:
            Normalized relative path starting with .orch/
        """
        path_obj = Path(path)

        # If absolute path, try to make it relative to project
        if path_obj.is_absolute():
            try:
                path_obj = path_obj.relative_to(self.project_dir)
            except ValueError:
                # Path not within project, use just the name for matching
                pass

        # Convert to string and ensure forward slashes
        normalized = str(path_obj).replace('\\', '/')

        # If it doesn't start with .orch, it's probably just the filename
        # Try to match by filename in that case
        return normalized

    def get_resolution_for_investigation(self, investigation_path: str) -> ResolutionStatus:
        """Get problem resolution status for an investigation.

        Looks up backlog.json entries that reference this investigation
        and determines overall resolution status.

        Args:
            investigation_path: Path to investigation file (absolute or relative)

        Returns:
            ResolutionStatus enum value:
            - FIX/WORKAROUND if all backlog items referencing this investigation are resolved
            - UNRESOLVED if any backlog item is not resolved
            - UNKNOWN if investigation not found in backlog
        """
        if not self.backlog:
            return ResolutionStatus.UNKNOWN

        features = self.backlog.get("features", [])
        if not features:
            return ResolutionStatus.UNKNOWN

        # Normalize the query path
        normalized_query = self._normalize_path(investigation_path)
        query_filename = Path(normalized_query).name

        # Find all backlog items referencing this investigation
        matching_items: List[Dict] = []

        for feature in features:
            feature_inv = feature.get("investigation")
            if not feature_inv:
                continue

            # Normalize the feature's investigation path
            normalized_feature = self._normalize_path(feature_inv)

            # Match by full path or filename
            if normalized_feature == normalized_query:
                matching_items.append(feature)
            elif Path(normalized_feature).name == query_filename:
                matching_items.append(feature)

        # No backlog items reference this investigation
        if not matching_items:
            return ResolutionStatus.UNKNOWN

        # Check resolution status of all matching items
        resolutions: List[Optional[str]] = [
            item.get("resolution") for item in matching_items
        ]

        # If any item is unresolved (resolution=null), overall is unresolved
        if any(r is None for r in resolutions):
            return ResolutionStatus.UNRESOLVED

        # All items have resolutions - determine overall status
        # If any is "fix", overall is fix; otherwise workaround
        if any(r == "fix" for r in resolutions):
            return ResolutionStatus.FIX
        elif any(r == "workaround" for r in resolutions):
            return ResolutionStatus.WORKAROUND

        # Fallback (shouldn't reach here with valid data)
        return ResolutionStatus.UNKNOWN


def get_investigation_resolution(
    investigation_path: str,
    project_dir: Path
) -> ResolutionStatus:
    """Convenience function to get resolution status for an investigation.

    Args:
        investigation_path: Path to investigation file
        project_dir: Path to project root

    Returns:
        ResolutionStatus enum value
    """
    resolver = BacklogResolver(project_dir)
    return resolver.get_resolution_for_investigation(investigation_path)
