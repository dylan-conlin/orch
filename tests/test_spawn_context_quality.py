"""
Tests for spawn context quality validation.

This module tests the validation logic that checks spawn contexts for
completeness and quality indicators as defined in the decision document:
.orch/decisions/2025-11-19-spawn-context-first-class-orchestrator-artifact.md

Related: Phase 2 of SPAWN_CONTEXT.md as first-class artifact feature.
"""

import pytest
from dataclasses import dataclass
from typing import List

# Import will fail until we implement the module - TDD style
# from orch.spawn_context_quality import (
#     validate_spawn_context_quality,
#     SpawnContextQuality,
#     QualityIndicator,
# )


class TestSpawnContextQualityValidation:
    """Tests for spawn context quality validation function."""

    def test_complete_spawn_context_returns_no_warnings(self):
        """A complete spawn context should have no warnings."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        complete_context = """TASK: Implement user authentication

CONTEXT: Need to add login/logout functionality to the app

PROJECT_DIR: /Users/test/project

SESSION SCOPE: Medium (estimated 2-4h)
- Multiple files involved
- Recommend checkpoint every 2 hours

SCOPE:
- IN: User login/logout, session management
- OUT: OAuth integration, password reset

AUTHORITY:
**You have authority to decide:**
- Implementation details
- Testing strategies

**You must escalate to orchestrator when:**
- Architectural decisions needed
- Scope unclear

DELIVERABLES (REQUIRED):
1. User authentication module
2. Tests for auth flow

VERIFICATION REQUIRED:
- [ ] Tests pass
- [ ] Manual verification complete
"""
        result = validate_spawn_context_quality(complete_context)

        assert result.is_complete, "Complete spawn context should be marked as complete"
        assert len(result.warnings) == 0, f"Expected no warnings, got: {result.warnings}"
        assert result.score == 100, f"Expected 100% score, got: {result.score}"

    def test_missing_task_returns_warning(self):
        """Missing TASK section should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_without_task = """CONTEXT: Some context here

PROJECT_DIR: /test/project

SCOPE:
- IN: Something
- OUT: Something else

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(context_without_task)

        assert not result.is_complete
        assert any("TASK" in w.message for w in result.warnings)

    def test_missing_scope_returns_warning(self):
        """Missing SCOPE section should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_without_scope = """TASK: Do something

PROJECT_DIR: /test/project

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(context_without_scope)

        assert not result.is_complete
        assert any("SCOPE" in w.message or "scope" in w.message for w in result.warnings)

    def test_missing_session_scope_returns_warning(self):
        """Missing SESSION SCOPE should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_without_session_scope = """TASK: Do something

PROJECT_DIR: /test/project

SCOPE:
- IN: This
- OUT: That

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(context_without_session_scope)

        assert any("SESSION SCOPE" in w.message for w in result.warnings)

    def test_missing_authority_returns_warning(self):
        """Missing AUTHORITY section should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_without_authority = """TASK: Do something

PROJECT_DIR: /test/project

SCOPE:
- IN: This
- OUT: That

SESSION SCOPE: Medium (estimated 2-4h)

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(context_without_authority)

        assert any("AUTHORITY" in w.message for w in result.warnings)

    def test_missing_deliverables_returns_warning(self):
        """Missing DELIVERABLES section should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_without_deliverables = """TASK: Do something

PROJECT_DIR: /test/project

SCOPE:
- IN: This
- OUT: That

AUTHORITY:
**You have authority to decide:**
- Implementation
"""
        result = validate_spawn_context_quality(context_without_deliverables)

        assert any("DELIVERABLES" in w.message for w in result.warnings)

    def test_placeholder_task_returns_warning(self):
        """TASK with placeholder text should return a warning."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        context_with_placeholder = """TASK: [One sentence description]

PROJECT_DIR: /test/project

SCOPE:
- IN: This
- OUT: That

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(context_with_placeholder)

        assert not result.is_complete
        assert any("placeholder" in w.message.lower() or "TASK" in w.message for w in result.warnings)

    def test_empty_context_returns_multiple_warnings(self):
        """Empty context should return warnings for all missing sections."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        result = validate_spawn_context_quality("")

        assert not result.is_complete
        assert len(result.warnings) >= 4  # At least TASK, SCOPE, DELIVERABLES, AUTHORITY

    def test_quality_score_reflects_completeness(self):
        """Quality score should reflect percentage of sections present."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        # Partial context - has some but not all sections
        partial_context = """TASK: Do something

PROJECT_DIR: /test/project

DELIVERABLES:
1. Something
"""
        result = validate_spawn_context_quality(partial_context)

        # Should have a score between 0 and 100 based on completeness
        assert 0 < result.score < 100
        assert not result.is_complete

    def test_severity_levels_assigned_correctly(self):
        """Different missing sections should have appropriate severity levels."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        # Context missing critical sections
        minimal_context = """TASK: Do something
