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
import functools
import os
import shlex

from orch.workspace import create_workspace, WorkspaceValidationError, truncate_at_word_boundary
from orch.workspace_naming import (
    STOP_WORDS,
    SKILL_PREFIXES,
    SKILL_EMOJIS,
    extract_meaningful_words,
    create_workspace_adhoc,
    get_emoji_for_skill
)
from orch.logging import OrchLogger
from orch.roadmap import RoadmapItem, find_roadmap_item, parse_roadmap_file_cached
from orch.roadmap_utils import parse_roadmap, detect_project_roadmap as detect_roadmap_utils
from orch.backends import ClaudeBackend, CodexBackend
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

logger = logging.getLogger(__name__)


# ========== Git State Validation ==========

def check_git_dirty_state(project_dir: Path) -> Dict[str, List[str]]:
    """
    Check if the project directory has uncommitted changes.

    Args:
        project_dir: Path to the project directory

    Returns:
        Dictionary with 'staged', 'unstaged', and 'untracked' file lists.
        Empty lists mean clean state.
    """
    result = {
        'staged': [],
        'unstaged': [],
        'untracked': []
    }

    try:
        # Check if it's a git repo
        git_check = subprocess.run(
            ['git', '-C', str(project_dir), 'rev-parse', '--git-dir'],
            capture_output=True, text=True
        )
        if git_check.returncode != 0:
            return result  # Not a git repo, nothing to check

        # Get porcelain status (machine-readable)
        status = subprocess.run(
            ['git', '-C', str(project_dir), 'status', '--porcelain'],
            capture_output=True, text=True
        )

        for line in status.stdout.rstrip('\n').split('\n'):
            if not line:
                continue
            # Format: XY filename (X=staged, Y=unstaged)
            # ?? = untracked, M = modified, A = added, D = deleted
            index_status = line[0] if len(line) > 0 else ' '
            worktree_status = line[1] if len(line) > 1 else ' '
            filename = line[3:] if len(line) > 3 else ''

            if index_status == '?' and worktree_status == '?':
                result['untracked'].append(filename)
            else:
                if index_status not in (' ', '?'):
                    result['staged'].append(filename)
                if worktree_status not in (' ', '?'):
                    result['unstaged'].append(filename)

    except Exception as e:
        logger.warning(f"Failed to check git status: {e}")

    return result


def git_stash_changes(project_dir: Path, message: str = "orch-spawn-stash") -> bool:
    """
    Stash uncommitted changes in the project directory.

    Args:
        project_dir: Path to the project directory
        message: Stash message for identification

    Returns:
        True if stash was created, False if nothing to stash or error
    """
    try:
        # Include untracked files in stash
        result = subprocess.run(
            ['git', '-C', str(project_dir), 'stash', 'push', '-u', '-m', message],
            capture_output=True, text=True
        )
        # "No local changes to save" means nothing was stashed
        if 'No local changes' in result.stdout or 'No local changes' in result.stderr:
            return False
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to stash changes: {e}")
        return False


