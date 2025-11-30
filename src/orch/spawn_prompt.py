"""
Spawn prompt building functionality.

This module contains the logic for building spawn prompts from templates.
Extracted from spawn.py for better separation of concerns.
"""

from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
import logging
import re

from orch.skill_discovery import (
    SkillMetadata,
    DEFAULT_DELIVERABLES,
)
from orch.workspace_naming import extract_meaningful_words

if TYPE_CHECKING:
    from orch.spawn import SpawnConfig

logger = logging.getLogger(__name__)


# ========== Default Verification Requirements ==========

DEFAULT_VERIFICATION = {
    'feature-impl': """- [ ] All configured phases completed
  - [ ] Investigation findings documented (if investigation phase used)
  - [ ] Design documented (if design phase used)
  - [ ] Implementation complete with all deliverables
  - [ ] Validation evidence provided (tests pass, smoke test documented, or multi-phase validation complete)
- [ ] Tests pass OR validation evidence documented in workspace
  - [ ] Automated tests pass (if test suite exists and validation != none)
  - [ ] OR smoke test documented with verification steps (for UI features)
  - [ ] OR multi-phase validation checkpoints completed (for phased work)
- [ ] Implementation matches design (if design phase used)
- [ ] No regressions introduced (existing functionality still works)
- [ ] All deliverables documented in workspace Handoff Notes""",

    'systematic-debugging': """- [ ] Root cause documented in investigation file
- [ ] If fix implemented: Verify fix works
  - [ ] Run automated tests if available
  - [ ] OR document manual verification steps and complete them
- [ ] No regression introduced (existing functionality still works)""",

    'quick-debugging': """- [ ] Fix verified working (tests pass or manual verification complete)
- [ ] No obvious regressions introduced""",

    'investigation': """- [ ] Findings documented in investigation file
- [ ] If next-actions identified: Listed in Next-Actions section
- [ ] If "no fix needed": Reason documented""",

    'brainstorming': """- [ ] Design document created
- [ ] Requirements addressed
- [ ] Trade-offs documented
- [ ] Next-Actions clear (implementation steps or decisions needed)""",
}


# ========== Helper Functions ==========

def render_deliverable_path(template: str, config: "SpawnConfig") -> str:
    """
    Render deliverable path template with variables.

    Supports:
    - {date}: YYYY-MM-DD
    - {slug}: Slugified task description
    - {workspace-name}: Workspace directory name

    Args:
        template: Path template with placeholders
        config: Spawn configuration

    Returns:
        Rendered path string
    """
    from datetime import datetime

    # Generate slug from task
    slug = '-'.join(extract_meaningful_words(config.task)[:5])
    if not slug:
        slug = 'task'

    # Replace variables
    rendered = template.replace('{date}', datetime.now().strftime('%Y-%m-%d'))
    rendered = rendered.replace('{slug}', slug)
    rendered = rendered.replace('{workspace-name}', config.workspace_name)
    rendered = rendered.replace('{project}', str(config.project_dir))
    rendered = rendered.replace('{type}', config.investigation_type or 'simple')

    return rendered


def get_verification_requirements(
    skill_name: Optional[str],
    skill_metadata: Optional[SkillMetadata] = None
) -> Optional[str]:
    """
    Get verification requirements for a skill.

    Args:
        skill_name: Name of the skill
        skill_metadata: Optional parsed skill metadata (if already available)

    Returns:
        Verification requirements string (markdown checklist) or None
    """
    # If skill metadata provided and has verification, use it
    if skill_metadata and skill_metadata.verification:
        return skill_metadata.verification.requirements

    # Otherwise use defaults based on skill name
    if skill_name and skill_name in DEFAULT_VERIFICATION:
        return DEFAULT_VERIFICATION[skill_name]

    # No verification requirements found
    return None


