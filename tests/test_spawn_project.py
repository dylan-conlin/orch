"""
Tests for project directory and detection functionality in orch spawn.

Tests project handling including:
- Getting project directories from active-projects.md
- Auto-detecting projects from current working directory
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    get_project_dir,
    detect_project_from_cwd,
)


class TestProjectDirectory:
    """Tests for project directory lookup."""

    def test_get_project_dir_found(self, tmp_path):
        """Test getting project directory from active-projects.md."""
        # Create directory structure
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)

        # Create test active-projects.md
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("""# Active Projects

## test-project

- **Path:** `/home/user/projects/test-project`

## another-project

- **Path:** `/home/user/projects/another`
""")

        # Mock Path.home() to return tmp_path
        with patch('orch.spawn.Path.home', return_value=tmp_path):
            # Mock Path.expanduser() for the path parsing
            with patch.object(Path, 'expanduser', return_value=Path("/home/user/projects/test-project")):
                project_dir = get_project_dir("test-project")

        # Should return the expanded path
        assert project_dir == Path("/home/user/projects/test-project")

    def test_get_project_dir_not_found(self, tmp_path):
        """Test getting project directory when project doesn't exist."""
        # Create directory structure
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)

        # Create test active-projects.md without target project
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("""# Active Projects

- **other-project**: /home/user/projects/other - Active
""")

        # Mock Path.home() to return tmp_path
        with patch('orch.spawn.Path.home', return_value=tmp_path):
            project_dir = get_project_dir("nonexistent-project")

        # Should return None
        assert project_dir is None


class TestProjectAutoDetection:
    """Tests for project auto-detection from current working directory."""

    def test_detect_project_from_cwd_in_project_root(self, tmp_path):
        """Test auto-detecting project when cwd is project root."""
        # Create project structure with .orch directory
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()

        # Create active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text(f"""## my-project
- **Path:** `{project_dir}`
""")

        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                result = detect_project_from_cwd()

            assert result is not None
            name, detected_dir = result
            assert name == "my-project"
            assert detected_dir.resolve() == project_dir.resolve()
        finally:
            os.chdir(original_cwd)

    def test_detect_project_from_cwd_in_subdirectory(self, tmp_path):
        """Test auto-detecting project when cwd is a subdirectory."""
        # Create project structure with .orch directory
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()
        subdir = project_dir / "src" / "components"
        subdir.mkdir(parents=True)

        # Create active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text(f"""## my-project
- **Path:** `{project_dir}`
""")

        # Change to subdirectory
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                result = detect_project_from_cwd()

            assert result is not None
            name, detected_dir = result
            assert name == "my-project"
            assert detected_dir.resolve() == project_dir.resolve()
        finally:
            os.chdir(original_cwd)

    def test_detect_project_from_cwd_not_in_project(self, tmp_path):
        """Test auto-detection returns None when not in a project."""
        # Create a directory without .orch
        random_dir = tmp_path / "not-a-project"
        random_dir.mkdir()

        # Change to non-project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(random_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                result = detect_project_from_cwd()

            assert result is None
        finally:
            os.chdir(original_cwd)

    def test_detect_project_from_cwd_unlisted_project(self, tmp_path):
        """Test auto-detection fallback for project not in active-projects.md."""
        # Create project structure with .orch directory but NOT in active-projects.md
        project_dir = tmp_path / "unlisted-project"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()

        # Create empty active-projects.md (project not listed)
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                result = detect_project_from_cwd()

            # Should return directory name as fallback
            assert result is not None
            name, detected_dir = result
            assert name == "unlisted-project"
            assert detected_dir.resolve() == project_dir.resolve()
        finally:
            os.chdir(original_cwd)


class TestGetProjectDirPathAcceptance:
    """Tests for get_project_dir() accepting filesystem paths directly.

    When --project is given a filesystem path (not just a name), it should:
    - Accept absolute paths to existing directories
    - Accept tilde-expanded paths (~/...)
    - Accept relative paths (./..., ../...)
    - NOT require the path to be registered in active-projects.md

    This enables cross-repo spawning to projects that aren't registered.
    See beads issue: orch-cli-ate
    """

    def test_get_project_dir_accepts_absolute_path(self, tmp_path):
        """Test get_project_dir() accepts absolute paths to existing directories."""
        # Create a directory that exists but is NOT in active-projects.md
        project_dir = tmp_path / "unregistered-project"
        project_dir.mkdir()

        # Create empty active-projects.md (project not registered)
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        with patch('orch.project_resolver.Path.home', return_value=tmp_path):
            # Should accept the absolute path directly
            result = get_project_dir(str(project_dir))

        assert result is not None
        assert result.resolve() == project_dir.resolve()

    def test_get_project_dir_accepts_tilde_path(self, tmp_path, monkeypatch):
        """Test get_project_dir() accepts ~/... paths."""
        # Create a directory under the mocked home
        project_dir = tmp_path / "Documents" / "projects" / "my-project"
        project_dir.mkdir(parents=True)

        # Create empty active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        # Mock HOME environment variable so expanduser() works correctly
        monkeypatch.setenv('HOME', str(tmp_path))

        with patch('orch.project_resolver.Path.home', return_value=tmp_path):
            # Use tilde path relative to mocked home
            result = get_project_dir("~/Documents/projects/my-project")

        assert result is not None
        assert result.resolve() == project_dir.resolve()

    def test_get_project_dir_rejects_nonexistent_path(self, tmp_path):
        """Test get_project_dir() rejects paths that don't exist."""
        # Create empty active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        with patch('orch.project_resolver.Path.home', return_value=tmp_path):
            # Path doesn't exist - should return None
            result = get_project_dir("/nonexistent/path/to/project")

        assert result is None

    def test_get_project_dir_registered_path_still_works(self, tmp_path):
        """Test that registered project paths still work."""
        # Create a directory that IS registered
        project_dir = tmp_path / "registered-project"
        project_dir.mkdir()

        # Create active-projects.md with this project registered
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text(f"""## registered-project
- **Path:** `{project_dir}`
""")

        with patch('orch.project_resolver.Path.home', return_value=tmp_path):
            # Should still work via path
            result = get_project_dir(str(project_dir))

        assert result is not None
        assert result.resolve() == project_dir.resolve()


