"""Help system for orch CLI - workflow-focused guidance."""
from pathlib import Path
import click


# Map of help topics to their text files
HELP_TOPICS = {
    'spawn': 'docs/help/spawn.txt',
    'monitor': 'docs/help/monitor.txt',
    'complete': 'docs/help/complete.txt',
    'maintain': 'docs/help/maintain.txt',
    'orchestrator-start': None,
}


def get_help_file_path(topic=None):
    """Get the path to a help file.

    Args:
        topic: Help topic name, or None for overview

    Returns:
        Path object to the help file
    """
    if topic is None:
        filename = 'docs/help/overview.txt'
    elif topic in HELP_TOPICS and HELP_TOPICS[topic]:
        filename = HELP_TOPICS[topic]
    else:
        return None

    # Get path relative to project root (3 levels up from this file)
    project_root = Path(__file__).parent.parent.parent
    return project_root / filename


def show_help_overview():
    """Display the help overview."""
    help_file = get_help_file_path(None)

    if help_file and help_file.exists():
        click.echo(help_file.read_text())
    else:
        # Fallback if file doesn't exist
        click.echo("orch help - AI Agent Orchestration CLI")
        click.echo("\nAvailable help topics:")
        for topic in HELP_TOPICS.keys():
            click.echo(f"  orch help {topic}")


def show_help_topic(topic):
    """Display help for a specific topic.

    Args:
        topic: The help topic name
    """
    # Special case: orchestrator-start is synthesized from docs/ + CLAUDE
    if topic == 'orchestrator-start':
        show_orchestrator_start_help()
        return

    help_file = get_help_file_path(topic)

    if help_file and help_file.exists():
        click.echo(help_file.read_text())
    else:
        click.echo(f"Error: Help file not found for topic '{topic}'")
        click.echo("\nAvailable topics:")
        for available_topic in HELP_TOPICS.keys():
            click.echo(f"  orch help {available_topic}")


def show_unknown_topic(topic):
    """Display error for unknown topic and show available topics.

    Args:
        topic: The unknown topic name
    """
    click.echo(f"Unknown help topic: {topic}")
    click.echo("\nAvailable topics:")
    for available_topic in HELP_TOPICS.keys():
        click.echo(f"  orch help {available_topic}")
    click.echo("\nFor overview:")
    click.echo("  orch help")


def show_orchestrator_start_help():
    """Display orchestrator session start guidance.

    This topic is designed for the orch-knowledge project. When
    called from other projects, it explains that and points to local
    CLAUDE/README docs instead of giving orch-knowledge-specific
    paths that may not exist.
    """
    from datetime import datetime

    # Detect whether we're inside the orch-knowledge repo by
    # walking up until we find docs/orch-knowledge-system-overview.md
    # and a .orch directory.
    cwd = Path.cwd()
    meta_root = None
    for parent in [cwd] + list(cwd.parents):
        orch_dir = parent / ".orch"
        overview_repo = parent / "docs" / "orch-knowledge-system-overview.md"
        overview_orch = orch_dir / "docs" / "orch-knowledge-system-overview.md"
        if orch_dir.is_dir() and (overview_repo.exists() or overview_orch.exists()):
            meta_root = parent
            break

    click.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    click.echo(" orch help orchestrator-start - Orchestrator Session Start")
    click.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    click.echo()

    if meta_root is None:
        # Not in orch-knowledge; provide generic guidance and explain scope.
        click.echo("NOTE")
        click.echo("  This topic is specific to the orch-knowledge project and")
        click.echo("  expects docs/orch-knowledge-system-overview.md to exist.")
        click.echo()
        click.echo("  You are currently in:")
        click.echo(f"    {cwd}")
        click.echo()
        click.echo("For this project, a safe session-start pattern is:")
        click.echo()
        click.echo("  1. Read ./CLAUDE.md (and, if present, ./.orch/CLAUDE.md)")
        click.echo("     - Understand project-specific orchestration guidance.")
        click.echo()
        click.echo("  2. Skim ./.orch/README.md and ./.orch/ROADMAP.org (if they")
        click.echo("     exist) to see recent decisions, investigations, and work.")
        click.echo()
        click.echo("  3. Use workflow help for concrete flows:")
        click.echo("       orch help spawn")
        click.echo("       orch help monitor")
        click.echo("       orch help complete")
        click.echo("       orch help maintain")
        click.echo()
        click.echo("TIP")
        click.echo("  If this project needs a deeper orchestrator overview, you can")
        click.echo("  mirror the pattern from orch-knowledge by adding a")
        click.echo("  project-specific system overview doc and pointing to it from")
        click.echo("  your CLAUDE.md.")
        click.echo()
        click.echo(f"Last updated: {datetime.now().strftime('%Y-%m-%d')}")
        return

    # orch-knowledge-specific guidance
    click.echo("PURPOSE")
    click.echo("  Standardize how you (or an agent) orient at the start of an")
    click.echo("  orchestrator session in orch-knowledge/.orch so each")
    click.echo("  session rebuilds the same mental model of the system.")
    click.echo()

    click.echo("SESSION START STEPS (orch-knowledge/.orch)")
    click.echo()
    click.echo("  1. Skim .orch/README.md")
    click.echo("     - Recent decisions, investigations, and active workspaces")
    click.echo()
    click.echo("  2. Rebuild the system model")
    click.echo("     - From the .orch/ directory, read")
    click.echo("       docs/orch-knowledge-system-overview.md to")
    click.echo("       re-establish architecture, invariants, and workflows.")
    click.echo()
    click.echo("  3. If doing broader meta-analysis")
    click.echo("     - Skim .claude/index.md for recent sessions, decisions,")
    click.echo("       knowledge, and skills across projects.")
    click.echo()
    click.echo("  4. Confirm current priorities")
    click.echo("     - Review .orch/ROADMAP.org (Phase 3 + Untriaged) to see")
    click.echo("       what meta-work is active or awaiting triage.")
    click.echo()
    click.echo("  5. Only then modify CLI, templates, or skills")
    click.echo("     - Ensure changes are grounded in the current system model")
    click.echo("       and existing decisions/investigations.")
    click.echo()

    click.echo("KEY FILES")
    click.echo("  - .orch/README.md                      # Artifact index")
    click.echo("  - docs/orch-knowledge-system-overview.md")
    click.echo("  - .claude/index.md                     # Cross-project index")
    click.echo("  - .orch/ROADMAP.org                    # orch-knowledge work")
    click.echo("  - .orch/CLAUDE.md                      # Orchestrator guidance")
    click.echo()

    click.echo("TIP")
    click.echo("  If you find yourself re-deriving how the system works from")
    click.echo("  code or scattered docs, pause and re-read the System Overview")
    click.echo("  instead. Treat it as the backbone for your mental model.")
    click.echo()

    click.echo(f"Project root: {meta_root}")
    click.echo(f"Last updated: {datetime.now().strftime('%Y-%m-%d')}")
