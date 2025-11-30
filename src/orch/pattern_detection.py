"""Pattern detection across investigations for synthesis opportunities."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from orch.backlog_resolution import BacklogResolver, ResolutionStatus


@dataclass
class InvestigationMatch:
    """A single investigation file that matches the pattern."""
    file_path: Path
    date: str
    title: str
    status: Optional[str] = None  # Investigation lifecycle: Complete, In-Progress, Superseded
    resolution_status: Optional[str] = None  # Problem status: Unresolved, Resolved, Recurring, Synthesized, Mitigated
    keywords: List[str] = None
    relevance: Optional[str] = None  # "title", "question", "content" - where topic matched


@dataclass
class PatternAnalysis:
    """Analysis of a pattern across multiple investigations."""
    topic: str
    total_count: int
    unresolved_count: int
    recurred_count: int
    matches: List[InvestigationMatch]
    shared_keywords: List[str]
    date_range: Tuple[Optional[str], Optional[str]]  # (earliest, latest)
    red_flag_count: int = 0  # Number of frame problem red flags detected
    red_flag_examples: List[str] = None  # Example phrases that triggered red flags


@dataclass
class TrendingPattern:
    """A trending topic found across investigations."""
    keyword: str
    investigation_count: int
    unresolved_count: int
    recurred_count: int
    synthesis_score: float  # Higher = more likely synthesis opportunity
    date_range: Tuple[Optional[str], Optional[str]]
    related_keywords: List[str]


class PatternDetector:
    """Detect recurring patterns across investigation files."""

    def __init__(self):
        self.investigations_paths = []

    def find_investigations(
        self,
        project_dir: Optional[Path] = None,
        global_search: bool = False,
        max_age_days: Optional[int] = None
    ) -> List[Path]:
        """Find investigation files to analyze.

        Args:
            project_dir: Project directory to search (defaults to current dir detection)
            global_search: Search across all projects
            max_age_days: Only include investigations from last N days

        Returns:
            List of investigation file paths
        """
        search_paths = []

        if global_search:
            # Global: ~/.orch + all project .orch directories
            search_paths.append(Path.home() / ".orch" / "investigations")

            # Find all projects via registry
            try:
                from orch.registry import AgentRegistry
                registry = AgentRegistry()
                seen = set()

                for agent in registry.list_agents():
                    project_path = Path(agent['project_dir'])
                    if project_path not in seen and project_path.exists():
                        inv_path = project_path / ".orch" / "investigations"
                        if inv_path.exists():
                            search_paths.append(inv_path)
                        seen.add(project_path)
            except (ImportError, FileNotFoundError, KeyError):
                pass
        else:
            # Project-scoped: detect current project
            if project_dir is None:
                project_dir = self._detect_project_dir()

            if project_dir:
                inv_path = project_dir / ".orch" / "investigations"
                if inv_path.exists():
                    search_paths.append(inv_path)

        # Collect all .md files from search paths
        investigation_files = []
        for search_path in search_paths:
            if search_path.exists():
                # Recursively find all .md files in investigations/ subdirectories
                investigation_files.extend(search_path.rglob("*.md"))

        # Filter by age if specified
        if max_age_days is not None:
            cutoff = datetime.now() - timedelta(days=max_age_days)
            investigation_files = [
                f for f in investigation_files
                if datetime.fromtimestamp(f.stat().st_mtime) > cutoff
            ]

        return investigation_files

    def analyze_pattern(
        self,
        topic: str,
        project_dir: Optional[Path] = None,
        global_search: bool = False,
        max_age_days: Optional[int] = None,
        status_filter: Optional[str] = None,
        relevance_filter: Optional[str] = None
    ) -> PatternAnalysis:
        """Analyze pattern across investigations.

        Args:
            topic: Topic/keyword to search for
            project_dir: Project directory (defaults to current)
            global_search: Search across all projects
            max_age_days: Only analyze investigations from last N days
            status_filter: Filter by resolution status (recurring, unresolved, mitigated, resolved, all)
            relevance_filter: Filter by relevance level:
                - "high" = only title/question matches (investigation is ABOUT this topic)
                - "medium" = title/question/content matches (any mention)
                - None = no filtering (all matches)

        Returns:
            PatternAnalysis with counts, matches, and insights
        """
        # Find all investigation files
        investigation_files = self.find_investigations(
            project_dir=project_dir,
            global_search=global_search,
            max_age_days=max_age_days
        )

        # Search for topic in files using ripgrep
        matches = self._search_files(topic, investigation_files)

        # Parse matched files for metadata (pass topic for relevance calculation)
        investigation_matches = []
        for file_path in matches:
            match = self._parse_investigation(file_path, topic=topic)
            if match:
                # Apply status filter if specified
                if status_filter and status_filter.lower() != 'all':
                    if not self._matches_status_filter(match, status_filter):
                        continue
                # Apply relevance filter if specified
                if relevance_filter == "high":
                    # Only include title/question matches (investigations ABOUT this topic)
                    if match.relevance not in ["title", "question"]:
                        continue
                investigation_matches.append(match)

        # Count unresolved (Resolution-Status indicates problem not fixed)
        # Use resolution_status if available, fallback to status for backward compatibility
        unresolved_count = sum(
            1 for m in investigation_matches
            if m.resolution_status and m.resolution_status.lower() in ['unresolved', 'recurring', 'mitigated']
            or (not m.resolution_status and m.status and m.status.lower() not in ['complete', 'resolved'])
        )

        # Count recurred (check for "recur" language in files)
        recurred_count = self._count_recurred(investigation_matches)

        # Extract shared keywords
        shared_keywords = self._extract_shared_keywords(investigation_matches)

        # Determine date range
        date_range = self._get_date_range(investigation_matches)

        # Detect semantic red flags (Gemini's Leading Indicator #3)
        red_flag_count, red_flag_examples = self._detect_red_flags(investigation_matches)

        return PatternAnalysis(
            topic=topic,
            total_count=len(investigation_matches),
            unresolved_count=unresolved_count,
            recurred_count=recurred_count,
            matches=investigation_matches,
            shared_keywords=shared_keywords,
            date_range=date_range,
            red_flag_count=red_flag_count,
            red_flag_examples=red_flag_examples
        )

    def _detect_project_dir(self) -> Optional[Path]:
        """Detect if we're in a project with .orch/ directory."""
        current = Path.cwd()
        max_depth = 5

        for _ in range(max_depth):
            if (current / ".orch").exists():
                return current

            if current == current.parent:
                break
            current = current.parent

        return None

    def _detect_project_from_path(self, file_path: Path) -> Optional[Path]:
        """Detect project directory from an investigation file path.

        Walks up from the file path looking for a directory containing .orch/.

        Args:
            file_path: Path to an investigation file

        Returns:
            Path to project root, or None if not found
        """
        current = file_path.parent
        max_depth = 10

        for _ in range(max_depth):
            if (current / ".orch").exists():
                return current

            if current == current.parent:
                break
            current = current.parent

        return None

    def _search_files(self, topic: str, files: List[Path]) -> List[Path]:
        """Search files for topic using ripgrep.

        Returns list of file paths that match the topic.
        """
        if not files:
            return []

        # Use ripgrep for fast search
        try:
            # Search files directly (ripgrep can handle file list)
            result = subprocess.run(
                ['rg', '-l', '-i', topic] + [str(f) for f in files],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return [Path(line) for line in result.stdout.strip().split('\n') if line]
            elif result.returncode == 1:
                # No matches found (not an error)
                return []
            else:
                # Actual error occurred
                return []

        except FileNotFoundError:
            # ripgrep not available, fall back to grep
            matching_files = []
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if topic.lower() in content:
                            matching_files.append(file_path)
                except (UnicodeDecodeError, OSError):
                    pass
            return matching_files

    def _calculate_relevance(self, topic: str, file_path: Path, title: str, content: str) -> str:
        """Calculate relevance based on where topic appears in investigation.

        Returns:
            "title" - Topic appears in title/filename (highest relevance - investigation is ABOUT this topic)
            "question" - Topic appears in Question/Synopsis section (high relevance - investigation is ABOUT this topic)
            "content" - Topic only appears in body content (low relevance - just mentioned in passing)
        """
        topic_lower = topic.lower()

        # Check title/filename (highest relevance)
        if topic_lower in title.lower() or topic_lower in file_path.stem.lower():
            return "title"

        # Check Question/Synopsis section (high relevance)
        # Look for Question: or Synopsis: fields in first 500 chars
        header_section = content[:1000].lower()
        question_match = re.search(r'\*\*question:\*\*\s*([^\n]+)', header_section)
        synopsis_match = re.search(r'\*\*synopsis:\*\*\s*([^\n]+)', header_section)

        if question_match and topic_lower in question_match.group(1):
            return "question"
        if synopsis_match and topic_lower in synopsis_match.group(1):
            return "question"

        # Also check the first # header line (sometimes more descriptive than title field)
        first_header = re.search(r'^#\s+[^\n]*' + re.escape(topic_lower), content.lower(), re.MULTILINE)
        if first_header:
            return "title"

        # Default: content mention only (low relevance)
        return "content"

    def _parse_investigation(self, file_path: Path, topic: Optional[str] = None) -> Optional[InvestigationMatch]:
        """Parse investigation file for metadata.

        Extracts:
        - Title (from # header or filename)
        - Date (from filename or **Started:** field)
        - Status (from **Status:** field - investigation lifecycle)
        - Resolution status (from backlog.json - problem lifecycle)
        - Keywords (from content analysis)
        - Relevance (if topic provided - where topic appears)

        Note: Resolution status is now looked up from backlog.json, not from the
        investigation file. This follows the decision to separate tracking from
        knowledge. See: .orch/decisions/2025-11-28-backlog-investigation-separation.md
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title from first # header or filename
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else file_path.stem

            # Extract date from filename (YYYY-MM-DD-*.md pattern)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
            date = date_match.group(1) if date_match else None

            # If no date in filename, try **Started:** field
            if not date:
                started_match = re.search(r'\*\*Started:\*\*\s*(\d{4}-\d{2}-\d{2})', content)
                date = started_match.group(1) if started_match else None

            # Extract status (investigation lifecycle - NOT problem status)
            status_match = re.search(r'\*\*Status:\*\*\s*([^\n]+)', content)
            status = status_match.group(1).strip() if status_match else None

            # Look up resolution status from backlog.json
            # This replaces reading Resolution-Status from the file
            resolution_status = self._get_resolution_from_backlog(file_path)

            # Extract keywords (simple implementation: look for common technical terms)
            keywords = self._extract_keywords(content)

            # Calculate relevance if topic provided
            relevance = None
            if topic:
                relevance = self._calculate_relevance(topic, file_path, title, content)

            return InvestigationMatch(
                file_path=file_path,
                date=date or "unknown",
                title=title,
                status=status,
                resolution_status=resolution_status,
                keywords=keywords,
                relevance=relevance
            )

        except (OSError, UnicodeDecodeError):
            return None

    def _get_resolution_from_backlog(self, file_path: Path) -> Optional[str]:
        """Get resolution status from backlog.json for an investigation.

        Args:
            file_path: Path to investigation file

        Returns:
            Resolution status string, or None if not found in backlog
            Values: 'Resolved', 'Unresolved', 'Mitigated', None (not tracked)
        """
        project_dir = self._detect_project_from_path(file_path)
        if not project_dir:
            return None

        try:
            resolver = BacklogResolver(project_dir)
            status = resolver.get_resolution_for_investigation(str(file_path))

            # Map ResolutionStatus enum to strings for backward compatibility
            if status == ResolutionStatus.FIX:
                return "Resolved"
            elif status == ResolutionStatus.WORKAROUND:
                return "Mitigated"
            elif status == ResolutionStatus.UNRESOLVED:
                return "Unresolved"
            else:
                return None  # Not tracked in backlog
        except Exception:
            return None

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract technical keywords from investigation content.

        Simple implementation: look for common patterns.
        """
        keywords = []

        # Common technical keywords to look for
        keyword_patterns = [
            r'\b(timeout|error|failure|bug|crash|exception)\b',
            r'\b(performance|latency|slow|fast)\b',
            r'\b(proxy|network|connection|request)\b',
            r'\b(database|query|orm|sql)\b',
            r'\b(auth|authentication|authorization|permission)\b',
            r'\b(rate[- ]limit|throttle|quota)\b',
            r'\b(cache|caching|redis|memcached)\b',
        ]

        for pattern in keyword_patterns:
            matches = re.findall(pattern, content.lower())
            keywords.extend(matches)

        # Return unique keywords, most common first
        from collections import Counter
        keyword_counts = Counter(keywords)
        return [kw for kw, _ in keyword_counts.most_common(10)]

    def _count_recurred(self, matches: List[InvestigationMatch]) -> int:
        """Count investigations that mention recurrence."""
        count = 0
        for match in matches:
            try:
                with open(match.file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    if any(keyword in content for keyword in ['recur', 'recurring', 'happened again', 'similar to']):
                        count += 1
            except (OSError, UnicodeDecodeError):
                pass
        return count

    def _detect_red_flags(self, matches: List[InvestigationMatch]) -> Tuple[int, List[str]]:
        """Detect semantic red flags indicating frame problems.

        Red flags: "inherent", "fundamental", "systematic limitation", "all X show"

        Returns:
            Tuple of (red_flag_count, example_phrases)
        """
        red_flag_patterns = [
            r'inherent(?:ly)?\s+\w+',
            r'fundamental\s+(?:architectural\s+)?problem',
            r'systematic\s+limitation',
            r'not\s+specific\s+to\s+\w+',
            r'all\s+\w+\s+show\s+the\s+same'
        ]

        count = 0
        examples = []

        for match in matches:
            try:
                with open(match.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern in red_flag_patterns:
                        matches_found = re.findall(pattern, content, re.IGNORECASE)
                        if matches_found:
                            count += len(matches_found)
                            # Collect unique examples (limit to 3)
                            for phrase in matches_found[:3]:
                                if phrase not in examples and len(examples) < 3:
                                    examples.append(phrase)
            except (OSError, UnicodeDecodeError):
                pass

        return count, examples

    def _extract_shared_keywords(self, matches: List[InvestigationMatch]) -> List[str]:
        """Find keywords that appear in multiple investigations."""
        if not matches:
            return []

        # Count keyword frequency across all matches
        from collections import Counter
        all_keywords = []
        for match in matches:
            if match.keywords:
                all_keywords.extend(match.keywords)

        # Return keywords that appear in at least 2 investigations
        keyword_counts = Counter(all_keywords)
        shared = [
            kw for kw, count in keyword_counts.most_common()
            if count >= 2
        ]

        return shared[:10]  # Top 10 shared keywords

    def _get_date_range(self, matches: List[InvestigationMatch]) -> Tuple[Optional[str], Optional[str]]:
        """Get earliest and latest dates from matches."""
        if not matches:
            return (None, None)

        dates = [m.date for m in matches if m.date and m.date != "unknown"]
        if not dates:
            return (None, None)

        dates.sort()
        return (dates[0], dates[-1])

    def analyze_trending_patterns(
        self,
        project_dir: Optional[Path] = None,
        global_search: bool = False,
        max_age_days: Optional[int] = None,
        min_count: int = 3,
        limit: int = 10
    ) -> List[TrendingPattern]:
        """Analyze all investigations to find trending patterns.

        Args:
            project_dir: Project directory (defaults to current)
            global_search: Search across all projects
            max_age_days: Only analyze investigations from last N days
            min_count: Minimum investigation count to include pattern (default: 3)
            limit: Maximum number of patterns to return (default: 10)

        Returns:
            List of TrendingPattern sorted by synthesis score (highest first)
        """
        from collections import Counter, defaultdict

        # Find all investigation files
        investigation_files = self.find_investigations(
            project_dir=project_dir,
            global_search=global_search,
            max_age_days=max_age_days
        )

        # Parse all investigations and collect keywords
        keyword_to_investigations = defaultdict(list)
        all_investigations = []

        for file_path in investigation_files:
            match = self._parse_investigation(file_path)
            if match and match.keywords:
                all_investigations.append(match)
                for keyword in match.keywords:
                    keyword_to_investigations[keyword].append(match)

        # Build trending patterns
        trending_patterns = []

        for keyword, investigations in keyword_to_investigations.items():
            # Filter by minimum count
            if len(investigations) < min_count:
                continue

            # Count unresolved (use resolution_status if available)
            unresolved_count = sum(
                1 for inv in investigations
                if inv.resolution_status and inv.resolution_status.lower() in ['unresolved', 'recurring', 'mitigated']
                or (not inv.resolution_status and inv.status and inv.status.lower() not in ['complete', 'resolved'])
            )

            # Count recurred
            recurred_count = self._count_recurred(investigations)

            # Get date range
            date_range = self._get_date_range(investigations)

            # Extract related keywords (keywords that frequently co-occur)
            related_keywords = self._get_related_keywords(keyword, investigations)

            # Calculate synthesis score
            # Higher score = more likely synthesis opportunity
            # Factors: count, unresolved ratio, recurrence ratio
            synthesis_score = self._calculate_synthesis_score(
                len(investigations), unresolved_count, recurred_count
            )

            trending_patterns.append(TrendingPattern(
                keyword=keyword,
                investigation_count=len(investigations),
                unresolved_count=unresolved_count,
                recurred_count=recurred_count,
                synthesis_score=synthesis_score,
                date_range=date_range,
                related_keywords=related_keywords
            ))

        # Sort by synthesis score (highest first) and limit
        trending_patterns.sort(key=lambda p: p.synthesis_score, reverse=True)
        return trending_patterns[:limit]

    def _get_related_keywords(self, primary_keyword: str, investigations: List[InvestigationMatch]) -> List[str]:
        """Find keywords that frequently co-occur with primary keyword."""
        from collections import Counter

        co_occurring = []
        for inv in investigations:
            if inv.keywords:
                # Add all keywords except the primary one
                co_occurring.extend([kw for kw in inv.keywords if kw != primary_keyword])

        # Return top 3 most common co-occurring keywords
        keyword_counts = Counter(co_occurring)
        return [kw for kw, _ in keyword_counts.most_common(3)]

    def _calculate_synthesis_score(self, total: int, unresolved: int, recurred: int) -> float:
        """Calculate synthesis opportunity score.

        Higher score = more likely synthesis opportunity
        Factors:
        - Total count (more investigations = higher score)
        - Unresolved ratio (more unresolved = higher score)
        - Recurrence ratio (more recurrence = higher score)
        """
        # Base score from count (diminishing returns after 10)
        count_score = min(total / 10.0, 1.0) * 50

        # Unresolved ratio (0-30 points)
        unresolved_ratio = unresolved / total if total > 0 else 0
        unresolved_score = unresolved_ratio * 30

        # Recurrence ratio (0-20 points)
        recurred_ratio = recurred / total if total > 0 else 0
        recurred_score = recurred_ratio * 20

        return count_score + unresolved_score + recurred_score

    def find_existing_synthesis(
        self,
        topic: str,
        project_dir: Optional[Path] = None,
        global_search: bool = False
    ) -> Optional[Tuple[Path, str]]:
        """Find existing synthesis file for topic.

        Args:
            topic: Topic/keyword to search for in synthesis filenames
            project_dir: Project directory (defaults to current)
            global_search: Search across all projects

        Returns:
            Tuple of (synthesis_path, status) if found, None otherwise
        """
        search_paths = []

        if global_search:
            # Global: ~/.orch + all project .orch directories
            search_paths.append(Path.home() / ".orch" / "synthesis")

            # Find all projects via registry
            try:
                from orch.registry import AgentRegistry
                registry = AgentRegistry()
                seen = set()

                for agent in registry.list_agents():
                    project_path = Path(agent['project_dir'])
                    if project_path not in seen and project_path.exists():
                        syn_path = project_path / ".orch" / "synthesis"
                        if syn_path.exists():
                            search_paths.append(syn_path)
                        seen.add(project_path)
            except (ImportError, FileNotFoundError, KeyError):
                pass
        else:
            # Project-scoped: detect current project
            if project_dir is None:
                project_dir = self._detect_project_dir()

            if project_dir:
                syn_path = project_dir / ".orch" / "synthesis"
                if syn_path.exists():
                    search_paths.append(syn_path)

        # Search for synthesis files matching topic
        # Use ripgrep on filename (case-insensitive)
        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Find .md files with topic in filename
            try:
                result = subprocess.run(
                    ['find', str(search_path), '-type', 'f', '-name', '*.md'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                for file_path in result.stdout.strip().split('\n'):
                    if not file_path:
                        continue

                    path = Path(file_path)
                    # Check if topic appears in filename (case-insensitive)
                    if topic.lower() in path.stem.lower():
                        # Parse synthesis file to extract status
                        try:
                            from orch.synthesis import parse_synthesis_file
                            synthesis_data = parse_synthesis_file(path)
                            return (path, synthesis_data.get('status', 'Unknown'))
                        except Exception:
                            # If parsing fails, just return path with unknown status
                            return (path, 'Unknown')

            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                continue

        return None

    def _matches_status_filter(self, match: InvestigationMatch, status_filter: str) -> bool:
        """Check if investigation matches the status filter.

        Args:
            match: InvestigationMatch to check
            status_filter: Status to filter by (recurring, unresolved, mitigated, resolved)

        Returns:
            True if match passes filter, False otherwise
        """
        if not status_filter or status_filter.lower() == 'all':
            return True

        status_filter_lower = status_filter.lower()

        # Use resolution_status if available
        if match.resolution_status:
            resolution_lower = match.resolution_status.lower()
            return resolution_lower == status_filter_lower

        # Fallback to status for backward compatibility
        if match.status:
            status_lower = match.status.lower()
            # Map old status values to resolution status equivalents
            if status_filter_lower == 'unresolved':
                # Match In Progress, Open, Pending (but not Complete, Resolved, Root Cause Identified)
                return any(term in status_lower for term in ['in progress', 'in-progress', 'ongoing', 'open', 'pending'])
            elif status_filter_lower == 'resolved':
                # Match Complete, Resolved, Root Cause Identified, Validated
                return any(term in status_lower for term in ['complete', 'resolved', 'root cause identified', 'validated'])

        return False

    def dashboard_analysis(
        self,
        project_dir: Optional[Path] = None,
        global_search: bool = False,
        status_filter: Optional[str] = None,
        age_filter_days: Optional[int] = None,
        age_filter_mode: Optional[str] = None
    ) -> Dict[str, any]:
        """Analyze all investigations for dashboard view.

        Args:
            project_dir: Project directory (defaults to current)
            global_search: Search across all projects
            status_filter: Filter by resolution status (recurring, unresolved, mitigated, resolved, all)
            age_filter_days: Number of days for age filtering
            age_filter_mode: 'stale' (older than N days) or 'recent' (newer than N days) or None

        Returns:
            Dictionary with dashboard data including counts and investigation matches
        """
        from datetime import datetime, timedelta

        # Find all investigation files
        investigation_files = self.find_investigations(
            project_dir=project_dir,
            global_search=global_search,
            max_age_days=None  # Don't filter by age at file level, we'll do it later
        )

        # Parse all investigation files
        all_matches = []
        for file_path in investigation_files:
            match = self._parse_investigation(file_path)
            if match:
                all_matches.append(match)

        # Apply status filter
        if status_filter and status_filter.lower() != 'all':
            all_matches = [m for m in all_matches if self._matches_status_filter(m, status_filter)]

        # Apply age filter based on mode
        if age_filter_days is not None and age_filter_mode:
            cutoff = datetime.now() - timedelta(days=age_filter_days)
            filtered_matches = []

            for match in all_matches:
                try:
                    # Parse date from match
                    if match.date and match.date != "unknown":
                        inv_date = datetime.strptime(match.date, "%Y-%m-%d")

                        if age_filter_mode == 'stale':
                            # Keep if older than cutoff
                            if inv_date < cutoff:
                                filtered_matches.append(match)
                        elif age_filter_mode == 'recent':
                            # Keep if newer than cutoff
                            if inv_date > cutoff:
                                filtered_matches.append(match)
                except (ValueError, AttributeError):
                    # If date parsing fails, skip this investigation
                    pass

            all_matches = filtered_matches
        elif age_filter_days is not None and not age_filter_mode:
            # Standard days filter (last N days)
            cutoff = datetime.now() - timedelta(days=age_filter_days)
            filtered_matches = []

            for match in all_matches:
                try:
                    if match.date and match.date != "unknown":
                        inv_date = datetime.strptime(match.date, "%Y-%m-%d")
                        if inv_date > cutoff:
                            filtered_matches.append(match)
                except (ValueError, AttributeError):
                    pass

            all_matches = filtered_matches

        # Count by resolution status
        status_counts = {
            'recurring': 0,
            'unresolved': 0,
            'mitigated': 0,
            'resolved': 0,
            'other': 0
        }

        for match in all_matches:
            if match.resolution_status:
                # Use explicit resolution_status field
                status_key = match.resolution_status.lower()
                if status_key in status_counts:
                    status_counts[status_key] += 1
                else:
                    status_counts['other'] += 1
            elif match.status:
                # Fallback: infer from Status field for backward compatibility
                status_lower = match.status.lower()

                # Resolved: Complete, Resolved, Root Cause Identified (investigation done)
                if any(term in status_lower for term in ['complete', 'resolved', 'root cause identified', 'validated']):
                    status_counts['resolved'] += 1
                # Unresolved: In Progress, Open, Pending
                elif any(term in status_lower for term in ['in progress', 'in-progress', 'ongoing', 'open', 'pending']):
                    status_counts['unresolved'] += 1
                # Superseded (investigation lifecycle status, not resolution status)
                elif 'superseded' in status_lower:
                    status_counts['other'] += 1
                else:
                    status_counts['other'] += 1
            else:
                # No status information at all
                status_counts['other'] += 1

        # Sort matches by date (newest first)
        all_matches.sort(key=lambda m: m.date if m.date != "unknown" else "0000-00-00", reverse=True)

        return {
            'total_count': len(all_matches),
            'status_counts': status_counts,
            'matches': all_matches,
            'date_range': self._get_date_range(all_matches)
        }


def format_pattern_analysis(analysis: PatternAnalysis, show_files: bool = False) -> str:
    """Format pattern analysis for display.

    Args:
        analysis: PatternAnalysis result
        show_files: Whether to show individual file matches

    Returns:
        Formatted string for terminal display
    """
    lines = []

    # Summary
    lines.append(f"Found {analysis.total_count} investigation(s) related to '{analysis.topic}'")

    # Date range if available
    if analysis.date_range[0]:
        lines.append(f"  Date range: {analysis.date_range[0]} to {analysis.date_range[1]}")

    # Stats
    lines.append(f"  - {analysis.unresolved_count}/{analysis.total_count} unresolved")
    if analysis.recurred_count > 0:
        lines.append(f"  - {analysis.recurred_count}/{analysis.total_count} mention recurrence")

    # Shared keywords
    if analysis.shared_keywords:
        lines.append(f"  - Shared keywords: {', '.join(analysis.shared_keywords)}")

    # Red flag detection (Gemini's Leading Indicator #3)
    if analysis.red_flag_count > 0:
        lines.append(f"  - 🔴 Red flags detected: {analysis.red_flag_count} frame problem indicators")
        if analysis.red_flag_examples:
            lines.append(f"     Examples: {', '.join(f'"{ex}"' for ex in analysis.red_flag_examples)}")

    lines.append("")

    # Synthesis opportunity signal
    # Emphasize synthesis if red flags detected (frame problem language)
    if analysis.red_flag_count > 0:
        lines.append("🔴 RED FLAG DETECTED: Frame problem language")
        lines.append("   Investigations use 'inherent' or 'fundamental' - this suggests systemic issue")
        lines.append("   💡 Consider synthesis (not local optimization)")
        lines.append("      Run synthesis to identify category-level solutions")
    elif analysis.total_count >= 3 and (analysis.unresolved_count >= 2 or analysis.recurred_count >= 1):
        lines.append("💡 Synthesis opportunity: Consider cross-investigation analysis")
        lines.append(f"   Multiple {('unresolved ' if analysis.unresolved_count >= 2 else '')}investigations suggest systemic pattern")
    elif analysis.total_count >= 3:
        lines.append(f"ℹ️  Pattern detected: {analysis.total_count} related investigations")
        lines.append("   Monitor for recurrence or resolution failures")
    else:
        lines.append("ℹ️  Limited pattern data: < 3 investigations found")

    # File list if requested
    if show_files and analysis.matches:
        lines.append("")
        lines.append("Matching investigations:")
        for match in analysis.matches:
            # Use resolution_status if available, fallback to status
            if match.resolution_status:
                if match.resolution_status.lower() == 'recurring':
                    status_marker = "🔴"  # Red - recurring problem (high priority!)
                    status_label = f"Recurring ({match.resolution_status})"
                elif match.resolution_status.lower() in ['unresolved', 'mitigated']:
                    status_marker = "🟡"  # Yellow - unresolved/mitigated
                    status_label = match.resolution_status
                elif match.resolution_status.lower() == 'resolved':
                    status_marker = "✅"  # Green - resolved
                    status_label = match.resolution_status
                elif match.resolution_status.lower() == 'synthesized':
                    status_marker = "🔵"  # Blue - fed into synthesis
                    status_label = match.resolution_status
                else:
                    status_marker = "⚪"  # Unknown
                    status_label = match.resolution_status
            else:
                # Fallback: use investigation status for backward compatibility
                status_marker = "🔴" if match.status and match.status.lower() not in ['complete', 'resolved'] else "✅"
                status_label = f"Status: {match.status}" if match.status else "No status"

            lines.append(f"  {status_marker} {match.date}: {match.title}")
            lines.append(f"     Resolution: {status_label}")
            lines.append(f"     {match.file_path}")

    return "\n".join(lines)


def format_trending_analysis(patterns: List[TrendingPattern], max_age_days: Optional[int] = None) -> str:
    """Format trending pattern analysis for display.

    Args:
        patterns: List of TrendingPattern results
        max_age_days: Time window for analysis (for display context)

    Returns:
        Formatted string for terminal display
    """
    if not patterns:
        return "No trending patterns found (minimum 3 investigations per topic)"

    lines = []

    # Header
    time_window = f"last {max_age_days} days" if max_age_days else "all time"
    lines.append(f"📊 Trending patterns ({time_window}):\n")

    # Display each pattern
    for i, pattern in enumerate(patterns, 1):
        # Synthesis opportunity indicator
        synthesis_marker = "💡" if pattern.synthesis_score >= 60 else ""

        lines.append(f"{i}. {pattern.keyword} {synthesis_marker}")
        lines.append(f"   {pattern.investigation_count} investigations, {pattern.unresolved_count} unresolved")

        if pattern.recurred_count > 0:
            lines.append(f"   {pattern.recurred_count} mention recurrence")

        if pattern.related_keywords:
            lines.append(f"   Related: {', '.join(pattern.related_keywords)}")

        if pattern.date_range[0]:
            lines.append(f"   Date range: {pattern.date_range[0]} to {pattern.date_range[1]}")

        lines.append("")  # Blank line between patterns

    # Legend
    lines.append("💡 = High synthesis opportunity (score ≥ 60)")
    lines.append("\nUse 'orch patterns <keyword> --show-files' to see specific investigations")

    return "\n".join(lines)


def format_dashboard_analysis(
    dashboard_data: Dict,
    show_files: bool = False,
    status_filter: Optional[str] = None,
    age_filter_days: Optional[int] = None,
    age_filter_mode: Optional[str] = None
) -> str:
    """Format dashboard analysis for display.

    Args:
        dashboard_data: Dashboard data from dashboard_analysis
        show_files: Whether to show individual file matches
        status_filter: Active status filter (for display context)
        age_filter_days: Active age filter (for display context)
        age_filter_mode: Age filter mode ('stale', 'recent', or None)

    Returns:
        Formatted string for terminal display
    """
    lines = []

    # Build filter description
    filters = []
    if status_filter and status_filter.lower() != 'all':
        filters.append(f"status={status_filter}")
    if age_filter_mode == 'stale':
        filters.append(f"stale (>{age_filter_days} days)")
    elif age_filter_mode == 'recent':
        filters.append(f"recent (<{age_filter_days} days)")
    elif age_filter_days:
        filters.append(f"last {age_filter_days} days")

    filter_text = f" ({', '.join(filters)})" if filters else ""

    # Header
    lines.append(f"📊 Investigation Dashboard{filter_text}\n")

    # Summary stats
    total = dashboard_data['total_count']
    status_counts = dashboard_data['status_counts']

    if total == 0:
        lines.append("No investigations found matching filters")
        return "\n".join(lines)

    lines.append(f"Total investigations: {total}")

    # Status breakdown
    if any(count > 0 for count in status_counts.values()):
        lines.append("\nBy resolution status:")
        if status_counts['recurring'] > 0:
            lines.append(f"  🔴 Recurring: {status_counts['recurring']}")
        if status_counts['unresolved'] > 0:
            lines.append(f"  🟡 Unresolved: {status_counts['unresolved']}")
        if status_counts['mitigated'] > 0:
            lines.append(f"  🟠 Mitigated: {status_counts['mitigated']}")
        if status_counts['resolved'] > 0:
            lines.append(f"  ✅ Resolved: {status_counts['resolved']}")
        if status_counts['other'] > 0:
            lines.append(f"  ⚪ Other/Unknown: {status_counts['other']}")

    # Date range
    if dashboard_data['date_range'][0]:
        lines.append(f"\nDate range: {dashboard_data['date_range'][0]} to {dashboard_data['date_range'][1]}")

    # Attention items (recurring and unresolved)
    attention_count = status_counts['recurring'] + status_counts['unresolved']
    if attention_count > 0:
        lines.append(f"\n⚠️  {attention_count} investigation(s) need attention (recurring/unresolved)")

    # File list if requested
    if show_files and dashboard_data['matches']:
        lines.append("\n" + "="*60)
        lines.append("Investigations:")
        lines.append("="*60 + "\n")

        for match in dashboard_data['matches']:
            # Determine status marker and label
            if match.resolution_status:
                status_lower = match.resolution_status.lower()
                if status_lower == 'recurring':
                    status_marker = "🔴"
                    status_label = f"Recurring ({match.resolution_status})"
                elif status_lower in ['unresolved', 'mitigated']:
                    status_marker = "🟡" if status_lower == 'unresolved' else "🟠"
                    status_label = match.resolution_status
                elif status_lower == 'resolved':
                    status_marker = "✅"
                    status_label = match.resolution_status
                elif status_lower == 'synthesized':
                    status_marker = "🔵"
                    status_label = match.resolution_status
                else:
                    status_marker = "⚪"
                    status_label = match.resolution_status
            else:
                # Fallback: use investigation status
                status_marker = "🔴" if match.status and match.status.lower() not in ['complete', 'resolved'] else "✅"
                status_label = f"Status: {match.status}" if match.status else "No status"

            lines.append(f"{status_marker} {match.date}: {match.title}")
            lines.append(f"   Resolution: {status_label}")
            lines.append(f"   {match.file_path}")
            lines.append("")  # Blank line between investigations

    else:
        lines.append(f"\nUse --show-files to see individual investigations")

    # Help text
    lines.append("\n" + "="*60)
    lines.append("Filter options:")
    lines.append("  --status recurring|unresolved|mitigated|resolved|all")
    lines.append("  --recent       Last 7 days")
    lines.append("  --stale        Older than 30 days")
    lines.append("  --days N       Last N days")
    lines.append("  --show-files   Show individual investigation files")

    return "\n".join(lines)
