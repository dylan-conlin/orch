#!/usr/bin/env python3
"""
Workspace Migration Script

Migrates workspace files to current template format by adding missing fields:
- Template-Version: v2
- Session Scope: Small/Medium/Large (default: Medium)
- Checkpoint Strategy
- Planned Checkpoint Points

Usage:
    python -m tools.orch.migrate_workspaces --dry-run  # Preview changes
    python -m tools.orch.migrate_workspaces            # Execute migration
    python -m tools.orch.migrate_workspaces --project /path/to/project

Features:
- Backup .orch/workspace/ before migration
- Dry-run mode for safe preview
- Skip Status: Active workspaces
- Validate migrated files
"""

import argparse
import shutil
from pathlib import Path
from datetime import datetime
import sys


def backup_workspaces(workspace_dir: Path) -> Path:
    """Create timestamped backup of workspace directory."""
    backup_name = f"workspace_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir = workspace_dir.parent / backup_name

    print(f"Creating backup: {backup_dir}")
    shutil.copytree(workspace_dir, backup_dir)
    print(f"✓ Backup created")

    return backup_dir


def should_skip_workspace(workspace_file: Path) -> tuple[bool, str]:
    """Determine if workspace should be skipped from migration.

    Returns: (should_skip, reason)
    """
    try:
        content = workspace_file.read_text()

        # Skip if Status: Active
        if 'Status:** Active' in content or 'Status:** [Active]' in content:
            return True, "Status: Active"

        # Skip if already has Template-Version: v2
        if 'Template-Version:** v2' in content:
            return True, "Already v2"

        # Skip if already has Session Scope section
        if '## Session Scope & Checkpoint Plan' in content:
            return True, "Already has Session Scope"

        return False, ""
    except Exception as e:
        return True, f"Read error: {e}"


def determine_scope(workspace_file: Path, content: str) -> str:
    """Determine appropriate Session Scope based on workspace characteristics.

    Heuristics:
    - Look for "Estimated-effort" in comments
    - Check number of tasks
    - Default to Medium if uncertain
    """
    # Try to extract estimated effort from content
    if 'Est: ' in content or 'estimated' in content.lower():
        # Look for hour estimates
        if '1h' in content or '2h' in content or '30 min' in content:
            return 'Small'
        elif '6h' in content or '8h' in content or 'day' in content.lower():
            return 'Large'

    # Count tasks (- [ ] or - [x] patterns)
    task_count = content.count('- [ ]') + content.count('- [x]')
    if task_count <= 3:
        return 'Small'
    elif task_count >= 8:
        return 'Large'

    # Default to Medium
    return 'Medium'


def get_estimated_duration(scope: str) -> str:
    """Get estimated duration based on scope."""
    duration_map = {
        'Small': '1-2h',
        'Medium': '2-4h',
        'Large': '4-6h+'
    }
    return duration_map.get(scope, '2-4h')


def get_checkpoint_strategy(scope: str) -> list[str]:
    """Get checkpoint strategy based on scope."""
    strategies = {
        'Small': ['- Single session, no planned checkpoints'],
        'Medium': ['- Checkpoint after Phase 1 if >3h elapsed'],
        'Large': ['- Checkpoint every 2-3 completed tasks OR every 3-4 hours']
    }
    return strategies.get(scope, strategies['Medium'])