def load_skill_content(
    skill_name: str,
    skill_metadata: Optional[SkillMetadata] = None
) -> Optional[str]:
    """
    Load full content from skill SKILL.md file.

    Args:
        skill_name: Name of the skill
        skill_metadata: Optional metadata (unused, kept for API compatibility)

    Returns:
        Full skill content, or None if file not found
    """
    skills_dir = Path.home() / ".claude" / "skills"

    # Search through all directories to find the skill
    # Note: We don't use metadata.category because it contains semantic skill type
    # (e.g., "debugging", "implementation") rather than directory name (e.g., "worker", "orchestrator")
    for category_dir in skills_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue
        potential_path = category_dir / skill_name / "SKILL.md"
        if potential_path.exists():
            try:
                return potential_path.read_text()
            except Exception:
                return None

    # Not found in any directory
    return None


def load_context_ref_content(
    context_ref: str,
    project_dir: Path
) -> Optional[str]:
    """
    Load content from a context_ref file.

    Context_ref is a relative path from project_dir to a design doc or investigation
    that provides context for the feature being implemented.

    Args:
        context_ref: Relative path to context file (e.g., ".orch/investigations/design/2025-11-28-topic.md")
        project_dir: Project directory (base for relative path)

    Returns:
        File content if file exists and is readable, None otherwise
    """
    if not context_ref:
        return None

    context_path = project_dir / context_ref
    if not context_path.exists():
        logger.warning(f"Context ref file not found: {context_path}")
        return None

    try:
        return context_path.read_text()
    except Exception as e:
        logger.warning(f"Error reading context ref file: {e}")
        return None


# ========== Template Loading ==========

def load_spawn_prompt_template() -> str:
    """
    Load the Basic Structure section from SPAWN_PROMPT.md template.

    Returns:
        Template string with variables to substitute, or fallback if not found.
    """
    # Try to find template (distribution first, then source for dev)
    template_path = Path.home() / ".orch" / "templates" / "SPAWN_PROMPT.md"
    if not template_path.exists():
        local_template = Path("templates-src/SPAWN_PROMPT.md")
        if local_template.exists():
            template_path = local_template

    if not template_path.exists():
        logger.warning(f"SPAWN_PROMPT.md not found at {template_path}, using fallback.")
        return """TASK: [One sentence description]

CONTEXT: [Minimal background needed]

PROJECT_DIR: [Absolute path to project]

SESSION SCOPE: [Small/Medium/Large] (estimated [duration])
- [Brief justification]
- Recommend checkpoint after [timing]

SCOPE:
- IN: [What's in scope]
- OUT: [What's explicitly out of scope]

AUTHORITY:
**You have authority to decide:**
- Implementation details (how to structure code, naming, file organization)
- Testing strategies (which tests to write, test frameworks to use)
- Refactoring within scope (improving code quality without changing behavior)
- Tool/library selection within established patterns
- Documentation structure and wording

**You must escalate to orchestrator when:**
- Architectural decisions needed (changing system structure, adding new patterns)
- Scope boundaries unclear (unsure if something is IN vs OUT scope)
- Requirements ambiguous (multiple valid interpretations exist)
- Blocked by external dependencies (missing access, broken tools, unclear context)
- Major trade-offs discovered (performance vs maintainability, security vs usability)
- Task estimation significantly wrong (2h task is actually 8h)

**When uncertain:** Err on side of escalation. Document question in workspace, set Status: QUESTION, and wait for orchestrator response. Better to ask than guess wrong.

DELIVERABLES (REQUIRED):
1. **FIRST:** Verify project location: pwd (must be PROJECT_DIR)
2. [COORDINATION_CHECK]
3. [COORDINATION_UPDATE]
4. [COORDINATION_PHASE]
5. [Task-specific deliverables]

STATUS UPDATES (CRITICAL):
Update Phase: field in your coordination artifact (investigation file) at transitions:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session

Signal orchestrator when blocked:
- Add '**Status:** BLOCKED - [reason]' to investigation file
- Add '**Status:** QUESTION - [question]' when needing input

Orchestrator monitors via 'orch status' (reads investigation file Phase field)"""

    try:
        content = template_path.read_text()

        # Extract Basic Structure section
        # Find start: "## Basic Structure" followed by code fence
        start_match = re.search(r'## Basic Structure\s*\n\s*```', content)
        if not start_match:
            logger.warning("Could not find '## Basic Structure' in SPAWN_PROMPT.md")
            return fallback_template()

        start_pos = start_match.end()

        # Find end: Look for closing ``` that's at start of line after the start position
        # We need to skip any nested code fences (like ```bash blocks)
        lines = content[start_pos:].split('\n')
        end_line = None
        in_nested_fence = False

        for i, line in enumerate(lines):
            # Check if this line starts a nested code fence
            if line.strip().startswith('```') and not line.strip() == '```':
                in_nested_fence = True
                continue
            # Check if this closes a nested fence
            if in_nested_fence and line.strip() == '```':
                in_nested_fence = False
                continue
            # Check if this is the closing fence for our main block (must be alone on line)
            if not in_nested_fence and line.strip() == '```':
                end_line = i
                break

        if end_line is None:
            logger.warning("Could not find closing ``` for Basic Structure")
            return fallback_template()

        extracted = '\n'.join(lines[:end_line])
        return extracted.strip()

    except Exception as e:
        logger.error(f"Error loading SPAWN_PROMPT.md template: {e}")
        return "(Error loading template - using minimal fallback)"


