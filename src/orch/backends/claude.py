"""ClaudeBackend implementation for Claude Code CLI."""

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from .base import Backend

if TYPE_CHECKING:
    from orch.spawn import SpawnConfig


class ClaudeBackend(Backend):
    """Backend adapter for Claude Code CLI."""

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "claude"

    def get_config_dir(self) -> Path:
        """Return Claude's configuration directory (~/.claude)."""
        return Path.home() / ".claude"

    def build_command(self, prompt: str, options: Optional[Dict] = None) -> str:
        """
        Build the Claude Code CLI command string.

        Args:
            prompt: The initial prompt to send to Claude
            options: Optional backend-specific options:
                - model: Model to use (e.g., "sonnet", "opus", "claude-sonnet-4-5-20250929")
                - agent_name: Agent name to use with --agent flag (replaces --allowed-tools)

        Returns:
            The command string to execute (without environment variable exports)
        """
        # Use existing hardcoded wrapper path (extracted from spawn.py:1175)
        wrapper_path = "~/.orch/scripts/claude-code-wrapper.sh"

        # Build command parts
        parts = [wrapper_path]

        # Use --agent flag if agent_name provided, otherwise fallback to --allowed-tools '*'
        if options and options.get('agent_name'):
            agent_name = options['agent_name']
            parts.append(f"--agent {agent_name}")
        else:
            parts.append("--allowed-tools '*'")

        # Build optional flags
        if options and options.get('model'):
            parts.append(f"--model {shlex.quote(options['model'])}")

        # Shell-quote the prompt for safety
        quoted_prompt = shlex.quote(prompt)
        parts.append(quoted_prompt)

        return " ".join(parts)

    def wait_for_ready(self, window_target: str, timeout: float = 15.0) -> bool:
        """
        Poll tmux pane for Claude to be ready instead of hardcoded sleep.

        This is extracted from spawn.py:wait_for_claude_ready() (lines 31-88).
        Checks for Claude prompt indicators in pane content with short polling intervals.

        Args:
            window_target: Tmux window target (e.g., "session:1")
            timeout: Maximum wait time in seconds (default: 5.0)

        Returns:
            True if Claude prompt detected, False if timeout reached
        """
        # Escape hatch for environments where Claude's tmux output no longer
        # matches the expected ready prompt patterns. When set, we skip prompt
        # probing entirely and assume success after a short grace period.
        if os.getenv("ORCH_SKIP_CLAUDE_READY") == "1":
            time.sleep(1.0)
            return True

        start = time.time()

        while (time.time() - start) < timeout:
            try:
                # Capture pane content to check for Claude prompt
                result = subprocess.run(
                    ["tmux", "capture-pane", "-t", window_target, "-p"],
                    capture_output=True,
                    text=True,
                    timeout=1.0
                )

                # Check for Claude prompt indicators in output
                # Note: Based on actual Claude Code output patterns (verified from tmux panes)
                # Actual output: "✽ Sublimating…" → separator lines "─────" → "> Try 'refactor ui.py'"
                output_lower = result.stdout.lower()

                # Skip if still in loading state (Sublimating)
                if "sublimating" in output_lower:
                    continue  # Not ready yet, keep polling

                # Check for actual Claude Code ready indicators
                if any(indicator in output_lower for indicator in [
                    "> try",              # Prompt with suggestion (e.g., "> Try 'refactor ui.py'")
                    "─────",              # Separator lines (frame around prompt)
                ]):
                    return True

            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                # Ignore subprocess errors and continue polling
                pass

            # Short polling interval (100ms)
            time.sleep(0.1)

        # Timeout reached without detecting Claude
        return False

    def get_env_vars(self, config: "SpawnConfig", workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
        """
        Get Claude-specific environment variables to export before spawning.

        This is extracted from spawn.py lines 1168-1173.

        Args:
            config: SpawnConfig containing project directory and other spawn settings
            workspace_abs: Absolute path to the workspace directory
            deliverables_list: Comma-separated list of deliverable types

        Returns:
            Dictionary of CLAUDE_* environment variable names to values
        """
        return {
            "CLAUDE_CONTEXT": "worker",
            "CLAUDE_WORKSPACE": str(workspace_abs),
            "CLAUDE_PROJECT": str(config.project_dir),
            "CLAUDE_DELIVERABLES": deliverables_list,
        }
