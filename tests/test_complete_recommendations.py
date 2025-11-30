"""
Tests for investigation recommendation surfacing in orch complete.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up

Feature: When completing investigation/codebase-audit/architect agents,
extract and display recommendations section from investigation file.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from orch.complete import (
    extract_recommendations_section,
    find_investigation_file,
    complete_agent_work,
)


class TestExtractRecommendationsSection:
    """Tests for extracting Recommendations section from investigation files."""

    def test_extract_recommendations_with_recommendations_header(self, tmp_path):
        """Test extracting content from ## Recommendations header."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings here.

## Recommendations

⭐ **RECOMMENDED:** Implement feature X
- **Why:** Addresses the gap identified
- **Trade-off:** Minor complexity increase

**Alternative: Feature Y**
- **Pros:** Simpler
- **Cons:** Less complete

## Self-Review

- [x] Complete
""")

        result = extract_recommendations_section(investigation_file)

        assert result is not None
        assert "RECOMMENDED" in result
        assert "Implement feature X" in result
        assert "Alternative: Feature Y" in result
        # Should not include next section
        assert "Self-Review" not in result

    def test_extract_recommendations_with_next_steps_header(self, tmp_path):
        """Test extracting content from ## Next Steps header."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

## Next Steps

1. Add feature X
2. Fix bug Y
3. Update documentation

## References

- Link 1
""")

        result = extract_recommendations_section(investigation_file)

        assert result is not None
        assert "Add feature X" in result
        assert "Fix bug Y" in result
        # Should not include next section
        assert "References" not in result

    def test_extract_recommendations_with_implementation_recommendations_header(self, tmp_path):
        """Test extracting content from ## Implementation Recommendations header."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Analysis

Analysis content.

## Implementation Recommendations

### Change 1: Add extract function
- Path: `tools/orch/complete.py`
- Purpose: Extract recommendations

### Change 2: Integration
- Integrate into complete flow

## Notes

Extra notes.
""")

        result = extract_recommendations_section(investigation_file)

        assert result is not None
        assert "Change 1: Add extract function" in result
        assert "Change 2: Integration" in result
        # Should not include next section
        assert "Extra notes" not in result

    def test_extract_recommendations_returns_none_when_no_section(self, tmp_path):
        """Test returns None when no recommendations section exists."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

## Conclusion

Done.
""")

        result = extract_recommendations_section(investigation_file)

        assert result is None

    def test_extract_recommendations_handles_section_at_end_of_file(self, tmp_path):
        """Test extracting recommendations at end of file (no following section)."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""# Investigation: Test

## Findings

Some findings.

## Recommendations

Do X and Y.
This is at the end of the file.
""")

        result = extract_recommendations_section(investigation_file)

        assert result is not None
        assert "Do X and Y" in result
        assert "end of the file" in result

    def test_extract_recommendations_returns_none_for_missing_file(self, tmp_path):
        """Test returns None when file doesn't exist."""
        investigation_file = tmp_path / "nonexistent.md"

        result = extract_recommendations_section(investigation_file)

        assert result is None

    def test_extract_recommendations_strips_whitespace(self, tmp_path):
        """Test that extracted content is stripped of leading/trailing whitespace."""
        investigation_file = tmp_path / "investigation.md"
        investigation_file.write_text("""## Recommendations


Content with spacing.


## Next Section
""")

        result = extract_recommendations_section(investigation_file)

        assert result is not None
        # Should be stripped
        assert result == "Content with spacing."


class TestFindInvestigationFile:
    """Tests for finding investigation file for an agent."""

    def test_find_investigation_file_by_workspace_name_match(self, tmp_path):
        """Test finding investigation file that matches workspace name."""
        # Create investigation directory structure
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        # Create investigation file with matching date and topic
        inv_file = inv_dir / "2025-11-29-test-feature-analysis.md"
        inv_file.write_text("# Investigation: Test Feature Analysis\n")

        result = find_investigation_file(
            workspace_name="2025-11-29-test-feature-analysis",
            project_dir=tmp_path
        )

        assert result is not None
        assert result.name == "2025-11-29-test-feature-analysis.md"

    def test_find_investigation_file_in_design_subdir(self, tmp_path):
        """Test finding investigation file in design subdirectory."""
        inv_dir = tmp_path / ".orch" / "investigations" / "design"
        inv_dir.mkdir(parents=True)

        inv_file = inv_dir / "2025-11-29-design-proposal.md"
        inv_file.write_text("# Investigation: Design Proposal\n")

        result = find_investigation_file(
            workspace_name="2025-11-29-design-proposal",
            project_dir=tmp_path
        )

        assert result is not None
        assert result.name == "2025-11-29-design-proposal.md"

    def test_find_investigation_file_returns_none_when_not_found(self, tmp_path):
        """Test returns None when no matching investigation file exists."""
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        result = find_investigation_file(
            workspace_name="nonexistent-workspace",
            project_dir=tmp_path
        )

        assert result is None

    def test_find_investigation_file_handles_missing_directory(self, tmp_path):
        """Test handles case where investigations directory doesn't exist."""
        result = find_investigation_file(
            workspace_name="any-workspace",
            project_dir=tmp_path
        )

        assert result is None

    def test_find_investigation_file_prefers_exact_match(self, tmp_path):
        """Test that exact name match is preferred over partial match."""
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)

        # Create two files with similar names
        inv_file1 = inv_dir / "2025-11-29-test.md"
        inv_file1.write_text("# Investigation 1\n")

        inv_file2 = inv_dir / "2025-11-29-test-extended.md"
        inv_file2.write_text("# Investigation 2\n")

        result = find_investigation_file(
            workspace_name="2025-11-29-test",
            project_dir=tmp_path
        )

        assert result is not None
        assert result.name == "2025-11-29-test.md"


