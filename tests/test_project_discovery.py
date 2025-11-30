"""Tests for project discovery functionality."""

import pytest
import json
from pathlib import Path
from datetime import datetime


# cli_runner fixture provided by conftest.py


def test_scan_projects_finds_initialized_projects(tmp_path):
    """Test that scan_projects finds directories with .orch/CLAUDE.md files."""
    from orch.project_discovery import scan_projects

    # Create test project structure
    project1 = tmp_path / "project1"
    project1.mkdir()
    (project1 / ".orch").mkdir()
    (project1 / ".orch" / "CLAUDE.md").write_text("# Project 1")

    project2 = tmp_path / "project2"
    project2.mkdir()
    (project2 / ".orch").mkdir()
    (project2 / ".orch" / "CLAUDE.md").write_text("# Project 2")

    # Project without .orch/CLAUDE.md should be ignored
    project3 = tmp_path / "project3"
    project3.mkdir()

    # Scan the tmp_path directory
    search_dirs = [str(tmp_path)]
    result = scan_projects(search_dirs)

    # Verify we found exactly 2 projects
    assert len(result) == 2

    # Verify both project paths are in the result
    project_paths = [str(p) for p in result]
    assert str(project1) in project_paths
    assert str(project2) in project_paths
    assert str(project3) not in project_paths


def test_write_cache_creates_valid_json(tmp_path):
    """Test that write_cache creates a valid JSON cache file."""
    from orch.project_discovery import write_cache

    cache_file = tmp_path / "initialized-projects.json"
    projects = [
        Path("/home/testuser/project-one"),
        Path("/home/testuser/projects/project-two")
    ]

    # Write cache
    write_cache(cache_file, projects)

    # Verify file exists
    assert cache_file.exists()

    # Read and verify JSON structure
    with open(cache_file) as f:
        data = json.load(f)

    assert data["version"] == "1.0"
    assert len(data["projects"]) == 2
    assert "/home/testuser/project-one" in data["projects"]
    assert "/home/testuser/projects/project-two" in data["projects"]
    assert "last_scan" in data
    # Verify last_scan is a valid ISO format timestamp
    datetime.fromisoformat(data["last_scan"].replace("Z", "+00:00"))


def test_read_cache_returns_projects(tmp_path):
    """Test that read_cache reads projects from cache file."""
    from orch.project_discovery import read_cache

    cache_file = tmp_path / "initialized-projects.json"

    # Create cache file manually
    cache_data = {
        "version": "1.0",
        "projects": [
            "/home/testuser/project-one",
            "/home/testuser/projects/project-two"
        ],
        "last_scan": "2025-11-15T17:30:00Z"
    }
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)

    # Read cache
    projects = read_cache(cache_file)

    # Verify we got back the correct projects
    assert len(projects) == 2
    assert Path("/home/testuser/project-one") in projects
    assert Path("/home/testuser/projects/project-two") in projects


def test_read_cache_returns_empty_list_if_file_missing(tmp_path):
    """Test that read_cache returns empty list if cache file doesn't exist."""
    from orch.project_discovery import read_cache

    cache_file = tmp_path / "nonexistent.json"

    # Read non-existent cache
    projects = read_cache(cache_file)

    # Should return empty list
    assert projects == []


def test_scan_projects_cli_command(tmp_path, mocker, cli_runner):
    """Test the orch scan-projects CLI command."""
    from orch.cli import cli

    # Create test project structure
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    project1 = projects_dir / "project1"
    project1.mkdir()
    (project1 / ".orch").mkdir()
    (project1 / ".orch" / "CLAUDE.md").write_text("# Project 1")

    project2 = projects_dir / "project2"
    project2.mkdir()
    (project2 / ".orch").mkdir()
    (project2 / ".orch" / "CLAUDE.md").write_text("# Project 2")

    # Mock the cache file location
    cache_file = tmp_path / "cache" / "initialized-projects.json"
    mocker.patch('orch.config.get_initialized_projects_cache', return_value=cache_file)

    # Mock the search directories
    mocker.patch('orch.project_discovery.get_default_search_dirs', return_value=[str(projects_dir)])

    # Run CLI command
    result = cli_runner.invoke(cli, ['scan-projects'])

    # Verify command succeeded
    assert result.exit_code == 0

    # Verify output mentions found projects
    assert "Found 2 initialized projects" in result.output or "2 projects" in result.output

    # Verify cache file was created
    assert cache_file.exists()

    # Verify cache contents
    with open(cache_file) as f:
        data = json.load(f)
    assert len(data["projects"]) == 2
    assert str(project1) in data["projects"]
    assert str(project2) in data["projects"]


def test_build_orchestrator_context_with_rescan(tmp_path, mocker, cli_runner):
    """Test that build-orchestrator-context --rescan rescans before building."""
    from orch.cli import cli

    # Create test project structure
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    project1 = projects_dir / "project1"
    project1.mkdir()
    (project1 / ".orch").mkdir()
    (project1 / ".orch" / "CLAUDE.md").write_text("# Project 1\n")

    # Mock the cache file location
    cache_file = tmp_path / "cache" / "initialized-projects.json"
    mocker.patch('orch.config.get_initialized_projects_cache', return_value=cache_file)

    # Mock the search directories
    mocker.patch('orch.project_discovery.get_default_search_dirs', return_value=[str(projects_dir)])

    # Mock template directory with correct structure
    template_dir = tmp_path / ".orch" / "templates" / "orchestrator"
    template_dir.mkdir(parents=True)
    (template_dir / "test.md").write_text("Test template content")
    mocker.patch('pathlib.Path.home', return_value=tmp_path)

    # Ensure cache doesn't exist initially
    assert not cache_file.exists()

    # Run CLI command with --rescan flag
    result = cli_runner.invoke(cli, ['build-orchestrator-context', '--rescan', '--dry-run'])

    # Command might fail (no templates), but rescan should still happen
    # Verify cache file was created by the rescan
    assert cache_file.exists()

    # Verify cache contains the discovered project
    with open(cache_file) as f:
        data = json.load(f)
    assert len(data["projects"]) == 1
    assert str(project1) in data["projects"]
