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

    Creates names with pattern: [skill-]description-DDMMM
    Date suffix uses compact format (e.g., 30nov, 15dec).
    Truncates at word boundaries to avoid mid-word cuts.

    Args:
        task: Task description
        skill_name: Optional skill name for prefixing
        project_dir: Project directory (for collision detection)

    Returns:
        Workspace name (string, not full path)
    """
    from orch.workspace import apply_abbreviations

    # Get compact date suffix (e.g., "30nov", "15dec")
    date_suffix = datetime.now().strftime("%d%b").lower()

    # Extract meaningful words
    words = extract_meaningful_words(task)

    # Apply abbreviations to make names more concise
    words = apply_abbreviations(words)

    # Build name with skill prefix if provided
    if skill_name and skill_name in SKILL_PREFIXES:
        prefix = SKILL_PREFIXES[skill_name]
        slug_words = [prefix] + words
    else:
        slug_words = words if words else ['workspace']

    # Calculate available space for slug
    # Format: slug-DDMMM (e.g., feat-auth-fix-30nov)
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