def git_stash_pop(project_dir: Path) -> bool:
    """
    Pop the most recent stash in the project directory.

    Args:
        project_dir: Path to the project directory

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', '-C', str(project_dir), 'stash', 'pop'],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to pop stash: {e}")
        return False


# ========== OpenCode Model Resolution ==========

# Default model for OpenCode spawns
OPENCODE_DEFAULT_MODEL = {
    "providerID": "anthropic",
    "modelID": "claude-opus-4-5-20251101"
}

# Model shorthand aliases for convenience
# Model IDs from OpenCode's anthropic provider
OPENCODE_MODEL_ALIASES = {
    # Opus variants
    "opus": {"providerID": "anthropic", "modelID": "claude-opus-4-5-20251101"},
    "opus-4.5": {"providerID": "anthropic", "modelID": "claude-opus-4-5-20251101"},
    "opus-4-5": {"providerID": "anthropic", "modelID": "claude-opus-4-5-20251101"},
    # Sonnet variants
    "sonnet": {"providerID": "anthropic", "modelID": "claude-sonnet-4-5-20250929"},
    "sonnet-4.5": {"providerID": "anthropic", "modelID": "claude-sonnet-4-5-20250929"},
    "sonnet-4-5": {"providerID": "anthropic", "modelID": "claude-sonnet-4-5-20250929"},
    # Haiku variants
    "haiku": {"providerID": "anthropic", "modelID": "claude-haiku-4-5-20251001"},
    "haiku-4.5": {"providerID": "anthropic", "modelID": "claude-haiku-4-5-20251001"},
}


def resolve_opencode_model(model_spec: Optional[str]) -> Dict[str, str]:
    """
    Resolve model specification to OpenCode format.

    Args:
        model_spec: Model name (e.g., "opus", "sonnet", "claude-opus-4-5-20250929")
                   or None for default

    Returns:
        Dictionary with providerID and modelID for OpenCode API
    """
    if not model_spec:
        return OPENCODE_DEFAULT_MODEL

    # Check aliases first
    if model_spec.lower() in OPENCODE_MODEL_ALIASES:
        return OPENCODE_MODEL_ALIASES[model_spec.lower()]

    # If it looks like a full model ID, use it directly with anthropic provider
    if "claude" in model_spec.lower():
        return {"providerID": "anthropic", "modelID": model_spec}

    # For other providers/models, assume format is "provider/model" or just model
    if "/" in model_spec:
        provider, model = model_spec.split("/", 1)
        return {"providerID": provider, "modelID": model}

    # Default: assume anthropic provider
    return {"providerID": "anthropic", "modelID": model_spec}


def wait_for_claude_ready(window_target: str, timeout: float = 15.0) -> bool:
    """
    Poll tmux pane for Claude to be ready instead of hardcoded sleep.

    Checks for Claude prompt indicators in pane content with short polling intervals.
    This is significantly faster than hardcoded sleeps while being more reliable.

    Args:
        window_target: Tmux window target (e.g., "session:1")
        timeout: Maximum wait time in seconds (default: 5.0)

    Returns:
        True if Claude prompt detected, False if timeout reached
    """
    # Escape hatch for environments where Claude's tmux output no longer
    # matches the expected ready prompt patterns. When set, we skip prompt
    # probing entirely and assume success after a short grace period.
    if os.getenv("ORCH_SKIP_CLAUDE_READY") == "1":
        time.sleep(1.0)
        return True

    start = time.time()

    while (time.time() - start) < timeout:
        try:
            # Capture pane content to check for Claude prompt
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", window_target, "-p"],
                capture_output=True,
                text=True,
                timeout=1.0
            )

            # Check for Claude prompt indicators in output
            # Note: Based on actual Claude Code output patterns (verified from tmux panes)
            # Actual output: "✽ Sublimating…" → separator lines "─────" → "> Try 'refactor ui.py'"
            output_lower = result.stdout.lower()

            # Skip if still in loading state (Sublimating)
            if "sublimating" in output_lower:
                continue  # Not ready yet, keep polling

            # Check for actual Claude Code ready indicators
            if any(indicator in output_lower for indicator in [
                "> try",              # Prompt with suggestion (e.g., "> Try 'refactor ui.py'")
                "─────",              # Separator lines (frame around prompt)
            ]):
                return True

        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            # Ignore subprocess errors and continue polling
            pass

        # Short polling interval (100ms)
        time.sleep(0.1)

    # Timeout reached without detecting Claude
    return False


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
    requires_workspace: bool = True  # Whether WORKSPACE.md is the coordination artifact
    primary_artifact: Optional[Path] = None  # Path to coordination artifact when not using workspace
    # Feature tracking (backlog.json integration)
    feature_id: Optional[str] = None  # Feature ID from backlog.json for lifecycle tracking
    context_ref: Optional[str] = None  # Path to context file (design doc, investigation) to include in spawn prompt
    # Interactive mode (for collaborative design work)
    interactive: bool = False  # If True, skill operates in collaborative mode with Dylan
    # Beads integration
    beads_id: Optional[str] = None  # Beads issue ID for lifecycle tracking
    # Additional context (incorporated into prompt, does NOT replace it)
    # Use this for beads issue context or other supplementary information
    # Contrast with custom_prompt which replaces the entire generated prompt
    additional_context: Optional[str] = None


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


# Heuristics
def looks_small_change(text: str) -> bool:
    """
    Heuristic: does the task look like a small/surgical change?

    Signals 'small' when:
    - Contains common quick-change keywords (typo, rename, docs, format, lint, bump, minor, one-liner)
    - Mentions single-file scope
    - Very short task description (<= 10 words) without "design/architecture" indicators
    """
    if not text:
        return False

    t = text.lower()

    # Obvious large/complex indicators
    large_indicators = [
        "architecture", "architect", "design", "multi-day", "multi step", "multi-step",
        "end-to-end", "across modules", "across services", "system", "component",
        "schema migration", "migration", "integration plan", "roadmap",
    ]
    if any(k in t for k in large_indicators):
        return False

    small_indicators = [
        "typo", "rename", "minor", "quick", "one-liner", "oneliner", "small",
        "single file", "single-file", "docs", "documentation", "readme", "changelog",
        "comment", "format", "formatting", "lint", "linter", "bump version", "version bump",
        "config", "configuration", "log message", "logging",
    ]
    if any(k in t for k in small_indicators):
        return True

    # Length-based fallback
    words = re.findall(r"\b\w+\b", t)
    return len(words) <= 10


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
        if deliverable.type == "investigation":
            rendered = render_deliverable_path(deliverable.path, config)
            return Path(rendered)

    return None


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
    click.echo("│   • CDD Essentials: meta-orchestration/docs/cdd-essentials.md  │")

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


def spawn_in_tmux(config: SpawnConfig, session_name: str = "workers") -> Dict[str, str]:
    """
    Spawn agent in tmux window with proper context.

    Args:
        config: Spawn configuration
        session_name: Tmux session name (default: "workers")

    Returns:
        Dictionary with spawn info:
        - window: Window target (e.g., "workers:10")
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

    # Log spawn start
    orch_logger.log_command_start("spawn", {
        "task": config.task,
        "project": config.project,
        "workspace": config.workspace_name,
        "skill": config.skill_name or "none"
    })

    try:
        # Check tmux availability
        if not is_tmux_available():
            orch_logger.log_error("spawn", "Tmux not available", {
                "reason": "tmux command not found or not running"
            })
            raise RuntimeError("Tmux not available. Cannot spawn agent.")

        # Verify session exists
        session = find_session(session_name)
        if not session:
            orch_logger.log_error("spawn", "Tmux session not found", {
                "session_name": session_name,
                "reason": f"session '{session_name}' does not exist"
            })
            raise RuntimeError(f"Tmux session '{session_name}' not found.")

        # Build window name with emoji
        emoji = get_emoji_for_skill(config.skill_name)
        window_name = f"{emoji} worker: {config.workspace_name}"

        # Build spawn prompt
        prompt = build_spawn_prompt(config)

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
    feature_id: Optional[str] = None
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
            feature_id=feature_id
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
            "feature_id": feature_id
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


