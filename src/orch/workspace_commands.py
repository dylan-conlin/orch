"""Workspace commands for orch CLI.

Commands for workspace management and project initialization.
"""

import click


def register_workspace_commands(cli):
    """Register workspace-related commands with the CLI."""

    @cli.command()
    @click.option('--path', type=click.Path(), help='Project directory (default: current directory)')
    @click.option('--name', 'project_name', help='Project name (default: directory name)')
    @click.option('--purpose', 'project_purpose', help='Project purpose (one-line description)')
    @click.option('--team', is_flag=True, help='Team project (commit CLAUDE.md, ignore state)')
    @click.option('--yes', '-y', is_flag=True, help='Skip confirmations')
    @click.option('--profile', type=click.Choice(['core', 'full', 'minimal']), default='full',
                  help='Instruction profile: core (recommended 7 templates), full (all), minimal (2)')
    def init(path, project_name, project_purpose, team, yes, profile):
        """
        Initialize project-scoped orchestration.

        Creates .orch/ directory structure with templates for high-level
        orchestration context, worker implementation context, and coordination journal.

        \b
        Instruction profiles:
          core    - Essential 7 templates (recommended for most projects)
          full    - All templates (default, backwards compatible)
          minimal - Just 2 identity templates (add more with orch add-instruction)

        \b
        Examples:
          orch init                                    # Initialize in current directory
          orch init --profile core                     # Use recommended core templates
          orch init --path ~/projects/my-app          # Initialize in specific directory
          orch init --name "My App" --purpose "..."   # Non-interactive
          orch init --team                            # Team project (commit .orch/CLAUDE.md)
        """
        from orch.init import init_project_orchestration

        success = init_project_orchestration(
            project_path=path,
            project_name=project_name,
            project_purpose=project_purpose,
            team=team,
            yes=yes,
            profile=profile
        )

        if not success:
            raise click.Abort()
