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

def filter_skill_phases(
    skill_content: Optional[str],
    phases: List[str],
    mode: Optional[str] = None
) -> Optional[str]:
    """
    Filter skill content to only include configured phases.

    When spawning feature-impl with --phases="implementation,validation",
    we don't need all 8 phases (1490 lines). This filters to only the
    configured phases, reducing context by ~60%.

    Args:
        skill_content: Full skill content from SKILL.md
        phases: List of phase names to include (e.g., ["implementation", "validation"])
        mode: Implementation mode ("tdd" or "direct"). Defaults to "tdd".
              Determines which implementation-* phase to include.

    Returns:
        Filtered skill content, or None if skill_content is None.

    Phase markers in skill content:
        <!-- SKILL-TEMPLATE: phase-name -->
        Content here
        <!-- /SKILL-TEMPLATE -->

    Special handling for "implementation" phase:
        - If mode="tdd": includes "implementation-tdd" section
        - If mode="direct": includes "implementation-direct" section
        - If mode=None: defaults to "implementation-tdd"
    """
    # Handle edge cases
    if skill_content is None:
        return None
    if skill_content == "":
        return ""

    # If no phases configured, return header and footer only (no phase content)
    # If content has no markers, return unchanged
    if "<!-- SKILL-TEMPLATE:" not in skill_content:
        return skill_content

    # Default mode to tdd
    effective_mode = mode or "tdd"

    # Build set of phase markers to include
    # Map "implementation" to specific variant based on mode
    phase_markers_to_include = set()
    for phase in phases:
        if phase == "implementation":
            # Map to specific implementation variant
            if effective_mode == "direct":
                phase_markers_to_include.add("implementation-direct")
            else:
                phase_markers_to_include.add("implementation-tdd")
        else:
            phase_markers_to_include.add(phase)

    # Parse skill content into sections
    # Pattern: <!-- SKILL-TEMPLATE: phase-name --> ... <!-- /SKILL-TEMPLATE -->
    pattern = r'(<!-- SKILL-TEMPLATE: (\S+) -->.*?<!-- /SKILL-TEMPLATE -->)'

    # Find all phase sections
    sections = list(re.finditer(pattern, skill_content, re.DOTALL))

    if not sections:
        # No phase markers found, return unchanged
        return skill_content

    # Extract header (content before first marker)
    first_section_start = sections[0].start()
    header = skill_content[:first_section_start]

    # Extract footer (content after last marker)
    last_section_end = sections[-1].end()
    footer = skill_content[last_section_end:]

    # Build filtered content
    filtered_sections = []
    for match in sections:
        full_section = match.group(1)
        phase_name = match.group(2)

        if phase_name in phase_markers_to_include:
            filtered_sections.append(full_section)

    # Combine header + filtered sections + footer
    result = header + "\n\n".join(filtered_sections) + footer

    # Clean up excessive newlines (more than 3 consecutive)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    return result


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
    # Note: SCOPE section omitted - when no explicit scope provided, omit entirely
    # rather than include confusing placeholder text (orch-cli-tmb)
    return """TASK: [One sentence description]

CONTEXT: [Minimal background needed]

PROJECT_DIR: [Absolute path to project]

SESSION SCOPE: Medium (estimated 2-4h)
- Default estimation
- Recommend checkpoint every 2 hours

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
2. [Task-specific deliverables]

STATUS UPDATES:
Report progress via `bd comment <beads-id>`:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session

Signal orchestrator when blocked:
- bd comment <beads-id> "BLOCKED: [reason]"
- bd comment <beads-id> "QUESTION: [question]"

Orchestrator monitors via beads comments"""


# ========== Meta-Orchestration Boilerplate ==========

# List of project path patterns that should include meta-orchestration boilerplate
META_ORCHESTRATION_PROJECTS = ['orch-cli', 'orch-knowledge']


def is_meta_orchestration_project(project_dir: Path) -> bool:
    """
    Check if project is a meta-orchestration project that needs template system warnings.

    Meta-orchestration projects (orch-cli, orch-knowledge) deal with orchestration
    templates and need the ~45 lines of template system warnings. Other projects
    don't need this irrelevant content.

    Args:
        project_dir: Path to the project directory

    Returns:
        True if project needs meta-orchestration boilerplate
    """
    project_path_str = str(project_dir).lower()
    return any(project in project_path_str for project in META_ORCHESTRATION_PROJECTS)


