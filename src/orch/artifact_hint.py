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

# Maximum artifacts to show in hint
MAX_ARTIFACTS_TO_SHOW = 5

# Maximum summary length
MAX_SUMMARY_LENGTH = 80


@dataclass
class ScoredArtifact:
    """An artifact with relevance scoring and summary."""
    path: Path
    score: float  # Higher = more relevant
    keyword_matches: int  # Number of keywords matched
    days_old: int  # Days since last modified
    summary: str  # TLDR or first meaningful line


@dataclass
class ArtifactSearchResult:
    """Result of artifact search."""
    found: bool
    artifacts: List[Path]  # Kept for backwards compat
    keywords: List[str]
    scored_artifacts: List[ScoredArtifact]  # New: ranked by relevance


def extract_artifact_summary(file_path: Path) -> str:
    """
    Extract a summary from an artifact file.

    Looks for TLDR line first, then falls back to first non-header line.

    Args:
        file_path: Path to the markdown file

    Returns:
        Summary string (truncated to MAX_SUMMARY_LENGTH chars)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        summary = ""

        for line in lines:
            line = line.strip()

            # Skip empty lines and markdown headers
            if not line or line.startswith('#') or line.startswith('---'):
                continue

            # Look for TLDR (various formats)
            if line.lower().startswith('**tldr:**') or line.lower().startswith('tldr:'):
                # Extract content after TLDR:
                if ':**' in line:
                    summary = line.split(':**', 1)[1].strip()
                elif ':' in line:
                    summary = line.split(':', 1)[1].strip()
                break

            # Also check for TLDR on the line itself
            if 'tldr' in line.lower() and ':' in line:
                summary = line.split(':', 1)[1].strip()
                break

            # Use first non-header content line if no TLDR found yet
            if not summary and line and not line.startswith('*') and not line.startswith('-'):
                summary = line

        # Clean up markdown formatting
        summary = summary.strip('*').strip()

        # Truncate if needed
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH - 3] + "..."

        return summary if summary else "(no summary)"

    except (UnicodeDecodeError, OSError):
        return "(unable to read)"


def score_artifact(
    file_path: Path,
    keyword_match_count: int,
    now: Optional[datetime] = None
) -> ScoredArtifact:
    """
    Score an artifact by relevance.

    Scoring formula: keyword_matches * 10 + recency_bonus
    - recency_bonus: 10 for today, decreasing by 0.5 per day

    Args:
        file_path: Path to the artifact
        keyword_match_count: Number of keywords that matched
        now: Current datetime (for testing)

    Returns:
        ScoredArtifact with score, summary, and metadata
    """
    if now is None:
        now = datetime.now()

    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        days_old = (now - mtime).days
    except OSError:
        days_old = 60  # Default to oldest if can't read

    # Recency bonus: 10 points for today, decreasing by 0.5/day
    recency_bonus = max(0, 10 - (days_old * 0.5))

    # Keyword match bonus: 10 points per keyword matched
    score = (keyword_match_count * 10) + recency_bonus

    # Extract summary
    summary = extract_artifact_summary(file_path)

    return ScoredArtifact(
        path=file_path,
        score=score,
        keyword_matches=keyword_match_count,
        days_old=days_old,
        summary=summary
    )


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
    for files containing the given keywords. Returns scored results
    ranked by relevance (keyword matches + recency).

    Args:
        keywords: List of keywords to search for
        project_dir: Path to the project directory
        max_age_days: Only consider artifacts from last N days (default: 60)

    Returns:
        ArtifactSearchResult with found status, matching artifacts, and
        scored_artifacts (top MAX_ARTIFACTS_TO_SHOW ranked by relevance)
    """
    if not keywords:
        return ArtifactSearchResult(
            found=False, artifacts=[], keywords=[], scored_artifacts=[]
        )

    orch_dir = project_dir / ".orch"
    if not orch_dir.exists():
        return ArtifactSearchResult(
            found=False, artifacts=[], keywords=keywords, scored_artifacts=[]
        )

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
        return ArtifactSearchResult(
            found=False, artifacts=[], keywords=keywords, scored_artifacts=[]
        )

    # Track keyword match counts per file
    file_keyword_counts: dict = {}

    for keyword in keywords:
        matches = _search_files_for_keyword(keyword, files_to_search)
        for match in matches:
            if match not in file_keyword_counts:
                file_keyword_counts[match] = 0
            file_keyword_counts[match] += 1

    if not file_keyword_counts:
        return ArtifactSearchResult(
            found=False, artifacts=[], keywords=keywords, scored_artifacts=[]
        )

    # Score and rank all matching artifacts
    scored = []
    for file_path, keyword_count in file_keyword_counts.items():
        scored_artifact = score_artifact(file_path, keyword_count)
        scored.append(scored_artifact)

    # Sort by score (descending), then by recency
    scored.sort(key=lambda x: (-x.score, x.days_old))

    # Return top N
    top_scored = scored[:MAX_ARTIFACTS_TO_SHOW]
    all_artifacts = sorted(file_keyword_counts.keys())

    return ArtifactSearchResult(
        found=True,
        artifacts=all_artifacts,
        keywords=keywords,
        scored_artifacts=top_scored
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
    scored_artifacts: List[ScoredArtifact],
    total_count: int,
    project_dir: Path
) -> str:
    """
    Format an artifact search hint message with ranked artifacts and summaries.

    Args:
        keywords: Keywords that were used for search
        scored_artifacts: Top-ranked artifacts with scores and summaries
        total_count: Total number of matching artifacts
        project_dir: Project directory for relative path display

    Returns:
        Formatted hint message showing top artifacts with summaries
    """
    keyword_str = ' '.join(keywords[:2])  # Use first 2 keywords

    lines = [
        "",
        "💡 PRIOR WORK HINT: Found related artifacts in project",
        ""
    ]

    # Show each scored artifact with its summary
    for i, artifact in enumerate(scored_artifacts, 1):
        try:
            rel_path = str(artifact.path.relative_to(project_dir))
        except ValueError:
            rel_path = str(artifact.path)

        # Format: path (days ago)
        age_str = "today" if artifact.days_old == 0 else f"{artifact.days_old}d ago"
        lines.append(f"   {i}. {rel_path} ({age_str})")
        lines.append(f"      {artifact.summary}")

    # Show count if there are more than displayed
    if total_count > len(scored_artifacts):
        lines.append("")
        lines.append(f"   ...and {total_count - len(scored_artifacts)} more")

    lines.extend([
        "",
        f"   Review with: orch search \"{keyword_str}\"",
        "   To skip: --skip-artifact-check",
        ""
    ])

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

    # Show hint with scored artifacts
    import click
    hint = format_artifact_hint(
        keywords=result.keywords,
        scored_artifacts=result.scored_artifacts,
        total_count=len(result.artifacts),
        project_dir=project_dir
    )
    click.echo(hint, err=True)
