"""Investigation validation module for orch validate command.

Provides two-layer validation:
1. Programmatic validation (fast, cheap) - structural and reference checks
2. Agent-driven validation (thorough, expensive) - claim verification via spawned agent
"""

from __future__ import annotations

import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.error import URLError


@dataclass
class ValidationIssue:
    """A single validation issue found during validation."""
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'structure', 'references', 'confidence', 'resolution'
    message: str
    line_number: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of investigation validation."""
    file_path: Path
    passed: bool
    critical_issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Return exit code based on validation results.

        Returns:
            0: All clear (passed all checks)
            1: Critical failures (must fix)
            2: Warnings (suggest agent validation)
        """
        if self.critical_issues:
            return 1
        elif self.warnings:
            return 2
        return 0

    @property
    def has_quality_warnings(self) -> bool:
        """Check if there are quality warnings that suggest agent validation."""
        return len(self.warnings) > 0


class InvestigationValidator:
    """Validator for investigation markdown files."""

    # Required sections for different investigation types
    REQUIRED_SECTIONS = {
        'default': ['Findings', 'Synthesis', 'Recommendations'],
        'agent-failure': ['Summary', 'Evidence', 'Root Cause', 'Resolution Plan'],
        'system': ['Findings', 'Synthesis'],
        'feasibility': ['Analysis', 'Recommendation'],
        'audit': ['Findings', 'Recommendations'],
        'performance': ['Findings', 'Analysis', 'Recommendations']
    }

    # Required metadata fields
    REQUIRED_METADATA = ['Question', 'Started', 'Status', 'Confidence']

    # Confidence levels
    CONFIDENCE_LEVELS = {
        'Very Low': (0, 39),
        'Low': (40, 59),
        'Medium': (60, 79),
        'High': (80, 94),
        'Very High': (95, 100)
    }

    # Valid Resolution-Status values (from investigation templates)
    VALID_RESOLUTION_STATUSES = [
        'unresolved',
        'resolved',
        'recurring',
        'synthesized',
        'mitigated'
    ]

    def __init__(self, investigation_path: Path):
        """Initialize validator with investigation file path.

        Args:
            investigation_path: Path to investigation markdown file
        """
        self.investigation_path = investigation_path
        self.content = ""
        self.lines = []
        self.metadata = {}
        self.sections = {}

    def validate(self, check_urls: bool = True, check_git: bool = True) -> ValidationResult:
        """Run full validation on investigation file.

        Args:
            check_urls: Whether to validate URLs (requires network)
            check_git: Whether to validate git commits (requires git repo)

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(
            file_path=self.investigation_path,
            passed=True
        )

        # Read file
        try:
            self.content = self.investigation_path.read_text()
            self.lines = self.content.split('\n')
        except Exception as e:
            result.critical_issues.append(ValidationIssue(
                severity='critical',
                category='structure',
                message=f"Failed to read file: {e}"
            ))
            result.passed = False
            return result

        # Parse metadata and sections
        self._parse_metadata()
        self._parse_sections()

        # Run validation checks
        self._check_required_metadata(result)
        self._check_required_sections(result)

        if check_urls:
            self._check_url_references(result)

        if check_git:
            self._check_git_references(result)

        self._check_file_references(result)
        self._check_confidence_calibration(result)
        self._check_resolution_evidence(result)

        # Update passed status
        result.passed = len(result.critical_issues) == 0

        return result

    def _parse_metadata(self):
        """Parse metadata fields from investigation file."""
        metadata_pattern = r'^\*\*([^:]+):\*\*\s*(.+)$'

        for line in self.lines[:50]:  # Metadata typically in first 50 lines
            match = re.match(metadata_pattern, line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                self.metadata[key] = value

    def _parse_sections(self):
        """Parse section headers from investigation file."""
        section_pattern = r'^#+\s+(.+)$'

        for i, line in enumerate(self.lines):
            match = re.match(section_pattern, line)
            if match:
                section_name = match.group(1).strip()
                self.sections[section_name] = i + 1  # 1-indexed line numbers

    def _get_investigation_type(self) -> str:
        """Determine investigation type from file path."""
        path_str = str(self.investigation_path).lower()

        if 'agent-failure' in path_str:
            return 'agent-failure'
        elif 'system' in path_str:
            return 'system'
        elif 'feasibility' in path_str:
            return 'feasibility'
        elif 'audit' in path_str:
            return 'audit'
        elif 'performance' in path_str:
            return 'performance'

        return 'default'

    def _check_required_metadata(self, result: ValidationResult):
        """Check for required metadata fields."""
        missing_fields = []

        for field in self.REQUIRED_METADATA:
            if field not in self.metadata:
                missing_fields.append(field)

        if missing_fields:
            result.critical_issues.append(ValidationIssue(
                severity='critical',
                category='structure',
                message=f"Missing required metadata fields: {', '.join(missing_fields)}"
            ))

    def _check_required_sections(self, result: ValidationResult):
        """Check for required sections based on investigation type."""
        inv_type = self._get_investigation_type()
        required_sections = self.REQUIRED_SECTIONS.get(inv_type, self.REQUIRED_SECTIONS['default'])

        # Section name aliases - be flexible with semantic variations
        section_aliases = {
            # Agent failure sections
            'Summary': ['Summary', 'Quick Summary', 'What Went Wrong'],
            'Evidence': ['Evidence'],
            'Root Cause': ['Root Cause', 'Analysis', 'Root cause'],
            'Resolution Plan': ['Resolution Plan', 'Recommendations', 'Resolution'],
            # Feasibility sections
            'Analysis': ['Analysis', 'Evidence Gathered', 'Options Considered', 'Context'],
            'Recommendation': ['Recommendation', 'Recommendations'],
            # Performance sections
            'Bottleneck Analysis': ['Bottleneck Analysis', 'Analysis', 'Profiling Results'],
            # Audit/general sections
            'Recommendations': ['Recommendations', 'Prioritized Recommendations', 'Optimization Recommendations'],
            'Findings': ['Findings']
        }

        missing_sections = []
        for section in required_sections:
            # Get aliases for this section (or just use the section name)
            aliases = section_aliases.get(section, [section])

            # Check if any alias matches any section in the document
            found = False
            for alias in aliases:
                if any(alias.lower() in s.lower() for s in self.sections.keys()):
                    found = True
                    break

            if not found:
                missing_sections.append(section)

        if missing_sections:
            # Only report as warning for agent-failure (structure may vary)
            severity = 'warning' if inv_type == 'agent-failure' else 'critical'
            issue_list = result.warnings if severity == 'warning' else result.critical_issues

            issue_list.append(ValidationIssue(
                severity=severity,
                category='structure',
                message=f"Missing or non-standard sections: {', '.join(missing_sections)}"
            ))

    def _check_url_references(self, result: ValidationResult):
        """Check that URL references are valid (return 200)."""
        url_pattern = r'https?://[^\s\)]+'
        urls_found = []

        for i, line in enumerate(self.lines, 1):
            urls = re.findall(url_pattern, line)
            for url in urls:
                # Clean up common markdown artifacts
                url = url.rstrip('.,;:')
                urls_found.append((url, i))

        broken_urls = []
        for url, line_num in urls_found:
            try:
                req = urllib.request.Request(url, method='HEAD')
                req.add_header('User-Agent', 'orch-validate/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status >= 400:
                        broken_urls.append((url, line_num, response.status))
            except (URLError, TimeoutError, Exception) as e:
                broken_urls.append((url, line_num, str(e)))

        for url, line_num, error in broken_urls:
            result.critical_issues.append(ValidationIssue(
                severity='critical',
                category='references',
                message=f"Broken URL: {url} (error: {error})",
                line_number=line_num
            ))

    def _check_git_references(self, result: ValidationResult):
        """Check that git commit references exist."""
        # Match git commit hashes (7-40 hex chars, typically preceded by context)
        commit_pattern = r'\b([0-9a-f]{7,40})\b'
        commits_found = []

        for i, line in enumerate(self.lines, 1):
            # Look for likely commit references (with context like "commit", "hash", etc.)
            if any(keyword in line.lower() for keyword in ['commit', 'hash', 'sha', 'fixed in']):
                matches = re.findall(commit_pattern, line)
                for commit_hash in matches:
                    if len(commit_hash) >= 7:  # Valid git short hash
                        commits_found.append((commit_hash, i))

        # Try to validate commits using git
        try:
            git_root = self._find_git_root()
            if git_root:
                for commit_hash, line_num in commits_found:
                    result_code = subprocess.run(
                        ['git', 'cat-file', '-t', commit_hash],
                        cwd=git_root,
                        capture_output=True,
                        timeout=5
                    )
                    if result_code.returncode != 0:
                        result.critical_issues.append(ValidationIssue(
                            severity='critical',
                            category='references',
                            message=f"Git commit not found: {commit_hash}",
                            line_number=line_num
                        ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Git not available or timeout - skip git validation
            pass

    def _check_file_references(self, result: ValidationResult):
        """Check that file path references exist."""
        # Match file paths (with common extensions or path patterns)
        file_pattern = r'(?:^|\s)([./~]?[\w\-./]+\.(?:py|md|js|ts|json|yaml|yml|txt|sh|go|rs|c|cpp|h|java))'
        files_found = []

        for i, line in enumerate(self.lines, 1):
            matches = re.findall(file_pattern, line)
            for file_path in matches:
                files_found.append((file_path, i))

        git_root = self._find_git_root()
        base_path = git_root if git_root else self.investigation_path.parent

        for file_path, line_num in files_found:
            # Resolve relative to git root or investigation directory
            resolved_path = Path(base_path) / file_path.lstrip('./')

            if not resolved_path.exists():
                result.warnings.append(ValidationIssue(
                    severity='warning',
                    category='references',
                    message=f"File not found: {file_path}",
                    line_number=line_num
                ))

    def _check_confidence_calibration(self, result: ValidationResult):
        """Check for confidence/evidence mismatches."""
        confidence = self.metadata.get('Confidence', '')

        # Extract confidence level and percentage
        confidence_level = None
        for level in self.CONFIDENCE_LEVELS:
            if level.lower() in confidence.lower():
                confidence_level = level
                break

        if not confidence_level:
            result.warnings.append(ValidationIssue(
                severity='warning',
                category='confidence',
                message="Confidence level not in standard format (Very Low/Low/Medium/High/Very High)"
            ))
            return

        # High or Very High confidence requires evidence
        if confidence_level in ['High', 'Very High']:
            has_evidence = any('evidence' in s.lower() for s in self.sections.keys())

            if not has_evidence:
                result.warnings.append(ValidationIssue(
                    severity='warning',
                    category='confidence',
                    message=f"{confidence_level} confidence ({confidence}) without Evidence section"
                ))

            # Check for reproduction steps if claiming root cause
            if any('root cause' in line.lower() for line in self.lines):
                has_reproduction = any(
                    keyword in self.content.lower()
                    for keyword in ['reproduce', 'reproduction', 'repro', 'steps to reproduce']
                )

                if not has_reproduction:
                    result.warnings.append(ValidationIssue(
                        severity='warning',
                        category='confidence',
                        message="Claims 'root cause' without reproduction steps"
                    ))

    def _check_resolution_evidence(self, result: ValidationResult):
        """Check for resolution status evidence."""
        resolution_status = self.metadata.get('Resolution-Status', '')

        # Skip if no Resolution-Status field
        if not resolution_status:
            return

        # Check if the status value is valid (one of the 5 standard values)
        status_value = resolution_status.lower().split()[0] if resolution_status else ''
        # Also check without splitting for cases like "Unresolved" vs "Unresolved - some note"
        status_is_valid = any(
            valid_status in resolution_status.lower()
            for valid_status in self.VALID_RESOLUTION_STATUSES
        )

        if not status_is_valid:
            result.warnings.append(ValidationIssue(
                severity='warning',
                category='resolution',
                message=f"Non-standard Resolution-Status value: '{resolution_status}'. Valid values: Unresolved, Resolved, Recurring, Synthesized, Mitigated"
            ))

        if 'resolved' in resolution_status.lower():
            # Check for validation evidence (commit hash, test results, validation date)
            has_commit = any(
                keyword in self.content.lower()
                for keyword in ['commit', 'fixed in', 'merged', 'pull request', 'pr #']
            )

            has_validation = any(
                keyword in self.content.lower()
                for keyword in ['validated', 'tested', 'verified', 'confirmed fixed']
            )

            if not (has_commit or has_validation):
                result.warnings.append(ValidationIssue(
                    severity='warning',
                    category='resolution',
                    message="Resolution-Status: Resolved without commit hash or validation evidence"
                ))

        elif 'recurring' in resolution_status.lower():
            # Check for link to original investigation
            has_reference = any(
                keyword in self.content.lower()
                for keyword in ['original investigation', 'previous', 'first occurrence', 'related to']
            )

            if not has_reference:
                result.warnings.append(ValidationIssue(
                    severity='warning',
                    category='resolution',
                    message="Resolution-Status: Recurring without link to original investigation"
                ))

    def _find_git_root(self) -> Optional[Path]:
        """Find git repository root."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                cwd=self.investigation_path.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None


