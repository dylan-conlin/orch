"""
Bootstrap project-scoped orchestration.

Creates .orch/ directory structure with templates for:
- High-level orchestration context (CLAUDE.md)
- Worker implementation context (project/CLAUDE.md)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import click


def get_template_path() -> Path:
    """Get the path to bootstrap templates directory."""
    # templates/ is sibling to tools/
    return Path(__file__).parent.parent.parent / "templates"


def read_template(template_name: str) -> str:
    """Read template file content."""
    template_path = get_template_path() / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text()


def substitute_variables(content: str, variables: Dict[str, str]) -> str:
    """Replace {{VAR}} placeholders with actual values."""
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def prompt_for_project_info(project_dir: Path) -> Dict[str, str]:
    """
    Prompt user for project information.

    Returns:
        Dictionary with PROJECT_NAME, PROJECT_PURPOSE, DATE
    """
    # Use directory name as default project name
    default_name = project_dir.name

    project_name = click.prompt("Project name", default=default_name)
    project_purpose = click.prompt("Project purpose (one-line description)")

    return {
        "PROJECT_NAME": project_name,
        "PROJECT_PURPOSE": project_purpose,
        "DATE": datetime.now().strftime("%Y-%m-%d")
    }


def create_orch_directory_structure(project_dir: Path) -> None:
    """Create .orch/ directory structure."""
    orch_dir = project_dir / ".orch"

    # Create directories
    (orch_dir / "workspace").mkdir(parents=True, exist_ok=True)

    click.echo(f"✓ Created directory structure at {orch_dir}")


def get_instruction_markers_for_profile(profile: str) -> str:
    """
    Get ORCH-TEMPLATE markers based on instruction profile.

    Profiles:
    - core: Essential 6 templates + error-recovery (recommended for most projects)
    - full: All available templates (orch-knowledge, advanced users)
    - minimal: Just identity/boundaries (quick setup, add more later)

    Returns:
        String of ORCH-TEMPLATE markers to include in CLAUDE.md
    """
    # Essential Core (6 templates) - required for any orchestrator
    core_templates = [
        "core-responsibilities",       # Identity and boundaries
        "delegation-thresholds",       # Decision framework
        "orchestrator-vs-worker-boundaries",  # Context detection
        "orch-commands",               # Command reference
        "spawning-checklist",          # Pre-spawn requirements
        "verification-checklist",      # Completion workflow
        "error-recovery-patterns",     # Error handling (new)
    ]

    # Operational templates - for active agent management
    operational_templates = [
        "worker-skills",
        "amnesia-resilient-design",
        "artifact-organization",
        "pre-response-protocol",
        "red-flags-and-decision-trees",
    ]

    # Specialized templates - context-specific
    specialized_templates = [
        "synthesis-workflow",
        "decision-transparency",
        "maintenance-patterns",
    ]

    if profile == "minimal":
        templates = ["core-responsibilities", "orchestrator-vs-worker-boundaries"]
    elif profile == "core":
        templates = core_templates
    else:  # full (default for backwards compatibility)
        templates = core_templates + operational_templates + specialized_templates

    # Generate marker pairs
    markers = []
    for template in templates:
        markers.append(f"<!-- ORCH-TEMPLATE: {template} -->\n<!-- /ORCH-TEMPLATE -->")

    return "\n\n".join(markers)


def create_orch_claude_md(project_dir: Path, variables: Dict[str, str], profile: str = "full") -> None:
    """
    Create minimal .orch/CLAUDE.md with template markers.

    This creates a skeleton file with PROJECT-SPECIFIC sections and ORCH-TEMPLATE
    markers. The actual template content is populated by build_orchestrator_context.

    Args:
        project_dir: Project root directory
        variables: Template variables
        profile: Instruction profile - "core" (recommended), "full" (all), "minimal"
    """
    # Get markers based on profile
    instruction_markers = get_instruction_markers_for_profile(profile)

    # Create minimal content with PROJECT-SPECIFIC sections and template markers
    content = f"""<!-- PROJECT-SPECIFIC-START -->
<!-- Safe to edit below: Project customization -->

# {variables['PROJECT_NAME']} - Orchestration Context

IMPORTANT: This augments `~/.claude/CLAUDE.md`. Keep this file lean; link to canonical docs for details.

Scope: This project ({variables['PROJECT_NAME']}). For orch-knowledge work, delegate to orch-knowledge repo.

---

## Project Overview

**Purpose:** {variables['PROJECT_PURPOSE']}

**Key Components:**
- Component A (path/) - Purpose
- Component B (path/) - Purpose
- Component C (path/) - Purpose