def fallback_template() -> str:
    """Fallback template when SPAWN_PROMPT.md cannot be loaded."""
    return """TASK: [One sentence description]

CONTEXT: [Minimal background needed]

PROJECT_DIR: [Absolute path to project]

SESSION SCOPE: Medium (estimated 2-4h)
- Default estimation. Please update in WORKSPACE.md based on your analysis.
- Recommend checkpoint every 2 hours.

SCOPE:
- IN: [Agent to define based on task]
- OUT: [Agent to define based on task]

AUTHORITY:
**You have authority to decide:**
- Implementation details
- Testing strategies
- Refactoring within scope

**You must escalate when:**
- Architectural decisions needed
- Scope unclear
- Requirements ambiguous

DELIVERABLES (REQUIRED):
1. **FIRST:** Verify project location: pwd (must be PROJECT_DIR)
2. **UPDATE workspace** (created for you)
3. Update workspace Phase field as you work
4. [Task-specific deliverables]

STATUS UPDATES (CRITICAL):
Update Phase: field in WORKSPACE.md at transitions:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session

Signal orchestrator when blocked:
- Add '**Status:** BLOCKED - [reason]' to workspace Summary section
- Add '**Status:** QUESTION - [question]' when needing input

Orchestrator monitors via 'orch status' (reads workspace Phase field)"""


# ========== Main Prompt Building ==========

