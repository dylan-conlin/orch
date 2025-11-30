"""Tests for build-readme command."""

import pytest
from pathlib import Path


# cli_runner fixture provided by conftest.py


def test_extract_investigation_category_from_path():
    """
    Test that we can extract the category (subdirectory) from an investigation file path.

    Given an investigation path like 'investigations/systems/2025-11-20-topic.md',
    we should extract 'systems' as the category.
    """
    # Import the function we're about to implement
    from orch.cli import extract_investigation_category

    # Test various investigation paths
    test_cases = [
        ('investigations/systems/2025-11-20-topic.md', 'systems'),
        ('investigations/feasibility/2025-11-19-research.md', 'feasibility'),
        ('investigations/audits/2025-11-18-audit.md', 'audits'),
        ('investigations/INDEX.md', None),  # No category for root files
    ]

    for path_str, expected_category in test_cases:
        path = Path(path_str)
        result = extract_investigation_category(path)
        assert result == expected_category, \
            f"Expected category '{expected_category}' for path '{path_str}', got '{result}'"


def test_build_readme_shows_investigation_categories(tmp_path, cli_runner):
    """
    Test that build-readme output includes category tags for investigations.

    Given investigations in subdirectories (systems/, feasibility/, audits/),
    the README should show category tags like [systems], [feasibility], [audits].
    """
    from orch.cli import cli

    # Create .orch directory structure
    orch_dir = tmp_path / '.orch'
    orch_dir.mkdir()

    # Create investigation subdirectories
    systems_dir = orch_dir / 'investigations' / 'systems'
    systems_dir.mkdir(parents=True)

    feasibility_dir = orch_dir / 'investigations' / 'feasibility'
    feasibility_dir.mkdir(parents=True)

    # Create sample investigation files with metadata
    systems_inv = systems_dir / '2025-11-20-test-system.md'
    systems_inv.write_text('''# Investigation: Test System

**Status:** Complete
**Confidence:** High
**Date:** 2025-11-20

Test content
''')

    feasibility_inv = feasibility_dir / '2025-11-19-test-feasibility.md'
    feasibility_inv.write_text('''# Investigation: Test Feasibility

**Status:** Active
**Confidence:** Medium
**Date:** 2025-11-19

Test content
''')

    # Run build-readme command
    result = cli_runner.invoke(cli, ['build-readme', '--project', str(tmp_path)])

    # Check command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Read generated README
    readme_path = orch_dir / 'README.md'
    assert readme_path.exists(), "README.md was not created"

    readme_content = readme_path.read_text()

    # Verify category tags appear in output
    assert '[systems]' in readme_content, \
        "Expected [systems] category tag in README output"
    assert '[feasibility]' in readme_content, \
        "Expected [feasibility] category tag in README output"

    # Verify the full format: path - [category] [status, confidence]
    assert 'investigations/systems/2025-11-20-test-system.md' in readme_content
    assert 'investigations/feasibility/2025-11-19-test-feasibility.md' in readme_content


def test_build_readme_full_list_hint_searches_recursively(tmp_path, cli_runner):
    """
    Test that the 'Full list' hint for investigations uses a recursive search command.

    The hint should NOT use 'ls -lt investigations/' which only shows subdirectories.
    It should use a command that finds .md files in subdirectories.
    """
    from orch.cli import cli

    # Create minimal .orch directory structure
    orch_dir = tmp_path / '.orch'
    orch_dir.mkdir()

    # Create investigations subdirectory with a file
    systems_dir = orch_dir / 'investigations' / 'systems'
    systems_dir.mkdir(parents=True)

    systems_inv = systems_dir / '2025-11-20-test.md'
    systems_inv.write_text('**Status:** Complete\n**Date:** 2025-11-20\n')

    # Run build-readme command
    result = cli_runner.invoke(cli, ['build-readme', '--project', str(tmp_path)])

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Read generated README
    readme_path = orch_dir / 'README.md'
    readme_content = readme_path.read_text()

    # The old hint (should NOT be present)
    assert '`ls -lt investigations/ | head' not in readme_content, \
        "README still uses old non-recursive 'ls -lt investigations/' hint"

    # The new hint should use find or similar recursive search
    # Accept either 'find' or 'fd' commands as both work recursively
    has_recursive_command = (
        'find investigations/' in readme_content or
        'fd' in readme_content and 'investigations/' in readme_content
    )

    assert has_recursive_command, \
        "README should use 'find' or 'fd' command for recursive investigation search"
