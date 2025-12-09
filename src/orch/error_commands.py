"""Error reporting commands for orch CLI.

Provides the `orch errors` command for viewing error statistics and history.
"""

import json
import click
from datetime import datetime
from typing import Optional

from orch.error_logging import (
    ErrorLogger,
    ErrorType,
    get_error_stats,
    get_recent_errors,
)


def register_error_commands(cli):
    """Register error commands with the CLI."""

    @cli.command()
    @click.option(
        '--days',
        default=7,
        type=int,
        help='Number of days to include in stats (default: 7)',
    )
    @click.option(
        '--type',
        'error_type',
        default=None,
        help='Filter by error type (e.g., AGENT_NOT_FOUND)',
    )
    @click.option(
        '--json',
        'output_json',
        is_flag=True,
        help='Output as JSON for programmatic access',
    )
    @click.option(
        '--limit',
        default=10,
        type=int,
        help='Number of recent errors to show (default: 10)',
    )
    def errors(days: int, error_type: Optional[str], output_json: bool, limit: int):
        """Show error statistics and recent errors.

        Displays aggregated error statistics and recent error history
        from ~/.orch/errors.jsonl.

        \b
        Examples:
            orch errors                    # Show last 7 days summary
            orch errors --days 30          # Show last 30 days
            orch errors --type AGENT_NOT_FOUND  # Filter by type
            orch errors --json             # Output as JSON
        """
        logger = ErrorLogger()
        stats = logger.get_error_stats(days=days)
        recent = logger.get_recent_errors(limit=limit)

        # Filter by type if specified
        if error_type:
            recent = [e for e in recent if e.get('error_type') == error_type]
            # Recalculate stats for filtered type
            if error_type in stats['by_type']:
                filtered_count = stats['by_type'].get(error_type, 0)
                stats = {
                    'total': filtered_count,
                    'by_type': {error_type: filtered_count},
                    'by_command': {},  # Would need to recalculate from filtered
                }
            else:
                stats = {'total': 0, 'by_type': {}, 'by_command': {}}

        if output_json:
            _output_json(stats, recent, days)
        else:
            _output_human(stats, recent, days, error_type)


def _output_json(stats: dict, recent: list, days: int) -> None:
    """Output stats and recent errors as JSON."""
    output = {
        'stats': stats,
        'recent_errors': recent,
        'days': days,
    }
    click.echo(json.dumps(output, indent=2))


def _output_human(
    stats: dict, recent: list, days: int, error_type: Optional[str]
) -> None:
    """Output stats and recent errors in human-readable format."""
    total = stats['total']

    if total == 0:
        if error_type:
            click.echo(f"No errors of type '{error_type}' in the last {days} days.")
        else:
            click.echo(f"No errors in the last {days} days. 🎉")
        return

    # Header
    click.echo(f"Error summary (last {days} days):")
    click.echo()

    # By type
    by_type = stats.get('by_type', {})
    if by_type:
        click.echo("By type:")
        # Sort by count descending
        sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        for error_type_name, count in sorted_types:
            pct = (count / total * 100) if total > 0 else 0
            # Pad type name for alignment
            click.echo(f"  {error_type_name:25} {count:4} ({pct:.0f}%)")
        click.echo()

    # By command
    by_command = stats.get('by_command', {})
    if by_command:
        click.echo("By command:")
        # Sort by count descending
        sorted_commands = sorted(by_command.items(), key=lambda x: x[1], reverse=True)
        # Find hotspot (highest count)
        hotspot = sorted_commands[0][0] if sorted_commands else None
        for cmd, count in sorted_commands:
            pct = (count / total * 100) if total > 0 else 0
            marker = " ← hotspot" if cmd == hotspot and count > 1 else ""
            click.echo(f"  orch {cmd:20} {count:4} ({pct:.0f}%){marker}")
        click.echo()

    # Recent errors
    if recent:
        click.echo("Recent errors:")
        for error in recent:
            ts_str = error.get('timestamp', '')
            # Parse and format timestamp
            try:
                ts = datetime.fromisoformat(ts_str.rstrip('Z'))
                ts_formatted = ts.strftime('%Y-%m-%d %H:%M')
            except (ValueError, AttributeError):
                ts_formatted = ts_str[:16] if ts_str else 'unknown'

            subcommand = error.get('subcommand', 'unknown')
            error_type_val = error.get('error_type', 'UNKNOWN')
            message = error.get('message', '')
            # Truncate message if too long
            if len(message) > 50:
                message = message[:47] + '...'

            click.echo(f"  {ts_formatted}  {subcommand:10}  {error_type_val:20}  {message}")
