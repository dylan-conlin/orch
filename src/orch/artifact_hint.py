"""
Artifact hint module for pre-spawn artifact search enforcement.

Provides functionality to:
1. Extract keywords from spawn task descriptions
2. Check for related artifacts in the project
3. Format hint messages suggesting artifact search

Related:
- ROADMAP entry: .orch/ROADMAP.org line 2906 (Enforce pre-spawn artifact search)
- Documentation: docs/spawning-agents.md (Pre-Spawn Artifact Check section)
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


# Stop words to filter from keyword extraction
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    'into', 'onto', 'upon', 'this', 'that', 'these', 'those', 'it', 'its',
    'add', 'fix', 'update', 'remove', 'delete', 'create', 'new', 'old',
    'implement', 'make', 'get', 'set', 'use', 'used', 'using', 'when',
    'where', 'which', 'what', 'who', 'how', 'why', 'all', 'each', 'every',
    'some', 'any', 'most', 'other', 'than', 'then', 'now', 'just', 'only'
}

# Minimum word length to include in keywords
MIN_WORD_LENGTH = 4

# Maximum number of keywords to extract
MAX_KEYWORDS = 3


@dataclass
class ArtifactSearchResult:
    """Result of artifact search."""
    found: bool
    artifacts: List[Path]
    keywords: List[str]


def extract_spawn_keywords(task: str) -> List[str]:
    """
    Extract meaningful keywords from a spawn task description.

    Filters out stop words and short words, returning meaningful terms
    that can be used for artifact search.

    Args:
        task: The task description string

    Returns:
        List of meaningful keywords (max 3)
    """
    # Split into words and normalize to lowercase
    words = task.lower().split()

    # Filter: remove stop words, short words, and non-alphabetic words
    meaningful_words = []
    for word in words:
        # Remove punctuation
        clean_word = ''.join(c for c in word if c.isalnum())

        # Filter criteria
        if (
            len(clean_word) >= MIN_WORD_LENGTH
            and clean_word.isalpha()  # Only alphabetic (no pure numbers)
            and clean_word not in STOP_WORDS
        ):
            meaningful_words.append(clean_word)

    # Return unique keywords, limited to MAX_KEYWORDS
    seen = set()
    unique_keywords = []
    for word in meaningful_words:
        if word not in seen:
            seen.add(word)
            unique_keywords.append(word)
            if len(unique_keywords) >= MAX_KEYWORDS:
                break

    return unique_keywords


def check_for_related_artifacts(
    keywords: List[str],
    project_dir: Path,
    max_age_days: int = 60
) -> ArtifactSearchResult:
    """
    Check for related artifacts in the project's .orch directory.

    Searches investigations, decisions, and knowledge directories
    for files containing the given keywords.

    Args:
        keywords: List of keywords to search for
        project_dir: Path to the project directory
        max_age_days: Only consider artifacts from last N days (default: 60)

    Returns:
        ArtifactSearchResult with found status and matching artifacts
    """
    if not keywords:
        return ArtifactSearchResult(found=False, artifacts=[], keywords=[])

    orch_dir = project_dir / ".orch"
    if not orch_dir.exists():
        return ArtifactSearchResult(found=False, artifacts=[], keywords=keywords)

    # Directories to search
    search_dirs = [
        orch_dir / "investigations",
        orch_dir / "decisions",
        orch_dir / "knowledge",
    ]

    # Collect all .md files within age limit
    cutoff = datetime.now() - timedelta(days=max_age_days)
    files_to_search = []

    for search_dir in search_dirs:
        if search_dir.exists():
            for md_file in search_dir.rglob("*.md"):
                try:
                    mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                    if mtime > cutoff:
                        files_to_search.append(md_file)
                except OSError:
                    pass

    if not files_to_search:
        return ArtifactSearchResult(found=False, artifacts=[], keywords=keywords)

    # Search files for keywords using ripgrep or fallback to grep
    matching_files = set()

    for keyword in keywords:
        matches = _search_files_for_keyword(keyword, files_to_search)
        matching_files.update(matches)

    return ArtifactSearchResult(
        found=len(matching_files) > 0,
        artifacts=sorted(matching_files),
        keywords=keywords
    )


def _search_files_for_keyword(keyword: str, files: List[Path]) -> List[Path]:
    """
    Search files for a keyword using ripgrep or fallback.

    Args:
        keyword: Keyword to search for
        files: List of files to search

    Returns:
        List of files containing the keyword
    """
    if not files:
        return []

    try:
        # Use ripgrep for fast search
        result = subprocess.run(
            ['rg', '-l', '-i', keyword] + [str(f) for f in files],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return [Path(line) for line in result.stdout.strip().split('\n') if line]
        elif result.returncode == 1:
            # No matches found (not an error)
            return []
        else:
            return []

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # ripgrep not available or timed out, fall back to Python search
        matching_files = []
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    if keyword.lower() in content:
                        matching_files.append(file_path)
            except (UnicodeDecodeError, OSError):
                pass
        return matching_files


def format_artifact_hint(
    keywords: List[str],
    artifact_count: int,
    artifact_example: str
) -> str:
    """
    Format an artifact search hint message.

    Args:
        keywords: Keywords that were used for search
        artifact_count: Number of related artifacts found
        artifact_example: Example artifact path to show

    Returns:
        Formatted hint message
    """
    keyword_str = ' '.join(keywords[:2])  # Use first 2 keywords

    lines = [
        "",
        "💡 PRIOR WORK HINT: Found related artifacts in project",
        f"   {artifact_count} artifact(s) related to your task topic",
        f"   Example: {artifact_example}",
        "",
        f"   Consider reviewing prior work before spawning:",
        f"      orch search \"{keyword_str}\"",
        "",
        "   To skip this hint: --skip-artifact-check",
        ""
    ]

    return "\n".join(lines)


def show_artifact_hint(
    task: str,
    project_dir: Path,
    skip_check: bool = False
) -> None:
    """
    Check for related artifacts and print hint if found.

    This is the main entry point called by spawn_commands.py.

    Args:
        task: The spawn task description
        project_dir: Path to the project directory
        skip_check: If True, skip the artifact check entirely
    """
    if skip_check:
        return

    # Extract keywords from task
    keywords = extract_spawn_keywords(task)
    if not keywords:
        return

    # Check for related artifacts
    result = check_for_related_artifacts(keywords, project_dir)
    if not result.found:
        return

    # Show hint
    import click
    example = str(result.artifacts[0].relative_to(project_dir)) if result.artifacts else ""
    hint = format_artifact_hint(
        keywords=result.keywords,
        artifact_count=len(result.artifacts),
        artifact_example=example
    )
    click.echo(hint, err=True)