**Architecture:** [Brief description or pointer to architecture doc]
- See @../docs/architecture.md for detailed design (if exists)

**Critical Constraints:**
- Constraint 1 (e.g., rate limiting, security requirements)
- Constraint 2 (e.g., manual review requirements)
- Constraint 3 (e.g., external dependencies)

**Important Files:**
- [Key file 1]: @../path/to/file
- [Key file 2]: @../path/to/file
- [Patterns/docs]: @../docs/patterns.md

---

## Spawning Guidance (Project-Specific)

**When spawning for [component X]:**
- Always mention [critical context]
- [Component Y] changes require [specific requirements]
- Point agents to [key patterns/docs]

**Verification Requirements:**
- [Type of change] requires manual review
- [Tests that must pass]
- [Quality gates that must be met]

**Project-Specific Delegation:**
- Complex [X] (threshold): delegate to agent
- Simple [Y]: execute directly
- [Special case]: [handling instructions]

<!-- PROJECT-SPECIFIC-END -->

---

> NOTE: Sections marked with `<!-- ORCH-TEMPLATE: ... -->` below are placeholder markers. For most projects, orchestration guidance is provided by the orchestrator skill loaded at runtime. If you need to customize these sections, you can manually populate them or remove the markers and add custom content.

{instruction_markers}
"""

    orch_claude = project_dir / ".orch" / "CLAUDE.md"
    orch_claude.write_text(content)

    click.echo(f"✓ Created {orch_claude} (skeleton with template markers)")


def build_orch_context_for_project(project_dir: Path) -> None:
    """
    Build orchestrator context by populating template markers.

    NOTE: Template population is currently manual. The ORCH-TEMPLATE markers
    in .orch/CLAUDE.md serve as placeholders that can be populated by copying
    content from ~/.orch/templates/orchestrator/ if that directory exists.

    For most projects, the skeleton with markers is sufficient - the actual
    orchestration guidance comes from the orchestrator skill loaded at runtime.
    """
    templates_dir = Path.home() / ".orch" / "templates" / "orchestrator"

    if templates_dir.exists():
        click.echo("✓ Template markers created (populate manually from ~/.orch/templates/orchestrator/)")
    else:
        click.echo("✓ Template markers created")
        click.echo("  → Orchestration guidance will be provided by the orchestrator skill at runtime")


def create_project_claude_md(project_dir: Path, variables: Dict[str, str], update: bool = False, yes: bool = False) -> None:
    """
    Create or update project/CLAUDE.md to import .orch/CLAUDE.md.

    Args:
        project_dir: Project root directory
        variables: Template variables
        update: If True, update existing file; if False, create new
        yes: If True, skip confirmation prompts
    """
    project_claude = project_dir / "CLAUDE.md"

    if project_claude.exists() and not update:
        click.echo(f"⚠️  {project_claude} already exists")
        if not yes and not click.confirm("Update to import .orch/CLAUDE.md?"):
            click.echo("  → Skipped updating project/CLAUDE.md")
            return

    if project_claude.exists():
        # Update existing file: add import at the top
        existing_content = project_claude.read_text()

        # Check if import already exists
        if "@.orch/CLAUDE.md" in existing_content:
            click.echo(f"✓ {project_claude} already imports .orch/CLAUDE.md")
            return

        # Add import at the beginning
        new_content = f"# {variables['PROJECT_NAME']} - Worker Context\n\n"
        new_content += "## Project Foundation\n"
        new_content += "@.orch/CLAUDE.md\n\n"
        new_content += "---\n\n"
        new_content += existing_content

        project_claude.write_text(new_content)
        click.echo(f"✓ Updated {project_claude} to import .orch/CLAUDE.md")
    else:
        # Create new file from template
        template_content = read_template("project-CLAUDE.md.template")
        content = substitute_variables(template_content, variables)

        project_claude.write_text(content)
        click.echo(f"✓ Created {project_claude}")
        click.echo("  → Edit this file to add implementation details")


# Deprecated: Coordination journal removed per decision 2025-11-15-deprecate-coordination-journal.md
# def create_coordination_journal(project_dir: Path, variables: Dict[str, str]) -> None:
#     """Create coordination journal from template."""
#     template_content = read_template("coordination-workspace.md.template")
#     content = substitute_variables(template_content, variables)
#
#     journal_path = project_dir / ".orch" / "workspace" / "coordination" / "WORKSPACE.md"
#     journal_path.write_text(content)
#
#     click.echo(f"✓ Created {journal_path}")


def setup_sessionstart_hook() -> None:
    """
    Set up SessionStart hook to inject orch command patterns.

    Creates hook script and registers it in ~/.claude/settings.json.
    Only runs when Claude is started from .orch/ directory.
    """
    hooks_dir = Path.home() / ".claude" / "hooks"
    hook_script = hooks_dir / "inject-orch-patterns.sh"
    settings_file = Path.home() / ".claude" / "settings.json"

    # Create hooks directory if it doesn't exist
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Check if hook script already exists
    if hook_script.exists():
        click.echo(f"✓ Hook script already exists: {hook_script}")
    else:
        # Create hook script
        hook_content = '''#!/bin/bash

# Inject orch command patterns into session context
# Only runs when started from INSIDE .orch/ directory

# Read stdin into variable
INPUT=$(cat)

# Read cwd from hook input
CWD=$(echo "$INPUT" | jq -r '.cwd // ""' 2>/dev/null)

if [ -z "$CWD" ]; then
  CWD=$(pwd)
fi

# Only inject if CWD contains /.orch/ in the path or ends with /.orch
if [[ ! "$CWD" =~ /.orch(/|$) ]]; then
  exit 0
fi

PATTERNS_FILE="$HOME/.orch/docs/orch-command-patterns.md"

if [ -f "$PATTERNS_FILE" ]; then
  CONTENT=$(cat "$PATTERNS_FILE")

  # Output JSON with additionalContext to stdout
  jq -n --arg content "$CONTENT" '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $content
    }
  }'
else
  exit 0
fi
'''
        hook_script.write_text(hook_content)
        hook_script.chmod(0o755)  # Make executable
        click.echo(f"✓ Created hook script: {hook_script}")

    # Check if hook is registered in settings.json
    if not settings_file.exists():
        click.echo(f"⚠️  Settings file not found: {settings_file}")
        click.echo("  → Run Claude Code once to create it, then run orch init again")
        return

    settings = json.loads(settings_file.read_text())

    # Check if SessionStart hook already registered
    session_start_hooks = settings.get("hooks", {}).get("SessionStart", [])
    hook_command = "$HOME/.claude/hooks/inject-orch-patterns.sh"

    already_registered = False
    for hook_config in session_start_hooks:
        for hook in hook_config.get("hooks", []):
            if hook.get("command") == hook_command:
                already_registered = True
                break

    if already_registered:
        click.echo(f"✓ Hook already registered in settings.json")
    else:
        # Add hook to settings
        if "hooks" not in settings:
            settings["hooks"] = {}
        if "SessionStart" not in settings["hooks"]:
            settings["SessionStart"] = []

        settings["hooks"]["SessionStart"].append({
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command
                }
            ]
        })

        settings_file.write_text(json.dumps(settings, indent=2))
        click.echo(f"✓ Registered hook in settings.json")
        click.echo("  → Restart Claude Code for hook to take effect")


def add_gitignore_entries(project_dir: Path, team_project: bool) -> None:
    """
    Add or update .gitignore for .orch/ directory.

    Args:
        project_dir: Project root directory
        team_project: If True, only ignore state; if False, ignore entire .orch/
    """
    gitignore_path = project_dir / ".gitignore"

    if team_project:
        entries = [
            "# Orchestration state (local)",
            ".orch/workspace/",
        ]
        message = "team projects"
    else:
        entries = [
            "# Orchestration directory (solo project)",
            ".orch/",
        ]
        message = "solo projects"

    # Read existing gitignore
    existing_content = ""
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text()

    # Check if .orch/ already mentioned
    if ".orch" in existing_content:
        click.echo(f"✓ .gitignore already mentions .orch/")
        return

    # Append entries
    new_content = existing_content
    if not new_content.endswith("\n\n"):
        new_content += "\n\n"
    new_content += "\n".join(entries) + "\n"

    gitignore_path.write_text(new_content)
    click.echo(f"✓ Updated .gitignore ({message})")


def setup_git_hooks(project_dir: Path) -> None:
    """
    Install git pre-commit hook for orchestration checks.

    Symlinks the hook from orch-knowledge/scripts/pre-commit to
    the project's .git/hooks/pre-commit. The hook checks:
    - Token/char limits when template sources change
    - CLAUDE.md/template sync
    - README auto-generation on artifact changes
    """
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        click.echo("⚠️  Not a git repo, skipping hook installation")
        return

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_dest = hooks_dir / "pre-commit"
    hook_source = Path.home() / "orch-knowledge" / "scripts" / "pre-commit"

    if not hook_source.exists():
        click.echo(f"⚠️  Hook source not found: {hook_source}")
        return

    if hook_dest.exists():
        # Check if it's already our hook (symlink to same source)
        if hook_dest.is_symlink() and hook_dest.resolve() == hook_source.resolve():
            click.echo("✓ Pre-commit hook already installed")
            return
        else:
            click.echo("⚠️  Pre-commit hook exists but differs, skipping (manual review needed)")
            return

    # Create symlink
    try:
        hook_dest.symlink_to(hook_source)
        click.echo(f"✓ Installed pre-commit hook (symlink to {hook_source})")
    except Exception as e:
        click.echo(f"⚠️  Failed to install pre-commit hook: {e}")


def init_project_orchestration(
    project_path: Optional[str] = None,
    project_name: Optional[str] = None,
    project_purpose: Optional[str] = None,
    team: bool = False,
    yes: bool = False,
    profile: str = "full"
) -> bool:
    """
    Initialize project-scoped orchestration.

    Args:
        project_path: Path to project directory (default: current directory)
        project_name: Project name (if None, prompt user)
        project_purpose: Project purpose (if None, prompt user)
        team: True for team projects (commit CLAUDE.md, ignore state)
        yes: Skip confirmations
        profile: Instruction profile - "core" (recommended), "full" (all), "minimal"

    Returns:
        True if successful, False otherwise
    """
    # Determine project directory
    if project_path:
        project_dir = Path(project_path).resolve()
    else:
        project_dir = Path.cwd()

    if not project_dir.exists():
        click.echo(f"✗ Directory not found: {project_dir}", err=True)
        return False

    # Check if .orch/ already exists
    orch_dir = project_dir / ".orch"
    if orch_dir.exists() and (orch_dir / "CLAUDE.md").exists():
        click.echo(f"⚠️  Project orchestration already initialized at {orch_dir}")
        if not yes and not click.confirm("Reinitialize?"):
            return False

    click.echo(f"\nInitializing project orchestration for: {project_dir}")
    click.echo()

    # Gather project information
    if project_name and project_purpose:
        variables = {
            "PROJECT_NAME": project_name,
            "PROJECT_PURPOSE": project_purpose,
            "DATE": datetime.now().strftime("%Y-%m-%d")
        }
        click.echo(f"Project: {project_name}")
        click.echo(f"Purpose: {project_purpose}")
        click.echo()
    else:
        variables = prompt_for_project_info(project_dir)
        click.echo()

    # Confirm
    if not yes:
        click.echo("This will create:")
        click.echo(f"  - {project_dir}/.orch/CLAUDE.md (high-level context)")
        click.echo(f"  - {project_dir}/.orch/workspace/ (agent workspaces)")
        click.echo(f"  - {project_dir}/CLAUDE.md (worker context, imports .orch/CLAUDE.md)")
        if team:
            click.echo(f"  - Update .gitignore (team mode: commit CLAUDE.md, ignore state)")
        else:
            click.echo(f"  - Update .gitignore (solo mode: ignore entire .orch/)")
        click.echo()

        if not click.confirm("Continue?"):
            click.echo("Cancelled.")
            return False
        click.echo()

    try:
        # Create structure
        create_orch_directory_structure(project_dir)
        create_orch_claude_md(project_dir, variables, profile=profile)

        # Build orchestrator context from templates
        click.echo()
        click.echo("Building orchestrator context from templates...")
        build_orch_context_for_project(project_dir)

        create_project_claude_md(project_dir, variables, update=False, yes=yes)
        # Coordination journal deprecated - see .orch/decisions/2025-11-15-deprecate-coordination-journal.md
        add_gitignore_entries(project_dir, team_project=team)

        click.echo()
        click.echo("Setting up SessionStart hook for pattern injection...")
        setup_sessionstart_hook()

        click.echo()
        click.echo("Setting up git pre-commit hook...")
        setup_git_hooks(project_dir)

        click.echo()
        click.echo("✅ Project orchestration initialized successfully!")
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  1. Edit {orch_dir}/CLAUDE.md (add project architecture, constraints)")
        click.echo(f"  2. Edit {project_dir}/CLAUDE.md (add implementation details)")
        click.echo(f"  3. cd {orch_dir}")
        click.echo(f"  4. claude")
        click.echo()
        click.echo("📝 Note: Orch command patterns will be auto-loaded when starting Claude from .orch/")
        click.echo()
        click.echo("See: docs/plans/2025-11-13-project-scoped-orchestration-design.md")

        return True

    except Exception as e:
        click.echo(f"\n✗ Error initializing project orchestration: {e}", err=True)
        import traceback
        traceback.print_exc()
        return False