# ROADMAP Mode
# NOTE: RoadmapItem, find_roadmap_item, and parse_roadmap_file_cached now imported from orch.roadmap

def spawn_from_roadmap(title: str, yes: bool = False, resume: bool = False, backend: Optional[str] = None, skill_name_override: Optional[str] = None, model: Optional[str] = None) -> Dict[str, str]:
    """
    Spawn agent from ROADMAP item.

    Args:
        title: ROADMAP item title to search for
        yes: Skip confirmation if True
        resume: Resume existing workspace instead of failing
        backend: AI backend to use (overrides config/default)
        skill_name_override: Optional skill name to override ROADMAP :Skill: property
        model: Optional model to use (e.g., "sonnet", "opus", or full model name)

    Returns:
        Spawn result dictionary with window, window_name, agent_id

    Raises:
        ValueError: If ROADMAP item not found or missing required properties
        RuntimeError: If spawn fails
    """
    import click
    import sys
    import os

    # Auto-detect non-interactive mode (TTY detection)
    if not yes:
        # Skip confirmation if stdin is not a TTY (non-interactive mode)
        if not sys.stdin.isatty():
            yes = True
        # Also check environment variable override
        elif os.getenv('ORCH_AUTO_CONFIRM') == '1':
            yes = True

    # Detect project-scoped ROADMAP (check .orch/ROADMAP.org in current dir or parents)
    project_roadmap = detect_project_roadmap()

    # Find ROADMAP item (use project ROADMAP if in project context, else meta-orchestration)
    item = find_roadmap_item(title, roadmap_path=project_roadmap)
    if not item:
        roadmap_context = "project ROADMAP" if project_roadmap else "meta-orchestration ROADMAP"
        raise ValueError(f"ROADMAP item not found in {roadmap_context}: '{title}'")

    # Extract required properties
    workspace_name = item.properties.get('Workspace')
    project = item.properties.get('Project')

    if not workspace_name:
        raise ValueError(f"ROADMAP item '{title}' missing :Workspace: property")
    if not project:
        raise ValueError(f"ROADMAP item '{title}' missing :Project: property")

    # Get project directory from active-projects.md
    project_dir = get_project_dir(project)
    if not project_dir:
        raise ValueError(format_project_not_found_error(project, "ROADMAP :Project: property"))

    # Get skill name (override takes precedence over ROADMAP property)
    skill_name = skill_name_override if skill_name_override else item.properties.get('Skill')

    # Get deliverables from skill if specified
    deliverables = None
    skill_metadata = None
    if skill_name:
        skills = discover_skills()
        if skill_name in skills:
            skill_metadata = skills[skill_name]  # Phase 3: Get full metadata
            deliverables = skill_metadata.deliverables

    # Skip workspace for investigation-category skills (investigation, systematic-debugging, codebase-audit)
    skip_workspace = skill_metadata and skill_metadata.category == "investigation"

    deliverables_list = list(deliverables) if deliverables else None

    # Build config
    # Use title for task (clean, concise)
    # Use full description for roadmap_context (all Context/Problem/Solution sections)
    # This provides complete context so agents don't need to read ROADMAP file
    # Investigation: .orch/investigations/2025-11-15-fix-orch-spawn-from-roadmap.md
    roadmap_context = f"From ROADMAP: {item.title}"
    if item.description:
        roadmap_context += f"\n\n{item.description}"

    config = SpawnConfig(
        task=item.title,
        project=project,
        project_dir=project_dir,
        workspace_name=workspace_name,
        skill_name=skill_name,
        deliverables=deliverables_list,
        roadmap_context=roadmap_context,
        skill_metadata=skill_metadata,  # Phase 3: Pass full metadata for verification
        backend=get_backend(cli_backend=backend),  # Phase 4: Backend configuration
        model=model,  # Model selection (e.g., "sonnet", "opus")
        requires_workspace=not skip_workspace
    )

    workspace_path = project_dir / ".orch" / "workspace" / workspace_name

    # Create workspace using integrated function (fixes PARTIAL state bug)
    if skip_workspace:
        workspace_path.mkdir(parents=True, exist_ok=True)
    else:
        try:
            workspace_info = create_workspace(
                workspace_name=workspace_name,
                project_dir=project_dir,
                workspace_type="planning",  # ROADMAP items are typically planning work
                owner=None,  # Auto-detect from git config
                resume=resume  # Allow resuming existing workspace
            )
            workspace_file = workspace_path / "WORKSPACE.md"

            # VERIFY file actually exists before proceeding (prevents race condition bug)
            if not workspace_file.exists():
                raise RuntimeError(
                    f"Workspace creation claimed success but file doesn't exist: {workspace_file}\n"
                    f"This may indicate a race condition or filesystem issue."
                )
        except WorkspaceValidationError as e:
            click.echo(f"⚠️  Workspace creation failed: {e}", err=True)
            raise

    try:
        # For investigation skill, hide workspace deliverable from preview (no-workspace path)
        if skip_workspace and config.deliverables:
            config.deliverables = [d for d in config.deliverables if d.type != "workspace"]

        if not config.requires_workspace:
            config.primary_artifact = determine_primary_artifact(config)

        # Show preview
        show_preview(config)

        # Confirm
        if not yes:
            response = click.prompt("Proceed? [Y/n/edit]", default="Y", show_default=False)
            if response.lower() in ['n', 'no']:
                # Cleanup workspace (only remove directories we created)
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
                session_id=spawn_info.get('session_id')
            )

            click.echo(f"\n✅ Spawned (OpenCode): {config.workspace_name}")
            click.echo(f"   Session: {spawn_info['session_id']}")
            click.echo(f"   Server: {spawn_info.get('server_url', 'auto-discovered')}")
            click.echo(f"   Workspace: {workspace_name}")
        else:
            # tmux-based backends (claude, codex)
            spawn_info = spawn_in_tmux(config)

            # Register agent (workspace may not exist for pure investigation skill)
            register_agent(
                agent_id=spawn_info['agent_id'],
                task=config.task,
                window=spawn_info['window'],
                window_id=spawn_info['window_id'],
                project_dir=config.project_dir,
                workspace_name=config.workspace_name,
                skill_name=config.skill_name,
                primary_artifact=str(config.primary_artifact) if config.primary_artifact else None
            )

            click.echo(f"\n✅ Spawned: {spawn_info['window_name']}")
            click.echo(f"   Window: {spawn_info['window']}")
            click.echo(f"   Workspace: {workspace_name}")

        return spawn_info

    except Exception as e:
        # Keep workspace on error for debugging
        logger.error(f"Spawn failed: {e}")
        raise


