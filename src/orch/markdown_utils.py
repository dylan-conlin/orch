"""Markdown utility functions for parsing common patterns."""

import re
from pathlib import Path
from typing import Optional


def extract_tldr(file_path: Path) -> Optional[str]:
    """
    Extract TLDR section from a markdown file.

    Looks for content between '**TLDR:**' and the next '---' separator.
    Returns None if TLDR not found or if it's a template placeholder.

    Args:
        file_path: Path to markdown file

    Returns:
        TLDR text (stripped) or None if not found/invalid
    """
    file_path = Path(file_path).expanduser()

    if not file_path.exists():
        return None

    try:
        content = file_path.read_text()
    except (FileNotFoundError, PermissionError):
        return None

    # Find TLDR section
    tldr_match = re.search(r'\*\*TLDR:\*\*\s*(.+?)(?=\n---|\Z)', content, re.DOTALL)

    if not tldr_match:
        return None

    tldr = tldr_match.group(1).strip()

    # Check for template placeholders
    if not tldr or '[' in tldr[:50]:  # Template placeholders often start with [
        return None

    return tldr
