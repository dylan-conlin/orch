"""Tests for investigation validation functionality."""

import pytest
from pathlib import Path
from orch.validate import (
    InvestigationValidator,
    ValidationResult,
    ValidationIssue,
    format_validation_output
)


@pytest.fixture
def tmp_investigation(tmp_path):
    """Create a temporary investigation file for testing."""
    def _create_investigation(content: str) -> Path:
        inv_path = tmp_path / "test-investigation.md"
        inv_path.write_text(content)
        return inv_path
    return _create_investigation


def test_valid_investigation_structure(tmp_investigation):
    """Test validation passes for well-formed investigation."""
    content = """# Investigation: Test Investigation

**Question:** How does feature X work?
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** Medium (60%)

## Findings

Finding 1

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    assert result.passed
    assert len(result.critical_issues) == 0
    assert result.exit_code == 0


def test_missing_required_metadata(tmp_investigation):
    """Test validation fails when required metadata is missing."""
    content = """# Investigation: Test Investigation

**Question:** How does feature X work?
**Started:** 2025-11-23
# Missing Status and Confidence fields

## Findings

Finding 1

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    assert not result.passed
    assert len(result.critical_issues) > 0
    assert any('metadata' in issue.message.lower() for issue in result.critical_issues)
    assert result.exit_code == 1


def test_missing_required_sections(tmp_investigation):
    """Test validation detects when required sections are missing."""
    content = """# Investigation: Test Investigation

**Question:** How does feature X work?
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** Medium (60%)

## Findings

Finding 1

Note: This investigation is incomplete.
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should detect missing Synthesis and Recommendations sections
    # With flexible section checking, this should produce warnings or critical issues
    has_structure_issues = any(
        'structure' in issue.category.lower() or 'section' in issue.message.lower()
        for issue in (result.critical_issues + result.warnings)
    )
    assert has_structure_issues, "Should detect missing sections"
    # Exit code should be 1 (critical) or 2 (warnings) due to missing sections
    assert result.exit_code in [1, 2]


def test_high_confidence_without_evidence_warning(tmp_investigation):
    """Test warning for high confidence without evidence section."""
    content = """# Investigation: Test Investigation

**Question:** How does feature X work?
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** High (85%)

## Findings

Finding 1

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should have warning about high confidence without evidence
    warnings = [w for w in result.warnings if 'confidence' in w.category.lower()]
    assert len(warnings) > 0
    assert any('evidence' in w.message.lower() for w in warnings)
    assert result.exit_code == 2


def test_root_cause_claim_without_reproduction(tmp_investigation):
    """Test warning for root cause claims without reproduction steps."""
    content = """# Investigation: Test Investigation

**Question:** Why does X fail?
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** High (85%)

## Findings

The root cause is a missing configuration.

## Evidence

Evidence section present

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should have warning about root cause without reproduction
    warnings = [w for w in result.warnings if 'confidence' in w.category.lower()]
    assert any('reproduction' in w.message.lower() for w in warnings)


def test_resolved_status_without_evidence(tmp_investigation):
    """Test warning for resolved status without validation evidence."""
    content = """# Investigation: Test Investigation

**Question:** Why does X fail?
**Started:** 2025-11-23
**Status:** Complete
**Resolution-Status:** Resolved
**Confidence:** Medium (60%)

## Findings

Finding 1

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should have warning about resolved without evidence
    warnings = [w for w in result.warnings if 'resolution' in w.category.lower()]
    assert len(warnings) > 0
    assert 'resolved' in warnings[0].message.lower()


def test_validation_result_exit_codes():
    """Test exit code calculation for ValidationResult."""
    # No issues = exit 0
    result = ValidationResult(file_path=Path("test.md"), passed=True)
    assert result.exit_code == 0

    # Critical issues = exit 1
    result.critical_issues.append(ValidationIssue(
        severity='critical',
        category='structure',
        message='Missing section'
    ))
    result.passed = False
    assert result.exit_code == 1

    # Only warnings = exit 2
    result2 = ValidationResult(file_path=Path("test.md"), passed=True)
    result2.warnings.append(ValidationIssue(
        severity='warning',
        category='confidence',
        message='High confidence without evidence'
    ))
    assert result2.exit_code == 2


def test_format_validation_output():
    """Test formatting of validation results."""
    result = ValidationResult(file_path=Path("test.md"), passed=True)
    output = format_validation_output(result, quiet=False)

    assert "test.md" in output
    assert "✅" in output
    assert "Exit code: 0" in output

    # Test with warnings
    result.warnings.append(ValidationIssue(
        severity='warning',
        category='confidence',
        message='High confidence without evidence'
    ))
    output = format_validation_output(result, quiet=False)

    assert "⚠️" in output
    assert "confidence" in output.lower()
    assert "💡 Tip" in output

    # Test quiet mode (suppresses tips)
    output_quiet = format_validation_output(result, quiet=True)
    assert "💡 Tip" not in output_quiet


