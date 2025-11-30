from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from orch.backlog_resolution import BacklogResolver, ResolutionStatus


@dataclass
class ArtifactReference:
    """Reference count information for an artifact."""
    reference_count: int
    last_referenced: Optional[str]  # ISO-8601 timestamp
    referenced_by: List[str]  # File paths that reference this artifact


@dataclass
class SearchResult:
    """A single search result with context."""
    file_path: str
    matches: List[Tuple[int, str]]  # (line_number, line_content)
    reference_info: Optional[ArtifactReference] = None
    metadata: Optional[Dict[str, str]] = None


class ReferenceCache:
    """Manages artifact reference count cache."""

    CACHE_VERSION = "1.0"

    def __init__(self, cache_path: Optional[Path] = None):
        if cache_path is None:
            cache_path = Path.home() / ".orch" / "cache" / "artifact-references.json"
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, ArtifactReference] = {}
        self._last_updated: Optional[datetime] = None

    def load(self) -> None:
        """Load cache from disk."""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path) as f:
                data = json.load(f)

            # Validate cache version
            if data.get("cache_version") != self.CACHE_VERSION:
                # Incompatible version, rebuild
                return

            # Load last updated timestamp
            if "last_updated" in data:
                self._last_updated = datetime.fromisoformat(data["last_updated"])

            # Load artifact references
            for path, ref_data in data.get("artifacts", {}).items():
                self._data[path] = ArtifactReference(
                    reference_count=ref_data["reference_count"],
                    last_referenced=ref_data.get("last_referenced"),
                    referenced_by=ref_data.get("referenced_by", [])
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted cache, will rebuild
            pass

    def save(self) -> None:
        """Save cache to disk."""
        data = {
            "cache_version": self.CACHE_VERSION,
            "last_updated": datetime.now().isoformat(),
            "artifacts": {
                path: asdict(ref) for path, ref in self._data.items()
            }
        }

        with open(self.cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get(self, artifact_path: str) -> Optional[ArtifactReference]:
        """Get reference information for an artifact."""
        return self._data.get(artifact_path)

    def needs_rebuild(self, max_age: Optional[timedelta] = None) -> bool:
        """Check if cache needs rebuilding."""
        if not self._last_updated:
            return True

        if max_age and datetime.now() - self._last_updated > max_age:
            return True

        return False

    def rebuild(self, search_paths: List[Path]) -> None:
        """Rebuild reference counts by scanning all files."""
        self._data.clear()

        # Find all artifacts first
        artifact_files = self._find_all_artifacts(search_paths)

        # Initialize all artifacts with zero count and build lookup map
        # Map: filename -> List[full_path] to handle potential duplicates or relative refs
        artifact_lookup: Dict[str, List[str]] = {}
        
        for artifact_file in artifact_files:
            full_path = str(artifact_file)
            name = artifact_file.name
            
            self._data[full_path] = ArtifactReference(
                reference_count=0,
                last_referenced=None,
                referenced_by=[]
            )
            
            # Add to lookup
            if name not in artifact_lookup:
                artifact_lookup[name] = []
            artifact_lookup[name].append(full_path)

        # Scan all markdown files for references to artifacts
        scannable_files = self._find_scannable_files(search_paths)
        
        # Compile regex for finding .md links/filenames once
        # Matches typical filenames: 2025-11-20-foo.md, something.md
        # We extract tokens that look like markdown files
        ref_pattern = re.compile(r'[a-zA-Z0-9_\-\./]+\.md')

        for file_path in scannable_files:
            self._scan_file_for_references(file_path, artifact_lookup, ref_pattern)

        # Update last_updated
        self._last_updated = datetime.now()

        # Save cache
        self.save()

    def _find_all_artifacts(self, search_paths: List[Path]) -> Set[Path]:
        """Find all artifact files to track."""
        artifacts = set()

        for base_path in search_paths:
            if not base_path.exists():
                continue

            # Find investigations, decisions, knowledge (recursive for investigations)
            for pattern in [
                "**/.orch/investigations/**/*.md",
                "**/.orch/decisions/*.md",
                "**/.orch/knowledge/*.md"
            ]:
                artifacts.update(base_path.glob(pattern))

        return artifacts

    def _find_scannable_files(self, search_paths: List[Path]) -> Set[Path]:
        """Find all files to scan for references."""
        scannable = set()

        for base_path in search_paths:
            if not base_path.exists():
                continue

            # Scan workspaces and coordination journals
            scannable.update(base_path.glob("**/.orch/workspace/**/*.md"))

        return scannable

    def _scan_file_for_references(
        self, 
        file_path: Path, 
        artifact_lookup: Dict[str, List[str]],
        ref_pattern: re.Pattern
    ) -> None:
        """Scan a single file for artifact references using regex."""
        try:
            content = file_path.read_text()
        except (IOError, UnicodeDecodeError):
            return

        # Extract all potential markdown file references
        # matches set to avoid counting same ref twice in one file
        matches = set(ref_pattern.findall(content))
        
        for match in matches:
            # match could be "foo.md" or "path/to/foo.md"
            # We check if the basename exists in our artifacts
            match_name = Path(match).name
            
            if match_name in artifact_lookup:
                # Found a reference! Update all artifacts with this name
                # (usually just one, but handles collisions)
                for artifact_full_path in artifact_lookup[match_name]:
                    ref_info = self._data.get(artifact_full_path)
                    if ref_info:
                        ref_info.reference_count += 1
                        if str(file_path) not in ref_info.referenced_by:
                            ref_info.referenced_by.append(str(file_path))

                        # Update last_referenced with file's mtime
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if not ref_info.last_referenced or mtime > datetime.fromisoformat(ref_info.last_referenced):
                            ref_info.last_referenced = mtime.isoformat()


class ArtifactSearcher:
    """Search artifacts with reference count tracking."""

    def __init__(self, cache: Optional[ReferenceCache] = None):
        self.cache = cache or ReferenceCache()
        self._has_rg = self._has_command("rg")  # Cache once, not per-file

    def search(
        self,
        query: str,
        artifact_type: str = "all",
        project: Optional[str] = None,
        global_search: bool = False,
        rebuild_cache: bool = False
    ) -> List[SearchResult]:
        """Search artifacts with reference counts.

        Args:
            query: Search query (regex supported)
            artifact_type: Filter by type (investigations, decisions, knowledge, workspace, all)
            project: Filter to specific project name
            global_search: Search across all projects
            rebuild_cache: Force cache rebuild before search

        Returns:
            List of search results with reference information
        """
        # Determine search scope
        search_paths = self._get_search_paths(global_search)

        # Load or rebuild cache
        if rebuild_cache or self.cache.needs_rebuild(max_age=timedelta(days=7)):
            self.cache.rebuild(search_paths)
        else:
            self.cache.load()

        # Find matching files
        matching_files = self._find_matching_files(
            query, search_paths, artifact_type, project
        )

        # Build results with reference info and metadata
        results = []
        for file_path, matches in matching_files:
            ref_info = self.cache.get(str(file_path))
            metadata = extract_artifact_metadata(str(file_path))
            results.append(SearchResult(
                file_path=str(file_path),
                matches=matches,
                reference_info=ref_info,
                metadata=metadata
            ))

        return results

    def _get_search_paths(self, global_search: bool) -> List[Path]:
        """Get base directories to search."""
        if not global_search:
            # Try to detect project directory
            project_dir = self._detect_project_dir()
            if project_dir:
                return [project_dir]

        # Global search: use registry to discover all projects + global .orch
        paths = [Path.home() / ".orch"]

        # Add all unique project directories from registry
        try:
            from orch.registry import AgentRegistry
            registry = AgentRegistry()
            seen = {Path.home() / ".orch"}  # Track to avoid duplicates

            for agent in registry.list_agents():
                project_dir = Path(agent['project_dir'])
                if project_dir not in seen and project_dir.exists():
                    paths.append(project_dir)
                    seen.add(project_dir)
        except (ImportError, FileNotFoundError, KeyError):
            # Fallback to standard locations if registry unavailable
            paths.extend([
                Path.home() / "Documents" / "personal",
                Path.home() / "Documents" / "work"
            ])

        return paths

    def _detect_project_dir(self) -> Optional[Path]:
        """Detect if we're in a project with .orch/"""
        current = Path.cwd()
        max_depth = 5

        for _ in range(max_depth):
            if (current / ".orch").exists():
                return current

            if current == current.parent or current == Path.home():
                break

            current = current.parent

        return None

    def _find_matching_files(
        self,
        query: str,
        search_paths: List[Path],
        artifact_type: str,
        project: Optional[str]
    ) -> List[Tuple[Path, List[Tuple[int, str]]]]:
        """Find files matching the query.

        Returns list of (file_path, [(line_num, line_content), ...])
        """
        # Build glob patterns based on type
        patterns = self._get_glob_patterns(artifact_type)
        
        results = []
        
        # Optimized search using batched rg if available
        if self._has_command("rg"):
            for base_path in search_paths:
                if not base_path.exists():
                    continue
                    
                # Use rg to find FILES first (fast)
                # This avoids complex output parsing of -C 2 and lets us use _search_file consistently
                files_cmd = ["rg", "--hidden", "-l", "-i"]
                
                # Add glob patterns (-g works on filenames, not full paths usually, but we can try)
                # Note: rg globs are simpler. ** patterns work.
                for pattern in patterns:
                    files_cmd.extend(["-g", pattern])
                    
                files_cmd.append(query)
                files_cmd.append(str(base_path))
                
                try:
                    files_res = subprocess.run(files_cmd, capture_output=True, text=True)
                    if files_res.returncode == 0:
                        found_files = files_res.stdout.splitlines()
                        for file_path_str in found_files:
                            file_path = Path(file_path_str)
                            # Apply project filter
                            if project and project not in str(file_path):
                                continue
                                
                            # Now get matches for this file
                            matches = self._search_file(file_path, query)
                            if matches:
                                results.append((file_path, matches))
                                
                except subprocess.CalledProcessError:
                    pass
        else:
            # Fallback to Python implementation
            for base_path in search_paths:
                if not base_path.exists():
                    continue

                for pattern in patterns:
                    for file_path in base_path.glob(pattern):
                        # Apply project filter if specified
                        if project and project not in str(file_path):
                            continue

                        # Search within file using ripgrep if available (fallback inside loop)
                        matches = self._search_file(file_path, query)
                        if matches:
                            results.append((file_path, matches))

        return results

    def _get_glob_patterns(self, artifact_type: str) -> List[str]:
        """Get glob patterns for artifact type.

        Returns patterns for both:
        - Project-scoped artifacts: **/.orch/TYPE/**/*.md
        - Global artifacts (when searching from ~/.orch): TYPE/**/*.md
        """
        if artifact_type == "investigations":
            return [
                "**/.orch/investigations/**/*.md",
                "investigations/**/*.md"  # For global ~/.orch
            ]
        elif artifact_type == "decisions":
            return [
                "**/.orch/decisions/*.md",
                "decisions/*.md"  # For global ~/.orch
            ]
        elif artifact_type == "knowledge":
            return [
                "**/.orch/knowledge/*.md",
                "knowledge/*.md"  # For global ~/.orch
            ]
        elif artifact_type == "workspace":
            return [
                "**/.orch/workspace/**/*.md",
                "workspace/**/*.md"  # For global ~/.orch
            ]
        else:  # all
            return [
                "**/.orch/investigations/**/*.md",
                "investigations/**/*.md",
                "**/.orch/decisions/*.md",
                "decisions/*.md",
                "**/.orch/knowledge/*.md",
                "knowledge/*.md"
            ]

    def _search_file(self, file_path: Path, query: str) -> List[Tuple[int, str]]:
        """Search within a file for the query.

        Returns list of (line_number, line_content) tuples.
        """
        try:
            # Try using ripgrep first (faster)
            if self._has_rg:
                result = subprocess.run(
                    ["rg", "--hidden", "-i", "-n", "-C", "2", query, str(file_path)],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    matches = []
                    for line in result.stdout.split('\n'):
                        if not line:
                            continue
                        # Parse ripgrep output: "line_num:content"
                        match = re.match(r'(\d+):(.*)$', line)
                        if match:
                            matches.append((int(match.group(1)), match.group(2)))
                    return matches

            # Fallback to Python implementation
            with open(file_path) as f:
                lines = f.readlines()

            matches = []
            pattern = re.compile(query, re.IGNORECASE)

            for i, line in enumerate(lines, start=1):
                if pattern.search(line):
                    matches.append((i, line.rstrip()))

            return matches

        except (IOError, UnicodeDecodeError):
            return []

    @staticmethod
    def _has_command(cmd: str) -> bool:
        """Check if command is available."""
        try:
            subprocess.run(
                ["which", cmd],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False


def extract_artifact_metadata(file_path: str) -> Dict[str, str]:
    """Extract metadata from artifact markdown files.

    Extracts:
    - tldr: First line after ## TLDR or content after **TLDR:**
    - status: Resolution status from backlog.json (for investigations)
    - date: YYYY-MM-DD from filename prefix
    - type: Derived from directory structure

    Note: Resolution status is now looked up from backlog.json, not from the
    investigation file. This follows the decision to separate tracking from
    knowledge. See: .orch/decisions/2025-11-28-backlog-investigation-separation.md

    Args:
        file_path: Path to artifact markdown file

    Returns:
        Dictionary with metadata fields (empty strings if not found)
    """
    metadata = {
        "tldr": "",
        "status": "",
        "date": "",
        "type": "unknown"
    }

    # Extract date from filename (YYYY-MM-DD prefix)
    filename = Path(file_path).name
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_match:
        metadata["date"] = date_match.group(1)

    # Extract type from directory structure
    path = Path(file_path)
    path_str = str(path)

    if "/investigations/systems/" in path_str or "\\investigations\\systems\\" in path_str:
        metadata["type"] = "investigation-systems"
    elif "/investigations/feasibility/" in path_str or "\\investigations\\feasibility\\" in path_str:
        metadata["type"] = "investigation-feasibility"
    elif "/investigations/audits/" in path_str or "\\investigations\\audits\\" in path_str:
        metadata["type"] = "investigation-audits"
    elif "/investigations/performance/" in path_str or "\\investigations\\performance\\" in path_str:
        metadata["type"] = "investigation-performance"
    elif "/investigations/agent-failures/" in path_str or "\\investigations\\agent-failures\\" in path_str:
        metadata["type"] = "investigation-agent-failures"
    elif "/investigations/" in path_str or "\\investigations\\" in path_str:
        metadata["type"] = "investigation"
    elif "/decisions/" in path_str or "\\decisions\\" in path_str:
        metadata["type"] = "decision"
    elif "/knowledge/" in path_str or "\\knowledge\\" in path_str:
        metadata["type"] = "knowledge"
    elif "/workspace/" in path_str or "\\workspace\\" in path_str:
        metadata["type"] = "workspace"

    # Try to read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, UnicodeDecodeError, FileNotFoundError):
        return metadata

    # Extract TLDR - try **TLDR:** format first
    tldr_inline_match = re.search(r'\*\*TLDR:\*\*\s*(.+?)(?:\n|$)', content)
    if tldr_inline_match:
        metadata["tldr"] = tldr_inline_match.group(1).strip()
    else:
        # Try ## TLDR heading format
        # Match content after ## TLDR until next heading or double newline
        # Ensure we don't capture empty sections or next headings
        tldr_heading_match = re.search(r'^## TLDR\s*\n\s*\n([^\n#][^\n]*?)(?:\n\n|\n##|$)', content, re.MULTILINE)
        if tldr_heading_match:
            tldr_text = tldr_heading_match.group(1).strip()
            # Only use if not empty and doesn't start with ##
            if tldr_text and not tldr_text.startswith('##'):
                metadata["tldr"] = tldr_text

    # Get resolution status from backlog.json for investigations
    if metadata["type"].startswith("investigation"):
        metadata["status"] = _get_resolution_status_from_backlog(file_path)

    return metadata


def _get_resolution_status_from_backlog(file_path: str) -> str:
    """Get resolution status from backlog.json for an investigation.

    Args:
        file_path: Path to investigation file

    Returns:
        Resolution status string, or empty string if not found
    """
    path = Path(file_path)

    # Find project directory by walking up from file
    current = path.parent
    project_dir = None
    max_depth = 10

    for _ in range(max_depth):
        if (current / ".orch").exists():
            project_dir = current
            break
        if current == current.parent:
            break
        current = current.parent

    if not project_dir:
        return ""

    try:
        resolver = BacklogResolver(project_dir)
        status = resolver.get_resolution_for_investigation(file_path)

        # Map ResolutionStatus enum to display strings
        if status == ResolutionStatus.FIX:
            return "Resolved"
        elif status == ResolutionStatus.WORKAROUND:
            return "Mitigated"
        elif status == ResolutionStatus.UNRESOLVED:
            return "Unresolved"
        else:
            return ""  # Not tracked in backlog
    except Exception:
        return ""


def format_time_ago(timestamp: Optional[str]) -> str:
    """Format ISO timestamp as human-readable time ago."""
    if not timestamp:
        return "never"

    try:
        dt = datetime.fromisoformat(timestamp)
        delta = datetime.now() - dt

        if delta.days > 365:
            years = delta.days // 365
            return f"{years}y ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months}mo ago"
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
        else:
            return "just now"
    except (ValueError, AttributeError):
        return "unknown"
