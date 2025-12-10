"""Abstract base class for backend implementations (Claude Code, Codex CLI, etc.)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from ..spawn import SpawnConfig


class Backend(ABC):
    """
    Abstract base class defining the interface for AI backend implementations.

    Each backend (Claude Code, Codex CLI, etc.) must implement these methods to integrate
    with the orch CLI spawning system.
    """

    @abstractmethod
    def build_command(self, prompt: str, options: Optional[Dict] = None) -> str:
        """
        Build the command string to invoke this backend's CLI.

        Args:
            prompt: The initial prompt to send to the backend
            options: Optional dictionary of backend-specific options (e.g., allowed_tools, permissions)

        Returns:
            The command string to execute (without environment variable exports)

        Example:
            For Claude: "~/.orch/scripts/claude-code-wrapper.sh --allowed-tools '*' --dangerously-skip-permissions 'prompt'"
            For Codex: "codex 'prompt'"
        """
        pass

    @abstractmethod
    def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
        """
        Poll tmux pane for backend to be ready instead of hardcoded sleep.

        Checks for backend-specific prompt indicators in pane content with short polling intervals.
        This is significantly faster than hardcoded sleeps while being more reliable.

        Args:
            window_target: Tmux window target (e.g., "session:1")
            timeout: Maximum wait time in seconds (default: 5.0)

        Returns:
            True if backend prompt detected, False if timeout reached

        Example:
            For Claude: Check for "sublimating", "> try", or "─────" patterns
            For Codex: Check for Codex-specific prompt patterns
        """
        pass

    @abstractmethod
    def get_env_vars(self, config: "SpawnConfig", workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
        """
        Get backend-specific environment variables to export before spawning.

        Args:
            config: SpawnConfig containing project directory and other spawn settings
            workspace_abs: Absolute path to the workspace directory
            deliverables_list: Comma-separated list of deliverable types

        Returns:
            Dictionary of environment variable names to values

        Example:
            For Claude: {"CLAUDE_CONTEXT": "worker", "CLAUDE_WORKSPACE": "/path/to/workspace", ...}
            For Codex: {"CODEX_CONTEXT": "worker", "CODEX_WORKSPACE": "/path/to/workspace", ...}
        """
        pass

    @abstractmethod
    def get_config_dir(self) -> Path:
        """
        Get the configuration directory path for this backend.

        Returns:
            Path to backend's config directory

        Example:
            For Claude: Path.home() / ".claude"
            For Codex: Path.home() / ".codex"
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the human-readable name of this backend.

        Returns:
            Backend name (e.g., "claude", "codex")
        """
        pass
