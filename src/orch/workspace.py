"""
Workspace naming utilities.

This module contains utilities for generating workspace names from task descriptions.
WORKSPACE.md file management has been removed - beads is now the source of truth
for agent state tracking.

See: .kb/decisions/2025-12-06-eliminate-workspace-md.md
"""

from typing import List, Dict


# ===== Workspace Naming Constants =====

# Common abbreviations for workspace naming
ABBREVIATIONS = {
    'investigate': 'inv',
    'investigation': 'inv',
    'implement': 'impl',
    'implementation': 'impl',
    'collection': 'coll',
    'debugging': 'debug',
    'configuration': 'config',
    'authentication': 'auth',
    'authorization': 'authz'
}


# ===== Workspace Naming Utilities =====

def apply_abbreviations(words: List[str], abbrev_dict: Dict[str, str] = None) -> List[str]:
    """
    Apply abbreviations to word list.

    Args:
        words: List of words to abbreviate
        abbrev_dict: Dictionary of abbreviations (defaults to ABBREVIATIONS)

    Returns:
        List of words with abbreviations applied

    Example:
        >>> apply_abbreviations(["investigate", "timeout"], ABBREVIATIONS)
        ['inv', 'timeout']
    """
    if abbrev_dict is None:
        abbrev_dict = ABBREVIATIONS

    result = []
    for word in words:
        # Check for abbreviation (case-insensitive)
        lower_word = word.lower()
        if lower_word in abbrev_dict:
            result.append(abbrev_dict[lower_word])
        else:
            result.append(word)

    return result


def truncate_at_word_boundary(text: str, max_length: int) -> str:
    """
    Truncate text at word boundary (last hyphen before max_length).

    Args:
        text: Text to truncate (kebab-case workspace name)
        max_length: Maximum length

    Returns:
        Truncated text at last hyphen before max_length, or text unchanged if under limit

    Examples:
        >>> truncate_at_word_boundary("explore-websocket-patterns-for-dashboard", 30)
        'explore-websocket-patterns'
        >>> truncate_at_word_boundary("short-name", 50)
        'short-name'
    """
    if len(text) <= max_length:
        return text

    # Find last hyphen before max_length
    truncated = text[:max_length]

    # Split at last hyphen and take first part
    if '-' in truncated:
        truncated = truncated.rsplit('-', 1)[0]
    else:
        # No hyphens found - truncate at max_length
        truncated = text[:max_length]

    return truncated
