"""Bug flagging workflow for immediate investigation."""

from pathlib import Path
from typing import Dict
import re
import subprocess
import os
from datetime import datetime

from orch.context_capture import capture_bug_context
from orch.workspace import create_workspace
from orch.logging import OrchLogger


def generate_workspace_slug(description: str, max_length: int = 50) -> str:
    """
    Generate workspace slug from bug description.

    Handles edge cases: empty descriptions, special characters, unicode.

    Args:
        description: Bug description
        max_length: Maximum slug length (default: 50)

    Returns:
        Workspace slug in format: debug-<kebab-case-description>
    """
    # Handle empty or whitespace-only descriptions
    if not description or not description.strip():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"debug-bug-{timestamp}"

    # Convert to lowercase and normalize unicode
    import unicodedata
    slug = description.lower()
    slug = unicodedata.normalize('NFKD', slug)
    slug = slug.encode('ascii', 'ignore').decode('ascii')

    # Remove apostrophes (so "isn't" becomes "isnt")
    slug = slug.replace("'", "")

    # Replace special characters and punctuation with spaces
    slug = re.sub(r'[^\w\s-]', ' ', slug)

    # Replace whitespace with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    # If slug is empty after cleaning (only special chars), use timestamp
    if not slug:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"debug-bug-{timestamp}"

    # Prepend debug- prefix
    slug = f"debug-{slug}"

    # Truncate if needed (keep at reasonable length)
    if len(slug) > max_length:
        # Try to truncate at word boundary
        truncated = slug[:max_length]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > len("debug-"):
            slug = truncated[:last_hyphen]
        else:
            slug = truncated

    return slug


def create_debugging_workspace(
    workspace_name: str,
    project_dir: Path,
    bug_context: Dict
) -> Dict:
    """
    Create debugging workspace with pre-filled context.

    Args:
        workspace_name: Workspace name (e.g., debug-price-calculation)
        project_dir: Project directory
        bug_context: Captured context from capture_bug_context

    Returns:
        Dict with workspace_path, workspace_file
    """
    # Create workspace using existing infrastructure
    workspace_result = create_workspace(
        workspace_name=workspace_name,
        project_dir=project_dir,
        workspace_type='investigation',
        resume=False
    )

    # Convert string path to Path object for file operations
    # Note: create_workspace returns paths relative to .orch directory
    workspace_file = project_dir / ".orch" / workspace_result['workspace_file']

    # Read workspace template
    content = workspace_file.read_text()

    # Pre-fill Context section
    context_text = f"""Investigating bug flagged from active work:

**Bug Description:** {bug_context['description']}

**Flagged From:** {bug_context['current_dir']}
"""

    # Add git context if available
    git_ctx = bug_context.get('git_context', {})
    if git_ctx.get('branch'):
        context_text += f"\n**Git Branch:** {git_ctx['branch']}"
    if git_ctx.get('modified_files'):
        context_text += f"\n**Modified Files:** {', '.join(git_ctx['modified_files'][:5])}"

    # Add workspace context if available
    ws_ctx = bug_context.get('workspace_context') or {}
    if ws_ctx.get('workspace_path'):
        context_text += f"\n\n**Source Workspace:** {ws_ctx['workspace_path']}"
        if ws_ctx.get('workspace_summary'):
            context_text += f"\n**Source Goal:** {ws_ctx['workspace_summary'].get('current_goal', 'Unknown')}"

    # Replace Context placeholder
    content = re.sub(
        r'## Context\n\[Background needed to understand this work\].*?(?=\n\n---|\Z)',
        f'## Context\n\n{context_text}',
        content,
        flags=re.DOTALL
    )

    # Write updated content
    workspace_file.write_text(content)

    # Also update External References section
    references_text = ""
    if ws_ctx.get('workspace_path'):
        references_text += f"- **Source workspace:** {ws_ctx['workspace_path']}\n"
    references_text += f"- **Flagged from:** {bug_context['current_dir']}\n"
    if git_ctx.get('branch'):
        references_text += f"- **Git context:** {git_ctx['branch']} branch"
        if git_ctx.get('modified_files'):
            file_count = len(git_ctx['modified_files'])
            references_text += f", {file_count} modified file{'s' if file_count != 1 else ''}"

    # Find and update External References section
    content = workspace_file.read_text()
    content = re.sub(
        r'## External References\n\n.*?(?=\n##|\Z)',
        f'## External References\n\n{references_text}\n',
        content,
        flags=re.DOTALL
    )
    workspace_file.write_text(content)

    return {
        'workspace_path': str(workspace_file.parent),
        'workspace_file': workspace_file
    }


