"""Tests for pyproject.toml configuration.

Verifies that code quality tools (mypy, black, flake8) are properly configured.
"""

import tomllib
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def pyproject_path(project_root: Path) -> Path:
    """Return the path to pyproject.toml."""
    return project_root / "pyproject.toml"


class TestPyprojectExists:
    """Test that pyproject.toml exists and is valid TOML."""

    def test_pyproject_toml_exists(self, pyproject_path: Path) -> None:
        """pyproject.toml should exist at project root."""
        assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    def test_pyproject_toml_is_valid(self, pyproject_path: Path) -> None:
        """pyproject.toml should be valid TOML."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        assert isinstance(config, dict), "pyproject.toml should parse to a dict"


class TestMypyConfiguration:
    """Test mypy configuration in pyproject.toml."""

    def test_mypy_section_exists(self, pyproject_path: Path) -> None:
        """pyproject.toml should have a [tool.mypy] section."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        assert "tool" in config, "Missing [tool] section"
        assert "mypy" in config["tool"], "Missing [tool.mypy] section"

    def test_mypy_python_version(self, pyproject_path: Path) -> None:
        """mypy should target Python 3.10+."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        mypy_config = config["tool"]["mypy"]
        assert "python_version" in mypy_config, "Missing python_version in mypy config"
        assert mypy_config["python_version"] >= "3.10", "Should target Python 3.10+"

    def test_mypy_strict_settings(self, pyproject_path: Path) -> None:
        """mypy should have reasonable strictness settings."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        mypy_config = config["tool"]["mypy"]
        # At minimum, warn about missing imports
        assert mypy_config.get("warn_return_any") is True or mypy_config.get(
            "ignore_missing_imports"
        ), "mypy should have some strictness settings"


class TestBlackConfiguration:
    """Test black configuration in pyproject.toml."""

    def test_black_section_exists(self, pyproject_path: Path) -> None:
        """pyproject.toml should have a [tool.black] section."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        assert "tool" in config, "Missing [tool] section"
        assert "black" in config["tool"], "Missing [tool.black] section"

    def test_black_line_length(self, pyproject_path: Path) -> None:
        """black should have a line length configured."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        black_config = config["tool"]["black"]
        assert "line-length" in black_config, "Missing line-length in black config"
        assert 79 <= black_config["line-length"] <= 120, "Line length should be reasonable"

    def test_black_target_version(self, pyproject_path: Path) -> None:
        """black should target Python 3.10+."""
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        black_config = config["tool"]["black"]
        assert "target-version" in black_config, "Missing target-version in black config"
        assert "py310" in black_config["target-version"], "Should target Python 3.10"


class TestFlake8Configuration:
    """Test flake8 configuration.

    Note: flake8 doesn't natively support pyproject.toml, but we can use
    .flake8 or setup.cfg, OR the flake8-pyproject plugin.
    We'll test for the presence of configuration in an expected location.
    """

    def test_flake8_config_exists(self, project_root: Path) -> None:
        """flake8 configuration should exist (pyproject.toml with plugin, .flake8, or setup.cfg)."""
        pyproject_path = project_root / "pyproject.toml"
        flake8_path = project_root / ".flake8"
        setup_cfg_path = project_root / "setup.cfg"

        # Check for flake8 config in any of the expected locations
        has_flake8_in_pyproject = False
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                config = tomllib.load(f)
            has_flake8_in_pyproject = "flake8" in config.get("tool", {})

        assert (
            has_flake8_in_pyproject or flake8_path.exists() or setup_cfg_path.exists()
        ), "flake8 configuration should exist in pyproject.toml, .flake8, or setup.cfg"

    def test_flake8_max_line_length(self, project_root: Path) -> None:
        """flake8 should have max-line-length configured to match black."""
        pyproject_path = project_root / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        # If flake8 config is in pyproject.toml
        if "flake8" in config.get("tool", {}):
            flake8_config = config["tool"]["flake8"]
            assert "max-line-length" in flake8_config, "Missing max-line-length in flake8 config"
            # Should match or be compatible with black's line length
            black_line_length = config.get("tool", {}).get("black", {}).get("line-length", 88)
            assert (
                flake8_config["max-line-length"] == black_line_length
            ), "flake8 max-line-length should match black's line-length"
