"""Work commands for orch CLI.

Commands for starting work on beads issues.
"""

import click
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from orch.beads_integration import (
    BeadsIntegration,
    BeadsCLINotFoundError,
    BeadsIssueNotFoundError,
)


# Skill inference mapping from issue type
ISSUE_TYPE_TO_SKILL = {
    "bug": "systematic-debugging",
    "feature": "feature-impl",
    "task": "investigation",
    "epic": "architect",
}

DEFAULT_SKILL = "feature-impl"


def infer_skill_from_issue_type(issue_type: Optional[str]) -> str:
    """Infer skill from beads issue type.

    Args:
        issue_type: The issue type (bug, feature, task, epic) or None

    Returns:
        The skill name to use for spawning
    """
    if issue_type is None:
        return DEFAULT_SKILL
    return ISSUE_TYPE_TO_SKILL.get(issue_type, DEFAULT_SKILL)


def get_ready_issues() -> list:
    """Get list of ready issues from bd ready.

    Returns:
        List of issue dicts with id, title, status, priority, issue_type
    """
    try:
        result = subprocess.run(
            ["bd", "ready", "--json"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise BeadsCLINotFoundError()

    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def register_work_commands(cli):
    """Register work-related commands with the CLI."""

    @cli.command()
    @click.argument('issue_id', required=False)
    @click.option('-s', '--skill', 'skill_override', help='Override inferred skill')
    @click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
    @click.option('--force', is_flag=True, help='Force spawn even for closed issues')
    @click.option('--project', help='Project name')
    @click.option('--name', 'workspace_name', help='Override workspace name')
    @click.option('--phases', help='Phases for feature-impl')
    @click.option('--mode', type=click.Choice(['tdd', 'direct']), help='Implementation mode')
    @click.option('--validation', type=click.Choice(['none', 'tests', 'smoke-test', 'multi-phase']), help='Validation level')
    @click.option('--backend', type=click.Choice(['claude', 'codex', 'opencode']), help='AI backend to use')
    @click.option('--model', help='Model to use')
    def work(issue_id, skill_override, yes, force, project, workspace_name, phases, mode, validation, backend, model):
        """
        Start work on a beads issue.

        \b
        Usage modes:
        1. With issue ID:    orch work <issue-id>           # Infer skill from issue type
        2. With skill:       orch work <issue-id> -s <skill> # Override skill
        3. List mode:        orch work                       # Show ready issues and exit

        \b
        Skill inference from issue type:
        - bug     → systematic-debugging
        - feature → feature-impl
        - task    → investigation
        - epic    → architect

        \b
        Examples:
            orch work                           # List ready issues (AI picks which to work on)
            orch work orch-cli-xyz              # Start work, infer skill
            orch work orch-cli-xyz -s architect # Override with architect skill
        """
        from orch.spawn import spawn_with_skill
        from orch.project_resolver import get_project_dir, format_project_not_found_error, detect_project_from_cwd

        # Context enforcement: Prevent workers from spawning
        claude_context = os.environ.get('CLAUDE_CONTEXT')
        if claude_context == 'worker':
            workspace_name_env = os.environ.get('CLAUDE_WORKSPACE', 'unknown')
            click.echo("❌ Cannot run 'orch work' from worker context", err=True)
            click.echo(f"   You are: worker (workspace: {os.path.basename(workspace_name_env)})", err=True)
            click.echo("   orch work is an orchestrator-only operation", err=True)
            raise click.Abort()

        # List mode: show ready issues and exit (AI-first design)
        if not issue_id:
            try:
                ready_issues = get_ready_issues()
            except BeadsCLINotFoundError:
                click.echo("❌ bd CLI not found. Install beads or check PATH.", err=True)
                raise click.Abort()

            if not ready_issues:
                click.echo("No ready issues found.")
                click.echo("Run 'bd ready' to see available work, or 'bd create' to create an issue.")
                return

            # Show available issues with inferred skills
            click.echo("Ready issues:\n")
            for issue in ready_issues:
                issue_type = issue.get('issue_type', 'unknown')
                skill = infer_skill_from_issue_type(issue_type)
                click.echo(f"  [{issue_type}] {issue.get('id')}: {issue.get('title', '')[:50]}")
                click.echo(f"     Skill: {skill}")
                click.echo(f"     → orch work {issue.get('id')}")
                click.echo()

            # Exit - orchestrator decides which issue to work on
            return

        # Look up the issue
        try:
            beads = BeadsIntegration()
            issue = beads.get_issue(issue_id)
        except BeadsCLINotFoundError:
            click.echo("❌ bd CLI not found. Install beads or check PATH.", err=True)
            raise click.Abort()
        except BeadsIssueNotFoundError:
            click.echo(f"❌ Beads issue '{issue_id}' not found", err=True)
            click.echo("   Run 'bd list' to see available issues.", err=True)
            raise click.Abort()

        # Refuse closed issues unless --force
        if issue.status == 'closed' and not force:
            click.echo(f"❌ Issue '{issue_id}' is already closed.", err=True)
            click.echo("   Use --force to spawn anyway.", err=True)
            raise click.Abort()

        # Determine skill
        if skill_override:
            skill_name = skill_override
        else:
            skill_name = infer_skill_from_issue_type(issue.issue_type)

        # Check for open blockers and warn (non-blocking)
        try:
            open_blockers = beads.get_open_blockers(issue_id)
            if open_blockers:
                blocker_ids = ", ".join(b.id for b in open_blockers)
                click.echo("")
                click.echo(f"⚠️  This issue has {len(open_blockers)} open blocker(s): {blocker_ids}", err=True)
                click.echo("")
        except Exception:
            pass

        # Resolve project directory
        project_dir = None
        if project:
            project_dir = get_project_dir(project)
            if not project_dir:
                click.echo(format_project_not_found_error(project, "--project"), err=True)
                raise click.Abort()
        else:
            detected = detect_project_from_cwd()
            if detected:
                project, project_dir = detected
            else:
                click.echo("❌ --project required (auto-detection failed)", err=True)
                click.echo("   Run from a project directory or specify --project", err=True)
                raise click.Abort()

        # Resolve beads db path for cross-repo spawning
        beads_db_path = None
        cwd = Path.cwd()
        beads_db = cwd / ".beads" / "beads.db"
        if beads_db.exists():
            beads_db_path = str(beads_db.resolve())

        # Build issue context
        issue_context = f"BEADS ISSUE: {issue_id}\n"
        if issue.description:
            issue_context += f"\nIssue Description:\n{issue.description}\n"
        if issue.notes:
            issue_context += f"\nNotes:\n{issue.notes}\n"

        click.echo(f"🔧 Starting work on: {issue_id}")
        click.echo(f"   Skill: {skill_name} (from issue type: {issue.issue_type or 'unknown'})")
        click.echo(f"   Title: {issue.title[:60]}{'...' if len(issue.title) > 60 else ''}")
        click.echo()

        # Confirmation unless -y, non-TTY, or ORCH_AUTO_CONFIRM
        # AI agents call this programmatically - auto-confirm when stdin is not a TTY
        should_skip = yes or not sys.stdin.isatty() or os.getenv('ORCH_AUTO_CONFIRM') == '1'
        if not should_skip:
            if not click.confirm("Start work?", default=True):
                click.echo("Cancelled.")
                return

        # Mark issue as in_progress
        beads.update_issue_status(issue_id, "in_progress")

        # Spawn the agent
        spawn_with_skill(
            skill_name=skill_name,
            task=issue.title,
            project=project,
            project_dir=project_dir,
            workspace_name=workspace_name,
            yes=True,  # Already confirmed
            resume=False,
            additional_context=issue_context,
            phases=phases,
            mode=mode,
            validation=validation,
            backend=backend,
            model=model,
            beads_id=issue_id,
            beads_db_path=beads_db_path,
        )
