"""
Tests for project directory and detection functionality in orch spawn.

Tests project handling including:
- Getting project directories from active-projects.md
- Auto-detecting projects from current working directory
- Finding project ROADMAP files
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from orch.spawn import (
    get_project_dir,
    detect_project_from_cwd,
    detect_project_roadmap,
)


class TestProjectDirectory:
    """Tests for project directory lookup."""

    def test_get_project_dir_found(self, tmp_path):
        """Test getting project directory from active-projects.md."""
        # Create directory structure
        meta_orch = tmp_path / "meta-orchestration" / ".orch"
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
        meta_orch = tmp_path / "meta-orchestration" / ".orch"
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
        meta_orch = tmp_path / "meta-orchestration" / ".orch"
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
        meta_orch = tmp_path / "meta-orchestration" / ".orch"
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
        meta_orch = tmp_path / "meta-orchestration" / ".orch"
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


class TestProjectRoadmapDetection:
    """Tests for project-scoped ROADMAP detection."""

    def test_detect_project_roadmap_in_current_dir(self, tmp_path):
        """Test detecting project ROADMAP in current directory."""
        # Create .orch/ROADMAP.org in test directory
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()
        roadmap_file = orch_dir / "ROADMAP.org"
        roadmap_file.write_text("* TODO Test Task")

        # Change to test directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = detect_project_roadmap()
            assert result == roadmap_file
        finally:
            os.chdir(original_cwd)

    def test_detect_project_roadmap_in_parent_dir(self, tmp_path):
        """Test detecting project ROADMAP in parent directory."""
        # Create .orch/ROADMAP.org in parent
        orch_dir = tmp_path / ".orch"
        orch_dir.mkdir()
        roadmap_file = orch_dir / "ROADMAP.org"
        roadmap_file.write_text("* TODO Test Task")

        # Create subdirectory and change to it
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = detect_project_roadmap()
            assert result == roadmap_file
        finally:
            os.chdir(original_cwd)

    def test_detect_project_roadmap_not_found(self, tmp_path):
        """Test detecting project ROADMAP when none exists."""
        # Change to test directory (no .orch/ROADMAP.org)
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = detect_project_roadmap()
            assert result is None
        finally:
            os.chdir(original_cwd)
