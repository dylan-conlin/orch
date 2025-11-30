"""
Tests for git_utils functionality.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up
"""

import pytest
import subprocess
from pathlib import Path
from orch.git_utils import validate_work_committed


class TestValidateWorkCommittedWithExclusions:
    """Tests for validate_work_committed with exclude_files parameter."""

    def test_validates_successfully_when_only_excluded_files_modified(self, tmp_path):
        """
        Test that validation passes when only excluded files are uncommitted.

        This is the core requirement: orchestrator working files (ROADMAP.org,
        coordination workspace) should not block agent completion.
        """
        # Setup: Create a git repo with uncommitted changes to excluded files
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True, capture_output=True)

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', 'README.md'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)

        # Create .orch directory structure
        orch_dir = repo_dir / ".orch"
        orch_dir.mkdir()

        # Modify excluded files (orchestrator working files)
        roadmap_file = orch_dir / "ROADMAP.org"
        roadmap_file.write_text("#+TITLE: Test Roadmap\n\n* TODO New task")

        coordination_dir = orch_dir / "workspace" / "coordination"
        coordination_dir.mkdir(parents=True)
        coordination_ws = coordination_dir / "WORKSPACE.md"
        coordination_ws.write_text("# Coordination Workspace\n\nUpdated notes")

        # Define excluded files (orchestrator working files)
        excluded_files = [
            '.orch/ROADMAP.org',
            '.orch/workspace/coordination/WORKSPACE.md'
        ]

        # Validate: Should pass because only excluded files are modified
        is_valid, message = validate_work_committed(repo_dir, exclude_files=excluded_files)

        assert is_valid, f"Validation should pass when only excluded files modified. Message: {message}"
        assert message == "", f"Should have no warning message. Got: {message}"

    def test_fails_when_non_excluded_files_modified(self, tmp_path):
        """
        Test that validation fails when non-excluded files are uncommitted.

        This ensures we're still catching uncommitted work that should be committed.
        """
        # Setup: Create a git repo with uncommitted changes to non-excluded files
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True, capture_output=True)

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', 'README.md'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)

        # Modify a non-excluded file (agent work that should be committed)
        (repo_dir / "new-feature.py").write_text("def new_feature():\n    pass")

        # Define excluded files
        excluded_files = ['.orch/ROADMAP.org']

        # Validate: Should fail because non-excluded file is modified
        is_valid, message = validate_work_committed(repo_dir, exclude_files=excluded_files)

        assert not is_valid, "Validation should fail when non-excluded files modified"
        assert "new-feature.py" in message, f"Error message should mention modified file. Got: {message}"

    def test_handles_mixed_excluded_and_non_excluded_files(self, tmp_path):
        """
        Test validation with both excluded and non-excluded files modified.

        Should fail and only report the non-excluded files.
        """
        # Setup: Create a git repo
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True, capture_output=True)

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', 'README.md'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)

        # Create .orch directory
        orch_dir = repo_dir / ".orch"
        orch_dir.mkdir()

        # Modify excluded file (orchestrator working file)
        roadmap_file = orch_dir / "ROADMAP.org"
        roadmap_file.write_text("#+TITLE: Test Roadmap")

        # Modify non-excluded file (agent work)
        (repo_dir / "agent-work.py").write_text("def agent_work():\n    pass")

        # Define excluded files
        excluded_files = ['.orch/ROADMAP.org']

        # Validate: Should fail because of non-excluded file
        is_valid, message = validate_work_committed(repo_dir, exclude_files=excluded_files)

        assert not is_valid, "Validation should fail when non-excluded files present"
        assert "agent-work.py" in message, "Should report non-excluded file"
        assert "ROADMAP.org" not in message, "Should NOT report excluded file"

    def test_validates_successfully_with_no_uncommitted_changes(self, tmp_path):
        """
        Test that validation passes when working tree is clean.

        Baseline case: no uncommitted changes at all.
        """
        # Setup: Create a git repo with clean working tree
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True, capture_output=True)

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', 'README.md'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)

        # Validate: Should pass (clean working tree)
        is_valid, message = validate_work_committed(repo_dir, exclude_files=[])

        assert is_valid, f"Validation should pass with clean working tree. Message: {message}"
        assert message == "", f"Should have no warning message. Got: {message}"

    def test_handles_different_git_status_formats(self, tmp_path):
        """
        Test that exclusion works for different git status format lines.

        Git status --porcelain can show files as:
        - " M file" (modified)
        - "?? file" (untracked)
        - "MM file" (modified in index and working tree)
        - " D file" (deleted)
        - "A  file" (added to index)
        """
        # Setup: Create a git repo
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True, capture_output=True)

        # Create initial commit
        (repo_dir / "README.md").write_text("# Test Project")
        subprocess.run(['git', 'add', 'README.md'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)

        # Create .orch directory
        orch_dir = repo_dir / ".orch"
        orch_dir.mkdir()

        # Test untracked file (?? status)
        roadmap_untracked = orch_dir / "ROADMAP.org"
        roadmap_untracked.write_text("#+TITLE: Test")

        # Test modified file ( M status)
        claude_md = orch_dir / "CLAUDE.md"
        claude_md.write_text("# Initial")
        subprocess.run(['git', 'add', str(claude_md.relative_to(repo_dir))], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add CLAUDE.md'], cwd=repo_dir, check=True, capture_output=True)
        claude_md.write_text("# Modified")

        # Define excluded files
        excluded_files = [
            '.orch/ROADMAP.org',
            '.orch/CLAUDE.md'
        ]

        # Validate: Should pass (both untracked and modified excluded files)
        is_valid, message = validate_work_committed(repo_dir, exclude_files=excluded_files)

        assert is_valid, f"Validation should pass for different status formats. Message: {message}"