def strip_meta_orchestration_boilerplate(template: str) -> str:
    """
    Remove meta-orchestration template system warnings from spawn prompt.

    The ~45 lines of META-ORCHESTRATION TEMPLATE SYSTEM warnings are only
    relevant for projects that deal with orchestration templates (orch-cli,
    orch-knowledge). This function removes that section for other projects.

    Args:
        template: The spawn prompt template

    Returns:
        Template with meta-orchestration section removed
    """
    # Markers for the meta-orchestration section
    start_marker = "⚠️ **META-ORCHESTRATION TEMPLATE SYSTEM**"
    end_marker = "**Reference:** .orch/CLAUDE.md lines 77-125 for template system documentation"

    start_idx = template.find(start_marker)
    if start_idx == -1:
        return template  # No meta-orchestration section found

    end_idx = template.find(end_marker)
    if end_idx == -1:
        return template  # End marker not found, don't strip

    # Find the end of the end marker line
    end_of_line = template.find('\n', end_idx)
    if end_of_line == -1:
        end_of_line = len(template)

    # Strip the section (including trailing newline)
    return template[:start_idx] + template[end_of_line + 1:]


def strip_unfilled_scope_section(template: str) -> str:
    """
    Remove SCOPE section when it contains unfilled placeholder text.

    When no explicit scope is provided, the SCOPE section with placeholder text
    "[Agent to define based on task]" confuses workers. Better to omit entirely.

    Args:
        template: The spawn prompt template

    Returns:
        Template with unfilled SCOPE section removed
    """
    # Check if template contains the unfilled placeholder
    if "[What's in scope]" not in template and "[What's explicitly out of scope]" not in template:
        return template  # No unfilled placeholders, keep SCOPE section

    # Find and remove the SCOPE section
    # Pattern: "SCOPE:\n- IN: ...\n- OUT: ...\n"
    start_marker = "SCOPE:\n- IN:"
    start_idx = template.find(start_marker)
    if start_idx == -1:
        return template  # No SCOPE section found

    # Find the end of the OUT line (next section starts with a capital letter or is empty line followed by section)
    end_idx = start_idx
    lines = template[start_idx:].split('\n')
    for i, line in enumerate(lines[2:], 2):  # Skip "SCOPE:" and "- IN:" lines
        # Stop at empty line or next section (line starting with capital letter or **
        if not line.strip() or (line and line[0].isupper()) or line.startswith('**'):
            end_idx = start_idx + sum(len(l) + 1 for l in lines[:i])
            break
    else:
        # Reached end of template
        end_idx = len(template)

    # Strip the section
    return template[:start_idx] + template[end_idx:]


