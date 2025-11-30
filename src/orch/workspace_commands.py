"""Workspace commands for orch CLI.

Commands for workspace management, artifact search, and project initialization.
"""

import click
import json
import subprocess
from pathlib import Path


def register_workspace_commands(cli):
    """Register workspace-related commands with the CLI."""

    @cli.command()
    @click.argument('query', required=False)
    @click.option('--type', 'artifact_type', type=click.Choice(['all', 'investigations', 'decisions', 'knowledge', 'workspace']), default='all', help='Filter by artifact type')
    @click.option('--project', help='Filter to specific project name')
    @click.option('--global', 'global_search', is_flag=True, help='Search across all projects (default: current project only)')
    @click.option('-i', '--interactive', is_flag=True, help='Interactive fuzzy search with preview')
    @click.option('--rebuild-cache', is_flag=True, help='Force rebuild of reference count cache')
    @click.option('--no-refs', is_flag=True, help='Hide reference counts (faster)')
    @click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help='Output format (text or json)')
    def search(query, artifact_type, project, global_search, interactive, rebuild_cache, no_refs, output_format):
        """
        Search across project .orch/ artifacts with reference tracking.

        Defaults to searching the current project only. Use --global to search
        across all projects. Shows reference counts to measure artifact value.

        \b
        Examples:
          orch search "authentication"              # Search current project
          orch search "JWT" --type decisions        # Search only decisions in current project
          orch search "caching" --global            # Search all projects
          orch search "cache" --project scs-api     # Search specific project
          orch search -i                            # Interactive fuzzy search (current project)
          orch search -i --global                   # Interactive search (all projects)
          orch search "auth" --rebuild-cache        # Rebuild reference counts first
          orch search "auth" --no-refs              # Skip reference counts (faster)
          orch search "auth" --format json          # Output as JSON with metadata
        """
        # Interactive mode falls back to bash script (for now)
        if interactive:
            script_path = Path.home() / ".orch" / "scripts" / "search.sh"

            if not script_path.exists():
                click.echo(f"❌ Search script not found: {script_path}", err=True)
                click.echo("   Expected at: ~/.orch/scripts/search.sh", err=True)
                raise click.Abort()

            cmd = [str(script_path), '-i']
            if global_search:
                cmd.append('--global')

            try:
                subprocess.run(cmd, check=True, capture_output=False, text=True)
            except subprocess.CalledProcessError as e:
                if e.returncode != 1:  # Exit 1 = no matches, which is normal
                    click.echo(f"❌ Search failed with exit code {e.returncode}", err=True)
                    raise click.Abort()
            except Exception as e:
                click.echo(f"❌ Unexpected error: {e}", err=True)
                raise click.Abort()
            return

        # Regular search mode with reference tracking
        if not query:
            click.echo("❌ Query required (or use -i for interactive mode)", err=True)
            raise click.Abort()

        from orch.artifact_search import ArtifactSearcher, format_time_ago

        searcher = ArtifactSearcher()

        try:
            # Show search info
            if global_search:
                click.echo(click.style("Global search across all projects", dim=True))
            else:
                project_dir = searcher._detect_project_dir()
                if project_dir:
                    click.echo(click.style(f"Searching in project: {project_dir.name}", dim=True))
                    click.echo(click.style("(Use --global to search all projects)", dim=True))
                else:
                    click.echo(click.style("No project detected, searching globally", dim=True))

            if no_refs:
                click.echo(click.style("Reference tracking disabled", dim=True))

            click.echo(click.style(f'Searching for: "{query}"', bold=True))
            if project:
                click.echo(click.style(f"Project filter: {project}", dim=True))
            click.echo(click.style(f"Type: {artifact_type}", dim=True))
            click.echo()

            # Perform search
            results = searcher.search(
                query=query,
                artifact_type=artifact_type,
                project=project,
                global_search=global_search,
                rebuild_cache=rebuild_cache
            )

            if not results:
                if output_format == 'json':
                    click.echo(json.dumps([], indent=2))
                else:
                    click.echo("No matches found.")
                return

            # JSON output format
            if output_format == 'json':
                json_results = []
                home = Path.home()

                for result in results:
                    # Format file path (relative to home)
                    file_path = Path(result.file_path)
                    try:
                        relative_path = file_path.relative_to(home)
                        display_path = f"~/{relative_path}"
                    except ValueError:
                        display_path = str(file_path)

                    # Build JSON object
                    json_obj = {
                        "file_path": display_path,
                        "absolute_path": str(file_path),
                        "matches": [
                            {"line_number": line_num, "content": line_content}
                            for line_num, line_content in result.matches
                        ],
                        "metadata": result.metadata or {}
                    }

                    # Add reference info if available and not disabled
                    if not no_refs and result.reference_info:
                        ref_info = result.reference_info
                        json_obj["reference_info"] = {
                            "reference_count": ref_info.reference_count,
                            "last_referenced": ref_info.last_referenced,
                            "last_referenced_ago": format_time_ago(ref_info.last_referenced),
                            "referenced_by": ref_info.referenced_by
                        }

                    json_results.append(json_obj)

                click.echo(json.dumps(json_results, indent=2))
                return

            # Text output format (existing code)
            home = Path.home()
            for result in results:
                # Format file path (relative to home)
                file_path = Path(result.file_path)
                try:
                    relative_path = file_path.relative_to(home)
                    display_path = f"~/{relative_path}"
                except ValueError:
                    display_path = str(file_path)

                # Add reference info if available and not disabled
                ref_suffix = ""
                if not no_refs and result.reference_info:
                    ref_info = result.reference_info
                    ref_count = ref_info.reference_count
                    last_ref = format_time_ago(ref_info.last_referenced)
                    ref_suffix = click.style(f" (refs: {ref_count}, last: {last_ref})", fg="cyan")

                # Print file path with reference info
                click.echo(click.style(display_path, fg="green", bold=True) + ref_suffix)

                # Print matching lines with context
                for line_num, line_content in result.matches:
                    click.echo(f"  {line_content}")

                click.echo()

        except Exception as e:
            click.echo(f"❌ Search error: {e}", err=True)
            import traceback
            traceback.print_exc()
            raise click.Abort()

    @cli.command('create-investigation')
    @click.argument('slug')
    @click.option('--type', 'investigation_type', default='simple',
                  type=click.Choice(['simple', 'audits']),
                  help='Investigation type: simple (default) or audits (comprehensive reviews)')
    @click.option('--project', type=click.Path(exists=True),
                  help='Project directory (default: auto-detect from CLAUDE_PROJECT or pwd)')
    def create_investigation_cmd(slug, investigation_type, project):
        """
        Create investigation file from template.

        Uses the simple template by default - minimal structure focused on
        testing hypotheses rather than producing elaborate artifacts.

        For comprehensive multi-hour reviews (security, architecture, test
        quality), use --type audits.

        \b
        Examples:
          orch create-investigation auth-flow
          orch create-investigation auth-flow --type audits  # comprehensive review
          orch create-investigation proxy-timeout --project /path/to/project
        """
        from orch.investigations import create_investigation, validate_investigation, InvestigationError

        try:
            # Create investigation
            result = create_investigation(
                slug=slug,
                investigation_type=investigation_type,
                project_dir=Path(project) if project else None
            )

            # Validate template structure
            validate_investigation(Path(result['file_path']), investigation_type)

            # Display success
            click.echo()
            click.echo(f"✅ Investigation created: {result['file_path']}")
            click.echo(f"   Type: {result['investigation_type']}")
            click.echo()

            if investigation_type == 'simple':
                click.echo("Next steps:")
                click.echo("• Fill in what you're trying to figure out")
                click.echo("• Document what you try and observe")
                click.echo("• TEST your hypothesis before concluding")
                click.echo()
            else:
                click.echo("Next steps (legacy template):")
                click.echo("• Fill Question field with specific investigation question")
                click.echo("• Document findings progressively (don't wait until end)")
                click.echo("• Update Confidence and Resolution-Status as you make progress")
                click.echo()

        except InvestigationError as e:
            click.echo(f"❌ Investigation creation failed:", err=True)
            click.echo(f"   {e}", err=True)
            raise click.Abort()

    @cli.command('create-decision')
    @click.argument('slug')
    @click.option('--project', type=click.Path(exists=True),
                  help='Project directory (default: auto-detect from CLAUDE_PROJECT or pwd)')
    def create_decision_cmd(slug, project):
        """
        Create decision record file from template.

        Creates a new decision record in .orch/decisions/ using the standard
        DECISION.md template from ~/.orch/templates/.

        \b
        Examples:
          orch create-decision api-versioning-strategy
          orch create-decision skill-consolidation --project /path/to/project
        """
        from orch.decisions import create_decision, DecisionError

        try:
            # Create decision
            result = create_decision(
                slug=slug,
                project_dir=Path(project) if project else None
            )

            # Display success
            click.echo()
            click.echo(f"✅ Decision record created: {result['file_path']}")
            click.echo()
            click.echo("Next steps:")
            click.echo("• Fill in the Problem section")
            click.echo("• Document Options Considered with trade-offs")
            click.echo("• Add Rationale explaining why this decision was made")
            click.echo()

        except DecisionError as e:
            click.echo(f"❌ Decision creation failed:", err=True)
            click.echo(f"   {e}", err=True)
            raise click.Abort()

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