def migrate_workspace(workspace_file: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Migrate a single workspace file.

    Returns: (success, message)
    """
    try:
        content = workspace_file.read_text()
        original_content = content

        # Determine scope
        scope = determine_scope(workspace_file, content)
        duration = get_estimated_duration(scope)
        checkpoint_strategy_lines = get_checkpoint_strategy(scope)

        # Find where to insert Template-Version field
        # Look for the metadata section after "# Workspace:"
        lines = content.split('\n')
        inserted_template_version = False
        inserted_session_scope = False

        new_lines = []
        i = 0
        in_yaml_frontmatter = False
        frontmatter_start_line = -1
        while i < len(lines):
            line = lines[i]

            # Detect YAML frontmatter (can start at line 0 or after a header)
            if line.strip() == '---' and not in_yaml_frontmatter:
                # Check if this looks like frontmatter start (not a section separator)
                # Frontmatter has key:value pairs between --- markers
                if i + 1 < len(lines) and ':' in lines[i + 1]:
                    in_yaml_frontmatter = True
                    frontmatter_start_line = i
            elif in_yaml_frontmatter and line.strip() == '---':
                # End of YAML frontmatter
                new_lines.append(line)
                in_yaml_frontmatter = False
                # Add Template-Version after YAML frontmatter if not present
                if not inserted_template_version:
                    new_lines.append('')
                    new_lines.append('**Template-Version:** v2')
                    inserted_template_version = True
                i += 1
                continue

            # Add Template-Version after Type field if not present (markdown format)
            if not inserted_template_version and line.startswith('**Type:**'):
                new_lines.append(line)
                # Check if next line is already Template-Version
                if i + 1 < len(lines) and 'Template-Version' in lines[i + 1]:
                    inserted_template_version = True
                else:
                    new_lines.append('**Template-Version:** v2')
                    inserted_template_version = True
                i += 1
                continue

            # Insert Session Scope section after Summary section
            if not inserted_session_scope and ('## Summary (Top 3)' in line or line.startswith('## Summary')):
                # Read until we find the next ## header or ---
                j = i + 1
                while j < len(lines) and not lines[j].startswith('##') and not (lines[j].strip() == '---' and j > i + 5):
                    new_lines.append(lines[i])
                    i += 1
                    j = i + 1

                # Add current line (the --- or next section)
                new_lines.append(lines[i])

                # Insert Session Scope section
                new_lines.append('')
                new_lines.append('## Session Scope & Checkpoint Plan')
                new_lines.append('')
                new_lines.append(f'**Scope:** {scope}')
                new_lines.append(f'**Estimated Duration:** {duration}')
                new_lines.append(f'**Session Started:** {datetime.now().isoformat()}')
                new_lines.append(f'**Last Activity:** {datetime.now().isoformat()}')
                new_lines.append('')
                new_lines.append('**Checkpoint Strategy:**')
                for strategy_line in checkpoint_strategy_lines:
                    new_lines.append(strategy_line)
                new_lines.append('')
                new_lines.append('**Planned Checkpoint Points:**')
                new_lines.append('- [ ] [Determined at runtime based on progress]')
                new_lines.append('')
                new_lines.append('---')

                inserted_session_scope = True
                i += 1
                continue

            new_lines.append(line)
            i += 1

        new_content = '\n'.join(new_lines)

        # Validate that we actually made changes
        if new_content == original_content:
            return False, "No changes needed"

        # Write if not dry-run
        if not dry_run:
            workspace_file.write_text(new_content)
            return True, f"Migrated (Scope: {scope})"
        else:
            return True, f"Would migrate (Scope: {scope})"

    except Exception as e:
        return False, f"Error: {e}"


def validate_migration(workspace_file: Path) -> tuple[bool, str]:
    """Validate that migration was successful.

    Returns: (valid, message)
    """
    try:
        content = workspace_file.read_text()

        # Check for required fields
        required = [
            'Template-Version:** v2',
            '## Session Scope & Checkpoint Plan',
            '**Scope:**',
            '**Checkpoint Strategy:**'
        ]

        missing = [req for req in required if req not in content]

        if missing:
            return False, f"Missing: {', '.join(missing)}"

        return True, "Valid"
    except Exception as e:
        return False, f"Validation error: {e}"


def main():
    parser = argparse.ArgumentParser(description='Migrate workspace files to v2 template')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    parser.add_argument('--project', type=str, help='Project root path (default: find .orch in tree)')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup (not recommended)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed progress')

    args = parser.parse_args()

    # Find project root
    if args.project:
        project_root = Path(args.project)
    else:
        # Walk up from cwd to find .orch
        current = Path.cwd()
        while current != current.parent:
            if (current / '.orch').is_dir():
                project_root = current
                break
            current = current.parent
        else:
            print("❌ Could not find .orch directory")
            print("   Run from within project or use --project flag")
            sys.exit(1)

    workspace_dir = project_root / '.orch' / 'workspace'

    if not workspace_dir.exists():
        print(f"❌ Workspace directory not found: {workspace_dir}")
        sys.exit(1)

    print(f"Project: {project_root}")
    print(f"Workspace directory: {workspace_dir}")
    print()

    # Find all workspace files
    workspace_files = list(workspace_dir.glob('*/WORKSPACE.md'))

    if not workspace_files:
        print("No workspace files found")
        sys.exit(0)

    print(f"Found {len(workspace_files)} workspaces")
    print()

    # Create backup unless disabled
    if not args.dry_run and not args.no_backup:
        backup_dir = backup_workspaces(workspace_dir)
        print()

    # Process workspaces
    skipped = []
    migrated = []
    failed = []

    for workspace_file in workspace_files:
        workspace_name = workspace_file.parent.name

        # Check if should skip
        should_skip, skip_reason = should_skip_workspace(workspace_file)
        if should_skip:
            skipped.append((workspace_name, skip_reason))
            if args.verbose:
                print(f"⊘ Skip: {workspace_name} ({skip_reason})")
            continue

        # Migrate
        success, message = migrate_workspace(workspace_file, dry_run=args.dry_run)

        if success:
            migrated.append((workspace_name, message))
            if args.verbose:
                print(f"✓ Migrate: {workspace_name} ({message})")
        elif message == "No changes needed":
            # Treat "no changes needed" as skip, not failure
            skipped.append((workspace_name, message))
            if args.verbose:
                print(f"⊘ Skip: {workspace_name} ({message})")
        else:
            failed.append((workspace_name, message))
            if args.verbose:
                print(f"✗ Failed: {workspace_name} ({message})")

    # Validate migrated workspaces (if not dry-run)
    if not args.dry_run and migrated:
        print()
        print("Validating migrations...")
        validation_failed = []

        for workspace_name, _ in migrated:
            workspace_file = workspace_dir / workspace_name / 'WORKSPACE.md'
            valid, message = validate_migration(workspace_file)
            if not valid:
                validation_failed.append((workspace_name, message))

        if validation_failed:
            print()
            print("⚠️  Validation failures:")
            for workspace_name, message in validation_failed:
                print(f"  {workspace_name}: {message}")

    # Summary
    print()
    print("=" * 60)
    print("Migration summary:")
    print(f"  ✓ {len(migrated)} migrated")
    print(f"  ⊘ {len(skipped)} skipped")
    print(f"  ✗ {len(failed)} failed")
    print()

    if args.dry_run:
        print("DRY RUN - No files were modified")
        print("Run without --dry-run to execute migration")
        print()

    if migrated and not args.dry_run:
        print("✅ Migration complete")
        if not args.no_backup:
            print(f"   Backup: {backup_dir}")
        print()

    # Show details
    if skipped:
        print()
        print("Skipped workspaces:")
        for workspace_name, reason in skipped[:10]:
            print(f"  {workspace_name}: {reason}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")

    if failed:
        print()
        print("Failed migrations:")
        for workspace_name, message in failed:
            print(f"  {workspace_name}: {message}")


if __name__ == '__main__':
    main()
