"""CLI documentation sync checker.

Extracts command/option information from the Click CLI and compares
against a documented reference file to detect drift.
"""

import click
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


def extract_command_info(cmd: click.Command) -> Dict[str, Any]:
    """Extract metadata from a single Click command.

    Args:
        cmd: The Click command to introspect

    Returns:
        Dictionary with command metadata
    """
    # Get first line of help text
    help_text = ''
    if cmd.help:
        help_text = cmd.help.strip().split('\n')[0]

    cmd_info = {
        'help': help_text,
        'options': [],
        'arguments': [],
        'subcommands': []
    }

    for param in cmd.params:
        if isinstance(param, click.Option):
            # Get the longest option name (prefer --foo over -f)
            opt_name = max(param.opts, key=len) if param.opts else ''
            opt_help = ''
            if param.help:
                opt_help = param.help.strip().split('\n')[0]

            # Skip hidden options
            if getattr(param, 'hidden', False):
                continue

            cmd_info['options'].append({
                'name': opt_name,
                'help': opt_help,
                'required': param.required,
                'is_flag': param.is_flag
            })
        elif isinstance(param, click.Argument):
            cmd_info['arguments'].append({
                'name': param.name,
                'required': param.required
            })

    # If this is a group, note its subcommands
    if isinstance(cmd, click.Group) and cmd.commands:
        cmd_info['subcommands'] = sorted(cmd.commands.keys())

    return cmd_info


def extract_cli_reference(cli_group: click.Group, prefix: str = '') -> Dict[str, Any]:
    """Extract all commands and options from a Click CLI group.

    Args:
        cli_group: The Click group to introspect
        prefix: Command name prefix for nested groups

    Returns:
        Dictionary mapping command names to their metadata
    """
    reference = {}

    for name, cmd in cli_group.commands.items():
        full_name = f"{prefix} {name}".strip() if prefix else name
        reference[full_name] = extract_command_info(cmd)

        # Recurse into command groups
        if isinstance(cmd, click.Group) and cmd.commands:
            nested = extract_cli_reference(cmd, full_name)
            reference.update(nested)

    return reference


def format_reference_markdown(reference: Dict[str, Any]) -> str:
    """Format extracted reference as minimal markdown.

    Args:
        reference: Output from extract_cli_reference

    Returns:
        Markdown string
    """
    lines = [
        "# orch CLI Reference",
        "",
        "Auto-generated from CLI introspection. Do not edit manually.",
        "",
        "---",
        ""
    ]

    for cmd_name in sorted(reference.keys()):
        cmd_info = reference[cmd_name]

        lines.append(f"## `orch {cmd_name}`")
        lines.append(f"{cmd_info['help']}")
        lines.append("")

        # Subcommands (for command groups)
        subcommands = cmd_info.get('subcommands', [])
        if subcommands:
            lines.append("**Subcommands:**")
            for sub in subcommands:
                lines.append(f"- `{sub}`")
            lines.append("")

        # Arguments
        if cmd_info['arguments']:
            for arg in cmd_info['arguments']:
                req = '' if arg['required'] else ' (optional)'
                lines.append(f"**Argument:** `{arg['name']}`{req}")
            lines.append("")

        # Options (only if there are non-trivial ones)
        visible_opts = [o for o in cmd_info['options'] if o['help']]
        if visible_opts:
            lines.append("**Options:**")
            for opt in visible_opts:
                lines.append(f"- `{opt['name']}`: {opt['help']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


def format_reference_json(reference: Dict[str, Any]) -> str:
    """Format extracted reference as JSON for programmatic comparison.

    Args:
        reference: Output from extract_cli_reference

    Returns:
        JSON string
    """
    return json.dumps(reference, indent=2, sort_keys=True)


def load_documented_commands(reference_path: Path) -> Dict[str, Any]:
    """Load previously documented CLI reference.

    Args:
        reference_path: Path to the reference JSON file

    Returns:
        Dictionary of documented commands, or empty dict if not found
    """
    if not reference_path.exists():
        return {}

    try:
        with open(reference_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def check_doc_sync(
    cli_group: click.Group,
    reference_path: Path,
    verbose: bool = False
) -> tuple[bool, List[str]]:
    """Compare current CLI against documented reference.

    Args:
        cli_group: The Click group to introspect
        reference_path: Path to the reference JSON file
        verbose: If True, include detailed diff information

    Returns:
        Tuple of (is_in_sync, list of issues)
    """
    current = extract_cli_reference(cli_group)
    documented = load_documented_commands(reference_path)

    issues = []

    # Check for undocumented commands
    current_cmds = set(current.keys())
    documented_cmds = set(documented.keys())

    undocumented = current_cmds - documented_cmds
    removed = documented_cmds - current_cmds

    if undocumented:
        issues.append(f"Undocumented commands: {', '.join(sorted(undocumented))}")

    if removed:
        issues.append(f"Removed commands (still documented): {', '.join(sorted(removed))}")

    # Check for option changes in existing commands
    for cmd_name in current_cmds & documented_cmds:
        current_opts = {o['name'] for o in current[cmd_name]['options']}
        doc_opts = {o['name'] for o in documented.get(cmd_name, {}).get('options', [])}

        new_opts = current_opts - doc_opts
        removed_opts = doc_opts - current_opts

        if new_opts:
            issues.append(f"  {cmd_name}: new options {', '.join(sorted(new_opts))}")
        if removed_opts:
            issues.append(f"  {cmd_name}: removed options {', '.join(sorted(removed_opts))}")

    return len(issues) == 0, issues


def generate_reference_files(
    cli_group: click.Group,
    output_dir: Path,
    formats: List[str] = None
) -> List[Path]:
    """Generate reference files in specified formats.

    Args:
        cli_group: The Click group to introspect
        output_dir: Directory to write files to
        formats: List of formats ('json', 'markdown'). Defaults to both.

    Returns:
        List of paths to generated files
    """
    if formats is None:
        formats = ['json', 'markdown']

    reference = extract_cli_reference(cli_group)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    if 'json' in formats:
        json_path = output_dir / 'cli-reference.json'
        with open(json_path, 'w') as f:
            f.write(format_reference_json(reference))
        generated.append(json_path)

    if 'markdown' in formats:
        md_path = output_dir / 'cli-reference.md'
        with open(md_path, 'w') as f:
            f.write(format_reference_markdown(reference))
        generated.append(md_path)

    return generated