def format_validation_output(result: ValidationResult, quiet: bool = False) -> str:
    """Format validation result for display.

    Args:
        result: ValidationResult to format
        quiet: If True, suppress tips and only show issues

    Returns:
        Formatted output string
    """
    lines = []

    lines.append(f"Validating: {result.file_path}")
    lines.append("")

    # Show critical issues
    if result.critical_issues:
        for issue in result.critical_issues:
            location = f" (line {issue.line_number})" if issue.line_number else ""
            lines.append(f"❌ {issue.category.title()}: {issue.message}{location}")
        lines.append("")
    else:
        lines.append("✅ Structure: All required sections present")
        lines.append("✅ References: All valid")

    # Show warnings
    if result.warnings:
        warning_by_category = {}
        for warning in result.warnings:
            if warning.category not in warning_by_category:
                warning_by_category[warning.category] = []
            warning_by_category[warning.category].append(warning)

        for category, warnings in warning_by_category.items():
            lines.append(f"⚠️  {category.title()} ({len(warnings)} issues):")
            for warning in warnings:
                location = f" (line {warning.line_number})" if warning.line_number else ""
                lines.append(f"  • {warning.message}{location}")
        lines.append("")
    else:
        if not result.critical_issues:
            lines.append("✅ Confidence: Appropriate for evidence provided")
            lines.append("")

    # Show info items
    if result.info:
        for info in result.info:
            lines.append(f"ℹ️  {info.message}")
        lines.append("")

    # Add tip for agent validation
    if result.has_quality_warnings and not quiet:
        lines.append("💡 Tip: Run 'orch validate --spawn' to verify claims")
        lines.append("")

    # Exit code
    exit_code_text = {
        0: "passed",
        1: "critical",
        2: "warnings"
    }.get(result.exit_code, "unknown")

    lines.append(f"Exit code: {result.exit_code} ({exit_code_text})")

    return "\n".join(lines)