def strip_prior_work_placeholder(template: str) -> str:
    """
    Remove [OPTIONAL] Context from Prior Work section with placeholder paths.

    This section contains example paths like "previous-agent/WORKSPACE.md" that
    don't exist and confuse workers. Should only be included when actual prior
    work reference is provided.

    Args:
        template: The spawn prompt template

    Returns:
        Template with placeholder Prior Work section removed
    """
    start_marker = "[OPTIONAL] Context from Prior Work:"
    start_idx = template.find(start_marker)
    if start_idx == -1:
        return template  # No Prior Work section found

    # Find the end of this section (next line that starts a new section)
    lines = template[start_idx:].split('\n')
    end_idx = start_idx
    for i, line in enumerate(lines[1:], 1):  # Skip the header line
        # Stop at empty line followed by section header, or a line starting with uppercase/section marker
        if not line.strip():
            # Check if next line starts a new section
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line and (next_line[0].isupper() or next_line.startswith('**') or next_line.startswith('-')):
                    continue  # This empty line is within the section
            end_idx = start_idx + sum(len(l) + 1 for l in lines[:i])
            break
        # Check if line starts new section (uppercase start, not a bullet point continuation)
        if line and line[0].isupper() and not line.startswith('- '):
            end_idx = start_idx + sum(len(l) + 1 for l in lines[:i])
            break
    else:
        # Section continues to end of template
        end_idx = len(template)

    # Strip the section
    return template[:start_idx] + template[end_idx:]


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

    # Strip meta-orchestration boilerplate for non-meta projects (orch-cli-1b5)
    # The ~45 lines of template system warnings are only relevant for projects
    # that deal with orchestration templates (orch-cli, orch-knowledge)
    if not is_meta_orchestration_project(config.project_dir):
        template = strip_meta_orchestration_boilerplate(template)

    # Prepare context text
    context_text = config.roadmap_context if config.roadmap_context else "[See task description]"

    # Substitute template variables
    # Note: Template uses [Variable Name] format which we replace with actual values
    prompt = template
    prompt = prompt.replace("[One sentence description]", config.task)

    # Insert CRITICAL instructions right after TASK section
    # This prevents agents from skipping the planning phase AND the completion protocol
    critical_instruction = """
🚨 CRITICAL - FIRST 3 ACTIONS:
You MUST do these within your first 3 tool calls:
1. Report via `bd comment <beads-id> "Phase: Planning - [brief description]"`
2. Read relevant codebase context for your task
3. Begin planning

If Phase is not reported within first 3 actions, you will be flagged as unresponsive.
Do NOT skip this - the orchestrator monitors via beads comments.

🚨 SESSION COMPLETE PROTOCOL (READ NOW, DO AT END):
After your final commit, BEFORE typing anything else:
1. Run: `bd comment <beads-id> "Phase: Complete - [1-2 sentence summary of deliverables]"`
2. Run: `/exit` to close the agent session

⚠️ Work is NOT complete until Phase: Complete is reported.
⚠️ The orchestrator cannot close this issue until you report Phase: Complete.
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
    prompt = prompt.replace("[Brief justification]", "Default estimation")
    prompt = prompt.replace("[Brief justification: task count, complexity, unknowns]", "Default estimation")
    prompt = prompt.replace("[specific phase/task]", "Phase 1")
    prompt = prompt.replace("[X]", "2")
    prompt = prompt.replace("after [timing]", "every 2 hours")

    # Strip unfilled placeholder sections (orch-cli-tmb)
    # When scope or prior work references are not provided, remove the sections
    # entirely rather than leaving confusing placeholder text
    prompt = strip_unfilled_scope_section(prompt)
    prompt = strip_prior_work_placeholder(prompt)

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
        # Beads is now source of truth - simplified coordination without WORKSPACE.md instructions
        coordination_check = (
            "**REPORT phase via beads:** `bd comment <beads-id> \"Phase: Planning - [task description]\"`\n"
            "   - This is your primary progress tracking mechanism\n"
            "   - Orchestrator monitors via `bd show <beads-id>`"
        )
        coordination_update = (
            "**REPORT progress via beads:**\n"
            "   - Use `bd comment <beads-id>` for phase transitions and milestones\n"
            "   - Report blockers immediately: `bd comment <beads-id> \"BLOCKED: [reason]\"`\n"
            "   - Report questions: `bd comment <beads-id> \"QUESTION: [question]\"`"
        )
        coordination_phase = "Report phase transitions via `bd comment <beads-id> \"Phase: [phase] - [details]\"`"
    else:
        # Generate slug for kb create investigation command (same logic as render_deliverable_path)
        inv_slug = '-'.join(extract_meaningful_words(config.task)[:5])
        if not inv_slug:
            inv_slug = 'investigation'
        inv_type = config.investigation_type or 'simple'

        coordination_check = (
            f"**SET UP investigation file:** Run `kb create investigation {inv_slug}` to create from template\n"
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
    coordination_artifact_name = "investigation file" if not config.requires_workspace else "beads comments"
    blocked_location = "investigation file" if not config.requires_workspace else "beads comments"

    if config.requires_workspace:
        status_updates = """STATUS UPDATES (CRITICAL):
Report phase transitions via `bd comment <beads-id>`:
- Phase: Planning
- Phase: Implementing
- Phase: Complete → then call /exit to close agent session

Signal orchestrator when blocked:
- `bd comment <beads-id> "BLOCKED: [reason]"`
- `bd comment <beads-id> "QUESTION: [question]"`

Orchestrator monitors via `bd show <beads-id>` (reads beads comments)"""
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

    # Beads progress tracking (when spawned from a beads issue)
    if config.beads_id:
        additional_parts.append("""
## BEADS PROGRESS TRACKING (PREFERRED)

You were spawned from beads issue: **{beads_id}**

**Use `bd comment` for progress updates instead of workspace-only tracking:**

```bash
# Report progress at phase transitions
bd comment {beads_id} "Phase: Planning - Analyzing codebase structure"
bd comment {beads_id} "Phase: Implementing - Adding authentication middleware"
bd comment {beads_id} "Phase: Complete - All tests passing, ready for review"

# Report blockers immediately
bd comment {beads_id} "BLOCKED: Need clarification on API contract"

# Report questions
bd comment {beads_id} "QUESTION: Should we use JWT or session-based auth?"
```

**When to comment:**
- Phase transitions (Planning → Implementing → Testing → Complete)
- Significant milestones or findings
- Blockers or questions requiring orchestrator input
- Completion summary with deliverables

**Why beads comments:** Creates permanent, searchable progress history linked to the issue. Orchestrator can track progress across sessions via `bd show {beads_id}`.

⛔ **NEVER run `bd close`** - Only the orchestrator closes issues via `orch complete`.
   - Workers report `Phase: Complete`, orchestrator verifies and closes
   - Running `bd close` bypasses verification and breaks tracking