class TestRecommendationSurfacingInComplete:
    """Tests for recommendation surfacing during agent completion."""

    def test_complete_agent_surfaces_recommendations_via_primary_artifact(self, tmp_path, capsys):
        """Test that primary_artifact field is used when workspace name doesn't match file."""
        # This tests the fix for workspace name mismatch bug
        workspace_name = "2025-11-29-inv-quick-test-how-many-decisions-created-last-days-scope"
        actual_inv_file = "2025-11-29-quick-test-how-many-decisions.md"

        # Setup workspace (with long name)
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-investigation
**Phase:** Complete
**Type:** Investigation
""")

        # Setup investigation file (with short name that doesn't match workspace)
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / actual_inv_file
        inv_path_abs = str(inv_file.resolve())
        inv_file.write_text("""# Investigation: Test

## Findings
Found something.

## Recommendations

⭐ **RECOMMENDED:** Add feature X
- **Why:** Solves the problem
""")

        # Setup git repo
        (tmp_path / ".git").mkdir()

        # Mock agent with investigation skill AND primary_artifact field
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active',
            'primary_artifact': inv_path_abs  # Key: exact path to investigation
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        # Verify success
        assert result['success'] is True

        # Check that recommendations were found via primary_artifact (not name matching)
        captured = capsys.readouterr()
        assert "Recommendations from investigation" in captured.out
        assert "Add feature X" in captured.out
        assert "orch backlog add" in captured.out

    def test_complete_agent_surfaces_recommendations_for_investigation_skill(self, tmp_path, capsys):
        """Test that completing investigation agent surfaces recommendations."""
        # Setup workspace
        workspace_name = "2025-11-29-test-investigation"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-investigation
**Phase:** Complete
**Type:** Investigation
""")

        # Setup investigation file with recommendations
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_file.write_text("""# Investigation: Test

## Findings
Found something.

## Recommendations

⭐ **RECOMMENDED:** Add feature X
- **Why:** Solves the problem
""")

        # Setup git repo
        (tmp_path / ".git").mkdir()

        # Mock agent with investigation skill
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        # Verify success
        assert result['success'] is True

        # Check that recommendations were output
        captured = capsys.readouterr()
        assert "Recommendations from investigation" in captured.out
        assert "Add feature X" in captured.out
        assert "orch backlog add" in captured.out

    def test_complete_agent_surfaces_recommendations_for_codebase_audit_skill(self, tmp_path, capsys):
        """Test that completing codebase-audit agent surfaces recommendations."""
        workspace_name = "2025-11-29-security-audit"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: security-audit
**Phase:** Complete
**Type:** Investigation
""")

        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_file.write_text("""# Security Audit

## Findings
Found security issues.

## Recommendations

1. Fix SQL injection in auth module
2. Add rate limiting to API
""")

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'codebase-audit',
            'status': 'active'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        assert result['success'] is True
        captured = capsys.readouterr()
        assert "Recommendations from investigation" in captured.out
        assert "SQL injection" in captured.out

    def test_complete_agent_surfaces_recommendations_for_architect_skill(self, tmp_path, capsys):
        """Test that completing architect agent surfaces recommendations."""
        workspace_name = "2025-11-29-auth-design"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: auth-design
**Phase:** Complete
**Type:** Investigation
""")

        inv_dir = tmp_path / ".orch" / "investigations" / "design"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_file.write_text("""# Design: Auth System

## Analysis
JWT vs sessions.

## Implementation Recommendations

Use JWT with refresh tokens.
""")

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'architect',
            'status': 'active'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        assert result['success'] is True
        captured = capsys.readouterr()
        assert "Recommendations from investigation" in captured.out
        assert "JWT" in captured.out

    def test_complete_agent_no_output_for_feature_impl_skill(self, tmp_path, capsys):
        """Test that feature-impl skill does not trigger recommendation surfacing."""
        workspace_name = "test-feature"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-feature