class TestGetProjectDirCwdFallback:
    """Tests for get_project_dir() falling back to current working directory.

    When --project NAME is specified but NAME is not in active-projects.md,
    get_project_dir() should still work if:
    - Current directory has .orch/
    - Current directory name matches the project name

    This ensures consistency with detect_project_from_cwd() which has this fallback.
    """

    def test_get_project_dir_cwd_fallback_for_unlisted_project(self, tmp_path):
        """Test get_project_dir() falls back to cwd when project name matches directory name."""
        # Create project structure with .orch directory but NOT in active-projects.md
        project_dir = tmp_path / "my-unlisted-project"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()

        # Create empty active-projects.md (project not listed)
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                # This should work because we're IN a directory with .orch/ that matches the name
                result = get_project_dir("my-unlisted-project")

            # Should return the project directory (cwd fallback)
            assert result is not None
            assert result.resolve() == project_dir.resolve()
        finally:
            os.chdir(original_cwd)

    def test_get_project_dir_cwd_fallback_case_insensitive(self, tmp_path):
        """Test cwd fallback works with case-insensitive matching."""
        # Create project structure
        project_dir = tmp_path / "MyProject"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()

        # Create empty active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                # Should work with different case
                result = get_project_dir("myproject")

            assert result is not None
            assert result.resolve() == project_dir.resolve()
        finally:
            os.chdir(original_cwd)

    def test_get_project_dir_cwd_fallback_no_orch_dir_fails(self, tmp_path):
        """Test cwd fallback doesn't work if directory doesn't have .orch/."""
        # Create directory WITHOUT .orch
        project_dir = tmp_path / "no-orch-project"
        project_dir.mkdir()

        # Create empty active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                # Should return None - no .orch/ directory
                result = get_project_dir("no-orch-project")

            assert result is None
        finally:
            os.chdir(original_cwd)

    def test_get_project_dir_cwd_fallback_name_mismatch_fails(self, tmp_path):
        """Test cwd fallback doesn't work if project name doesn't match directory name."""
        # Create project structure with .orch
        project_dir = tmp_path / "actual-name"
        project_dir.mkdir()
        orch_dir = project_dir / ".orch"
        orch_dir.mkdir()

        # Create empty active-projects.md
        meta_orch = tmp_path / "orch-knowledge" / ".orch"
        meta_orch.mkdir(parents=True)
        active_projects = meta_orch / "active-projects.md"
        active_projects.write_text("# Active Projects\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            with patch('orch.spawn.Path.home', return_value=tmp_path):
                # Should return None - name doesn't match
                result = get_project_dir("different-name")

            assert result is None
        finally:
            os.chdir(original_cwd)