def test_investigation_type_detection(tmp_investigation):
    """Test detection of investigation type from file path."""
    # Create investigation in agent-failures subdirectory
    content = """# Investigation

**Question:** Test
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** Medium (60%)

## Summary
Summary
"""
    # Create temporary directory structure
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        agent_failures_dir = Path(tmpdir) / "investigations" / "agent-failures"
        agent_failures_dir.mkdir(parents=True)

        inv_path = agent_failures_dir / "test.md"
        inv_path.write_text(content)

        validator = InvestigationValidator(inv_path)
        inv_type = validator._get_investigation_type()

        assert inv_type == 'agent-failure'


def test_file_reference_validation(tmp_investigation):
    """Test validation of file references."""
    content = """# Investigation

**Question:** Test
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** Medium (60%)

## Findings

See tools/orch/nonexistent.py for details.

## Synthesis
Synthesis

## Recommendations
Recommendations
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should have warning about missing file
    warnings = [w for w in result.warnings if 'references' in w.category.lower()]
    assert len(warnings) > 0
    assert 'nonexistent.py' in warnings[0].message


def test_confidence_level_parsing(tmp_investigation):
    """Test parsing of confidence levels."""
    levels = [
        ("Very Low (30%)", "Very Low"),
        ("Low (50%)", "Low"),
        ("Medium (70%)", "Medium"),
        ("High (85%)", "High"),
        ("Very High (95%)", "Very High")
    ]

    for confidence_str, expected_level in levels:
        content = f"""# Investigation

**Question:** Test
**Started:** 2025-11-23
**Status:** Complete
**Confidence:** {confidence_str}

## Findings
Findings

## Synthesis
Synthesis

## Recommendations
Recommendations
"""
        inv_path = tmp_investigation(content)
        validator = InvestigationValidator(inv_path)

        # Need to read the content first
        validator.content = inv_path.read_text()
        validator.lines = validator.content.split('\n')

        # Verify metadata parsing
        validator._parse_metadata()
        assert 'Confidence' in validator.metadata, f"Metadata: {validator.metadata}"
        assert expected_level.lower() in validator.metadata['Confidence'].lower()


def test_invalid_resolution_status_value(tmp_investigation):
    """Test warning for non-standard Resolution-Status values.

    Valid values are: Unresolved, Resolved, Recurring, Synthesized, Mitigated
    Invalid values like 'Actionable' should produce a warning.
    """
    content = """# Investigation: Test Investigation

**Question:** Why does X fail?
**Started:** 2025-11-23
**Status:** Complete
**Resolution-Status:** Actionable - Clear fix identified
**Confidence:** Medium (60%)

## Findings

Finding 1

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
    inv_path = tmp_investigation(content)
    validator = InvestigationValidator(inv_path)
    result = validator.validate(check_urls=False, check_git=False)

    # Should have warning about invalid Resolution-Status value
    warnings = [w for w in result.warnings if 'resolution' in w.category.lower()]
    assert len(warnings) > 0, "Should produce warning for invalid Resolution-Status"
    assert any('actionable' in w.message.lower() or 'non-standard' in w.message.lower() or 'valid' in w.message.lower()
               for w in warnings), f"Warning should mention the invalid status value. Warnings: {[w.message for w in warnings]}"


def test_valid_resolution_status_values(tmp_investigation):
    """Test that valid Resolution-Status values don't produce warnings."""
    valid_statuses = [
        "Unresolved",
        "Resolved",
        "Recurring",
        "Synthesized",
        "Mitigated"
    ]

    for status in valid_statuses:
        content = f"""# Investigation: Test Investigation

**Question:** Why does X fail?
**Started:** 2025-11-23
**Status:** Complete
**Resolution-Status:** {status}
**Confidence:** Medium (60%)

## Findings

Finding 1. This issue was fixed in commit abc123.

## Synthesis

Key insights

## Recommendations

Recommendation 1
"""
        inv_path = tmp_investigation(content)
        validator = InvestigationValidator(inv_path)
        result = validator.validate(check_urls=False, check_git=False)

        # Filter warnings to only resolution category that mention invalid status
        invalid_status_warnings = [
            w for w in result.warnings
            if 'resolution' in w.category.lower()
            and ('non-standard' in w.message.lower() or 'valid' in w.message.lower())
        ]
        assert len(invalid_status_warnings) == 0, f"Valid status '{status}' should not produce invalid status warning"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
