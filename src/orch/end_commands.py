"""End command for orch CLI - clean session exit with knowledge capture gates.

This implements `orch end` which:
1. Detects if running in tmux
2. Checks for knowledge entries (kn) since session start
3. Prompts if no knowledge was captured (soft gate)
4. Sends /exit to trigger proper SessionEnd hooks
"""

import click


def register_end_commands(cli):
    """Register end commands with the CLI."""

    @cli.command()
    @click.option(
        '-y', '--yes',
        is_flag=True,
        help='Skip confirmation prompt (auto-confirm exit)',
    )
    def end(yes: bool):
        """End session cleanly with knowledge capture check.

        Checks for knowledge entries (kn) captured during this session.
        If none found, prompts to confirm exit (soft gate).
        After running, use /exit to close the session.

        \b
        Examples:
            orch end          # Check knowledge, prompt if none
            orch end -y       # Skip prompt
        """
        from orch.end import end_session

        end_session(skip_prompt=yes)
