"""Tests for type hint coverage in CLI layer.

Verifies that mypy passes on the tools/orch directory.
This test suite enforces type safety for the orch CLI.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


class TestMypyTypeHints:
    """Test that mypy passes on the CLI layer."""

    def test_mypy_cli_layer_passes(self, project_root: Path) -> None:
        """mypy should pass on tools/orch with no errors.

        This is the primary test for type hint coverage.
        If this fails, there are type errors in the CLI layer.
        """
        cli_path = project_root / "tools" / "orch"
        assert cli_path.exists(), f"CLI path not found: {cli_path}"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                str(cli_path),
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Collect error lines (exclude notes, only from tools/orch)
        error_lines = [
            line
            for line in result.stdout.splitlines()
            if ": error:" in line and "tools/orch" in line
        ]

        # Provide helpful error message
        if error_lines:
            error_count = len(error_lines)
            sample_errors = error_lines[:10]
            error_sample = "\n".join(sample_errors)
            if error_count > 10:
                error_sample += f"\n... and {error_count - 10} more errors"

            pytest.fail(
                f"mypy found {error_count} type errors in tools/orch:\n\n{error_sample}"
            )

    def test_mypy_no_implicit_optional(self, project_root: Path) -> None:
        """mypy should not find implicit Optional issues.

        Python 3.10+ style: use X | None instead of Optional[X].
        """
        cli_path = project_root / "tools" / "orch"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                str(cli_path),
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Count implicit optional errors specifically (only from tools/orch)
        implicit_optional_errors = [
            line
            for line in result.stdout.splitlines()
            if ("PEP 484 prohibits implicit Optional" in line
                or "no_implicit_optional" in line)
            and "tools/orch" in line
        ]

        if implicit_optional_errors:
            sample = "\n".join(implicit_optional_errors[:5])
            pytest.fail(
                f"Found {len(implicit_optional_errors)} implicit Optional issues. "
                f"Use 'X | None' instead of 'Optional[X]':\n\n{sample}"
            )
