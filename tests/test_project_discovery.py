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


def test_scan_projects_cli_command(tmp_path, monkeypatch, cli_runner):
    """Test the orch scan-projects CLI command."""
    from orch.cli import cli
    import orch.config
    import orch.project_discovery

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
    monkeypatch.setattr(orch.config, 'get_initialized_projects_cache', lambda: cache_file)

    # Mock the search directories
    monkeypatch.setattr(orch.project_discovery, 'get_default_search_dirs', lambda: [str(projects_dir)])

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


@pytest.mark.skip(reason="build-orchestrator-context command was removed; test was never working (required mocker fixture)")
def test_build_orchestrator_context_with_rescan(tmp_path, monkeypatch, cli_runner):
    """Test that build-orchestrator-context --rescan rescans before building.
    
    NOTE: This test was never working - it used 'mocker' fixture which isn't installed.
    The build-orchestrator-context command has been removed from the CLI.
    """
    from orch.cli import cli
    import orch.config
    import orch.project_discovery
    import pathlib

    # Create test project structure
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    project1 = projects_dir / "project1"
    project1.mkdir()
    (project1 / ".orch").mkdir()
    (project1 / ".orch" / "CLAUDE.md").write_text("# Project 1\n")

    # Mock the cache file location
    cache_file = tmp_path / "cache" / "initialized-projects.json"
    monkeypatch.setattr(orch.config, 'get_initialized_projects_cache', lambda: cache_file)

    # Mock the search directories
    monkeypatch.setattr(orch.project_discovery, 'get_default_search_dirs', lambda: [str(projects_dir)])

    # Mock template directory with correct structure
    template_dir = tmp_path / ".orch" / "templates" / "orchestrator"
    template_dir.mkdir(parents=True)
    (template_dir / "test.md").write_text("Test template content")
    
    # Mock Path.home() properly by patching it in pathlib module
    monkeypatch.setattr(pathlib.Path, 'home', staticmethod(lambda: tmp_path))

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


# ============================================================================
# Tests for get_kb_projects() - reading from kb's project registry
# ============================================================================


def test_get_kb_projects_reads_from_kb_registry(tmp_path, monkeypatch):
    """Test that get_kb_projects reads projects from ~/.kb/projects.json."""
    import orch.project_discovery as pd

    # Create mock kb projects.json
    kb_dir = tmp_path / ".kb"
    kb_dir.mkdir()
    projects_file = kb_dir / "projects.json"
    
    kb_data = {
        "projects": [
            {"name": "orch-cli", "path": "/Users/test/projects/orch-cli"},
            {"name": "beads", "path": "/Users/test/projects/beads"},
            {"name": "kb-cli", "path": "/Users/test/projects/kb-cli"}
        ]
    }
    projects_file.write_text(json.dumps(kb_data))

    # Mock the kb projects path
    monkeypatch.setattr(pd, 'get_kb_projects_path', lambda: projects_file)

    # Get projects
    projects = pd.get_kb_projects()

    # Verify we got all projects
    assert len(projects) == 3
    assert Path("/Users/test/projects/orch-cli") in projects
    assert Path("/Users/test/projects/beads") in projects
    assert Path("/Users/test/projects/kb-cli") in projects


def test_get_kb_projects_returns_empty_list_if_file_missing(tmp_path, monkeypatch):
    """Test that get_kb_projects returns empty list if kb projects.json doesn't exist."""
    import orch.project_discovery as pd

    # Point to non-existent file
    monkeypatch.setattr(pd, 'get_kb_projects_path', 
                        lambda: tmp_path / ".kb" / "projects.json")

    # Get projects
    projects = pd.get_kb_projects()

    # Should return empty list
    assert projects == []


def test_get_kb_projects_handles_empty_projects_array(tmp_path, monkeypatch):
    """Test that get_kb_projects handles empty projects array gracefully."""
    import orch.project_discovery as pd

    # Create mock kb projects.json with empty projects
    kb_dir = tmp_path / ".kb"
    kb_dir.mkdir()
    projects_file = kb_dir / "projects.json"
    projects_file.write_text(json.dumps({"projects": []}))

    monkeypatch.setattr(pd, 'get_kb_projects_path', lambda: projects_file)

    # Get projects
    projects = pd.get_kb_projects()

    # Should return empty list
    assert projects == []


def test_get_kb_projects_handles_malformed_json(tmp_path, monkeypatch):
    """Test that get_kb_projects handles malformed JSON gracefully."""
    import orch.project_discovery as pd

    # Create malformed JSON file
    kb_dir = tmp_path / ".kb"
    kb_dir.mkdir()
    projects_file = kb_dir / "projects.json"
    projects_file.write_text("{ not valid json")

    monkeypatch.setattr(pd, 'get_kb_projects_path', lambda: projects_file)

    # Get projects - should not raise, return empty list
    projects = pd.get_kb_projects()
    assert projects == []


def test_get_kb_projects_handles_missing_projects_key(tmp_path, monkeypatch):
    """Test that get_kb_projects handles JSON without 'projects' key."""
    import orch.project_discovery as pd

    # Create JSON without projects key
    kb_dir = tmp_path / ".kb"
    kb_dir.mkdir()
    projects_file = kb_dir / "projects.json"
    projects_file.write_text(json.dumps({"version": "1.0"}))

    monkeypatch.setattr(pd, 'get_kb_projects_path', lambda: projects_file)

    # Get projects - should return empty list
    projects = pd.get_kb_projects()
    assert projects == []


def test_get_kb_projects_filters_nonexistent_paths(tmp_path, monkeypatch):
    """Test that get_kb_projects optionally filters out paths that don't exist."""
    import orch.project_discovery as pd

    # Create one real project path and one that doesn't exist
    real_project = tmp_path / "real-project"
    real_project.mkdir()

    kb_dir = tmp_path / ".kb"
    kb_dir.mkdir()
    projects_file = kb_dir / "projects.json"
    
    kb_data = {
        "projects": [
            {"name": "real-project", "path": str(real_project)},
            {"name": "missing-project", "path": "/nonexistent/path/to/project"}
        ]
    }
    projects_file.write_text(json.dumps(kb_data))

    monkeypatch.setattr(pd, 'get_kb_projects_path', lambda: projects_file)

    # Get all projects (no filter)
    all_projects = pd.get_kb_projects(filter_existing=False)
    assert len(all_projects) == 2

    # Get only existing projects
    existing_projects = pd.get_kb_projects(filter_existing=True)
    assert len(existing_projects) == 1
    assert real_project in existing_projects