def detect_project_roadmap() -> Optional[Path]:
    """
    Detect if we're in a project context with its own ROADMAP file.

    Searches current directory and parents for .orch/ROADMAP.{md,org}.
    Delegates to roadmap_utils for format-agnostic detection.

    Returns:
        Path to project ROADMAP if found, None otherwise
    """
    return detect_roadmap_utils()


# Skill-Based Mode

# Active Projects Parsing (with caching)
def _get_active_projects_file() -> Optional[Path]:
    """
    Locate the active-projects.md file.

    Returns:
        Path to active-projects.md if found, None otherwise
    """
    # Prefer default under home (patched in tests)
    active_projects_file = Path.home() / "meta-orchestration" / ".orch" / "active-projects.md"
    if not active_projects_file.exists():
        try:
            from orch.config import get_active_projects_file
            cfg_file = get_active_projects_file()
            if cfg_file.exists():
                active_projects_file = cfg_file
        except Exception:
            pass

    return active_projects_file if active_projects_file.exists() else None


@functools.lru_cache(maxsize=1)
def _parse_active_projects(file_path: str, file_mtime: float) -> Dict[str, Path]:
    """
    Parse active-projects.md and return mapping of project names to paths.

    Args:
        file_path: Path to active-projects.md (as string for cache key)
        file_mtime: Modification time (for cache invalidation)

    Returns:
        Dictionary mapping project name to resolved Path
    """
    projects = {}
    current_project = None

    with open(file_path, 'r') as f:
        for line in f:
            # Project names are headers: ## project-name
            if line.strip().startswith('## '):
                project_name = line.strip()[3:].strip()
                # Skip meta-sections
                if project_name.lower() not in ['instructions', 'inactive projects', 'active projects']:
                    current_project = project_name
            # Extract path for current project
            elif current_project and '**Path:**' in line:
                if '`' in line:
                    path_part = line.split('`')[1].strip()
                    projects[current_project] = Path(path_part).expanduser()
                    current_project = None  # Reset after finding path

    return projects


