"""
Tests for feature-impl skill configuration in orch spawn.

Tests feature-impl skill configuration flags including:
- --phases parameter for phase selection
- --mode parameter for TDD vs direct mode
- --validation parameter for validation levels
- Phase/mode/validation validation logic
- Multi-phase validation dependencies
"""

import pytest
from pathlib import Path

from orch.spawn import (
    SpawnConfig,
    validate_feature_impl_config,
)


class TestFeatureImplConfiguration:
    """Tests for feature-impl skill configuration flags (--phases, --mode, --validation)."""

    def test_spawn_config_accepts_phases_parameter(self):
        """Test that SpawnConfig accepts phases parameter."""
        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="feature-test",
            phases="investigation,design,implementation,validation"
        )

        assert config.phases == "investigation,design,implementation,validation"

    def test_spawn_config_accepts_mode_parameter(self):
        """Test that SpawnConfig accepts mode parameter."""
        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="feature-test",
            mode="tdd"
        )

        assert config.mode == "tdd"

    def test_spawn_config_accepts_validation_parameter(self):
        """Test that SpawnConfig accepts validation parameter."""
        config = SpawnConfig(
            task="Implement feature",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="feature-test",
            validation="smoke-test"
        )

        assert config.validation == "smoke-test"

    def test_validate_feature_impl_config_valid_phases(self):
        """Test validation accepts valid phase combinations."""
        # Valid single phase
        validate_feature_impl_config(phases="implementation")

        # Valid multiple phases
        validate_feature_impl_config(phases="investigation,design,implementation,validation")

        # Valid all phases
        validate_feature_impl_config(phases="investigation,design,implementation,validation,integration")

    def test_validate_feature_impl_config_clarifying_questions_phase(self):
        """Test validation accepts clarifying-questions phase.

        The clarifying-questions phase should come BEFORE design to surface
        ambiguities before architectural decisions are made.
        Pattern learned from feature-dev workflow.
        """
        # Valid with just clarifying-questions
        validate_feature_impl_config(phases="clarifying-questions")

        # Valid in canonical order (investigation -> clarifying-questions -> design)
        validate_feature_impl_config(phases="investigation,clarifying-questions,design,implementation")

        # Valid full workflow with clarifying-questions
        validate_feature_impl_config(phases="investigation,clarifying-questions,design,implementation,validation")

    def test_validate_feature_impl_config_invalid_phases(self):
        """Test validation rejects invalid phase names."""
        with pytest.raises(ValueError, match="Invalid phase"):
            validate_feature_impl_config(phases="invalid-phase")

        with pytest.raises(ValueError, match="Invalid phase"):
            validate_feature_impl_config(phases="investigation,invalid,validation")

    def test_validate_feature_impl_config_valid_modes(self):
        """Test validation accepts valid implementation modes."""
        validate_feature_impl_config(mode="tdd")
        validate_feature_impl_config(mode="direct")

    def test_validate_feature_impl_config_invalid_mode(self):
        """Test validation rejects invalid modes."""
        with pytest.raises(ValueError, match="Invalid mode"):
            validate_feature_impl_config(mode="invalid")

    def test_validate_feature_impl_config_valid_validation_levels(self):
        """Test validation accepts valid validation levels."""
        validate_feature_impl_config(validation="none")
        validate_feature_impl_config(validation="tests")
        validate_feature_impl_config(validation="smoke-test")
        # multi-phase tested separately (requires phase-id)

    def test_validate_feature_impl_config_invalid_validation(self):
        """Test validation rejects invalid validation levels."""
        with pytest.raises(ValueError, match="Invalid validation level"):
            validate_feature_impl_config(validation="invalid")

    def test_validate_feature_impl_config_mode_requires_implementation_phase(self):
        """Test that mode is only relevant when implementation phase is included."""
        # Should warn when mode specified but no implementation phase
        # (Not raising error, just ignoring mode)
        validate_feature_impl_config(
            phases="investigation,design",
            mode="tdd"
        )
        # Should not raise - mode is simply ignored

    def test_validate_feature_impl_config_validation_requires_validation_phase(self):
        """Test that validation level is only relevant when validation phase is included."""
        # Should work - validation ignored when no validation phase
        validate_feature_impl_config(
            phases="investigation,design",
            validation="smoke-test"
        )
        # Should not raise - validation level is simply ignored

    def test_validate_feature_impl_config_multi_phase_requires_phase_id(self):
        """Test that multi-phase validation requires phase-id."""
        # Should raise when multi-phase without phase-id
        with pytest.raises(ValueError, match="multi-phase validation requires --phase-id"):
            validate_feature_impl_config(
                validation="multi-phase",
                phase_id=None
            )

        # Should work with phase-id
        validate_feature_impl_config(
            validation="multi-phase",
            phase_id="phase-a"
        )

    def test_validate_feature_impl_config_depends_on_requires_phase_id(self):
        """Test that depends-on requires phase-id."""
        # Should raise when depends-on without phase-id
        with pytest.raises(ValueError, match="--depends-on requires --phase-id"):
            validate_feature_impl_config(
                depends_on="phase-a",
                phase_id=None
            )

        # Should work with phase-id
        validate_feature_impl_config(
            depends_on="phase-a",
            phase_id="phase-b"
        )