"""
        result = validate_spawn_context_quality(minimal_context)

        # Find severity levels
        has_critical = any(w.severity == "critical" for w in result.warnings)
        has_warning = any(w.severity == "warning" for w in result.warnings)

        # Missing SCOPE and DELIVERABLES should be critical/important
        assert has_critical or has_warning, "Should have severity indicators"


class TestSpawnContextQualityIntegration:
    """Integration tests for spawn context quality with real-world scenarios."""

    def test_feature_impl_spawn_context_quality(self):
        """Validate a typical feature-impl spawn context."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        feature_impl_context = """TASK: Add rate limiting to API endpoints

CONTEXT: Users are hitting rate limits inconsistently. Need standardized rate limiting.

PROJECT_DIR: /Users/dev/api-service

SESSION SCOPE: Medium (estimated 2-4h)
- 3-4 files to modify
- Recommend checkpoint every 2 hours

SCOPE:
- IN: Rate limiting middleware, configuration, tests
- OUT: User notifications, admin dashboard

AUTHORITY:
**You have authority to decide:**
- Implementation details (how to structure code)
- Testing strategies
- Library selection within established patterns

**You must escalate to orchestrator when:**
- Architectural decisions (new patterns)
- Rate limit values (business decision)

DELIVERABLES (REQUIRED):
1. Rate limiting middleware implementation
2. Configuration for different endpoint tiers
3. Unit and integration tests

VERIFICATION REQUIRED:
- [ ] All tests pass
- [ ] Rate limiting works in development
- [ ] No performance regression

## SKILL GUIDANCE (feature-impl)
...skill content...

FEATURE-IMPL CONFIGURATION:
Phases: implementation
Mode: tdd
Validation: tests
"""
        result = validate_spawn_context_quality(feature_impl_context)

        assert result.is_complete, f"Feature-impl context should be complete. Warnings: {result.warnings}"
        assert result.score >= 80

    def test_investigation_spawn_context_quality(self):
        """Validate a typical investigation spawn context."""
        from orch.spawn_context_quality import validate_spawn_context_quality

        investigation_context = """TASK: Investigate why webhook processing is slow

PROJECT_DIR: /Users/dev/webhook-service

SESSION SCOPE: Small (estimated 1-2h)
- Focused investigation
- Single session expected

SCOPE:
- IN: Webhook handler, queue processing, timing analysis
- OUT: Fixing the issue (just investigation)

AUTHORITY:
**You have authority to decide:**
- Investigation approach
- Tools to use for profiling

**You must escalate to orchestrator when:**
- Findings suggest architectural changes needed
- Multiple root causes discovered

DELIVERABLES (REQUIRED):
1. Investigation file with findings
2. Clear recommendation for next steps

VERIFICATION REQUIRED:
- [ ] Root cause identified or narrowed down
- [ ] Findings documented with evidence
"""
        result = validate_spawn_context_quality(investigation_context)

        # Investigation contexts should also be complete
        assert result.score >= 80


class TestQualityIndicatorDataclass:
    """Tests for the QualityIndicator dataclass."""

    def test_quality_indicator_has_required_fields(self):
        """QualityIndicator should have message, severity, and section fields."""
        from orch.spawn_context_quality import QualityIndicator

        indicator = QualityIndicator(
            message="Missing SCOPE section",
            severity="warning",
            section="SCOPE"
        )

        assert indicator.message == "Missing SCOPE section"
        assert indicator.severity == "warning"
        assert indicator.section == "SCOPE"


class TestSpawnContextQualityResult:
    """Tests for the SpawnContextQuality result dataclass."""

    def test_result_has_required_fields(self):
        """SpawnContextQuality should have is_complete, warnings, and score."""
        from orch.spawn_context_quality import SpawnContextQuality, QualityIndicator

        result = SpawnContextQuality(
            is_complete=False,
            warnings=[QualityIndicator("test", "warning", "SCOPE")],
            score=50,
            sections_present=["TASK"],
            sections_missing=["SCOPE"]
        )

        assert result.is_complete is False
        assert len(result.warnings) == 1
        assert result.score == 50
        assert "TASK" in result.sections_present
        assert "SCOPE" in result.sections_missing