def construct_spawn_prompt(bug_context: Dict, workspace_path: str) -> str:
    """
    Construct spawn prompt for debugging agent.

    Args:
        bug_context: Captured bug context
        workspace_path: Path to debugging workspace

    Returns:
        Spawn prompt string
    """
    git_ctx = bug_context.get('git_context') or {}
    ws_ctx = bug_context.get('workspace_context') or {}

    prompt = f"""TASK: Investigate bug: "{bug_context['description']}"

CONTEXT CAPTURED:
- Working directory: {bug_context['current_dir']}
"""

    # Add workspace context if available
    if ws_ctx.get('workspace_path'):
        prompt += f"- Active workspace: {ws_ctx['workspace_path']}\n"
        if ws_ctx.get('workspace_summary'):
            goal = ws_ctx['workspace_summary'].get('current_goal', 'Unknown')
            prompt += f"  Goal: {goal}\n"

    # Add git context
    if git_ctx.get('branch'):
        prompt += f"- Git branch: {git_ctx['branch']}"
        if git_ctx.get('modified_files'):
            file_count = len(git_ctx['modified_files'])
            prompt += f" ({file_count} modified file{'s' if file_count != 1 else ''})"
        prompt += "\n"

    # Add source workspace link
    if ws_ctx.get('workspace_path'):
        prompt += f"""
SOURCE WORKSPACE LINK:
This bug was noticed while working on: {ws_ctx['workspace_path']}
Review that workspace's context if needed for background.
"""

    # Add instructions
    prompt += f"""
INSTRUCTIONS:
Use systematic-debugging skill. When investigation completes:
1. Update source workspace's "Issues Discovered" section with findings
2. If fix is straightforward, implement it
3. If complex, document root cause and recommended approach

WORKSPACE: {workspace_path}/WORKSPACE.md
"""

    return prompt


def spawn_debugging_agent(
    workspace_name: str,
    workspace_path: str,
    spawn_prompt: str,
    project_dir: Path
) -> Dict:
    """
    Spawn debugging agent in tmux window.

    Args:
        workspace_name: Workspace name for tmux window
        workspace_path: Path to workspace directory
        spawn_prompt: Prompt for agent
        project_dir: Project directory

    Returns:
        Dict with window info and success status
    """
    # Use existing spawn infrastructure
    # This will be integrated with orch spawn in next task

    # For now, create a temporary prompt file and use spawn
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(spawn_prompt)
        prompt_file = f.name

    try:
        # Call orch spawn with custom prompt
        result = subprocess.run(
            [
                'orch', 'spawn',
                'systematic-debugging',
                '--project', str(project_dir),  # Full path for universal compatibility
                '--name', workspace_name,
                '--prompt-file', prompt_file,
                '--yes'  # Skip confirmation
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True
        )

        return {
            'success': True,
            'output': result.stdout
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'error': e.stderr
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(prompt_file)
        except Exception:
            pass


def flag_bug(description: str, project_dir: Path) -> Dict:
    """
    Main workflow: flag bug and spawn debugging agent.

    Args:
        description: Bug description from user
        project_dir: Project directory (defaults to cwd)

    Returns:
        Dict with success status, workspace info, spawn info
    """
    logger = OrchLogger()

    try:
        # Step 1: Capture context
        current_dir = Path.cwd()
        bug_context = capture_bug_context(
            description=description,
            current_dir=current_dir,
            project_dir=project_dir
        )

        # Step 2: Generate workspace slug
        workspace_name = generate_workspace_slug(description)

        # Step 3: Create debugging workspace with context
        workspace_result = create_debugging_workspace(
            workspace_name=workspace_name,
            project_dir=project_dir,
            bug_context=bug_context
        )

        workspace_path = workspace_result['workspace_path']

        # Step 4: Construct spawn prompt
        spawn_prompt = construct_spawn_prompt(bug_context, workspace_path)

        # Step 5: Spawn debugging agent
        spawn_result = spawn_debugging_agent(
            workspace_name=workspace_name,
            workspace_path=workspace_path,
            spawn_prompt=spawn_prompt,
            project_dir=project_dir
        )

        if not spawn_result['success']:
            return {
                'success': False,
                'error': f"Failed to spawn agent: {spawn_result.get('error', 'Unknown error')}"
            }

        logger.log_event('flag', f"Bug flagged and agent spawned: {workspace_name}", {
            'description': description,
            'workspace': workspace_path
        }, level='INFO')

        return {
            'success': True,
            'workspace_name': workspace_name,
            'workspace_path': workspace_path,
            'spawn_output': spawn_result.get('output', '')
        }

    except Exception as e:
        logger.log_error('flag', f"Bug flagging failed: {str(e)}", {
            'description': description,
            'error': str(e)
        })
        return {
            'success': False,
            'error': str(e)
        }
