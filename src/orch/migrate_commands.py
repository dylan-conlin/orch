"""
CLI commands for migration operations.
"""
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from orch.migrate_frontmatter import (
    migrate_project,
    find_files_to_migrate,
    FileType,
    detect_file_type,
)
from orch.path_utils import find_orch_root


def register_migrate_commands(cli):
    """Register migrate commands with the CLI."""

    @cli.group()
    def migrate():
        """Migration utilities for orchestration artifacts.

        \b
        Subcommands:
          frontmatter  - Convert inline metadata to YAML frontmatter
        """
        pass

    @migrate.command('frontmatter')
    @click.option('--dry-run', is_flag=True, default=False,
                  help='Preview changes without writing files')
    @click.option('--project', '-p', type=click.Path(exists=True),
                  help='Project directory (default: current directory)')
    @click.option('--verbose', '-v', is_flag=True, default=False,
                  help='Show detailed output for each file')
    def frontmatter(dry_run: bool, project: str, verbose: bool):
        """Convert inline metadata to YAML frontmatter.

        \b
        Migrates orchestration files (workspaces, investigations, decisions)
        from inline **Field:** format to YAML frontmatter.

        \b
        Examples:
          orch migrate frontmatter --dry-run     # Preview changes
          orch migrate frontmatter               # Execute migration
          orch migrate frontmatter -p /path/to/project
        """
        console = Console()

        # Determine project directory
        if project:
            project_dir = Path(project)
        else:
            project_dir = find_orch_root(Path.cwd())
            if not project_dir:
                console.print("[red]Error:[/red] No .orch directory found")
                console.print("Run from a project with .orch/ or specify --project")
                raise SystemExit(1)

        # Find files
        files = find_files_to_migrate(project_dir)

        if not files:
            console.print(f"[yellow]No files to migrate in {project_dir}[/yellow]")
            return

        console.print(f"[bold]Found {len(files)} files to check[/bold]")

        if dry_run:
            console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
            console.print()

        # Run migration
        results = migrate_project(project_dir, dry_run=dry_run)

        # Build summary
        migrated = [r for r in results if r.success and not r.skipped]
        skipped = [r for r in results if r.skipped]
        failed = [r for r in results if not r.success]

        # Show detailed output if verbose
        if verbose:
            table = Table(title="Migration Results")
            table.add_column("File", style="cyan")
            table.add_column("Type", style="blue")
            table.add_column("Status", style="green")
            table.add_column("Details")

            for result in results:
                rel_path = result.path.relative_to(project_dir) if project_dir in result.path.parents else result.path.name
                file_type = detect_file_type(result.path)

                if result.skipped:
                    status = "[yellow]Skipped[/yellow]"
                    details = result.skip_reason or ""
                elif result.success:
                    status = "[green]Migrated[/green]" if not dry_run else "[blue]Would migrate[/blue]"
                    details = ""
                else:
                    status = "[red]Failed[/red]"
                    details = result.error or ""

                table.add_row(str(rel_path), file_type.value, status, details)

            console.print(table)
            console.print()

        # Summary
        console.print(f"[bold]Summary:[/bold]")
        action_word = "Would migrate" if dry_run else "Migrated"
        console.print(f"  {action_word}: [green]{len(migrated)}[/green] files")
        console.print(f"  Skipped: [yellow]{len(skipped)}[/yellow] files (already migrated or no metadata)")
        if failed:
            console.print(f"  Failed: [red]{len(failed)}[/red] files")
            for r in failed:
                console.print(f"    - {r.path}: {r.error}")

        if dry_run and migrated:
            console.print()
            console.print("[dim]Run without --dry-run to apply changes[/dim]")
