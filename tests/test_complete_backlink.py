"""
Tests for investigation backlink automation in orch complete.

When completing a feature that has a context_ref pointing to an investigation,
we should check if all features from that investigation are complete and
prompt to mark the investigation as resolved.

Following TDD workflow:
- RED: Write failing test
- GREEN: Write minimal code to pass
- REFACTOR: Clean up
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from orch.features import Feature, load_features, save_features


class TestIsInvestigationRef:
    """Tests for detecting if context_ref points to an investigation."""

    def test_returns_true_for_investigation_path(self):
        """context_ref pointing to .orch/investigations/ should be detected."""
        from orch.complete import is_investigation_ref

        assert is_investigation_ref(".orch/investigations/simple/2025-11-28-test.md") is True
        assert is_investigation_ref(".orch/investigations/audits/2025-11-27-security.md") is True
        assert is_investigation_ref(".orch/investigations/design/2025-11-28-discovery.md") is True

    def test_returns_false_for_decision_path(self):
        """context_ref pointing to decisions should not be detected as investigation."""
        from orch.complete import is_investigation_ref

        assert is_investigation_ref(".orch/decisions/2025-11-27-feature-list.md") is False

    def test_returns_false_for_workspace_path(self):
        """context_ref pointing to workspace should not be detected."""
        from orch.complete import is_investigation_ref

        assert is_investigation_ref(".orch/workspace/test/WORKSPACE.md") is False

    def test_returns_false_for_none(self):
        """None context_ref should return False."""
        from orch.complete import is_investigation_ref

        assert is_investigation_ref(None) is False

    def test_returns_false_for_empty_string(self):
        """Empty string context_ref should return False."""
        from orch.complete import is_investigation_ref

        assert is_investigation_ref("") is False


class TestGetFeaturesByContextRef:
    """Tests for finding all features that reference a specific context_ref."""

    def test_finds_all_features_with_matching_context_ref(self, tmp_path):
        """Should find all features that have the same context_ref."""
        from orch.features import get_features_by_context_ref

        # Create backlog.json with multiple features referencing same investigation
        features = [
            Feature(
                id="feature-1",
                description="First feature",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/audits/2025-11-27-test.md",
            ),
            Feature(
                id="feature-2",
                description="Second feature",
                skill="feature-impl",
                status="in_progress",
                context_ref=".orch/investigations/audits/2025-11-27-test.md",
            ),
            Feature(
                id="feature-3",
                description="Third feature (different ref)",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/simple/other.md",
            ),
            Feature(
                id="feature-4",
                description="Fourth feature (no ref)",
                skill="feature-impl",
                status="pending",
                context_ref=None,
            ),
        ]
        save_features(features, tmp_path)

        # Find features by context_ref
        result = get_features_by_context_ref(
            ".orch/investigations/audits/2025-11-27-test.md",
            tmp_path
        )

        # Should find exactly 2 features
        assert len(result) == 2
        assert {f.id for f in result} == {"feature-1", "feature-2"}

    def test_returns_empty_list_when_no_matches(self, tmp_path):
        """Should return empty list when no features match."""
        from orch.features import get_features_by_context_ref

        features = [
            Feature(
                id="feature-1",
                description="Feature",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/decisions/some-decision.md",
            ),
        ]
        save_features(features, tmp_path)

        result = get_features_by_context_ref(
            ".orch/investigations/nonexistent.md",
            tmp_path
        )

        assert len(result) == 0


class TestAllFeaturesComplete:
    """Tests for checking if all features from an investigation are complete."""

    def test_returns_true_when_all_complete(self, tmp_path):
        """Should return True when all features with context_ref are complete."""
        from orch.features import all_features_complete_for_context_ref

        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/test.md",
            ),
            Feature(
                id="feature-2",
                description="Second",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/test.md",
            ),
        ]
        save_features(features, tmp_path)

        result = all_features_complete_for_context_ref(
            ".orch/investigations/test.md",
            tmp_path
        )

        assert result is True

    def test_returns_false_when_some_incomplete(self, tmp_path):
        """Should return False when some features are not complete."""
        from orch.features import all_features_complete_for_context_ref

        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/test.md",
            ),
            Feature(
                id="feature-2",
                description="Second",
                skill="feature-impl",
                status="in_progress",
                context_ref=".orch/investigations/test.md",
            ),
        ]
        save_features(features, tmp_path)

        result = all_features_complete_for_context_ref(
            ".orch/investigations/test.md",
            tmp_path
        )

        assert result is False

    def test_returns_false_when_pending(self, tmp_path):
        """Should return False when features are pending."""
        from orch.features import all_features_complete_for_context_ref

        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/test.md",
            ),
            Feature(
                id="feature-2",
                description="Second",
                skill="feature-impl",
                status="pending",
                context_ref=".orch/investigations/test.md",
            ),
        ]
        save_features(features, tmp_path)

        result = all_features_complete_for_context_ref(
            ".orch/investigations/test.md",
            tmp_path
        )

        assert result is False


class TestMarkInvestigationResolved:
    """Tests for mark_investigation_resolved deprecation.

    Note: Resolution status is now tracked in backlog.json, not in investigation files.
    See: .orch/decisions/2025-11-28-backlog-investigation-separation.md
    """

    def test_mark_investigation_resolved_is_deprecated(self, tmp_path):
        """mark_investigation_resolved() should raise deprecation error."""
        import warnings
        from orch.investigations import mark_investigation_resolved, InvestigationError

        inv_path = tmp_path / ".orch" / "investigations" / "simple"
        inv_path.mkdir(parents=True)
        inv_file = inv_path / "2025-11-28-test.md"
        inv_file.write_text("""# Investigation: Test