def build_spawn_prompt(config: "SpawnConfig") -> str:
    """
    Build spawn prompt from SPAWN_PROMPT.md template with variable substitution.

    Args:
        config: Spawn configuration

    Returns:
        Complete spawn prompt string
    """
    from orch.workspace_naming import get_emoji_for_skill

    # If custom prompt provided, use it directly
    if config.custom_prompt:
        return config.custom_prompt

    # Load template from SPAWN_PROMPT.md
    template = load_spawn_prompt_template()

    # Prepare context text
    context_text = config.roadmap_context if config.roadmap_context else "[See task description]"

    # Substitute template variables
    # Note: Template uses [Variable Name] format which we replace with actual values
    prompt = template
    prompt = prompt.replace("[One sentence description]", config.task)

    # Insert CRITICAL instruction right after TASK section
    # This prevents "Phase: Unknown" from persisting - agents MUST set Phase: Planning early
    critical_instruction = """
🚨 CRITICAL - FIRST 3 ACTIONS:
You MUST do these within your first 3 tool calls:
1. Read your coordination artifact (WORKSPACE.md or create investigation file)
2. Set Phase: Planning in the artifact
3. Begin planning

If Phase is not set to Planning within first 3 actions, you will be flagged as unresponsive.
Do NOT skip this - the orchestrator monitors Phase to track agent status.
"""
    # Find end of TASK line and insert critical instruction after it
    task_end = prompt.find('\n', prompt.find('TASK:'))
    if task_end != -1:
        prompt = prompt[:task_end] + '\n' + critical_instruction + prompt[task_end:]

    prompt = prompt.replace("[Minimal background needed]", context_text)
    prompt = prompt.replace("[Absolute path to project]", str(config.project_dir))

    # Session scope defaults
    prompt = prompt.replace("[Small/Medium/Large]", "Medium")
    prompt = prompt.replace("[estimated [duration]]", "(estimated 2-4h)")
    prompt = prompt.replace("[estimated [1-2h / 2-4h / 4-6h+]]", "(estimated 2-4h)")
    prompt = prompt.replace("[Brief justification]", "Default estimation. Please update in WORKSPACE.md based on your analysis.")
    prompt = prompt.replace("[Brief justification: task count, complexity, unknowns]", "Default estimation. Please update in WORKSPACE.md based on your analysis.")
    prompt = prompt.replace("[specific phase/task]", "Phase 1")
    prompt = prompt.replace("[X]", "2")
    prompt = prompt.replace("after [timing]", "every 2 hours")

    # Scope defaults
    prompt = prompt.replace("[What's in scope]", "[Agent to define based on task]")
    prompt = prompt.replace("[What's explicitly out of scope]", "[Agent to define based on task]")

    # Deliverables substitutions
    # Replace literal PROJECT_DIR references in instructions (but not "PROJECT_DIR:" label)
    # Must preserve "PROJECT_DIR: /path/to/project" but replace "must be PROJECT_DIR" and "ls -la PROJECT_DIR/.orch"
    prompt = prompt.replace(" PROJECT_DIR\n", f" {config.project_dir}\n")  # "must be PROJECT_DIR" at end of line
    prompt = prompt.replace(" PROJECT_DIR)", f" {config.project_dir})")    # "must be PROJECT_DIR)"
    prompt = prompt.replace("PROJECT_DIR/", f"{config.project_dir}/")      # "ls -la PROJECT_DIR/.orch"
    prompt = prompt.replace("workspace-name", config.workspace_name)

    workspace_path = config.project_dir / ".orch" / "workspace" / config.workspace_name
    workspace_file = workspace_path / "WORKSPACE.md"
    workspace_check_path = f"{workspace_path}/WORKSPACE.md"
    coordination_artifact_path = str(config.primary_artifact) if config.primary_artifact else "your investigation file deliverable"

    if config.requires_workspace:
        coordination_check = (
            f"**VERIFY workspace exists:** Run `ls -la {workspace_check_path}`\n"
            "   - File exists (created by orchestrator before you started)\n"
            "   - If not found: Report error to orchestrator (workspace creation failed)"
        )
        coordination_update = (
            "**UPDATE workspace** (created for you, don't create new one):\n"
            "   - Write TLDR section at top (30-second resumption test - see .orch/docs/workspace-conventions.md)\n"
            "   - Fill Session Scope section with estimated duration and checkpoint plan\n"
            "   - Mark planned checkpoint points in Progress Tracking during planning phase\n"
            "   - Update Last Activity timestamp after each completed task\n"
            "   - Track actual time spent per task (add to completed task line)\n"
            "   - Follow amnesia-resilient standards (docs/amnesia-compensation-checklist.md)"
        )
        coordination_phase = "Update workspace Phase field as you work (Planning → Implementation → Testing → Complete)"
    else:
        # Generate slug for orch create-investigation command (same logic as render_deliverable_path)
        inv_slug = '-'.join(extract_meaningful_words(config.task)[:5])
        if not inv_slug:
            inv_slug = 'investigation'
        inv_type = config.investigation_type or 'simple'

        coordination_check = (
            f"**SET UP investigation file:** Run `orch create-investigation {inv_slug} --type {inv_type}` to create from template\n"
            f"   - This creates: `.orch/investigations/{inv_type}/YYYY-MM-DD-{inv_slug}.md`\n"
            "   - This file is your coordination artifact (replaces WORKSPACE.md)\n"
            "   - If command fails, report to orchestrator immediately"
        )
        coordination_update = (
            "**UPDATE investigation file** as you work:\n"
            "   - Add TLDR at top (1-2 sentence summary of question and finding)\n"
            "   - Fill sections: What I tried → What I observed → Test performed\n"
            "   - Only fill Conclusion if you actually tested (this is the key discipline)"
        )
        coordination_phase = "Update Status: field when done (Active → Complete)"

    # Build STATUS UPDATES section based on requires_workspace
    coordination_artifact_name = "investigation file" if not config.requires_workspace else "WORKSPACE.md"
    blocked_location = "investigation file" if not config.requires_workspace else "workspace Summary section"

    if config.requires_workspace:
        status_updates = f"""STATUS UPDATES (CRITICAL):
Update Phase: field in your coordination artifact ({coordination_artifact_name}) at transitions:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session

Signal orchestrator when blocked:
- Add '**Status:** BLOCKED - [reason]' to {blocked_location}
- Add '**Status:** QUESTION - [question]' when needing input

Orchestrator monitors via 'orch status' (reads coordination artifact Phase field)"""
    else:
        # Simplified status for investigations (no Phase field, just Status)
        status_updates = f"""STATUS UPDATES:
Update Status: field in your {coordination_artifact_name}:
- Status: Active (while working)
- Status: Complete (when done and committed) → then call /exit to close agent session

Signal orchestrator when blocked:
- Add '**Status:** BLOCKED - [reason]' to {blocked_location}
- Add '**Status:** QUESTION - [question]' when needing input"""

    prompt = prompt.replace("[COORDINATION_CHECK]", coordination_check)
    prompt = prompt.replace("[COORDINATION_UPDATE]", coordination_update)
    prompt = prompt.replace("[COORDINATION_PHASE]", coordination_phase)
    prompt = prompt.replace("[STATUS_UPDATES]", status_updates)

    # Build additional sections that don't come from template
    additional_parts = []

    # Additional context (from beads issues, etc.) - incorporated into prompt
    if config.additional_context:
        additional_parts.append("\n## ADDITIONAL CONTEXT\n")
        additional_parts.append(config.additional_context)
        additional_parts.append("\n")

    # Design context from context_ref (if provided)
    # This gives the agent background from prior design work
    if config.context_ref:
        context_content = load_context_ref_content(config.context_ref, config.project_dir)
        if context_content:
            additional_parts.append("\n## DESIGN CONTEXT\n")
            additional_parts.append(f"**Source:** {config.context_ref}\n")
            additional_parts.append("The following design document provides context for this task:\n")
            additional_parts.append("---\n")
            additional_parts.append(context_content)
            additional_parts.append("\n---\n")
        else:
            additional_parts.append(f"\n## DESIGN CONTEXT\n")
            additional_parts.append(f"**Source:** {config.context_ref}\n")
            additional_parts.append("(Warning: Context file not found or unreadable)\n")

    # Skill instruction (if skill-based)
    if config.skill_name:
        additional_parts.append(f"\n## SKILL GUIDANCE ({config.skill_name})\n")
        additional_parts.append("**IMPORTANT:** You have been spawned WITH this skill context already loaded.")
        additional_parts.append("You do NOT need to invoke this skill using the Skill tool.")
        additional_parts.append("Simply follow the guidance provided below.\n")

        # Interactive mode flag for skills that support it (e.g., architect)
        if config.interactive:
            additional_parts.append("**MODE:** INTERACTIVE_MODE=true")
            additional_parts.append("You are in interactive/collaborative mode. Dylan is in the tmux window with you.")
            additional_parts.append("Use brainstorming-style conversation - ask questions, present options, iterate.\n")

        # Load and include skill content
        skill_content = load_skill_content(config.skill_name, config.skill_metadata)
        if skill_content:
            additional_parts.append("---\n")
            additional_parts.append(skill_content)
            additional_parts.append("\n---\n")
        else:
            additional_parts.append(f"(Skill content not found - follow {config.skill_name} skill principles)\n")

    # Feature-impl configuration - apply defaults when skill is feature-impl
    # Default phases/mode/validation: implementation+validation, tdd, tests
    is_feature_impl = config.skill_name == 'feature-impl'

    # Apply defaults for feature-impl if not explicitly specified
    # Default includes validation phase to ensure agents verify their work
    phases = config.phases or ('implementation,validation' if is_feature_impl else None)
    mode = config.mode or ('tdd' if is_feature_impl else None)
    validation = config.validation or ('tests' if is_feature_impl else None)

    if any([phases, mode, validation, config.phase_id, config.depends_on]):
        additional_parts.append("FEATURE-IMPL CONFIGURATION:")
        if phases:
            additional_parts.append(f"Phases: {phases}")
        if mode:
            additional_parts.append(f"Mode: {mode}")
        if validation:
            additional_parts.append(f"Validation: {validation}")
        if config.phase_id:
            additional_parts.append(f"Phase-ID: {config.phase_id}")
        if config.depends_on:
            additional_parts.append(f"Depends-On: {config.depends_on}")
        additional_parts.append("")
        additional_parts.append("Follow phase guidance from the feature-impl skill.\n")

    # Investigation configuration
    if config.investigation_type:
        additional_parts.append("INVESTIGATION CONFIGURATION:")
        additional_parts.append(f"Type: {config.investigation_type}")
        additional_parts.append("")
        additional_parts.append(f"Create investigation file in .orch/investigations/{config.investigation_type}/ subdirectory.")
        additional_parts.append(f"Follow investigation skill guidance for {config.investigation_type} investigations.\n")

    # Parallel execution mode (codebase-audit specific)
    if config.parallel and config.skill_name == 'codebase-audit':
        additional_parts.append("EXECUTION MODE: PARALLEL")
        additional_parts.append("")
        additional_parts.append("**You are running in parallel execution mode.** Follow the mode-parallel.md workflow:")
        additional_parts.append("")
        additional_parts.append("1. **Spawn 5 dimension agents in parallel** (use Task tool with 5 concurrent invocations)")
        additional_parts.append("   - Security Agent (Haiku) - secrets, injection, auth")
        additional_parts.append("   - Performance Agent (Haiku) - large files, complexity, N+1")
        additional_parts.append("   - Architecture Agent (Haiku) - god objects, coupling")
        additional_parts.append("   - Tests Agent (Haiku) - coverage gaps, flaky indicators")
        additional_parts.append("   - Organizational Agent (Haiku) - drift, doc sync")
        additional_parts.append("")
        additional_parts.append("2. **Each agent returns JSON findings** (structured for synthesis)")
        additional_parts.append("")
        additional_parts.append("3. **Spawn synthesis agent** after all dimension agents complete")
        additional_parts.append("   - Combines findings, assigns severity, sorts by ROI")
        additional_parts.append("   - Produces prioritized report with top 20 findings")
        additional_parts.append("")
        additional_parts.append("4. **Write final report** to investigation file")
        additional_parts.append("")
        additional_parts.append("See mode-parallel.md in the skill for detailed JSON formats and prompts.")
        additional_parts.append("Expected speedup: ~3x faster than sequential (5-10 min vs 15-30 min)\n")

    # Task-specific deliverables (append to template's deliverables section)
    deliverables = config.deliverables or DEFAULT_DELIVERABLES
    if deliverables:
        additional_parts.append("\nADDITIONAL DELIVERABLES:")
        for deliverable in deliverables:
            rendered_path = render_deliverable_path(deliverable.path, config)
            required_str = "REQUIRED" if deliverable.required else "OPTIONAL"
            additional_parts.append(f"- {deliverable.type}: {rendered_path} ({required_str})")

    # Coordination artifact note
    if config.requires_workspace:
        additional_parts.append(f"\nWORKSPACE: {workspace_path}/WORKSPACE.md")
        if workspace_file.exists():
            additional_parts.append("(Workspace created automatically - WORKSPACE.md exists)\n")
        else:
            additional_parts.append("(WARNING: Workspace file not found - may need manual creation)\n")
    else:
        additional_parts.append(f"\nCOORDINATION ARTIFACT: {coordination_artifact_path}")
        additional_parts.append("(Investigation file is your deliverable - update Status when complete)\n")

    # Verification requirements
    verification_reqs = get_verification_requirements(config.skill_name, config.skill_metadata)
    if verification_reqs:
        additional_parts.append("\nVERIFICATION REQUIRED:")
        additional_parts.append(verification_reqs)
        additional_parts.append("")
        if config.requires_workspace:
            additional_parts.append("IMPORTANT: Copy the verification requirements above to your workspace 'Verification Required' section.")
            additional_parts.append("When you mark Phase: Complete, ensure all verification items are checked off.")
            additional_parts.append("Mark items complete as you verify them: - [x] Item description")
            additional_parts.append("  Result: (Add test results or verification evidence here)")
        else:
            # For investigations: verification is inline, no separate section
            additional_parts.append("IMPORTANT: Ensure these requirements are met before marking Status: Complete.")
        additional_parts.append("")

    # Status updates guidance - now handled by [STATUS_UPDATES] placeholder in template

    # Coordination artifact population guidance (only for workspaces)
    if config.requires_workspace:
        additional_parts.append("COORDINATION ARTIFACT POPULATION (REQUIRED):")
        additional_parts.append("Immediately after planning phase:")
        additional_parts.append("1. Fill TLDR / summary section (problem, status, next)")
        additional_parts.append("2. Capture Session Scope (validate scope estimate, mark checkpoint points)")
        additional_parts.append("3. Fill Progress Tracking (tasks with time estimates)")
        additional_parts.append("4. Update metadata fields (Owner, Started, Phase, Status)")
        additional_parts.append("\nDuring execution:")
        additional_parts.append("- Update Last Activity after each completed task")
        additional_parts.append("- Update Phase field at workflow transitions")
        additional_parts.append("- Mark checkpoint opportunities in Progress Tracking")
        additional_parts.append("\nSee: .orch/docs/workspace-conventions.md for details\n")

    # Available context
    additional_parts.append("CONTEXT AVAILABLE:")
    additional_parts.append("- Global: ~/.claude/CLAUDE.md")
    additional_parts.append(f"- Project: {config.project_dir}/.claude/CLAUDE.md")
    additional_parts.append(f"- Orchestrator: {config.project_dir}/.orch/CLAUDE.md")
    additional_parts.append("- CDD: ~/meta-orchestration/docs/cdd-essentials.md")
    if config.skill_name:
        # Build hierarchical path if category known
        if config.skill_metadata and config.skill_metadata.category:
            skill_path = f"~/.claude/skills/{config.skill_metadata.category}/{config.skill_name}/SKILL.md"
        else:
            skill_path = f"~/.claude/skills/{config.skill_name}/SKILL.md"
        additional_parts.append(f"- Process guide: {skill_path}")

    # Combine template with additional sections
    return prompt + "\n\n" + "\n".join(additional_parts)