def get_project_dir(project_name_or_path: str) -> Optional[Path]:
    """
    Get project directory from active-projects.md (cached).

    Accepts either a project name or full path for flexibility with AI agents.

    Args:
        project_name_or_path: Either:
          - Project name (e.g., "price-watch")
          - Full path (e.g., "/Users/.../price-watch")
          - Tilde path (e.g., "~/Documents/.../price-watch")
          - Relative path (e.g., ".", "..", "./subdir")

    Returns:
        Path to project directory or None if not found
    """
    active_projects_file = _get_active_projects_file()
    if not active_projects_file:
        return None

    # Get cached projects (with mtime-based invalidation)
    try:
        mtime = os.path.getmtime(active_projects_file)
    except (OSError, FileNotFoundError):
        return None

    projects = _parse_active_projects(str(active_projects_file), mtime)

    # If input looks like a path (contains / or is . or ..), try to match by resolved path first
    if '/' in project_name_or_path or project_name_or_path in ('.', '..'):
        try:
            input_path = Path(project_name_or_path).expanduser().resolve()
            # Match by resolved path
            for project_name, project_path in projects.items():
                if project_path.resolve() == input_path:
                    return project_path
        except Exception:
            # Invalid path, fall through to name matching
            pass

    # Fall back to name matching (case-insensitive)
    for project_name, project_path in projects.items():
        if project_name.lower() == project_name_or_path.lower():
            return project_path

    return None


def list_available_projects() -> List[str]:
    """
    List all available project names from active-projects.md (cached).

    Returns:
        List of project names (empty list if file doesn't exist or has no projects)
    """
    active_projects_file = _get_active_projects_file()
    if not active_projects_file:
        return []

    # Get cached projects (with mtime-based invalidation)
    try:
        mtime = os.path.getmtime(active_projects_file)
    except (OSError, FileNotFoundError):
        return []

    projects = _parse_active_projects(str(active_projects_file), mtime)
    return list(projects.keys())


