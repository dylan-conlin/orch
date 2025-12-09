"""Spawn commands for orch CLI.

Commands for spawning new worker agents.
"""

import click
import os
from pathlib import Path

from orch.registry import AgentRegistry
from orch.logging import OrchLogger
from orch.beads_integration import (
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)
from orch.git_utils import find_commits_mentioning_issue


def register_spawn_commands(cli):
    """Register spawn-related commands with the CLI."""

    @cli.command(hidden=True)
    @click.option('--agent-id', required=True, help='Unique agent identifier')
    @click.option('--window', required=True, help='Tmux window target (session:index)')
    @click.option('--task', required=True, help='Task description')
    @click.option('--project-dir', required=True, help='Project directory path')
    @click.option('--workspace', required=True, help='Workspace relative path')
    def register(agent_id, window, task, project_dir, workspace):
        """Register a new agent in the registry (internal command)."""

        # Initialize logger
        orch_logger = OrchLogger()

        registry = AgentRegistry()

        try:
            agent = registry.register(
                agent_id=agent_id,
                task=task,
                window=window,
                project_dir=project_dir,
                workspace=workspace
            )

            # Log successful registration
            orch_logger.log_event("register", f"Agent registered: {agent_id}", {
                "agent_id": agent_id,
                "window": window,
                "project_dir": project_dir,
                "workspace": workspace,
                "task": task
            }, level="INFO")

            click.echo(f"✅ Registered agent: {agent_id}")
            click.echo(f"   Window: {window}")
            click.echo(f"   Task: {task}")
        except ValueError as e:
            # Log registration failure
            orch_logger.log_error("register", f"Registration failed: {agent_id}", {
                "agent_id": agent_id,
                "reason": str(e)
            })

            click.echo(f"❌ Registration failed: {e}", err=True)
            raise click.Abort()

    @cli.command()
    @click.argument('context_or_skill', required=False)
    @click.argument('task', required=False)
    @click.option('--from-roadmap', 'roadmap_title', help='Spawn from ROADMAP item')
    @click.option('--project', help='Project name')
    @click.option('--name', 'workspace_name', help='Override workspace name')
    @click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
    @click.option('-i', '--interactive', is_flag=True, help='Interactive mode for human exploration')
    @click.option('--resume', is_flag=True, help='Resume existing workspace instead of failing')
    @click.option('--prompt-file', type=click.Path(exists=True), help='Read full prompt from file')
    @click.option('--from-stdin', is_flag=True, help='Read full prompt from stdin')
    @click.option('--phases', help='Phases for feature-impl (e.g., "investigation,design,implementation,validation")')
    @click.option('--mode', type=click.Choice(['tdd', 'direct']), help='Implementation mode for feature-impl')
    @click.option('--validation', type=click.Choice(['none', 'tests', 'smoke-test', 'multi-phase']), help='Validation level for feature-impl')
    @click.option('--phase-id', help='Phase identifier for multi-phase work (e.g., "phase-a")')
    @click.option('--depends-on', help='Phase dependency (requires --phase-id)')
    @click.option('--type', 'investigation_type', type=click.Choice(['simple', 'systems', 'feasibility', 'audits', 'performance', 'agent-failures']), default='simple', help='Investigation type (default: simple)')
    @click.option('--backend', type=click.Choice(['claude', 'codex', 'opencode']), help='AI backend to use (default: claude)')
    @click.option('--model', help='Model to use (e.g., "sonnet", "opus", or full model name like "claude-sonnet-4-5-20250929")')
    @click.option('--issue', 'issue_id', help='Spawn from beads issue by ID (e.g., orch-cli-ltv)')
    @click.option('--stash', is_flag=True, help='Stash uncommitted changes before spawn (auto-unstash on complete)')
    @click.option('--allow-dirty/--require-clean', default=True, help='Allow spawn with uncommitted changes (default: allow)')
    @click.option('--skip-artifact-check', is_flag=True, help='Skip pre-spawn artifact search hint')
    @click.option('--context-ref', help='Path to context file (design doc, investigation) to include in spawn prompt')
    @click.option('--parallel', is_flag=True, help='Use parallel execution mode (codebase-audit: spawn 5 dimension agents + synthesis)')
    @click.option('--agent-mail', is_flag=True, help='Include Agent Mail coordination in spawn prompt (auto-included for Medium/Large scope)')
    @click.option('--force', is_flag=True, help='Force spawn even for closed issues')
    def spawn(context_or_skill, task, roadmap_title, project, workspace_name, yes, interactive, resume, prompt_file, from_stdin, phases, mode, validation, phase_id, depends_on, investigation_type, backend, model, issue_id, stash, allow_dirty, skip_artifact_check, context_ref, parallel, agent_mail, force):
        """
        Spawn a new worker agent or interactive session.

        \b
        Four modes:
        1. ROADMAP mode:       orch spawn --from-roadmap "Item Title"
                               orch spawn SKILL_NAME --from-roadmap "Item Title"  (with skill override)
        2. Skill mode:         orch spawn SKILL_NAME "task description" [--project NAME]
        3. Interactive skill:  orch spawn SKILL_NAME "task" -i [--project NAME]
        4. Interactive:        orch spawn -i "starting context" --project NAME

        \b
        Interactive skill mode (mode 3):
        Combines skill guidance with collaborative design. Agent uses brainstorming-style
        conversation with Dylan in the tmux window. Example: orch spawn architect "design auth" -i

        \b
        ROADMAP + Skill:
        When using --from-roadmap with a skill name, the skill overrides the ROADMAP :Skill: property.
        This allows using feature-impl or other skills with ROADMAP metadata (project, workspace, etc.).
        """
        from orch.spawn import spawn_from_roadmap, spawn_with_skill, spawn_interactive, validate_feature_impl_config
        import sys

        # Context enforcement: Prevent workers from spawning other workers
        claude_context = os.environ.get('CLAUDE_CONTEXT')
        if claude_context == 'worker':
            workspace_name = os.environ.get('CLAUDE_WORKSPACE', 'unknown')
            click.echo("❌ Cannot spawn from worker context", err=True)
            click.echo(f"   You are: worker (workspace: {os.path.basename(workspace_name)})", err=True)
            click.echo("   Spawning is orchestrator-only operation", err=True)
            click.echo("", err=True)
            click.echo("   Workers should:", err=True)
            click.echo("   • Focus on their assigned task", err=True)
            click.echo("   • Ask questions if scope unclear", err=True)
            click.echo("   • Escalate blockers to orchestrator", err=True)
            raise click.Abort()

        try:
            # Validate feature-impl configuration if provided
            if any([phases, mode, validation, phase_id, depends_on]):
                validate_feature_impl_config(
                    phases=phases,
                    mode=mode,
                    validation=validation,
                    phase_id=phase_id,
                    depends_on=depends_on
                )

            # Read custom prompt or stdin context
            # - --prompt-file: Replace entire prompt (power user feature)
            # - --from-stdin: Add to ADDITIONAL CONTEXT section (not replace)
            # - Piped stdin (auto-detected): Add to ADDITIONAL CONTEXT section
            custom_prompt = None
            stdin_context = None

            if prompt_file:
                # --prompt-file replaces entire prompt (full control mode)
                with open(prompt_file, 'r') as f:
                    custom_prompt = f.read().strip()
            elif from_stdin:
                # --from-stdin flag: read stdin as context (not prompt replacement)
                stdin_context = sys.stdin.read().strip()
            elif not sys.stdin.isatty():
                # Auto-detect piped stdin (heredoc or pipe without explicit flag)
                # This enables: orch spawn skill "task" << 'CONTEXT' ... CONTEXT
                stdin_context = sys.stdin.read().strip()

            # Mode 4: Issue mode (from beads)
            if issue_id:
                # Auto-detect project directory
                project_dir = None
                if project:
                    from orch.project_resolver import get_project_dir, format_project_not_found_error
                    project_dir = get_project_dir(project)
                    if not project_dir:
                        click.echo(format_project_not_found_error(project, "--project"), err=True)
                        raise click.Abort()
                else:
                    # Try auto-detection
                    from orch.project_resolver import detect_project_from_cwd
                    detected = detect_project_from_cwd()
                    if detected:
                        project, project_dir = detected
                    else:
                        click.echo("❌ --project required when using --issue (auto-detection failed)", err=True)
                        raise click.Abort()

                try:
                    # Look up beads issue
                    beads = BeadsIntegration()
                    issue = beads.get_issue(issue_id)
                except BeadsCLINotFoundError:
                    click.echo("❌ bd CLI not found. Install beads or check PATH.", err=True)
                    click.echo("   See: https://github.com/dylanconlin/beads", err=True)
                    raise click.Abort()
                except BeadsIssueNotFoundError:
                    click.echo(f"❌ Beads issue '{issue_id}' not found", err=True)
                    click.echo("   Run 'bd list' to see available issues.", err=True)
                    raise click.Abort()

                # Refuse closed issues unless --force is provided
                if issue.status == 'closed' and not force:
                    click.echo(f"❌ Issue '{issue_id}' is already closed.", err=True)
                    click.echo("   Use --force to spawn anyway.", err=True)
                    raise click.Abort()

                # Check for open blockers and warn (non-blocking)
                try:
                    open_blockers = beads.get_open_blockers(issue_id)
                    if open_blockers:
                        blocker_ids = ", ".join(b.id for b in open_blockers)
                        click.echo("")
                        click.echo(f"⚠️  This issue has {len(open_blockers)} open blocker(s): {blocker_ids}", err=True)
                        click.echo("")
                except Exception:
                    # Silently ignore blocker check errors - don't block spawning
                    pass

                # Check for prior commits mentioning this issue
                # Prevents spawning for already-completed work
                # Skip check for open/in_progress issues - commits are from issue creation or WIP
                if project_dir and issue.status not in ('open', 'in_progress'):
                    prior_commits = find_commits_mentioning_issue(Path(project_dir), issue_id)
                    if prior_commits:
                        # Only show warning and prompt if not using -y flag
                        if not yes:
                            click.echo("")
                            click.echo(f"⚠️  Found {len(prior_commits)} prior commit(s) mentioning {issue_id}:", err=True)
                            for commit in prior_commits[:5]:  # Show first 5
                                click.echo(f"   • {commit.short_hash} {commit.short_message[:60]}", err=True)
                            if len(prior_commits) > 5:
                                click.echo(f"   ... and {len(prior_commits) - 5} more", err=True)
                            click.echo("")
                            click.echo("   Work may already be completed for this issue.", err=True)
                            click.echo(f"   Review: git log --grep='{issue_id}'", err=True)
                            click.echo("")

                            # Prompt to continue or abort
                            if not click.confirm("Spawn agent anyway?", default=False):
                                raise click.Abort()

                # Use issue title as task, with skill from first positional arg or default
                skill_name = context_or_skill if context_or_skill else "feature-impl"
                task_description = issue.title

                # Resolve beads db path for cross-repo spawning
                # The db is in the current working directory (where spawn is invoked)
                beads_db_path = None
                cwd = Path.cwd()
                beads_db = cwd / ".beads" / "beads.db"
                if beads_db.exists():
                    beads_db_path = str(beads_db.resolve())

                # Build beads issue context (added to full prompt, not replacing it)
                issue_context = f"BEADS ISSUE: {issue_id}\n"
                if issue.description:
                    issue_context += f"\nIssue Description:\n{issue.description}\n"
                if issue.labels:
                    labels_str = ", ".join(issue.labels)
                    issue_context += f"\nLabels: {labels_str}\n"
                if issue.notes:
                    issue_context += f"\nNotes:\n{issue.notes}\n"

                click.echo(f"🔗 Spawning from beads issue: {issue_id}")
                click.echo(f"   Skill: {skill_name}")
                click.echo(f"   Title: {task_description[:60]}{'...' if len(task_description) > 60 else ''}")

                # Mark issue as in_progress
                beads.update_issue_status(issue_id, "in_progress")

                # Spawn with beads tracking
                # Note: issue_context goes to additional_context (incorporated into full prompt)
                # custom_prompt (from --prompt-file) still works as full replacement if provided
                # Pass project_dir to avoid re-resolution (fixes project not found for auto-detected projects)
                spawn_with_skill(
                    skill_name=skill_name,
                    task=task_description,
                    project=project,
                    project_dir=project_dir,
                    workspace_name=workspace_name,
                    yes=yes,
                    resume=resume,
                    custom_prompt=custom_prompt,  # Only used if --prompt-file provided
                    additional_context=issue_context,  # Beads context added to full prompt
                    stdin_context=stdin_context,  # Heredoc/pipe context (added to ADDITIONAL CONTEXT)
                    phases=phases,
                    mode=mode,
                    validation=validation,
                    phase_id=phase_id,
                    depends_on=depends_on,
                    investigation_type=investigation_type,
                    backend=backend,
                    model=model,
                    stash=stash,
                    allow_dirty=allow_dirty,
                    beads_id=issue_id,
                    beads_db_path=beads_db_path,
                    context_ref=context_ref,
                    include_agent_mail=agent_mail
                )
                return

            # Mode 1: ROADMAP (optionally with skill override)
            if roadmap_title:
                # If skill name provided as first positional argument, use it to override ROADMAP :Skill: property
                skill_override = context_or_skill if context_or_skill else None
                spawn_from_roadmap(roadmap_title, yes=yes, resume=resume, backend=backend, skill_name_override=skill_override, model=model)
                return

            # Mode 3: Interactive
            if interactive:
                # Check if a skill name was provided (skill + -i = interactive skill mode)
                # Detect skill by checking if context_or_skill looks like a skill name
                from orch.skill_discovery import discover_skills
                skill_metadata = None
                if context_or_skill:
                    try:
                        skills = discover_skills()
                        if context_or_skill in skills:
                            skill_metadata = skills[context_or_skill]
                    except Exception:
                        skill_metadata = None

                if skill_metadata and task:
                    # Interactive skill mode: skill + task + -i
                    # Example: orch spawn architect "design auth system" -i
                    spawn_with_skill(
                        skill_name=context_or_skill,
                        task=task,
                        project=project,
                        workspace_name=workspace_name,
                        yes=yes,
                        resume=resume,
                        stdin_context=stdin_context,  # Heredoc/pipe context
                        phases=phases,
                        mode=mode,
                        validation=validation,
                        phase_id=phase_id,
                        depends_on=depends_on,
                        investigation_type=investigation_type,
                        backend=backend,
                        model=model,
                        stash=stash,
                        allow_dirty=allow_dirty,
                        interactive=True,  # Key difference: interactive mode
                        context_ref=context_ref,
                        include_agent_mail=agent_mail
                    )
                    return
                else:
                    # Generic interactive mode: -i with context only (no skill)
                    # Example: orch spawn -i "explore codebase" --project X
                    context = task if task else (context_or_skill or "")
                    spawn_interactive(
                        context=context,
                        project=project,
                        yes=yes,
                        resume=resume,
                        backend=backend,
                        model=model
                    )
                    return

            # Mode 3b: 'interactive' as alias for -i flag
            # Example: orch spawn interactive "explore codebase" --project X
            # Treats 'interactive' as if user had specified -i flag
            if context_or_skill == 'interactive':
                context = task if task else ""
                spawn_interactive(
                    context=context,
                    project=project,
                    yes=yes,
                    resume=resume,
                    backend=backend,
                    model=model
                )
                return

            # Mode 2: Skill-based (with optional custom prompt)
            # Allow missing task if custom_prompt is provided
            if not context_or_skill or (not task and not custom_prompt):
                click.echo("❌ Usage: orch spawn SKILL_NAME \"task description\"", err=True)
                click.echo("   Or:    orch spawn --from-roadmap \"ROADMAP Item Title\"", err=True)
                click.echo("   Or:    orch spawn -i \"context\" --project NAME", err=True)
                click.echo("   Or:    orch spawn interactive \"context\" --project NAME", err=True)
                click.echo("   Or:    orch spawn SKILL_NAME --project NAME --prompt-file FILE", err=True)
                raise click.Abort()

            # If task is missing but custom_prompt provided, extract first line as task description
            task_description = task
            if not task_description and custom_prompt:
                # Use first non-empty line from custom prompt as task description
                first_line = custom_prompt.split('\n')[0].strip()
                # If first line starts with "TASK:", extract it
                if first_line.startswith('TASK:'):
                    task_description = first_line[5:].strip()
                else:
                    # Use first line, truncate if too long
                    task_description = first_line[:100] if len(first_line) > 100 else first_line

            # Pre-spawn artifact search hint (for all spawns)
            # Shows hint if related artifacts exist but weren't mentioned in context
            if task_description and not skip_artifact_check:
                from orch.artifact_hint import show_artifact_hint

                try:
                    # Find current project directory
                    hint_project_dir = None
                    if project:
                        # Resolve project name to directory
                        registry = AgentRegistry()
                        for agent in registry.list_agents():
                            if Path(agent['project_dir']).name == project:
                                hint_project_dir = Path(agent['project_dir'])
                                break
                    else:
                        # Walk up from cwd looking for .orch directory
                        current = Path.cwd()
                        for _ in range(5):
                            if (current / ".orch").exists():
                                hint_project_dir = current
                                break
                            if current == current.parent:
                                break
                            current = current.parent

                    if hint_project_dir:
                        show_artifact_hint(
                            task=task_description,
                            project_dir=hint_project_dir,
                            skip_check=skip_artifact_check
                        )
                except Exception:
                    # Silently ignore hint errors (don't block spawning)
                    pass

            spawn_with_skill(
                skill_name=context_or_skill,
                task=task_description,
                project=project,
                workspace_name=workspace_name,
                yes=yes,
                resume=resume,
                custom_prompt=custom_prompt,
                stdin_context=stdin_context,  # Heredoc/pipe context (added to ADDITIONAL CONTEXT)
                phases=phases,
                mode=mode,
                validation=validation,
                phase_id=phase_id,
                depends_on=depends_on,
                investigation_type=investigation_type,
                backend=backend,
                model=model,
                stash=stash,
                allow_dirty=allow_dirty,
                context_ref=context_ref,
                parallel=parallel,
                include_agent_mail=agent_mail
            )

        except ValueError as e:
            click.echo(f"❌ {e}", err=True)
            raise click.Abort()
        except RuntimeError as e:
            click.echo(f"❌ {e}", err=True)
            raise click.Abort()
        except Exception as e:
            click.echo(f"❌ Unexpected error: {e}", err=True)
            raise
