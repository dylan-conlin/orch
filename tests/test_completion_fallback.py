"""
Tests for fallback completion detection when workspace phase is unknown.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime


class TestDetectCompletionFallback:
    """Tests for _detect_completion_fallback function."""

    def test_returns_none_when_no_signals(self, tmp_path):
        """When no completion signals exist, return None."""
        from orch.monitor import _detect_completion_fallback

        agent_info = {
            'id': 'test-agent',
            'status': 'active',
            'skill': 'feature-impl',
            'workspace': '.orch/workspace/test-workspace',
            'spawned_at': datetime.now().isoformat()
        }

        result = _detect_completion_fallback(agent_info, tmp_path)
        assert result is None

    def test_returns_inferred_when_registry_status_completed(self, tmp_path):
        """When registry status is 'completed', return inferred completion."""
        from orch.monitor import _detect_completion_fallback

        agent_info = {
            'id': 'test-agent',
            'status': 'completed',  # Set by reconcile when tmux window closes
            'skill': 'feature-impl',
            'workspace': '.orch/workspace/test-workspace',
            'spawned_at': datetime.now().isoformat()
        }

        result = _detect_completion_fallback(agent_info, tmp_path)
        assert result == "Complete (inferred)"

    def test_returns_inferred_for_investigation_with_complete_deliverable(self, tmp_path):
        """When investigation agent has completed deliverable, return inferred."""
        from orch.monitor import _detect_completion_fallback

        # Create investigation file with Phase: Complete
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "test-workspace.md"
        inv_file.write_text("**Phase:** Complete\n**Status:** Complete")

        agent_info = {
            'id': 'test-agent',
            'status': 'active',
            'skill': 'investigation',
            'workspace': '.orch/workspace/test-workspace',
            'spawned_at': datetime.now().isoformat()
        }

        result = _detect_completion_fallback(agent_info, tmp_path)
        assert result == "Complete (inferred)"

    def test_returns_none_for_investigation_with_incomplete_deliverable(self, tmp_path):
        """When investigation file exists but not complete, return None."""
        from orch.monitor import _detect_completion_fallback

        # Create investigation file with Phase: In Progress
        inv_dir = tmp_path / ".orch" / "investigations" / "simple"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "test-workspace.md"
        inv_file.write_text("**Phase:** In Progress\n**Status:** Active")

        agent_info = {
            'id': 'test-agent',
            'status': 'active',
            'skill': 'investigation',
            'workspace': '.orch/workspace/test-workspace',
            'spawned_at': datetime.now().isoformat()
        }

        result = _detect_completion_fallback(agent_info, tmp_path)
        assert result is None


class TestDetectCompletionScenarioWithPhaseOverride:
    """Tests for detect_completion_scenario with phase_override parameter."""

    def test_uses_phase_override_when_provided(self, tmp_path):
        """When phase_override is provided, use it instead of workspace phase."""
        from orch.monitor import detect_completion_scenario, Scenario

        agent_info = {
            'id': 'test-agent',
            'status': 'completed',
            'project_dir': str(tmp_path),
            'workspace': '.orch/workspace/test',
        }

        # No workspace file exists
        coordination_file = tmp_path / ".orch" / "workspace" / "test" / "WORKSPACE.md"

        scenario, recommendation = detect_completion_scenario(
            agent_info,
            coordination_file,
            phase_override="Complete (inferred)"
        )

        assert scenario == Scenario.READY_COMPLETE
        assert "inferred" in recommendation.lower()

    def test_returns_working_when_no_phase_override_and_no_workspace(self, tmp_path):
        """When no phase_override and workspace missing, return WORKING."""
        from orch.monitor import detect_completion_scenario, Scenario

        agent_info = {
            'id': 'test-agent',
            'status': 'active',
            'project_dir': str(tmp_path),
            'workspace': '.orch/workspace/test',
        }

        coordination_file = tmp_path / ".orch" / "workspace" / "test" / "WORKSPACE.md"

        scenario, recommendation = detect_completion_scenario(
            agent_info,
            coordination_file,
            phase_override=None
        )

        assert scenario == Scenario.WORKING
        assert recommendation is None

    def test_handles_complete_inferred_pattern(self, tmp_path):
        """Phase override with 'Complete (inferred)' is recognized as complete."""
        from orch.monitor import detect_completion_scenario, Scenario

        agent_info = {
            'id': 'test-agent',
            'status': 'completed',
            'project_dir': str(tmp_path),
            'workspace': '.orch/workspace/test',
        }

        coordination_file = tmp_path / ".orch" / "workspace" / "test" / "WORKSPACE.md"

        # Test various inferred patterns
        for phase in ["Complete (inferred)", "complete (inferred)", "COMPLETE (INFERRED)"]:
            scenario, _ = detect_completion_scenario(
                agent_info,
                coordination_file,
                phase_override=phase
            )
            assert scenario == Scenario.READY_COMPLETE, f"Failed for phase: {phase}"


class TestCheckAgentStatusFallback:
    """Tests for check_agent_status with fallback detection."""

    def test_uses_fallback_when_workspace_missing(self, tmp_path):
        """When workspace is missing but agent is completed, use fallback phase."""
        from orch.monitor import check_agent_status

        agent_info = {
            'id': 'test-agent',
            'status': 'completed',  # Set by reconcile
            'project_dir': str(tmp_path),
            'workspace': '.orch/workspace/test',
            'spawned_at': datetime.now().isoformat()
        }

        status = check_agent_status(agent_info)

        # Should have inferred phase
        assert "complete" in status.phase.lower()
        assert "inferred" in status.phase.lower()

    def test_keeps_workspace_phase_when_exists(self, tmp_path):
        """When workspace exists with phase, use workspace phase (not fallback)."""
        from orch.monitor import check_agent_status

        # Create workspace with explicit phase
        workspace_dir = tmp_path / ".orch" / "workspace" / "test"
        workspace_dir.mkdir(parents=True)
        workspace_file = workspace_dir / "WORKSPACE.md"
        workspace_file.write_text("**Phase:** Implementation\n**Status:** Active")

        agent_info = {
            'id': 'test-agent',
            'status': 'active',
            'project_dir': str(tmp_path),
            'workspace': '.orch/workspace/test',
            'spawned_at': datetime.now().isoformat()
        }

        status = check_agent_status(agent_info)

        # Should use workspace phase, not fallback
        assert status.phase == "Implementation"
        assert "inferred" not in status.phase.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