def format_project_not_found_error(project_name: str, context: str = "") -> str:
    """
    Format a helpful "project not found" error message with available projects.

    Args:
        project_name: The project name that wasn't found
        context: Optional context about where the project was specified (e.g., "--project", "ROADMAP :Project:")

    Returns:
        Formatted error message with available projects listed
    """
    available = list_available_projects()
    if available:
        available_str = ', '.join(available[:10])
        if len(available) > 10:
            available_str += f", ... ({len(available)} total)"
        hint = f"\nAvailable projects: {available_str}"
    else:
        hint = "\nNo projects found in ~/.claude/active-projects.md"

    source = f" (from {context})" if context else ""
    return f"❌ Project '{project_name}' not found{source}.{hint}"


def detect_project_from_cwd() -> Optional[tuple]:
    """
    Auto-detect project from current working directory.

    Walks up directory tree looking for .orch/ directory, then matches
    against active-projects.md to get canonical project name.

    Returns:
        Tuple of (project_name, project_dir) if detected, None otherwise.
        If project has .orch/ but isn't in active-projects.md, returns
        (directory_name, project_dir) as fallback.
    """
    from orch.path_utils import find_orch_root

    # Find project root by looking for .orch/ directory
    project_root = find_orch_root()
    if not project_root:
        return None

    project_dir = Path(project_root)

    # Try to find matching project in active-projects.md
    # get_project_dir accepts paths and matches by resolved path
    matched_dir = get_project_dir(str(project_dir))
    if matched_dir:
        # Found in active-projects.md - get the canonical project name
        active_projects_file = _get_active_projects_file()
        if active_projects_file:
            try:
                mtime = os.path.getmtime(active_projects_file)
                projects = _parse_active_projects(str(active_projects_file), mtime)
                # Find project name by path match
                for name, path in projects.items():
                    if path.resolve() == matched_dir.resolve():
                        return (name, matched_dir)
            except (OSError, FileNotFoundError):
                pass

    # Fallback: project has .orch/ but isn't in active-projects.md
    # Use directory name as project identifier
    return (project_dir.name, project_dir)


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
            "Use: orch spawn SKILL_NAME 'task' --backend opencode\n"
            "Or: orch spawn --from-roadmap 'Item' --backend opencode"
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

    try:
        workspace_info = create_workspace(
            workspace_name=workspace_name,
            project_dir=project_dir,
            workspace_type="planning",  # Interactive sessions use planning template
            owner=None,  # Auto-detect from git config
            resume=resume  # Allow resuming existing workspace
        )
        workspace_path = project_dir / ".orch" / "workspace" / workspace_name
        workspace_file = workspace_path / "WORKSPACE.md"

        # VERIFY file actually exists before proceeding (prevents race condition bug)
        if not workspace_file.exists():
            raise RuntimeError(
                f"Workspace creation claimed success but file doesn't exist: {workspace_file}\n"
                f"This may indicate a race condition or filesystem issue."
            )
    except WorkspaceValidationError as e:
        click.echo(f"⚠️  Workspace creation failed: {e}", err=True)
        raise

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

    # Build window name with 💬 emoji (use workspace_name for consistency with agent ID)
    window_name = f"💬 {workspace_name}"

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
        model=model  # Model selection (e.g., "sonnet", "opus")
    )
    prompt = build_spawn_prompt(config)

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
    if not wait_for_claude_ready(actual_window_target, timeout=spawn_timeout):
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
        skill_name=None
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
    workspace_name: Optional[str] = None,
    yes: bool = False,
    resume: bool = False,
    custom_prompt: Optional[str] = None,
    additional_context: Optional[str] = None,
    phases: Optional[str] = None,
    mode: Optional[str] = None,
    validation: Optional[str] = None,
    phase_id: Optional[str] = None,
    depends_on: Optional[str] = None,
    investigation_type: Optional[str] = None,
    backend: Optional[str] = None,
    model: Optional[str] = None,
    stash: bool = False,
    allow_dirty: bool = False,
    feature_id: Optional[str] = None,
    interactive: bool = False,
    context_ref: Optional[str] = None,
    beads_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Spawn agent with specific skill.

    Args:
        skill_name: Name of skill to use
        task: Task description
        project: Project name (prompts if not provided)
        workspace_name: Override workspace name (auto-generates if not provided)
        yes: Skip confirmation if True
        resume: Allow resuming existing workspace
        custom_prompt: Optional custom prompt to replace generated prompt
        additional_context: Optional context to incorporate into prompt (does not replace)
        phases: Comma-separated phases for feature-impl
        mode: Implementation mode (tdd or direct)
        validation: Validation level (none, tests, smoke-test, multi-phase)
        phase_id: Phase identifier for multi-phase work
        depends_on: Phase dependency
        investigation_type: Investigation type (systems, feasibility, audits, performance, agent-failures)
        backend: AI backend to use (overrides config/default)
        model: Optional model to use (e.g., "sonnet", "opus", or full model name)
        stash: If True, stash uncommitted changes before spawn
        allow_dirty: If True, allow spawn with uncommitted changes without prompting
        feature_id: Feature ID from backlog.json for lifecycle tracking
        interactive: If True, skill operates in collaborative mode with Dylan
        beads_id: Beads issue ID for lifecycle tracking

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
                f"Example: orch spawn {skill_name} \"task description\" --project PROJECT_NAME"
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

    # Skip workspace for investigation-category skills (investigation, systematic-debugging, codebase-audit)
    skip_workspace = skill_metadata and skill_metadata.category == "investigation"

    deliverables = list(skill_metadata.deliverables) if skill_metadata.deliverables else None

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
        requires_workspace=not skip_workspace,
        # Feature tracking (backlog.json integration)
        feature_id=feature_id,
        context_ref=context_ref,  # Design context file to include in spawn prompt
        # Interactive mode (collaborative design)
        interactive=interactive,
        # Beads integration
        beads_id=beads_id
    )

    # Create workspace using integrated function (fixes PARTIAL state bug)
    # Heuristic nudges to avoid heavy skills for small tasks
    if skill_name == "systematic-debugging" and looks_trivial_bug(task):
        click.echo("\n⚠️  This looks like an obvious/localized failure.")
        click.echo("   'systematic-debugging' is thorough and heavier.")
        click.echo("   Consider 'quick-debugging' or 'feature-impl --mode direct' if the fix is trivial.")

    if skip_workspace and config.deliverables:
        config.deliverables = [d for d in config.deliverables if d.type != "workspace"]

    if not config.requires_workspace:
        config.primary_artifact = determine_primary_artifact(config)

    # Map skill name to workspace type (used when we DO create a workspace)
    workspace_type = (
        "investigation" if skill_name in ("systematic-debugging", "quick-debugging") else "implementation"
    )

    workspace_path = project_dir / ".orch" / "workspace" / workspace_name

    if skip_workspace:
        workspace_path.mkdir(parents=True, exist_ok=True)
    else:
        try:
            workspace_info = create_workspace(
                workspace_name=workspace_name,
                project_dir=project_dir,
                workspace_type=workspace_type,
                owner=None,  # Auto-detect from git config
                resume=resume  # Allow resuming existing workspace
            )
            workspace_file = workspace_path / "WORKSPACE.md"

            # VERIFY file actually exists before proceeding (prevents race condition bug)
            if not workspace_file.exists():
                raise RuntimeError(
                    f"Workspace creation claimed success but file doesn't exist: {workspace_file}\n"
                    f"This may indicate a race condition or filesystem issue."
                )
        except WorkspaceValidationError as e:
            click.echo(f"⚠️  Workspace creation failed: {e}", err=True)
            raise

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
                feature_id=config.feature_id
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
                feature_id=config.feature_id
            )

            click.echo(f"\n✅ Spawned: {spawn_info['window_name']}")
            click.echo(f"   Window: {spawn_info['window']}")
            click.echo(f"   Workspace: {workspace_name}")
            if stashed:
                click.echo(f"   ⚠️  Git changes stashed (will auto-unstash on complete)")

        # Update beads issue with workspace link if spawned from beads
        if config.beads_id:
            try:
                from orch.beads_integration import BeadsIntegration
                beads = BeadsIntegration()
                workspace_rel = f".orch/workspace/{config.workspace_name}"
                beads.add_workspace_link(config.beads_id, workspace_rel)
                click.echo(f"   Beads: {config.beads_id} → workspace linked")
            except Exception as e:
                # Don't fail spawn if beads update fails
                click.echo(f"   ⚠️  Could not update beads issue: {e}", err=True)

        return spawn_info

    except Exception as e:
        # Keep workspace on error for debugging
        logger.error(f"Spawn failed: {e}")
        raise