**Phase:** Complete
**Type:** Implementation
""")

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'feature-impl',
            'status': 'active'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        assert result['success'] is True
        captured = capsys.readouterr()
        # Should NOT mention recommendations
        assert "Recommendations from investigation" not in captured.out

    def test_complete_agent_no_error_when_no_recommendations(self, tmp_path, capsys):
        """Test completes normally when investigation has no recommendations section."""
        workspace_name = "2025-11-29-no-recs"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: no-recs
**Phase:** Complete
**Type:** Investigation
""")

        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_file.write_text("""# Investigation: Test

## Findings
Found something.

## Conclusion
Done - no recommendations needed.
""")

        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active'
        }

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                                            )

        # Should succeed without error
        assert result['success'] is True
        captured = capsys.readouterr()
        # Should NOT show recommendations section (no section exists)
        assert "Recommendations from investigation" not in captured.out

    def test_complete_agent_no_error_when_investigation_file_missing(self, tmp_path, capsys):
        """Test that recommendation surfacing handles missing investigation file gracefully.

        Note: This test mocks verification to pass, allowing us to test that
        recommendation surfacing code doesn't crash when investigation file
        is missing. In practice, verification would fail first for investigation
        skill when no investigation file exists.
        """
        workspace_name = "2025-11-29-missing-file"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: missing-file
**Phase:** Complete
**Type:** Investigation
""")

        # Don't create investigation file
        (tmp_path / ".git").mkdir()

        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'skill': 'investigation',
            'status': 'active'
        }

        # Mock verification to pass (to test recommendation surfacing code path)
        from orch.complete import VerificationResult
        mock_verification = VerificationResult(passed=True, errors=[])

        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.complete.validate_work_committed', return_value=(True, "")):
                    with patch('orch.complete.verify_agent_work', return_value=mock_verification):
                        result = complete_agent_work(
                            agent_id=workspace_name,
                            project_dir=tmp_path,
                                                    )

        # Should succeed without error (recommendation surfacing handles missing file)
        assert result['success'] is True
        # Should NOT have recommendations in result (file missing)
        assert 'recommendations' not in result or result.get('recommendations') is None
        captured = capsys.readouterr()
        # Should NOT show recommendations section
        assert "Recommendations from investigation" not in captured.out


class TestRecommendationSurfacingInAsyncComplete:
    """Tests for recommendation surfacing in async completion path.

    The async path (complete_agent_async) spawns a background daemon.
    Recommendations must be surfaced BEFORE the daemon spawn, since
    click.echo() in the daemon goes nowhere (stdout is devnull'd).
    """

    def test_async_complete_surfaces_recommendations_before_daemon(self, tmp_path, capsys):
        """Test that async completion surfaces recommendations in foreground."""
        from orch.complete import complete_agent_async
        from orch.registry import AgentRegistry

        workspace_name = "2025-11-29-async-test-investigation"

        # Setup workspace
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: async-test
**Phase:** Complete
**Type:** Investigation
""")

        # Setup investigation file with recommendations
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / f"{workspace_name}.md"
        inv_file.write_text("""# Investigation: Async Test

## Findings
Found something important.

## Recommendations

⭐ **RECOMMENDED:** Implement async feature
- **Why:** Improves user experience
""")

        # Setup registry with mock agent
        registry_path = tmp_path / "test-registry.json"
        registry = AgentRegistry(registry_path)
        registry.register(
            agent_id=workspace_name,
            task="Test investigation",
            window="test:0",
            project_dir=str(tmp_path),
            workspace=f".orch/workspace/{workspace_name}",
            skill='investigation'
        )

        # Mock the daemon subprocess spawn to avoid actual daemon
        with patch('subprocess.Popen') as mock_popen:
            mock_popen.return_value.pid = 12345

            result = complete_agent_async(
                agent_id=workspace_name,
                project_dir=tmp_path,
                registry_path=registry_path
            )

        # Verify recommendations were surfaced (in result dict)
        assert 'recommendations' in result
        assert result['recommendations'] is not None
        assert 'Implement async feature' in result['recommendations']['recommendations']

        # Verify recommendations were output to terminal
        captured = capsys.readouterr()
        assert "Recommendations from investigation" in captured.out
        assert "Implement async feature" in captured.out
        assert "orch backlog add" in captured.out

    def test_async_complete_no_recommendations_for_non_investigation_skill(self, tmp_path, capsys):
        """Test that async completion doesn't surface recommendations for feature-impl."""
        from orch.complete import complete_agent_async
        from orch.registry import AgentRegistry

        workspace_name = "test-feature-impl"

        # Setup workspace
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("""# Workspace: test-feature
**Phase:** Complete
**Type:** Implementation
""")

        # Setup registry with mock agent
        registry_path = tmp_path / "test-registry.json"
        registry = AgentRegistry(registry_path)
        registry.register(
            agent_id=workspace_name,
            task="Test feature",
            window="test:0",
            project_dir=str(tmp_path),
            workspace=f".orch/workspace/{workspace_name}",
            skill='feature-impl'
        )

        # Mock the daemon subprocess spawn
        with patch('subprocess.Popen') as mock_popen:
            mock_popen.return_value.pid = 12345

            result = complete_agent_async(
                agent_id=workspace_name,
                project_dir=tmp_path,
                registry_path=registry_path
            )

        # Should NOT have recommendations (not investigation skill)
        assert result.get('recommendations') is None

        # Should NOT show recommendations in output
        captured = capsys.readouterr()
        assert "Recommendations from investigation" not in captured.out
