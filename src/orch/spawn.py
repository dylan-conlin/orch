"""
Spawning functionality for orch tool.

Supports three modes:
1. ROADMAP mode - Spawn pre-triaged work from ROADMAP.org
2. Skill-based mode - Quick spawns with CDD skills
3. Interactive mode - Guided workflow for complex tasks
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import yaml
import re
import subprocess
from datetime import datetime
import time
import os
import shlex

from orch.workspace import truncate_at_word_boundary
from orch.workspace_naming import (
    STOP_WORDS,
    SKILL_PREFIXES,
    SKILL_EMOJIS,
    extract_meaningful_words,
    create_workspace_adhoc,
    get_emoji_for_skill,
    abbreviate_project_name,
    build_window_name,
)
from orch.logging import OrchLogger
from orch.backends import ClaudeBackend, CodexBackend
from orch.backends.opencode import (
    OPENCODE_DEFAULT_MODEL,
    OPENCODE_MODEL_ALIASES,
    resolve_opencode_model,
)
from orch.config import get_backend
from orch.skill_discovery import (
    SkillDeliverable,
    SkillVerification,
    SkillMetadata,
    DEFAULT_DELIVERABLES,
    discover_skills,
    parse_skill_metadata
)
from orch.spawn_prompt import (
    DEFAULT_VERIFICATION,
    render_deliverable_path,
    get_verification_requirements,
    load_skill_content,
    load_spawn_prompt_template,
    fallback_template,
    build_spawn_prompt,
)
from orch.spawn_context_quality import (
    validate_spawn_context_length,
    SpawnContextTooShortError,
)
from orch.git_utils import (
    check_git_dirty_state,
    git_stash_changes,
    git_stash_pop,
)
from orch.tmuxinator import (
    ensure_tmuxinator_config,
    start_workers_session,
    switch_workers_client,
)
from orch.project_resolver import (
    _get_active_projects_file,
    _parse_active_projects,
    get_project_dir,
    list_available_projects,
    format_project_not_found_error,
    detect_project_from_cwd,
)

logger = logging.getLogger(__name__)


# Data Classes imported from skill_discovery:
# - SkillDeliverable
# - SkillVerification
# - SkillMetadata


@dataclass
class SpawnConfig:
    """Configuration for spawning an agent."""
    task: str
    project: str
    project_dir: Path
    workspace_name: str
    skill_name: Optional[str] = None
    deliverables: List[SkillDeliverable] = None
    roadmap_context: Optional[str] = None
    custom_prompt: Optional[str] = None
    skill_metadata: Optional[SkillMetadata] = None  # Phase 3: Full skill metadata for verification
    # Feature-impl configuration (Phase 4)
    phases: Optional[str] = None  # Comma-separated phases (e.g., "investigation,design,implementation,validation")
    mode: Optional[str] = None  # Implementation mode: "tdd" or "direct"
    validation: Optional[str] = None  # Validation level: "none", "tests", "smoke-test", "multi-phase"
    phase_id: Optional[str] = None  # Phase identifier for multi-phase work
    depends_on: Optional[str] = None  # Phase dependency (requires phase_id)
    # Investigation configuration
    investigation_type: Optional[str] = None  # Investigation type: "systems", "feasibility", "audits", "performance", "agent-failures"
    # Backend configuration (Phase 1)
    backend: str = "claude"  # Backend to use: "claude" (default), "codex", etc.
    model: Optional[str] = None  # Model to use (e.g., "sonnet", "opus", or "claude-sonnet-4-5-20250929")
    # Coordination metadata
    beads_only: bool = True  # True = use beads comments only, False = use investigation file as primary artifact
    primary_artifact: Optional[Path] = None  # Path to coordination artifact when not using workspace
    # Feature tracking (backlog.json integration)
    feature_id: Optional[str] = None  # Feature ID from backlog.json for lifecycle tracking
    context_ref: Optional[str] = None  # Path to context file (design doc, investigation) to include in spawn prompt
    # Interactive mode (for collaborative design work)
    interactive: bool = False  # If True, skill operates in collaborative mode with Dylan
    # Beads integration
    beads_id: Optional[str] = None  # Beads issue ID for lifecycle tracking (primary issue)
    beads_ids: Optional[List[str]] = None  # Multiple beads issue IDs for multi-issue spawns
    beads_db_path: Optional[str] = None  # Absolute path to beads db (for cross-repo spawning)
    # Additional context (incorporated into prompt, does NOT replace it)
    # Use this for beads issue context or other supplementary information
    # Contrast with custom_prompt which replaces the entire generated prompt
    additional_context: Optional[str] = None
    # Stdin context (from heredoc/pipe, added to ADDITIONAL CONTEXT section)
    # Separate from additional_context to allow combining beads context with heredoc
    stdin_context: Optional[str] = None
    # Parallel execution mode (codebase-audit: spawn 5 dimension agents + synthesis)
    parallel: bool = False
    # Cross-repo spawning: track origin directory to sync workspace back on completion
    origin_dir: Optional[Path] = None
    # Agent Mail coordination (scope-aware: only included for Medium/Large scope or explicit flag)
    include_agent_mail: bool = False


# Constants
# DEFAULT_DELIVERABLES imported from skill_discovery
# STOP_WORDS, SKILL_PREFIXES, SKILL_EMOJIS imported from workspace_naming
# DEFAULT_VERIFICATION imported from spawn_prompt


# Feature-impl Configuration Validation
def validate_feature_impl_config(
    phases: Optional[str] = None,
    mode: Optional[str] = None,
    validation: Optional[str] = None,
    phase_id: Optional[str] = None,
    depends_on: Optional[str] = None
) -> None:
    """
    Validate feature-impl configuration flags.

    Args:
        phases: Comma-separated list of phases
        mode: Implementation mode (tdd or direct)
        validation: Validation level (none, tests, smoke-test, multi-phase)
        phase_id: Phase identifier for multi-phase work
        depends_on: Phase dependency

    Raises:
        ValueError: If configuration is invalid
    """
    # Valid phase names
    valid_phases = {'investigation', 'clarifying-questions', 'design', 'implementation', 'validation', 'integration'}

    # Validate phases
    if phases:
        phase_list = [p.strip() for p in phases.split(',')]
        for phase in phase_list:
            if phase not in valid_phases:
                raise ValueError(f"Invalid phase '{phase}'. Valid phases: {', '.join(sorted(valid_phases))}")

    # Validate mode
    if mode:
        valid_modes = {'tdd', 'direct'}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Valid modes: {', '.join(sorted(valid_modes))}")

    # Validate validation level
    if validation:
        valid_validation_levels = {'none', 'tests', 'smoke-test', 'multi-phase'}
        if validation not in valid_validation_levels:
            raise ValueError(f"Invalid validation level '{validation}'. Valid levels: {', '.join(sorted(valid_validation_levels))}")

    # Validate multi-phase requirements
    if validation == 'multi-phase' and not phase_id:
        raise ValueError("multi-phase validation requires --phase-id")

    # Validate depends-on requirements
    if depends_on and not phase_id:
        raise ValueError("--depends-on requires --phase-id")


# Skill Discovery functions imported from skill_discovery module:
# - discover_skills()
# - parse_skill_metadata()
# - _discover_skills_cached() (internal)


# Per-Project Session Name Derivation
def get_workers_session_name(project_name: str) -> str:
    """
    Derive per-project workers session name from project name.

    Creates a tmux session name in the format 'workers-{project_name}'
    for organizing agents by project.

    Args:
        project_name: Name of the project (e.g., 'orch-cli', 'beads')

    Returns:
        Session name (e.g., 'workers-orch-cli', 'workers-beads')
    """
    return f"workers-{project_name}"


# Heuristics
def looks_trivial_bug(text: str) -> bool:
    """
    Heuristic: does the task look like an obvious/localized failure suitable for quick-debugging?

    Signals trivial bug when task mentions common localized errors or lints.
    """
    if not text:
        return False

    t = text.lower()
    indicators = [
        "importerror", "module not found", "modulenotfounderror", "undefined name",
        "nameerror", "attributeerror", "signature mismatch", "missing required positional argument",
        "typeerror", "flake8", "mypy", "lint error", "pre-commit", "typo", "rename",
        "single failing test", "one test failing", "fix test"
    ]
    return any(k in t for k in indicators)


# Workspace Creation
# extract_meaningful_words, create_workspace_adhoc, get_emoji_for_skill imported from workspace_naming
# render_deliverable_path imported from spawn_prompt


def determine_primary_artifact(config: SpawnConfig) -> Optional[Path]:
    """
    Determine coordination artifact path (e.g., investigation file) from deliverables.

    Args:
        config: Spawn configuration with deliverables

    Returns:
        Path to coordination artifact if derivable, else None
    """
    if not config.deliverables:
        return None

    for deliverable in config.deliverables:
        if deliverable.type == "investigation" and deliverable.required:
            rendered = render_deliverable_path(deliverable.path, config)
            return Path(rendered)

    return None


def generate_agent_file(config: SpawnConfig) -> Optional[Path]:
    """
    Generate .claude/agents/{skill}-worker.md file from skill metadata.

    Creates an agent file with tool restrictions and model configuration
    that can be passed to Claude Code via --agent flag. This provides
    native tool restrictions without using --allowed-tools '*'.

    Agent file provides: tool restrictions, model, description
    SPAWN_CONTEXT.md provides: detailed procedural guidance

    Args:
        config: SpawnConfig with skill_metadata containing tool restrictions

    Returns:
        Path to generated agent file, or None if no tool restrictions needed
    """
    # No agent file needed without skill metadata
    if not config.skill_metadata:
        return None

    metadata = config.skill_metadata

    # No agent file needed if skill has no tool restrictions
    has_tool_restrictions = metadata.allowed_tools or metadata.disallowed_tools
    if not has_tool_restrictions:
        return None

    # Determine model (config override > skill default > no model line)
    model = config.model or metadata.default_model

    # Build agent file content
    agent_name = f"{config.skill_name}-worker"
    lines = ["---"]
    lines.append(f"name: {agent_name}")

    if metadata.description:
        lines.append(f"description: {metadata.description}")

    if metadata.allowed_tools:
        tools_str = ", ".join(metadata.allowed_tools)
        lines.append(f"tools: {tools_str}")

    if metadata.disallowed_tools:
        disallowed_str = ", ".join(metadata.disallowed_tools)
        lines.append(f"disallowedTools: {disallowed_str}")

    if model:
        lines.append(f"model: {model}")

    lines.append("---")
    lines.append("")  # Empty line after frontmatter

    content = "\n".join(lines)

    # Write to .claude/agents/{skill}-worker.md
    agents_dir = config.project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    agent_path = agents_dir / f"{agent_name}.md"
    agent_path.write_text(content)

    return agent_path


def show_preview(config: SpawnConfig) -> None:
    """
    Display spawn preview with configuration details.

    Shows:
    - Project and workspace info
    - Task description
    - Deliverables (with rendered paths)
    - Context sources
    - Estimated duration (if available)

    Args:
        config: Spawn configuration
    """
    import click

    # Header
    click.echo()
    click.echo("╭─ orch spawn " + "─" * 57 + "╮")
    click.echo("│" + " " * 70 + "│")

    # Project info
    click.echo(f"│ Project:    {config.project:<56} │")
    click.echo(f"│ Workspace:  {config.workspace_name:<56} │")

    if config.skill_name:
        emoji = get_emoji_for_skill(config.skill_name)
        skill_display = f"{emoji} {config.skill_name}"
        click.echo(f"│ Skill:      {skill_display:<56} │")

    click.echo("│" + " " * 70 + "│")

    # Task (wrap if needed)
    task_lines = _wrap_text(config.task, 60)
    if len(task_lines) == 1:
        click.echo(f"│ Task:       {task_lines[0]:<58} │")
    else:
        click.echo(f"│ Task:       {task_lines[0]:<58} │")
        for line in task_lines[1:]:
            click.echo(f"│             {line:<58} │")

    click.echo("│" + " " * 70 + "│")

    # Deliverables
    click.echo("│ Deliverables:" + " " * 57 + "│")
    deliverables = config.deliverables or DEFAULT_DELIVERABLES
    for d in deliverables:
        rendered_path = render_deliverable_path(d.path, config)
        marker = "✓" if d.required else "○"
        type_display = d.type.capitalize()

        # Truncate path if too long
        if len(rendered_path) > 45:
            rendered_path = "..." + rendered_path[-42:]

        click.echo(f"│   {marker} {type_display}:{' ' * (13 - len(type_display))}{rendered_path:<45} │")

    click.echo("│" + " " * 70 + "│")

    # Context
    click.echo("│ Context:" + " " * 62 + "│")
    click.echo(f"│   • PROJECT_DIR: {str(config.project_dir):<49} │")
    click.echo("│   • Global: ~/.claude/CLAUDE.md" + " " * 37 + "│")
    click.echo(f"│   • Project: {config.project}/.claude/CLAUDE.md{' ' * (31 - len(config.project))}│")
    click.echo("│   • CDD Essentials: orch-knowledge/docs/cdd-essentials.md      │")

    if config.skill_name:
        # Build hierarchical path if category known
        if config.skill_metadata and config.skill_metadata.category:
            skill_path = f"~/.claude/skills/{config.skill_metadata.category}/{config.skill_name}/SKILL.md"
        else:
            skill_path = f"~/.claude/skills/{config.skill_name}/SKILL.md"
        if len(skill_path) > 51:
            skill_path = "..." + skill_path[-48:]
        click.echo(f"│   • Process guide: {skill_path:<49} │")

    click.echo("│" + " " * 70 + "│")

    # Footer
    click.echo("╰" + "─" * 70 + "╯")
    click.echo()


def _wrap_text(text: str, width: int) -> List[str]:
    """
    Wrap text to specified width, breaking on word boundaries.

    Args:
        text: Text to wrap
        width: Maximum line width

    Returns:
        List of wrapped lines
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)

        if current_length + word_length + len(current_line) <= width:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(' '.join(current_line))

    return lines if lines else ['']


