"""ClaudeBackend implementation for Claude Code CLI."""

import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .base import Backend

if TYPE_CHECKING:
    from orch.spawn import SpawnConfig


# Built-in MCP server configurations for commonly used servers
# These are used as fallbacks when no user-defined config exists
BUILTIN_MCP_SERVERS = {
    "playwright": {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"]
    },
    "browser-use": {
        "command": "npx",
        "args": ["-y", "browser-use-mcp@latest"]
    },
    "puppeteer": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer@latest"]
    }
}


def resolve_mcp_servers(server_names: str, workspace_path: Optional[Path] = None) -> Optional[str]:
    """
    Resolve MCP server names to a config file path for --mcp-config.

    Looks for user-defined configs at ~/.orch/mcp/{name}.json first,
    then falls back to built-in defaults. Writes the combined config
    to a file in the workspace directory to avoid shell escaping issues.

    Args:
        server_names: Comma-separated list of server names (e.g., "playwright,browser-use")
        workspace_path: Path to workspace directory where config file will be written.
                        If None, returns JSON string (for backward compatibility).

    Returns:
        Path to config file (if workspace_path provided), or JSON string (if not),
        or None if no valid servers found
    """
    if not server_names:
        return None

    mcp_config_dir = Path.home() / ".orch" / "mcp"
    servers = {}
    missing = []

    for name in server_names.split(","):
        name = name.strip()
        if not name:
            continue

        # Check for user-defined config file first
        user_config_path = mcp_config_dir / f"{name}.json"
        if user_config_path.exists():
            try:
                with open(user_config_path) as f:
                    user_config = json.load(f)
                # User config can be either a single server config or an mcpServers wrapper
                if "mcpServers" in user_config:
                    servers.update(user_config["mcpServers"])
                else:
                    servers[name] = user_config
                continue
            except (json.JSONDecodeError, IOError):
                pass  # Fall through to built-in

        # Fall back to built-in defaults
        if name in BUILTIN_MCP_SERVERS:
            servers[name] = BUILTIN_MCP_SERVERS[name]
        else:
            missing.append(name)

    if missing:
        import click
        click.echo(f"⚠️  Unknown MCP server(s): {', '.join(missing)}", err=True)
        click.echo(f"   Available built-in: {', '.join(sorted(BUILTIN_MCP_SERVERS.keys()))}", err=True)
        click.echo(f"   Custom configs: ~/.orch/mcp/{{name}}.json", err=True)

    if not servers:
        return None

    # Build the mcpServers wrapper format that Claude Code expects
    config = {"mcpServers": servers}

    # Write to file if workspace_path provided, otherwise return JSON string
    if workspace_path:
        config_file = workspace_path / "mcp-config.json"
        config_file.write_text(json.dumps(config, indent=2))
        return str(config_file)
    else:
        # Backward compatibility: return JSON string if no workspace path
        return json.dumps(config)


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
                - mcp_servers: Comma-separated MCP server names to include (e.g., "playwright,browser-use")
                - mcp_only: If True, add --strict-mcp-config to disable global MCP servers
                - workspace_path: Path to workspace directory for writing config files

        Returns:
            The command string to execute (without environment variable exports)
        """
        # Use existing hardcoded wrapper path and flags (extracted from spawn.py:1175)
        wrapper_path = "~/.orch/scripts/claude-code-wrapper.sh"
        skip_permissions = "--dangerously-skip-permissions"

        # Build command parts
        parts = [wrapper_path]

        # Use --agent flag if agent_name provided, otherwise fallback to --allowed-tools '*'
        if options and options.get('agent_name'):
            agent_name = options['agent_name']
            parts.append(f"--agent {agent_name}")
        else:
            parts.append("--allowed-tools '*'")

        parts.append(skip_permissions)

        # Build optional flags
        if options and options.get('model'):
            parts.append(f"--model {shlex.quote(options['model'])}")

        # Add MCP server configuration if specified
        # Write config to file in workspace directory to avoid shell escaping issues
        if options and options.get('mcp_servers'):
            workspace_path = options.get('workspace_path')
            mcp_config_path = resolve_mcp_servers(options['mcp_servers'], workspace_path)
            if mcp_config_path:
                # Pass file path to --mcp-config (or JSON string if no workspace_path)
                parts.append(f"--mcp-config {shlex.quote(mcp_config_path)}")

        # Add --strict-mcp-config to disable global MCP servers
        if options and options.get('mcp_only'):
            parts.append("--strict-mcp-config")

        # Add -- separator to signal end of options
        # This is critical for variadic options like --mcp-config <configs...>
        # which would otherwise consume the prompt as another config argument
        parts.append("--")

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
