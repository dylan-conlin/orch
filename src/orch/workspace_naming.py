"""
Workspace naming utilities for orch tool.

Provides functions for generating workspace names from task descriptions,
including abbreviation application, stop word filtering, and collision detection.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import re


# Stop words to exclude from workspace names
STOP_WORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'should', 'could', 'may', 'might', 'must', 'can'
}

# Skill name to prefix mapping for workspace names
SKILL_PREFIXES = {
    'feature-impl': 'feat',
    'systematic-debugging': 'debug',
    'quick-debugging': 'qdbg',
    'brainstorming': 'brainstorm',
    'code-review': 'review',
    'writing-plans': 'plan',
    'capture-knowledge': 'knowledge',
    'record-decision': 'decision',
    'investigation': 'inv',
}

# Skill name to emoji mapping for tmux window names
SKILL_EMOJIS = {
    'feature-impl': '✨',
    'systematic-debugging': '🔍',
    'quick-debugging': '⚡️',
    'brainstorming': '💭',
    'code-review': '📝',
    'writing-plans': '📝',
    'investigation': '🔬',
}


def extract_meaningful_words(text: str) -> List[str]:
    """
    Extract meaningful words from text for workspace naming.

    Removes stop words and extracts alphanumeric words.
    Treats underscores as word separators (converts to spaces) to ensure
    kebab-case compliance (workspace names must not contain underscores).

    Args:
        text: Input text

    Returns:
        List of meaningful words (lowercase)
    """
    # Normalize underscores to spaces for kebab-case compatibility
    text_normalized = text.replace('_', ' ')

    # Convert to lowercase and extract words
    words = re.findall(r'\b\w+\b', text_normalized.lower())

    # Filter out stop words
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    return meaningful


def create_workspace_adhoc(task: str, skill_name: Optional[str] = None, project_dir: Optional[Path] = None) -> str:
    """
    Auto-generate workspace name for ad-hoc spawns.

    Creates names with pattern: [project-][skill-]description-DDMMM
    Project prefix ensures global uniqueness across projects.
    Date suffix uses compact format (e.g., 30nov, 15dec).
    Truncates at word boundaries to avoid mid-word cuts.

    Args:
        task: Task description
        skill_name: Optional skill name for prefixing
        project_dir: Project directory (for collision detection AND project prefix)

    Returns:
        Workspace name (string, not full path)
    """
    from orch.workspace import apply_abbreviations

    # Get compact date suffix (e.g., "30nov", "15dec")
    date_suffix = datetime.now().strftime("%d%b").lower()

    # Get project prefix for global uniqueness
    # This prevents collisions when different projects spawn similar tasks
    project_prefix = ""
    if project_dir:
        project_name = project_dir.name
        project_prefix = abbreviate_project_name(project_name)

    # Extract meaningful words
    words = extract_meaningful_words(task)

    # Apply abbreviations to make names more concise
    words = apply_abbreviations(words)

    # Build name with project prefix, skill prefix, and task keywords
    if skill_name and skill_name in SKILL_PREFIXES:
        skill_prefix = SKILL_PREFIXES[skill_name]
        # Filter out words that match the prefix to avoid duplicates like "inv-inv-"
        # This handles cases where task contains "investigate" which abbreviates to "inv"
        # and skill is "investigation" which also has prefix "inv"
        filtered_words = [w for w in words if w != skill_prefix]
        slug_words = [project_prefix, skill_prefix] + filtered_words if project_prefix else [skill_prefix] + filtered_words
    else:
        slug_words = [project_prefix] + words if project_prefix and words else words if words else ['workspace']

    # Filter out empty strings
    slug_words = [w for w in slug_words if w]

    # Calculate available space for slug
    # Format: slug-DDMMM (e.g., oc-feat-auth-fix-30nov)
    # 5 chars for date + 1 for hyphen = 6
    # Target max length: 35 chars (much shorter than old 70)
    max_length = 35
    available_chars = max_length - 6

    # Build slug with smart truncation at word boundaries
    slug_parts = []
    current_length = 0

    for word in slug_words:
        # Check if adding this word (plus hyphen) would exceed limit
        word_length = len(word) + (1 if slug_parts else 0)  # +1 for hyphen separator

        if current_length + word_length <= available_chars:
            slug_parts.append(word)
            current_length += word_length
        else:
            # Stop at word boundary - don't add partial words
            break

    # Ensure we have at least one word in the slug
    if not slug_parts and slug_words:
        # If first word alone is too long, truncate it
        slug_parts = [slug_words[0][:available_chars]]

    slug = '-'.join(slug_parts)
    name = f"{slug}-{date_suffix}"

    # Check for collision if project_dir provided
    if project_dir:
        workspace_path = project_dir / ".orch" / "workspace" / name
        if workspace_path.exists():
            # Add hash suffix on collision (truncate slug to make room)
            task_hash = abs(hash(task)) % 10000  # 4-digit hash (shorter)
            # Format: slug-XXXX-DDMMM (need 5 chars for -XXXX)
            max_slug_length = max_length - 6 - 5  # date - hash suffix
            truncated_slug = '-'.join(slug_parts)[:max_slug_length].rstrip('-')
            name = f"{truncated_slug}-{task_hash:04d}-{date_suffix}"

    return name


def get_emoji_for_skill(skill_name: Optional[str]) -> str:
    """
    Get emoji for skill name.

    Args:
        skill_name: Skill name

    Returns:
        Emoji character (falls back to generic worker emoji)
    """
    if not skill_name:
        return '⚙️'

    return SKILL_EMOJIS.get(skill_name, '⚙️')


def abbreviate_project_name(project_name: str) -> str:
    """
    Create human-readable abbreviation from project name.

    Takes first letter of each hyphen-separated segment.
    For single words, takes first 2-3 chars.

    Args:
        project_name: Full project name (e.g., "price-watch", "orch-cli")

    Returns:
        Abbreviated name (e.g., "pw", "oc")

    Examples:
        >>> abbreviate_project_name("price-watch")
        'pw'
        >>> abbreviate_project_name("orch-cli")
        'oc'
        >>> abbreviate_project_name("beads")
        'beads'
        >>> abbreviate_project_name("kb-cli")
        'kc'
    """
    parts = project_name.split('-')

    if len(parts) == 1:
        # Single word: keep as-is if short, otherwise first 3 chars
        return project_name if len(project_name) <= 5 else project_name[:3]

    # Multiple segments: first letter of each
    return ''.join(p[0] for p in parts if p)


def build_window_name(
    workspace_name: str,
    project_dir: Path,
    skill_name: Optional[str] = None,
    beads_id: Optional[str] = None,
    max_length: int = 40
) -> str:
    """
    Build tmux window name with project context and optional beads ID.

    Format:
        With beads:    "{emoji} {beads_id}: {task_slug}"
        Without beads: "{emoji} {abbrev_project}: {task_slug}"

    Args:
        workspace_name: Full workspace name (e.g., "debug-fix-prefixes-05dec")
        project_dir: Project directory path
        skill_name: Optional skill name for emoji selection
        beads_id: Optional beads issue ID (e.g., "orch-cli-06j")
        max_length: Maximum window name length (default 40)

    Returns:
        Formatted window name for tmux

    Example:
        >>> build_window_name("debug-fix-prefixes-05dec", Path("/projects/orch-cli"),
        ...                   skill_name="systematic-debugging", beads_id="orch-cli-06j")
        '🔍 orch-cli-06j: fix-prefixes'
        >>> build_window_name("feat-config-parts-05dec", Path("/projects/price-watch"),
        ...                   skill_name="feature-impl")
        '✨ pw: config-parts'
    """
    emoji = get_emoji_for_skill(skill_name)
    project_name = project_dir.name

    # Extract task slug from workspace name (remove skill prefix and date suffix)
    # Format: "debug-fix-prefixes-05dec" -> "fix-prefixes"
    parts = workspace_name.split('-')

    # Remove date suffix (last part, e.g., "05dec")
    if parts and re.match(r'^\d{2}[a-z]{3}$', parts[-1]):
        parts = parts[:-1]

    # Remove skill prefix if present (first part matches a known prefix)
    if parts and parts[0] in SKILL_PREFIXES.values():
        parts = parts[1:]

    task_slug = '-'.join(parts) if parts else workspace_name

    # Build window name based on whether we have beads ID
    if beads_id:
        # With beads: use full beads_id (already contains project context)
        prefix = f"{emoji} {beads_id}: "
    else:
        # Without beads: use abbreviated project name
        abbrev = abbreviate_project_name(project_name)
        prefix = f"{emoji} {abbrev}: "

    window_name = f"{prefix}{task_slug}"

    # Truncate task_slug if too long (preserve prefix)
    if len(window_name) > max_length:
        available = max_length - len(prefix)
        if available > 3:
            task_slug = task_slug[:available-2] + ".."
            window_name = f"{prefix}{task_slug}"

    return window_name