# Prompt building helpers imported from spawn_prompt:
# - get_verification_requirements
# - load_skill_content
# - load_spawn_prompt_template
# - fallback_template
# - build_spawn_prompt


def spawn_in_tmux(config: SpawnConfig, session_name: str = None) -> Dict[str, str]:
    """
    Spawn agent in tmux window with proper context.

    Uses per-project workers sessions (e.g., workers-orch-cli, workers-beads)
    instead of a single global 'workers' session.

    Args:
        config: Spawn configuration
        session_name: Tmux session name (derived from config.project if not provided)

    Returns:
        Dictionary with spawn info:
        - window: Window target (e.g., "workers-orch-cli:10")
        - window_name: Human-readable window name
        - agent_id: Unique agent identifier (workspace name)

    Raises:
        RuntimeError: If tmux not available or spawn fails
    """
    from orch.tmux_utils import is_tmux_available, find_session

    # Initialize logger
    orch_logger = OrchLogger()

    # Start timing
    start_time = time.time()

    # Derive per-project session name if not explicitly provided
    if session_name is None:
        session_name = get_workers_session_name(config.project)

    # Log spawn start
    orch_logger.log_command_start("spawn", {
        "task": config.task,
        "project": config.project,
        "workspace": config.workspace_name,
        "skill": config.skill_name or "none",
        "session": session_name
    })

    try:
        # Check tmux availability
        if not is_tmux_available():
            orch_logger.log_error("spawn", "Tmux not available", {
                "reason": "tmux command not found or not running"
            })
            raise RuntimeError("Tmux not available. Cannot spawn agent.")

        # Ensure per-project tmuxinator config exists
        ensure_tmuxinator_config(config.project, config.project_dir)

        # Start per-project workers session if not already running
        if not start_workers_session(config.project):
            orch_logger.log_error("spawn", "Failed to start workers session", {
                "session_name": session_name,
                "reason": "tmuxinator start failed"
            })
            raise RuntimeError(f"Failed to start workers session '{session_name}'.")

        # Verify session exists (should now be running)
        session = find_session(session_name)
        if not session:
            orch_logger.log_error("spawn", "Tmux session not found after start", {
                "session_name": session_name,
                "reason": f"session '{session_name}' does not exist"
            })
            raise RuntimeError(f"Tmux session '{session_name}' not found.")

        # Build window name with project context and optional beads ID
        window_name = build_window_name(
            workspace_name=config.workspace_name,
            project_dir=config.project_dir,
            skill_name=config.skill_name,
            beads_id=config.beads_id
        )

        # Build spawn prompt
        prompt = build_spawn_prompt(config)

        # Validate spawn context length - fail fast if context is too short
        # This catches incomplete templates, missing skill content, etc.
        validate_spawn_context_length(prompt, workspace_name=config.workspace_name)

        # Write full prompt to file (workaround for Claude Code display bug)
        # Bug: When agent loads a skill, Claude Code re-displays the initial CLI prompt
        # Solution: Write context to file, pass minimal CLI message instead
        workspace_path = config.project_dir / ".orch" / "workspace" / config.workspace_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        context_file = workspace_path / "SPAWN_CONTEXT.md"
        context_file.write_text(prompt)

        # Create minimal prompt that instructs agent to read context file
        minimal_prompt = (
            f"Read your spawn context from .orch/workspace/{config.workspace_name}/SPAWN_CONTEXT.md "
            f"and begin the task."
        )

        # Create detached window and get its index and ID
        # Use -d (detached), -P (print info), -F (format output)
        # Format: "index:id" (e.g., "10:@1008")
        # Note: -t only specifies session (not index) to let tmux fill gaps naturally
        create_window_cmd = [
            "tmux", "new-window",
            "-t", session_name,  # Only session, no explicit index - tmux fills gaps
            "-n", window_name,
            "-c", str(config.project_dir),
            "-d", "-P", "-F", "#{window_index}:#{window_id}"
        ]

        result = subprocess.run(create_window_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            orch_logger.log_error("spawn", "Failed to create tmux window", {
                "reason": result.stderr,
                "session_name": session_name,
                "window_name": window_name
            })
            raise RuntimeError(f"Failed to create tmux window: {result.stderr}")

        # Parse "index:id" output
        output = result.stdout.strip()
        window_index, window_id = output.split(':', 1)
        actual_window_target = f"{session_name}:{window_index}"

        # Send backend command with minimal prompt (full context in file)
        # Using CLI's built-in initial prompt support avoids paste mode timing issues
        # Reference: ~/.claude/docs/official/claude-code/cli-reference.md - `claude "query"`

        # Instantiate backend adapter based on config.backend field (defaults to "claude" from Phase 1)
        # Both ClaudeBackend and CodexBackend are now available (Phases 2-3 complete)
        if config.backend == "claude":
            backend = ClaudeBackend()
        elif config.backend == "codex":
            backend = CodexBackend()
        else:
            raise ValueError(f"Unsupported backend: {config.backend}. Supported backends: claude, codex")

        # Set context environment variables for spawned agent (backend-specific)
        workspace_abs = config.project_dir / ".orch" / "workspace" / config.workspace_name
        deliverables_list = ",".join(d.type for d in (config.deliverables or [])) if config.deliverables else "workspace"

        # Get backend-specific environment variables
        env_vars = backend.get_env_vars(config, workspace_abs, deliverables_list)
        env_exports = " && ".join(f"export {key}={shlex.quote(value)}" for key, value in env_vars.items()) + " && "

        # Build backend-specific command with options (model, etc.)
        backend_options = {}
        if config.model:
            backend_options['model'] = config.model
        backend_cmd = backend.build_command(minimal_prompt, backend_options if backend_options else None)
        full_cmd = f"{env_exports}{backend_cmd}"

        send_backend_cmd = [
            "tmux", "send-keys",
            "-t", actual_window_target,
            full_cmd
        ]
        subprocess.run(send_backend_cmd, check=True)

        # Send Enter to execute backend command
        subprocess.run([
            "tmux", "send-keys",
            "-t", actual_window_target,
            "Enter"
        ], check=True)

        # Wait for backend to start (intelligent polling instead of blocking sleep)
        # Allow override via environment variable for slow systems
        spawn_timeout = float(os.getenv("ORCH_SPAWN_TIMEOUT") or "15.0")
        if not backend.wait_for_ready(actual_window_target, timeout=spawn_timeout):
            orch_logger.log_error("spawn", f"{backend.name} backend failed to start within timeout", {
                "backend": backend.name,
                "window": actual_window_target,
                "timeout": spawn_timeout
            })
            raise RuntimeError(
                f"{backend.name.capitalize()} backend failed to start in window {actual_window_target} within {spawn_timeout} seconds. "
                f"Check tmux session manually for error messages. "
                f"Set ORCH_SPAWN_TIMEOUT to increase timeout if needed."
            )

        # Minimal prompt passed as CLI argument; full context available in SPAWN_CONTEXT.md

        # POST-SPAWN VALIDATION: Verify window still exists
        # (Catches cases where backend CLI fails to start or crashes immediately)
        from orch.tmux_utils import get_window_by_target
        if not get_window_by_target(actual_window_target):
            orch_logger.log_error("spawn", "Window closed immediately after creation", {
                "backend": backend.name,
                "window": actual_window_target,
                "reason": f"{backend.name} backend may have crashed or failed to start"
            })
            raise RuntimeError(
                f"Spawn failed: Window {actual_window_target} closed immediately after creation. "
                f"{backend.name.capitalize()} backend may have crashed or failed to start. "
                f"Check tmux session manually for error messages."
            )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log spawn complete
        orch_logger.log_command_complete("spawn", duration_ms, {
            "agent_id": config.workspace_name,
            "window": actual_window_target,
            "window_id": window_id,
            "project": config.project,
            "workspace": config.workspace_name
        })

        # Auto-focus the newly spawned window in the workers session
        # This allows the orchestrator to spawn from left window and immediately see
        # the new agent activate in the right window
        subprocess.run([
            "tmux", "select-window",
            "-t", actual_window_target
        ], check=False)  # Don't fail spawn if select fails

        # Switch workers Ghostty client to show this per-project session
        # This auto-switches the workers window when spawning for a different project
        # Use check_orchestrator_context=True to prevent race conditions when user
        # quickly switches orchestrator context after requesting spawn
        # Failure to switch is not fatal - just log and continue
        if not switch_workers_client(session_name, check_orchestrator_context=True):
            logger.debug(f"Could not switch workers client to {session_name} (no workers client attached or context changed?)")

        return {
            'window': actual_window_target,
            'window_id': window_id,  # Stable window ID for reliable cleanup
            'window_name': window_name,
            'agent_id': config.workspace_name  # Use workspace name as agent ID
        }

    except Exception as e:
        # Log any unhandled errors
        duration_ms = int((time.time() - start_time) * 1000)
        orch_logger.log_error("spawn", f"Spawn failed: {str(e)}", {
            "error_type": type(e).__name__,
            "workspace": config.workspace_name,
            "project": config.project,
            "duration_ms": duration_ms
        })
        raise


def spawn_with_opencode(config: SpawnConfig, server_url: Optional[str] = None) -> Dict[str, str]:
    """
    Spawn agent using OpenCode HTTP API instead of tmux.

    This is an alternative to spawn_in_tmux() that uses OpenCode's client-server
    architecture. Benefits:
    - No tmux dependency
    - Structured API responses
    - Real-time monitoring via SSE
    - Session management via HTTP

    Args:
        config: Spawn configuration
        server_url: OpenCode server URL (auto-discovers if not provided)

    Returns:
        Dictionary with spawn info:
        - session_id: OpenCode session ID
        - agent_id: Unique agent identifier (workspace name)
        - backend: "opencode"

    Raises:
        RuntimeError: If OpenCode server not available or spawn fails
    """
    from orch.backends.opencode import OpenCodeBackend, discover_server

    # Initialize logger
    orch_logger = OrchLogger()

    # Start timing
    start_time = time.time()

    # Log spawn start
    orch_logger.log_command_start("spawn", {
        "task": config.task,
        "project": config.project,
        "workspace": config.workspace_name,
        "skill": config.skill_name or "none",
        "backend": "opencode"
    })

    try:
        # Discover or use provided server URL
        url = server_url or discover_server()
        if not url:
            orch_logger.log_error("spawn", "OpenCode server not found", {
                "reason": "No running OpenCode server discovered"
            })
            raise RuntimeError(
                "OpenCode server not found. Start one with: "
                "cd ~/Documents/personal/opencode && bun run dev serve --port 4096"
            )

        # Initialize backend
        backend = OpenCodeBackend(url)

        # Verify server is responding
        if not backend.wait_for_ready("", timeout=5.0):
            orch_logger.log_error("spawn", "OpenCode server not responding", {
                "url": url
            })
            raise RuntimeError(f"OpenCode server at {url} not responding")

        # Build spawn prompt (same as tmux path)
        prompt = build_spawn_prompt(config)

        # Validate spawn context length - fail fast if context is too short
        # This catches incomplete templates, missing skill content, etc.
        validate_spawn_context_length(prompt, workspace_name=config.workspace_name)

        # Write full prompt to SPAWN_CONTEXT.md (same as tmux path)
        workspace_path = config.project_dir / ".orch" / "workspace" / config.workspace_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        context_file = workspace_path / "SPAWN_CONTEXT.md"
        context_file.write_text(prompt)

        # Create minimal prompt that instructs agent to read context file
        minimal_prompt = (
            f"Read your spawn context from .orch/workspace/{config.workspace_name}/SPAWN_CONTEXT.md "
            f"and begin the task."
        )

        # Spawn OpenCode session
        # Note: OpenCode's "build" agent = full access, "plan" = read-only
        agent_type = "build"  # Default to full access for worker agents

        # Resolve model for OpenCode
        # Default to Opus 4.5 if no model specified
        opencode_model = resolve_opencode_model(config.model)

        session = backend.spawn_session(
            prompt=minimal_prompt,
            directory=str(config.project_dir),
            agent=agent_type,
            async_mode=True,  # Return immediately while agent processes
            model=opencode_model
        )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log spawn complete
        orch_logger.log_command_complete("spawn", duration_ms, {
            "agent_id": config.workspace_name,
            "session_id": session.id,
            "project": config.project,
            "workspace": config.workspace_name,
            "backend": "opencode"
        })

        return {
            'session_id': session.id,
            'agent_id': config.workspace_name,
            'backend': 'opencode',
            'server_url': url
        }

    except Exception as e:
        # Log any unhandled errors
        duration_ms = int((time.time() - start_time) * 1000)
        orch_logger.log_error("spawn", f"OpenCode spawn failed: {str(e)}", {
            "error_type": type(e).__name__,
            "workspace": config.workspace_name,
            "project": config.project,
            "duration_ms": duration_ms,
            "backend": "opencode"
        })
        raise


# Auto-registration
def register_agent(
    agent_id: str,
    task: str,
    window: Optional[str],
    project_dir: Path,
    workspace_name: str,
    window_id: str = None,
    is_interactive: bool = False,
    skill_name: Optional[str] = None,
    primary_artifact: Optional[str] = None,
    backend: Optional[str] = None,
    session_id: Optional[str] = None,
    stashed: bool = False,
    feature_id: Optional[str] = None,
    beads_id: Optional[str] = None,
    beads_ids: Optional[List[str]] = None,
    beads_db_path: Optional[str] = None,
    origin_dir: Optional[Path] = None
) -> None:
    """
    Register agent in orch registry.

    Args:
        agent_id: Unique agent identifier
        task: Task description
        window: Tmux window target (e.g., "orchestrator:10"), None for non-tmux backends
        window_id: Stable tmux window ID (e.g., "@1008")
        project_dir: Project directory path
        workspace_name: Workspace directory name
        is_interactive: True for interactive sessions, False for autonomous agents
        backend: Backend type ('claude', 'codex', 'opencode')
        session_id: OpenCode session ID (for opencode backend)
        stashed: True if git changes were stashed before spawn
        feature_id: Feature ID from backlog.json for lifecycle tracking
        beads_id: Beads issue ID for lifecycle tracking (auto-close on complete)
        beads_ids: List of beads issue IDs for multi-issue spawns (all closed on complete)
        beads_db_path: Absolute path to beads db (for cross-repo spawning)
        origin_dir: Directory where spawn was invoked (for cross-repo workspace sync)

    Raises:
        ValueError: If agent_id already exists
    """
    from orch.registry import AgentRegistry

    # Initialize orch logger for structured logging
    orch_logger = OrchLogger()

    registry = AgentRegistry()

    # Build workspace relative path
    workspace_rel = f".orch/workspace/{workspace_name}"

    try:
        registry.register(
            agent_id=agent_id,
            task=task,
            window=window,
            window_id=window_id,
            project_dir=str(project_dir),
            workspace=workspace_rel,
            is_interactive=is_interactive,
            skill=skill_name,
            primary_artifact=primary_artifact,
            backend=backend,
            session_id=session_id,
            stashed=stashed,
            feature_id=feature_id,
            beads_id=beads_id,
            beads_ids=beads_ids,
            beads_db_path=beads_db_path,
            origin_dir=str(origin_dir) if origin_dir else None
        )

        # Log successful registration to orch logs
        orch_logger.log_event("register", f"Agent registered: {agent_id}", {
            "agent_id": agent_id,
            "window": window,
            "window_id": window_id,
            "project_dir": str(project_dir),
            "workspace": workspace_rel,
            "is_interactive": is_interactive,
            "skill": skill_name,
            "backend": backend,
            "feature_id": feature_id,
            "beads_id": beads_id,
            "beads_ids": beads_ids,
            "beads_db_path": beads_db_path
        }, level="INFO")

        if backend == "opencode":
            logger.info(f"Registered agent '{agent_id}' with OpenCode session {session_id}")
        else:
            logger.info(f"Registered agent '{agent_id}' at window {window} (ID: {window_id}) [interactive={is_interactive}]")

    except ValueError as e:
        # Log registration failure to orch logs (fixes spawn logging gap)
        # Previously, registration failures only went to stderr, not orch logs
        orch_logger.log_error("register", f"Registration failed: {agent_id}", {
            "agent_id": agent_id,
            "window": window,
            "project_dir": str(project_dir),
            "workspace": workspace_rel,
            "reason": str(e),
            "error_type": "ValueError"
        })
        raise  # Re-raise to preserve existing error handling


# Skill-Based Mode

def spawn_interactive(
    context: str,
    project: Optional[str] = None,
    yes: bool = False,
    resume: bool = False,
    backend: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, str]:
    """
    Spawn interactive session for human exploration.

    Creates tmux window with Claude CLI and full workspace tracking.
    Interactive sessions now use the same workspace tracking as autonomous agents,
    ensuring discussions and learnings are amnesia-resilient.

    Args:
        context: Starting context or question
        project: Project name (prompts if not provided)
        yes: Skip confirmation if True
        resume: Allow resuming existing workspace
        backend: AI backend to use (overrides config/default)
        model: Optional model to use (e.g., "sonnet", "opus", or full model name)

    Returns:
        Spawn result dictionary with window, window_name

    Raises:
        ValueError: If project not found
        RuntimeError: If spawn fails
    """
    import click
    import sys
    import os
    import time
    from orch.tmux_utils import is_tmux_available, find_session

    # Auto-detect non-interactive mode (TTY detection)
    is_interactive = sys.stdin.isatty()
    if not yes:
        # Skip confirmation if stdin is not a TTY (non-interactive mode)
        if not is_interactive:
            yes = True
        # Also check environment variable override
        elif os.getenv('ORCH_AUTO_CONFIRM') == '1':
            yes = True

    # Check backend - opencode not yet supported for interactive mode
    resolved_backend = get_backend(cli_backend=backend)
    if resolved_backend == "opencode":
        raise ValueError(
            "Interactive mode (-i) not yet supported with OpenCode backend.\n"
            "Use: orch spawn SKILL_NAME 'task' --backend opencode"
        )

    # Auto-detect or prompt for project if not provided
    if not project:
        # Try auto-detection from current directory first
        detected = detect_project_from_cwd()
        if detected:
            project, project_dir = detected
            click.echo(f"📍 Auto-detected project: {project}")
        elif not is_interactive:
            # Non-interactive mode - fail fast with actionable error
            available = list_available_projects()
            available_str = ', '.join(available[:10])
            if len(available) > 10:
                available_str += f", ... ({len(available)} total)"
            raise ValueError(
                f"--project required (auto-detection failed - no .orch/ directory found).\n"
                f"Available projects: {available_str}\n"
                f"Example: orch spawn -i \"context\" --project PROJECT_NAME"
            )
        else:
            # Interactive mode - prompt as usual
            project = click.prompt("Project name")
            project_dir = get_project_dir(project)
            if not project_dir:
                raise ValueError(format_project_not_found_error(project))
    else:
        # Explicit project provided - resolve it
        project_dir = get_project_dir(project)
        if not project_dir:
            raise ValueError(format_project_not_found_error(project, "--project"))

    # Create workspace for interactive session
    # Use descriptive slugified naming based on context (or timestamp fallback)
    from datetime import datetime

    if context and context.strip():
        # Generate descriptive name using same logic as skill-based spawns
        base_name = create_workspace_adhoc(context, skill_name=None, project_dir=project_dir)
        # Insert 'interactive-' before the date suffix
        # Format: slug-DDMMM -> slug-interactive-DDMMM
        # The date suffix is always 5 chars (e.g., "30nov")
        parts = base_name.rsplit('-', 1)  # Split on last hyphen
        if len(parts) == 2:
            slug_part = parts[0]
            date_suffix = parts[1]

            # Calculate available chars for context
            # Max length: 35, date: 5, interactive: 11, hyphens: 2 = 17 chars for slug
            max_length = 35
            available_chars = max_length - 5 - 11 - 2
            original_slug = slug_part

            # Truncate slug if needed to fit within limit
            slug_part = truncate_at_word_boundary(slug_part, available_chars)

            # Log if truncation occurred
            if len(slug_part) < len(original_slug):
                import click
                click.echo(f"ℹ️  Context truncated to fit 35-char limit: '{original_slug[:15]}...' → '{slug_part}'")

            workspace_name = f"{slug_part}-interactive-{date_suffix}"
        else:
            # Fallback: prepend interactive to entire name
            workspace_name = f"interactive-{base_name}"
    else:
        # Fallback to timestamp for empty context
        date_suffix = datetime.now().strftime("%d%b").lower()
        workspace_name = f"interactive-{date_suffix}"

    # Create workspace directory only (WORKSPACE.md no longer created - beads is source of truth)
    workspace_path = project_dir / ".orch" / "workspace" / workspace_name
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Check tmux availability
    if not is_tmux_available():
        raise RuntimeError("Tmux not available. Cannot spawn interactive session.")

    # Verify session exists
    try:
        from orch.config import get_tmux_session_default
        session_name = get_tmux_session_default()
    except Exception:
        session_name = "workers"
    session = find_session(session_name)
    if not session:
        raise RuntimeError(f"Tmux session '{session_name}' not found.")

    # Build window name with project context (interactive uses 💬 emoji via skill_name=None)
    window_name = build_window_name(
        workspace_name=workspace_name,
        project_dir=project_dir,
        skill_name=None,  # Uses default ⚙️ emoji, but we override to 💬 below
        beads_id=None
    )
    # Override emoji for interactive mode
    window_name = f"💬{window_name[1:]}"  # Replace first emoji with 💬

    # Capture origin_dir for cross-repo workspace sync
    origin_dir = Path.cwd().resolve()
    cross_repo = origin_dir != project_dir.resolve()

    # Build interactive prompt using standard workspace-tracked prompt
    # This ensures interactive sessions track their work in workspaces like autonomous agents
    config = SpawnConfig(
        task=context or "Interactive session",
        project=project,
        project_dir=project_dir,
        workspace_name=workspace_name,
        skill_name=None,  # Interactive mode has no predefined skill
        deliverables=None,  # Will use DEFAULT_DELIVERABLES (workspace only)
        backend=get_backend(cli_backend=backend),  # Phase 4: Backend configuration
        model=model,  # Model selection (e.g., "sonnet", "opus")
        origin_dir=origin_dir if cross_repo else None
    )
    prompt = build_spawn_prompt(config)

    # Note: Skip spawn context length validation for interactive mode
    # Interactive mode doesn't include embedded skill content, so contexts are
    # intentionally shorter. Validation is for skill-based spawns only.

    # Write full prompt to file (workaround for Claude Code display bug)
    # Bug: When agent loads a skill, Claude Code re-displays the initial CLI prompt
    # Solution: Write context to file, pass minimal CLI message instead
    context_file = workspace_path / "SPAWN_CONTEXT.md"
    context_file.write_text(prompt)

    # Create minimal prompt for interactive mode
    if context:
        minimal_prompt = (
            f"Read your spawn context from .orch/workspace/{workspace_name}/SPAWN_CONTEXT.md "
            f"and begin the interactive session."
        )
    else:
        minimal_prompt = None  # No initial prompt for empty context

    # Create detached window and get its index and ID
    # Note: -t only specifies session (not index) to let tmux fill gaps naturally
    create_window_cmd = [
        "tmux", "new-window",
        "-t", session_name,  # Only session, no explicit index - tmux fills gaps
        "-n", window_name,
        "-c", str(project_dir),
        "-d", "-P", "-F", "#{window_index}:#{window_id}"
    ]

    result = subprocess.run(create_window_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create tmux window: {result.stderr}")

    # Parse "index:id" output
    output = result.stdout.strip()
    window_index, window_id = output.split(':', 1)
    actual_window_target = f"{session_name}:{window_index}"

    # Send claude command with minimal prompt (full context in file)
    # Using CLI's built-in initial prompt support avoids paste mode timing issues
    # Reference: ~/.claude/docs/official/claude-code/cli-reference.md - `claude "query"`

    # Set context environment variables for spawned agent
    workspace_abs = project_dir / ".orch" / "workspace" / workspace_name

    env_exports = (
        f"export CLAUDE_CONTEXT=worker && "
        f"export CLAUDE_WORKSPACE={shlex.quote(str(workspace_abs))} && "
        f"export CLAUDE_PROJECT={shlex.quote(str(project_dir))} && "
        f"export CLAUDE_DELIVERABLES=workspace && "  # Interactive sessions always create workspace
    )

    if minimal_prompt:
        claude_cmd = f"{env_exports}~/.orch/scripts/claude-code-wrapper.sh --allowed-tools '*' --dangerously-skip-permissions {shlex.quote(minimal_prompt)}"
    else:
        claude_cmd = f"{env_exports}~/.orch/scripts/claude-code-wrapper.sh --allowed-tools '*' --dangerously-skip-permissions"

    send_claude_cmd = [
        "tmux", "send-keys",
        "-t", actual_window_target,
        claude_cmd
    ]
    subprocess.run(send_claude_cmd, check=True)

    # Send Enter to execute claude command
    subprocess.run([
        "tmux", "send-keys",
        "-t", actual_window_target,
        "Enter"
    ], check=True)

    # Wait for claude to start (intelligent polling instead of blocking sleep)
    # Allow override via environment variable for slow systems
    spawn_timeout = float(os.getenv("ORCH_SPAWN_TIMEOUT") or "15.0")
    backend = ClaudeBackend()
    if not backend.wait_for_ready(actual_window_target, timeout=spawn_timeout):
        raise RuntimeError(
            f"Claude failed to start in window {actual_window_target} within {spawn_timeout} seconds. "
            f"Check tmux session manually for error messages. "
            f"Set ORCH_SPAWN_TIMEOUT to increase timeout if needed."
        )

    # Minimal prompt passed as CLI argument; full context available in SPAWN_CONTEXT.md

    # POST-SPAWN VALIDATION: Verify window still exists
    from orch.tmux_utils import get_window_by_target
    if not get_window_by_target(actual_window_target):
        raise RuntimeError(
            f"Spawn failed: Window {actual_window_target} closed immediately after creation. "
            f"Claude Code may have crashed or failed to start."
        )

    # Register agent with is_interactive=True
    register_agent(
        agent_id=workspace_name,
        task=context or "Interactive session",
        window=actual_window_target,
        window_id=window_id,
        project_dir=project_dir,
        workspace_name=workspace_name,
        is_interactive=True,
        skill_name=None,
        origin_dir=config.origin_dir
    )

    # Auto-focus the newly spawned window
    subprocess.run([
        "tmux", "select-window",
        "-t", actual_window_target
    ], check=False)  # Don't fail spawn if select fails

    # Display connection info
    click.echo(f"\n✅ Interactive session ready: {window_name}")
    click.echo(f"   Window: {actual_window_target}")
    click.echo(f"   Project: {project_dir}")
    click.echo(f"\n   Attach with: tmux attach-session -t {session_name}")
    click.echo(f"   Or select window {window_index} in your tmux session\n")

    return {
        'window': actual_window_target,
        'window_id': window_id,
        'window_name': window_name,
        'agent_id': workspace_name
    }


def _display_dirty_state(dirty_state: Dict[str, List[str]]) -> None:
    """Display uncommitted changes to stderr."""
    import click

    click.echo("\n⚠️  Uncommitted changes detected in project:", err=True)
    if dirty_state['staged']:
        click.echo("  Staged:", err=True)
        for f in dirty_state['staged'][:5]:
            click.echo(f"    {f}", err=True)
        if len(dirty_state['staged']) > 5:
            click.echo(f"    ... and {len(dirty_state['staged']) - 5} more", err=True)
    if dirty_state['unstaged']:
        click.echo("  Modified:", err=True)
        for f in dirty_state['unstaged'][:5]:
            click.echo(f"    {f}", err=True)
        if len(dirty_state['unstaged']) > 5:
            click.echo(f"    ... and {len(dirty_state['unstaged']) - 5} more", err=True)


def _try_stash_changes(project_dir: Path, workspace_name: Optional[str]) -> bool:
    """Attempt to stash changes. Returns True if stashed successfully."""
    import click

    click.echo("\n📦 Stashing changes...", err=True)
    stash_msg = f"orch-spawn-{workspace_name or 'agent'}"
    if git_stash_changes(project_dir, stash_msg):
        click.echo("✓ Changes stashed (will auto-unstash on complete)", err=True)
        return True
    click.echo("⚠️  Stash failed, proceeding anyway", err=True)
    return False


def _handle_dirty_state_interactive(project_dir: Path, workspace_name: Optional[str]) -> bool:
    """Handle dirty git state interactively. Returns True if stashed, raises Abort on quit."""
    import click

    click.echo("\n⚠️  Agent may bundle these into its commits.", err=True)
    click.echo("Options:", err=True)
    click.echo("  1. Commit these first (recommended)", err=True)
    click.echo("  2. Stash temporarily (--stash)", err=True)
    click.echo("  3. Proceed anyway (--allow-dirty)", err=True)
    click.echo()

    choice = click.prompt("Choose", type=click.Choice(['1', '2', '3', 'q']), default='1')
    if choice == '1':
        click.echo("\nPlease commit your changes first, then re-run spawn.", err=True)
        raise click.Abort()
    elif choice == '2':
        return _try_stash_changes(project_dir, workspace_name)
    elif choice == '3':
        click.echo("\n⚠️  Proceeding with uncommitted changes", err=True)
        return False
    else:  # 'q'
        raise click.Abort()


def _handle_git_dirty_state(
    project_dir: Path,
    workspace_name: Optional[str],
    allow_dirty: bool,
    stash_requested: bool,
    is_interactive: bool,
    yes: bool
) -> bool:
    """
    Handle uncommitted git changes before spawn.

    Args:
        project_dir: Project directory path
        workspace_name: Workspace name for stash message
        allow_dirty: If True, skip dirty state check
        stash_requested: If True, auto-stash changes
        is_interactive: True if running interactively
        yes: True if confirmation should be skipped

    Returns:
        True if changes were stashed, False otherwise

    Raises:
        click.Abort: If user chooses to abort
    """
    import click

    if allow_dirty:
        return False

    dirty_state = check_git_dirty_state(project_dir)
    has_changes = dirty_state['staged'] or dirty_state['unstaged']

    if not has_changes:
        return False

    _display_dirty_state(dirty_state)

    if stash_requested:
        return _try_stash_changes(project_dir, workspace_name)

    if is_interactive and not yes:
        return _handle_dirty_state_interactive(project_dir, workspace_name)

    # Non-interactive without --allow-dirty - fail with guidance
    click.echo("\n❌ Cannot spawn with uncommitted changes in non-interactive mode.", err=True)
    click.echo("   Use --stash to stash changes, or --allow-dirty to proceed anyway.", err=True)
    raise click.Abort()


def spawn_with_skill(
    skill_name: str,
    task: str,
    project: Optional[str] = None,
    project_dir: Optional[Path] = None,
    workspace_name: Optional[str] = None,
    yes: bool = False,
    resume: bool = False,
    custom_prompt: Optional[str] = None,
    additional_context: Optional[str] = None,
    stdin_context: Optional[str] = None,
    phases: Optional[str] = None,
    mode: Optional[str] = None,
    validation: Optional[str] = None,
    phase_id: Optional[str] = None,
    depends_on: Optional[str] = None,
    investigation_type: Optional[str] = None,
    backend: Optional[str] = None,
    model: Optional[str] = None,
    stash: bool = False,
    allow_dirty: bool = True,
    feature_id: Optional[str] = None,
    interactive: bool = False,
    context_ref: Optional[str] = None,
    beads_id: Optional[str] = None,
    beads_ids: Optional[List[str]] = None,
    beads_db_path: Optional[str] = None,
    parallel: bool = False,
    include_agent_mail: bool = False
) -> Dict[str, str]:
    """
    Spawn agent with specific skill.

    Args:
        skill_name: Name of skill to use
        task: Task description
        project: Project name (prompts if not provided)
        project_dir: Project directory path (skips re-resolution if provided)
        workspace_name: Override workspace name (auto-generates if not provided)
        yes: Skip confirmation if True
        resume: Allow resuming existing workspace
        custom_prompt: Optional custom prompt to replace generated prompt
        additional_context: Optional context to incorporate into prompt (does not replace)
        stdin_context: Optional context from stdin/heredoc (added to ADDITIONAL CONTEXT section)
        phases: Comma-separated phases for feature-impl
        mode: Implementation mode (tdd or direct)
        validation: Validation level (none, tests, smoke-test, multi-phase)
        phase_id: Phase identifier for multi-phase work
        depends_on: Phase dependency
        investigation_type: Investigation type (systems, feasibility, audits, performance, agent-failures)
        backend: AI backend to use (overrides config/default)
        model: Optional model to use (e.g., "sonnet", "opus", or full model name)
        stash: If True, stash uncommitted changes before spawn
        beads_db_path: Absolute path to beads db (for cross-repo spawning)
        allow_dirty: If True, allow spawn with uncommitted changes without prompting
        feature_id: Feature ID from backlog.json for lifecycle tracking
        interactive: If True, skill operates in collaborative mode with Dylan
        beads_id: Beads issue ID for lifecycle tracking (primary issue)
        beads_ids: List of beads issue IDs for multi-issue spawns (all closed on complete)

    Returns:
        Spawn result dictionary with window, window_name, agent_id

    Raises:
        ValueError: If skill not found or project not found
        RuntimeError: If spawn fails
    """
    import click
    import sys
    import os

    # Auto-detect non-interactive mode (TTY detection)
    is_interactive = sys.stdin.isatty()
    if not yes:
        # Skip confirmation if stdin is not a TTY (non-interactive mode)
        if not is_interactive:
            yes = True
        # Also check environment variable override
        elif os.getenv('ORCH_AUTO_CONFIRM') == '1':
            yes = True

    # Check for deprecated skills first
    DEPRECATED_SKILLS = {
        'feature-coordination': 'feature-impl --phases "investigation,design,implementation,validation"',
        'test-driven-development': 'feature-impl --mode tdd',
        'surgical-change': 'feature-impl --mode direct',
        'executing-plans': 'writing-plans (for humans) or feature-impl --phases "design,implementation" (for AI)'
    }

    if skill_name in DEPRECATED_SKILLS:
        replacement = DEPRECATED_SKILLS[skill_name]
        raise ValueError(
            f"\nError: Skill '{skill_name}' has been removed (replaced 2025-11-18)\n\n"
            f"Replacement: {replacement}\n\n"
            f"See .orch/CLAUDE.md section \"Deprecated Skills\" for migration guide."
        )

    # Discover and validate skill
    skills = discover_skills()
    if skill_name not in skills:
        available = ', '.join(sorted(skills.keys())[:10])
        raise ValueError(f"Skill '{skill_name}' not found. Available: {available}...")

    skill_metadata = skills[skill_name]

    # Auto-detect or prompt for project if not provided
    if project and project_dir:
        # Both project name and directory provided - use them directly
        # This happens when caller already resolved the project (e.g., issue mode)
        click.echo(f"📍 Using project: {project}")
    elif not project:
        # Try auto-detection from current directory first
        detected = detect_project_from_cwd()
        if detected:
            project, project_dir = detected
            click.echo(f"📍 Auto-detected project: {project}")
        elif not is_interactive:
            # Non-interactive mode - fail fast with actionable error
            available = list_available_projects()
            available_str = ', '.join(available[:10])
            if len(available) > 10:
                available_str += f", ... ({len(available)} total)"
            raise ValueError(
                f"--project required (auto-detection failed - no .orch/ directory found).\n"
                f"Available projects: {available_str}\n"
                f"Example: orch spawn {skill_name} \"task description\" --project PROJECT_NAME"
            )
        else:
            # Interactive mode - prompt as usual
            project = click.prompt("Project name")
            project_dir = get_project_dir(project)
            if not project_dir:
                raise ValueError(format_project_not_found_error(project))
    else:
        # Explicit project name provided without directory - resolve it
        project_dir = get_project_dir(project)
        if not project_dir:
            raise ValueError(format_project_not_found_error(project, "--project"))

    # Git State Validation
    stashed = _handle_git_dirty_state(
        project_dir=project_dir,
        workspace_name=workspace_name,
        allow_dirty=allow_dirty,
        stash_requested=stash,
        is_interactive=is_interactive,
        yes=yes
    )

    # Generate or use provided workspace name
    if not workspace_name:
        workspace_name = create_workspace_adhoc(task, skill_name, project_dir)

    # Skip workspace for skills that produce investigation deliverables
    # (investigation, systematic-debugging, codebase-audit, etc.)
    has_investigation_deliverable = skill_metadata and any(
        d.type == "investigation" for d in (skill_metadata.deliverables or [])
    )
    skip_workspace = has_investigation_deliverable

    deliverables = list(skill_metadata.deliverables) if skill_metadata.deliverables else None

    # Capture origin_dir for cross-repo workspace sync
    origin_cwd = Path.cwd().resolve()
    cross_repo = origin_cwd != project_dir.resolve()

    # Build config
    config = SpawnConfig(
        task=task,
        project=project,
        project_dir=project_dir,
        workspace_name=workspace_name,
        skill_name=skill_name,
        deliverables=deliverables,
        custom_prompt=custom_prompt,
        additional_context=additional_context,  # Incorporated into prompt (not replacing)
        stdin_context=stdin_context,  # From heredoc/pipe (added to ADDITIONAL CONTEXT)
        skill_metadata=skill_metadata,  # Phase 3: Pass full metadata for verification
        # Phase 4: Feature-impl configuration
        phases=phases,
        mode=mode,
        validation=validation,
        phase_id=phase_id,
        depends_on=depends_on,
        # Investigation configuration
        investigation_type=investigation_type,
        # Backend configuration (Phase 4)
        backend=get_backend(cli_backend=backend),
        model=model,  # Model selection (e.g., "sonnet", "opus")
        beads_only=not skip_workspace,
        # Feature tracking (backlog.json integration)
        feature_id=feature_id,
        context_ref=context_ref,  # Design context file to include in spawn prompt
        # Interactive mode (collaborative design)
        interactive=interactive,
        # Beads integration
        beads_id=beads_id,
        beads_ids=beads_ids,
        beads_db_path=beads_db_path,
        # Parallel execution mode
        parallel=parallel,
        # Cross-repo spawning
        origin_dir=origin_cwd if cross_repo else None,
        # Agent Mail coordination (scope-aware)
        include_agent_mail=include_agent_mail
    )

    # Create workspace using integrated function (fixes PARTIAL state bug)
    # Heuristic nudges to avoid heavy skills for small tasks
    if skill_name == "systematic-debugging" and looks_trivial_bug(task):
        click.echo("\n⚠️  This looks like an obvious/localized failure.")
        click.echo("   'systematic-debugging' is thorough and heavier.")
        click.echo("   Consider 'quick-debugging' or 'feature-impl --mode direct' if the fix is trivial.")

    if skip_workspace and config.deliverables:
        config.deliverables = [d for d in config.deliverables if d.type != "workspace"]

    if not config.beads_only:
        config.primary_artifact = determine_primary_artifact(config)

    # Map skill name to workspace type (used when we DO create a workspace)
    workspace_type = (
        "investigation" if skill_name in ("systematic-debugging", "quick-debugging") else "implementation"
    )

    workspace_path = project_dir / ".orch" / "workspace" / workspace_name

    # Create workspace directory only (WORKSPACE.md no longer created - beads is source of truth)
    workspace_path.mkdir(parents=True, exist_ok=True)

    try:
        # Show preview
        show_preview(config)

        # Confirm
        if not yes:
            response = click.prompt("Proceed? [Y/n/edit]", default="Y", show_default=False)
            if response.lower() in ['n', 'no']:
                # Cleanup workspace
                if workspace_path.exists() and not resume:
                    import shutil
                    shutil.rmtree(workspace_path)
                click.echo("Spawn cancelled")
                return None

        # Spawn agent - dispatch based on backend
        if config.backend == "opencode":
            spawn_info = spawn_with_opencode(config)

            # Register agent with opencode-specific info
            register_agent(
                agent_id=spawn_info['agent_id'],
                task=config.task,
                window=None,  # No tmux window for opencode
                window_id=None,
                project_dir=config.project_dir,
                workspace_name=config.workspace_name,
                skill_name=config.skill_name,
                primary_artifact=str(config.primary_artifact) if config.primary_artifact else None,
                backend="opencode",
                session_id=spawn_info.get('session_id'),
                stashed=stashed,
                feature_id=config.feature_id,
                beads_id=config.beads_id,
                beads_ids=config.beads_ids,
                beads_db_path=config.beads_db_path,
                origin_dir=config.origin_dir
            )

            click.echo(f"\n✅ Spawned (OpenCode): {config.workspace_name}")
            click.echo(f"   Session: {spawn_info['session_id']}")
            click.echo(f"   Server: {spawn_info.get('server_url', 'auto-discovered')}")
            click.echo(f"   Workspace: {workspace_name}")
            if stashed:
                click.echo(f"   ⚠️  Git changes stashed (will auto-unstash on complete)")
        else:
            # tmux-based backends (claude, codex)
            spawn_info = spawn_in_tmux(config)

            # Register agent
            register_agent(
                agent_id=spawn_info['agent_id'],
                task=config.task,
                window=spawn_info['window'],
                window_id=spawn_info['window_id'],
                project_dir=config.project_dir,
                workspace_name=config.workspace_name,
                skill_name=config.skill_name,
                primary_artifact=str(config.primary_artifact) if config.primary_artifact else None,
                stashed=stashed,
                feature_id=config.feature_id,
                beads_id=config.beads_id,
                beads_ids=config.beads_ids,
                beads_db_path=config.beads_db_path,
                origin_dir=config.origin_dir
            )

            click.echo(f"\n✅ Spawned: {spawn_info['window_name']}")
            click.echo(f"   Window: {spawn_info['window']}")
            click.echo(f"   Workspace: {workspace_name}")
            if stashed:
                click.echo(f"   ⚠️  Git changes stashed (will auto-unstash on complete)")

        # Update beads issue with workspace link and agent metadata if spawned from beads
        if config.beads_id:
            try:
                from orch.beads_integration import BeadsIntegration
                beads = BeadsIntegration(db_path=config.beads_db_path)
                workspace_rel = f".orch/workspace/{config.workspace_name}"
                beads.add_workspace_link(config.beads_id, workspace_rel)

                # Phase 1 of registry removal: store agent metadata in beads
                # This enables future lookups without the JSON registry file
                window_id = spawn_info.get('window_id')
                if window_id:
                    beads.add_agent_metadata(
                        issue_id=config.beads_id,
                        agent_id=config.workspace_name,
                        window_id=window_id,
                        skill=config.skill_name,
                        project_dir=str(config.project_dir)
                    )
                    click.echo(f"   Beads: {config.beads_id} → agent metadata stored")
                else:
                    click.echo(f"   Beads: {config.beads_id} → workspace linked")
            except Exception as e:
                # Don't fail spawn if beads update fails
                click.echo(f"   ⚠️  Could not update beads issue: {e}", err=True)

        return spawn_info

    except Exception as e:
        # Keep workspace on error for debugging
        logger.error(f"Spawn failed: {e}")
        raise
