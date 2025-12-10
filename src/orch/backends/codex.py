"""CodexBackend implementation for OpenAI Codex CLI."""

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from .base import Backend

if TYPE_CHECKING:
    from orch.spawn import SpawnConfig


class CodexBackend(Backend):
    """Backend adapter for OpenAI Codex CLI.

    This adapter enables orch CLI to spawn Codex agents as an alternative to Claude Code.
    Key differences from Claude:
    - Uses 'codex' command directly (not claude wrapper script)
    - Config directory: ~/.codex (not ~/.claude)
    - Context file: AGENTS.md (not CLAUDE.md) - validated via OpenAI documentation
    - Environment variables: CODEX_* prefix (not CLAUDE_*)

    Validated implementation (2025-11-21):
    - Command syntax: 'codex "prompt"' confirmed working (v0.59.0)
    - Readiness patterns: "OpenAI Codex", "›" prompt, "context left" status
    - AGENTS.md: Confirmed as standard context file (also supports AGENTS.override.md)
    - Environment variables: CODEX_CONTEXT, CODEX_WORKSPACE, CODEX_PROJECT, CODEX_DELIVERABLES

    Note: AGENTS.md is an open standard used across multiple AI coding assistants
    (Codex, Cursor, Jules, Factory). Codex reads from ~/.codex/AGENTS.md for global
    instructions and walks from repo root to current directory for project-specific files.
    """

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "codex"

    def get_config_dir(self) -> Path:
        """Return Codex's configuration directory (~/.codex).

        Validated implementation (2025-11-21):
        - Codex uses ~/.codex for configuration (config.toml, auth.json, history.jsonl)
        - Global AGENTS.md file location: ~/.codex/AGENTS.md (optional)
        - Similar to Claude's ~/.claude pattern
        """
        return Path.home() / ".codex"

    def build_command(self, prompt: str, options: Optional[Dict] = None) -> str:
        """
        Build the Codex CLI command string.

        Args:
            prompt: The initial prompt to send to Codex
            options: Optional backend-specific options (currently unused, maintained for API compatibility)

        Returns:
            The command string to execute (without environment variable exports)

        Validated implementation (2025-11-21):
        - Codex CLI accepts initial prompt via command line: codex "prompt text"
        - Tested with Codex CLI v0.59.0
        - No wrapper script needed (unlike Claude's wrapper.sh)
        - Uses --dangerously-bypass-approvals-and-sandbox for worker agents (parallel to Claude's --dangerously-skip-permissions)
        - Future phases can make this configurable via options parameter
        """
        # Shell-quote the prompt for safety
        quoted_prompt = shlex.quote(prompt)

        # Use codex command directly with bypass flag (validated command syntax)
        bypass_flag = "--dangerously-bypass-approvals-and-sandbox"
        return f"codex {bypass_flag} {quoted_prompt}"

    def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
        """
        Poll tmux pane for Codex to be ready instead of hardcoded sleep.

        Similar to ClaudeBackend approach but adapted for Codex prompt patterns.
        Checks for Codex prompt indicators in pane content with short polling intervals.

        Args:
            window_target: Tmux window target (e.g., "session:1")
            timeout: Maximum wait time in seconds (default: 5.0)

        Returns:
            True if Codex prompt detected, False if timeout reached

        Implementation notes:
        - Validated with Codex CLI v0.59.0 on 2025-11-21
        - Codex shows "OpenAI Codex" banner during startup
        - Ready state indicated by "›" prompt (Unicode U+203A)
        - Status bar shows "context left" when ready for input
        - Patterns may need updates if Codex UI changes significantly
        """
        # Escape hatch for environments where Codex's tmux output no longer
        # matches the expected ready prompt patterns. When set, we skip prompt
        # probing entirely and assume success after a short grace period.
        if os.getenv("ORCH_SKIP_CODEX_READY") == "1":
            time.sleep(1.0)
            return True

        start = time.time()

        while (time.time() - start) < timeout:
            try:
                # Capture pane content to check for Codex prompt
                result = subprocess.run(
                    ["tmux", "capture-pane", "-t", window_target, "-p"],
                    capture_output=True,
                    text=True,
                    timeout=1.0
                )

                output = result.stdout
                output_lower = output.lower()

                # Check for Codex ready indicators (validated 2025-11-21)
                # Pattern 1: Startup banner contains "OpenAI Codex"
                # Pattern 2: Ready prompt is "›" (U+203A right-pointing arrow)
                # Pattern 3: Status bar shows "context left" when ready
                # Pattern 4: Help commands like "/init" appear after startup
                if any(indicator in output_lower for indicator in [
                    "openai codex",       # Startup banner indicator
                    "context left",       # Status bar ready indicator
                    "/init",              # Help commands indicator (startup complete)
                ]) or "›" in output:      # Ready prompt (case-sensitive Unicode char)
                    return True

            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                # Ignore subprocess errors and continue polling
                pass

            # Short polling interval (100ms)
            time.sleep(0.1)

        # Timeout reached without detecting Codex
        return False

    def get_env_vars(self, config: "SpawnConfig", workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
        """
        Get Codex-specific environment variables to export before spawning.

        Mirrors ClaudeBackend structure but uses CODEX_* prefix instead of CLAUDE_*.

        Args:
            config: SpawnConfig containing project directory and other spawn settings
            workspace_abs: Absolute path to the workspace directory
            deliverables_list: Comma-separated list of deliverable types

        Returns:
            Dictionary of CODEX_* environment variable names to values

        Implementation notes (2025-11-21):
        - Uses CODEX_* prefix (parallel to Claude's CLAUDE_* pattern)
        - Same semantic meaning: CONTEXT, WORKSPACE, PROJECT, DELIVERABLES
        - These variables are available in spawned Codex agent sessions
        - Can be referenced in AGENTS.md files or agent logic
        """
        return {
            "CODEX_CONTEXT": "worker",
            "CODEX_WORKSPACE": str(workspace_abs),
            "CODEX_PROJECT": str(config.project_dir),
            "CODEX_DELIVERABLES": deliverables_list,
        }