""".format(beads_id=config.beads_id))

    # Agent Mail coordination (scope-aware: only included when explicitly requested or Medium/Large scope)
    # Determine if Agent Mail should be included
    include_agent_mail = config.include_agent_mail
    if not include_agent_mail and config.phases:
        # Include for Medium/Large scope (3+ phases)
        phase_count = len([p.strip() for p in config.phases.split(',') if p.strip()])
        include_agent_mail = phase_count >= 3

    if include_agent_mail:
        task_short = config.task[:50] + "..." if len(config.task) > 50 else config.task
        additional_parts.append("""
## AGENT MAIL COORDINATION (OPTIONAL)

Agent Mail MCP is available for inter-agent messaging. On startup:

1. **Register yourself** (first 5 actions):
   ```
   mcp__agent-mail__register_agent(
     project_key="{project_dir}",
     program="claude-code",
     model="{model}",
     task_description="{task_short}"
   )
   ```
   This gives you a memorable identity (e.g., "BlueLake") for messaging.

2. **Check inbox periodically** (every 30 min or at phase transitions):
   ```
   mcp__agent-mail__fetch_inbox(
     project_key="{project_dir}",
     agent_name="<your-registered-name>"
   )
   ```

3. **Acknowledge urgent messages** immediately if `ack_required=true`

4. **Message orchestrator** if blocked or need coordination:
   ```
   mcp__agent-mail__send_message(
     project_key="{project_dir}",
     sender_name="<your-name>",
     to=["<orchestrator-name>"],
     subject="Status update",
     body_md="..."
   )
   ```

**Why this matters:** Enables persistent, searchable communication between agents.
The orchestrator may send you guidance via Agent Mail instead of tmux.
""".format(
            project_dir=str(config.project_dir),
            model=config.model or "sonnet",
            task_short=task_short
        ))

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

    # Feature-impl configuration - apply defaults when skill is feature-impl
    # Determine phases/mode BEFORE loading skill content so we can filter phases
    # Default phases/mode/validation: implementation+validation, tdd, tests
    is_feature_impl = config.skill_name == 'feature-impl'

    # Apply defaults for feature-impl if not explicitly specified
    # Default includes validation phase to ensure agents verify their work
    phases = config.phases or ('implementation,validation' if is_feature_impl else None)
    mode = config.mode or ('tdd' if is_feature_impl else None)
    validation = config.validation or ('tests' if is_feature_impl else None)

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

        # Filter skill phases for feature-impl to reduce context size
        # Only include phase sections that match configured phases
        if skill_content and is_feature_impl and phases:
            phases_list = [p.strip() for p in phases.split(',')]
            skill_content = filter_skill_phases(skill_content, phases_list, mode)

        if skill_content:
            additional_parts.append("---\n")
            additional_parts.append(skill_content)
            additional_parts.append("\n---\n")
        else:
            additional_parts.append(f"(Skill content not found - follow {config.skill_name} skill principles)\n")

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
        # Beads is source of truth - no workspace file needed
        additional_parts.append(f"\nWORKSPACE DIR: {workspace_path}")
        additional_parts.append("(Use `bd comment <beads-id>` for progress tracking)\n")
    else:
        additional_parts.append(f"\nCOORDINATION ARTIFACT: {coordination_artifact_path}")
        additional_parts.append("(Investigation file is your deliverable - update Status when complete)\n")

    # Verification requirements
    verification_reqs = get_verification_requirements(config.skill_name, config.skill_metadata)
    if verification_reqs:
        additional_parts.append("\nVERIFICATION REQUIRED:")
        additional_parts.append(verification_reqs)
        additional_parts.append("")
        additional_parts.append("IMPORTANT: Ensure these requirements are met before reporting Phase: Complete via `bd comment`.")
        additional_parts.append("")

    # Status updates guidance - now handled by [STATUS_UPDATES] placeholder in template
    # Note: COORDINATION ARTIFACT POPULATION section removed - beads is source of truth

    # Available context
    additional_parts.append("CONTEXT AVAILABLE:")
    additional_parts.append("- Global: ~/.claude/CLAUDE.md")
    additional_parts.append(f"- Project: {config.project_dir}/.claude/CLAUDE.md")
    additional_parts.append(f"- Orchestrator: {config.project_dir}/.orch/CLAUDE.md")
    additional_parts.append("- CDD: ~/orch-knowledge/docs/cdd-essentials.md")
    if config.skill_name:
        # Build hierarchical path if category known
        if config.skill_metadata and config.skill_metadata.category:
            skill_path = f"~/.claude/skills/{config.skill_metadata.category}/{config.skill_name}/SKILL.md"
        else:
            skill_path = f"~/.claude/skills/{config.skill_name}/SKILL.md"
        additional_parts.append(f"- Process guide: {skill_path}")

    # Combine template with additional sections
    return prompt + "\n\n" + "\n".join(additional_parts)