**Status:** Complete
""")

        # Should raise InvestigationError with deprecation message
        with pytest.raises(InvestigationError, match="deprecated"):
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                mark_investigation_resolved(inv_file)

    def test_mark_investigation_resolved_deprecation_warning(self, tmp_path):
        """mark_investigation_resolved() should emit DeprecationWarning."""
        import warnings
        from orch.investigations import mark_investigation_resolved, InvestigationError

        inv_path = tmp_path / ".orch" / "investigations" / "simple"
        inv_path.mkdir(parents=True)
        inv_file = inv_path / "2025-11-28-test.md"
        inv_file.write_text("""# Investigation: Test
**Status:** Complete
""")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                mark_investigation_resolved(inv_file)
            except InvestigationError:
                pass

            # Should have emitted a DeprecationWarning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()


class TestCheckInvestigationBacklink:
    """Tests for the main backlink check function."""

    def test_returns_investigation_info_when_all_complete(self, tmp_path):
        """When completing feature triggers all-complete, should return investigation info."""
        from orch.complete import check_investigation_backlink

        # Create investigation file
        inv_path = tmp_path / ".orch" / "investigations" / "simple"
        inv_path.mkdir(parents=True)
        inv_file = inv_path / "2025-11-28-test.md"
        inv_file.write_text("""# Investigation
**Resolution-Status:** Unresolved
""")

        # Create features - all complete
        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/simple/2025-11-28-test.md",
            ),
            Feature(
                id="feature-2",
                description="Second",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/simple/2025-11-28-test.md",
            ),
        ]
        save_features(features, tmp_path)

        # Check backlink for feature-1 (which just completed)
        result = check_investigation_backlink(
            context_ref=".orch/investigations/simple/2025-11-28-test.md",
            project_dir=tmp_path
        )

        assert result is not None
        assert result['all_complete'] is True
        assert result['investigation_path'] == ".orch/investigations/simple/2025-11-28-test.md"
        assert result['feature_count'] == 2

    def test_returns_none_when_not_all_complete(self, tmp_path):
        """Should return None when not all features are complete."""
        from orch.complete import check_investigation_backlink

        # Create investigation file
        inv_path = tmp_path / ".orch" / "investigations" / "simple"
        inv_path.mkdir(parents=True)
        inv_file = inv_path / "2025-11-28-test.md"
        inv_file.write_text("# Investigation\n**Resolution-Status:** Unresolved\n")

        # Create features - one still in progress
        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/simple/2025-11-28-test.md",
            ),
            Feature(
                id="feature-2",
                description="Second",
                skill="feature-impl",
                status="in_progress",
                context_ref=".orch/investigations/simple/2025-11-28-test.md",
            ),
        ]
        save_features(features, tmp_path)

        result = check_investigation_backlink(
            context_ref=".orch/investigations/simple/2025-11-28-test.md",
            project_dir=tmp_path
        )

        assert result is None

    def test_returns_none_for_non_investigation_ref(self, tmp_path):
        """Should return None when context_ref is not an investigation."""
        from orch.complete import check_investigation_backlink

        result = check_investigation_backlink(
            context_ref=".orch/decisions/some-decision.md",
            project_dir=tmp_path
        )

        assert result is None

    def test_returns_none_for_none_context_ref(self, tmp_path):
        """Should return None when context_ref is None."""
        from orch.complete import check_investigation_backlink

        result = check_investigation_backlink(
            context_ref=None,
            project_dir=tmp_path
        )

        assert result is None


class TestCompleteAgentWorkWithBacklink:
    """Integration tests for backlink in complete_agent_work flow."""

    def test_complete_includes_backlink_info_when_applicable(self, tmp_path):
        """complete_agent_work should include investigation backlink info in result."""
        from orch.complete import complete_agent_work

        # Setup workspace
        workspace_name = "test-agent"
        workspace_dir = tmp_path / ".orch" / "workspace" / workspace_name
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Complete\n")

        # Setup investigation
        inv_path = tmp_path / ".orch" / "investigations" / "simple"
        inv_path.mkdir(parents=True)
        inv_file = inv_path / "2025-11-28-test.md"
        inv_file.write_text("""# Investigation
**Resolution-Status:** Unresolved
""")

        # Setup features - this is the last one completing
        features = [
            Feature(
                id="feature-1",
                description="First",
                skill="feature-impl",
                status="complete",
                context_ref=".orch/investigations/simple/2025-11-28-test.md",
            ),
        ]
        save_features(features, tmp_path)

        # Setup git repo
        (tmp_path / ".git").mkdir()

        # Mock agent registry
        mock_agent = {
            'id': workspace_name,
            'workspace': f".orch/workspace/{workspace_name}",
            'status': 'active',
            'feature_id': 'feature-1'  # Agent has feature_id
        }

        # Complete the work
        with patch('orch.complete.get_agent_by_id', return_value=mock_agent):
            with patch('orch.complete.clean_up_agent'):
                with patch('orch.git_utils.validate_work_committed', return_value=(True, "")):
                    result = complete_agent_work(
                        agent_id=workspace_name,
                        project_dir=tmp_path,
                        roadmap_path=None,
                    )

        # Should include investigation backlink info
        assert result['success'] is True
        assert 'investigation_backlink' in result
        assert result['investigation_backlink'] is not None
        assert result['investigation_backlink']['all_complete'] is True
