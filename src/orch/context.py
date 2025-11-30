"""
Context monitoring for spawned agents.

Sends /context command to agents and parses token usage.
"""

import subprocess
import time
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ContextInfo:
    """Parsed context information from /context command."""
    tokens_used: int
    tokens_total: int
    percentage: float

    @property
    def is_high_usage(self) -> bool:
        """Check if context usage is above 85% threshold."""
        return self.percentage >= 85.0


def parse_context_output(text: str) -> Optional[ContextInfo]:
    """
    Parse /context command output to extract token usage.

    Expected format examples:
    - "Token usage: 45000/200000 (22.5%)"
    - "45000/200000"
    - "Token usage: 45000 / 200000"

    Args:
        text: Raw tmux pane output containing /context result

    Returns:
        ContextInfo if parsing succeeds, None otherwise
    """
    # Pattern: captures "45000/200000" or "45000 / 200000"
    # Also handles optional "Token usage:" prefix and "(22.5%)" suffix
    pattern = r'(\d+)\s*/\s*(\d+)'

    match = re.search(pattern, text)
    if not match:
        return None

    tokens_used = int(match.group(1))
    tokens_total = int(match.group(2))

    # Calculate percentage
    percentage = (tokens_used / tokens_total * 100) if tokens_total > 0 else 0.0

    return ContextInfo(
        tokens_used=tokens_used,
        tokens_total=tokens_total,
        percentage=percentage
    )


def get_context_info(agent: Dict[str, Any], timeout: float = 3.0) -> Optional[ContextInfo]:
    """
    Get context usage info for an agent by sending /context command.

    Uses stable window_id if available (doesn't change with tmux renumbering),
    falls back to window target for legacy agents without window_id.

    LIMITATION: The /context command only works when agents are idle (waiting
    at prompt). When agents are actively processing tools/responses, /context
    gets queued as user input or ignored. This means context checking is most
    useful for spot-checking idle/stuck agents, not routine monitoring of
    active agents.

    Args:
        agent: Agent dict from registry (must have 'window' or 'window_id' key)
        timeout: Seconds to wait for /context output (default: 3.0)

    Returns:
        ContextInfo if successful, None if failed (or agent is busy)
    """
    # Prefer stable window_id over window target (window indices change when tmux renumbers)
    window_target = agent.get('window_id', agent['window'])

    try:
        # Clear the pane first to get clean output
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_target, 'C-l'],
            check=True,
            stderr=subprocess.DEVNULL
        )

        # Wait briefly for clear to complete
        time.sleep(0.2)

        # Send /context command
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_target, '/context'],
            check=True,
            stderr=subprocess.DEVNULL
        )

        # Send Enter
        subprocess.run(
            ['tmux', 'send-keys', '-t', window_target, 'Enter'],
            check=True,
            stderr=subprocess.DEVNULL
        )

        # Wait for output to appear
        time.sleep(timeout)

        # Capture pane output
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', window_target, '-p'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse the output
        return parse_context_output(result.stdout)

    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None
