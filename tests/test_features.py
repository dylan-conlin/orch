"""Tests for backlog.json management module (formerly features.json)."""

import json
import pytest
from pathlib import Path

from orch.features import (
    Feature,
    load_features,
    load_features_safe,
    save_features,
    add_feature,
    update_feature,
    get_feature,
    list_features,
    start_feature,
    complete_feature,
    block_feature,
    validate_schema,
    validate_id,
    generate_id,
    get_features_path,
    BACKLOG_FILENAME,
    FeaturesNotFoundError,
    FeaturesValidationError,
    FeatureNotFoundError,
    DuplicateFeatureError,
)


# cli_runner fixture is now provided by conftest.py


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with .orch folder."""
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_features_json(tmp_project):
    """Create a sample backlog.json file."""
    features_data = {
        "version": "1.0",
        "features": [
            {
                "id": "rate-limiting",
                "description": "Add rate limiting to API endpoints",
                "category": "feature",
                "skill": "feature-impl",
                "skill_args": {"validation": "tests"},
                "verification": None,
                "context_ref": "ROADMAP.org#rate-limiting",
                "status": "pending",
                "workspace": None,
                "started_at": None,
                "completed_at": None
            },
            {
                "id": "fix-auth-bug",
                "description": "Fix authentication token refresh",
                "category": "bug",
                "skill": "feature-impl",
                "skill_args": {},
                "verification": ["login works", "token refresh works"],
                "context_ref": None,
                "status": "in_progress",
                "workspace": ".orch/workspace/2025-11-27-fix-auth-bug",
                "started_at": "2025-11-27T10:00:00",
                "completed_at": None
            },
            {
                "id": "add-caching",
                "description": "Implement Redis caching layer",
                "category": "infrastructure",
                "skill": "feature-impl",
                "skill_args": {},
                "verification": None,
                "context_ref": None,
                "status": "complete",
                "workspace": ".orch/workspace/2025-11-27-add-caching",
                "started_at": "2025-11-26T09:00:00",
                "completed_at": "2025-11-26T15:00:00"
            }
        ]
    }

    # Use backlog.json (renamed from features.json)
    features_path = tmp_project / ".orch" / "backlog.json"
    with features_path.open('w') as f:
        json.dump(features_data, f, indent=2)

    return tmp_project


# cli_runner fixture is now provided by conftest.py


# ============================================================================
# Feature dataclass tests
# ============================================================================

class TestFeatureDataclass:
    def test_create_feature_minimal(self):
        """Test creating Feature with minimal required fields."""
        feature = Feature(
            id="test-feature",
            description="A test feature",
            skill="feature-impl"
        )
        assert feature.id == "test-feature"
        assert feature.description == "A test feature"
        assert feature.skill == "feature-impl"
        assert feature.status == "pending"
        assert feature.category is None

    def test_create_feature_all_fields(self):
        """Test creating Feature with all fields."""
        feature = Feature(
            id="full-feature",
            description="A complete feature",
            skill="feature-impl",
            status="in_progress",
            category="feature",
            skill_args={"validation": "tests"},
            verification=["tests pass"],
            context_ref="ROADMAP.org#section",
            workspace=".orch/workspace/test",
            started_at="2025-11-27T10:00:00",
            completed_at=None
        )
        assert feature.status == "in_progress"
        assert feature.category == "feature"
        assert feature.skill_args == {"validation": "tests"}
        assert feature.verification == ["tests pass"]

    def test_feature_to_dict(self):
        """Test Feature.to_dict() serialization."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl",
            category="bug"
        )
        d = feature.to_dict()
        assert d["id"] == "test"
        assert d["category"] == "bug"
        assert d["status"] == "pending"

    def test_feature_from_dict(self):
        """Test Feature.from_dict() deserialization."""
        data = {
            "id": "from-dict",
            "description": "Created from dict",
            "skill": "investigation",
            "status": "blocked",
            "category": "infrastructure"
        }
        feature = Feature.from_dict(data)
        assert feature.id == "from-dict"
        assert feature.status == "blocked"
        assert feature.category == "infrastructure"


# ============================================================================
# File operation tests
# ============================================================================

class TestFileOperations:
    def test_get_features_path(self, tmp_project):
        """Test get_features_path returns correct path (backlog.json)."""
        path = get_features_path(tmp_project)
        assert path == tmp_project / ".orch" / "backlog.json"

    def test_load_features_not_found(self, tmp_project):
        """Test load_features raises when file doesn't exist."""
        with pytest.raises(FeaturesNotFoundError):
            load_features(tmp_project)

    def test_load_features_safe_not_found(self, tmp_project):
        """Test load_features_safe returns empty list when file doesn't exist."""
        features = load_features_safe(tmp_project)
        assert features == []

    def test_load_features_success(self, sample_features_json):
        """Test load_features returns Feature objects."""
        features = load_features(sample_features_json)
        assert len(features) == 3
        assert all(isinstance(f, Feature) for f in features)
        assert features[0].id == "rate-limiting"

    def test_save_features_creates_file(self, tmp_project):
        """Test save_features creates new file."""
        features = [
            Feature(id="new-feature", description="New", skill="feature-impl")
        ]
        save_features(features, tmp_project)

        # Verify file exists and has correct content
        path = get_features_path(tmp_project)
        assert path.exists()

        with path.open() as f:
            data = json.load(f)
        assert data["version"] == "1.0"
        assert len(data["features"]) == 1
        assert data["features"][0]["id"] == "new-feature"

    def test_save_features_overwrites(self, sample_features_json):
        """Test save_features overwrites existing file."""
        features = [
            Feature(id="only-one", description="Single", skill="feature-impl")
        ]
        save_features(features, sample_features_json)

        loaded = load_features(sample_features_json)
        assert len(loaded) == 1
        assert loaded[0].id == "only-one"


# ============================================================================
# Validation tests
# ============================================================================

class TestValidation:
    def test_validate_schema_valid(self):
        """Test validate_schema passes for valid data."""
        data = {
            "version": "1.0",
            "features": [
                {"id": "test", "description": "Test", "skill": "feature-impl"}
            ]
        }
        validate_schema(data)  # Should not raise

    def test_validate_schema_missing_version(self):
        """Test validate_schema fails without version."""
        with pytest.raises(FeaturesValidationError, match="Missing 'version'"):
            validate_schema({"features": []})

    def test_validate_schema_missing_features(self):
        """Test validate_schema fails without features array."""
        with pytest.raises(FeaturesValidationError, match="Missing 'features'"):
            validate_schema({"version": "1.0"})

    def test_validate_schema_duplicate_ids(self):
        """Test validate_schema fails on duplicate IDs."""
        data = {
            "version": "1.0",
            "features": [
                {"id": "same", "description": "First", "skill": "feature-impl"},
                {"id": "same", "description": "Second", "skill": "feature-impl"}
            ]
        }
        with pytest.raises(FeaturesValidationError, match="Duplicate"):
            validate_schema(data)

    def test_validate_schema_invalid_status(self):
        """Test validate_schema fails on invalid status."""
        data = {
            "version": "1.0",
            "features": [
                {"id": "test", "description": "Test", "skill": "feature-impl", "status": "invalid"}
            ]
        }
        with pytest.raises(FeaturesValidationError, match="invalid status"):
            validate_schema(data)

    def test_validate_id_valid(self):
        """Test validate_id passes for kebab-case IDs."""
        validate_id("valid-id")
        validate_id("another-valid-123")
        validate_id("single")

    def test_validate_id_invalid(self):
        """Test validate_id fails for non-kebab-case IDs."""
        with pytest.raises(FeaturesValidationError):
            validate_id("Invalid_ID")
        with pytest.raises(FeaturesValidationError):
            validate_id("UPPERCASE")
        with pytest.raises(FeaturesValidationError):
            validate_id("")


# ============================================================================
# CRUD operation tests
# ============================================================================

class TestCRUDOperations:
    def test_generate_id(self):
        """Test generate_id creates kebab-case ID."""
        assert generate_id("Add rate limiting") == "add-rate-limiting"
        assert generate_id("Fix the BUG!") == "fix-the-bug"
        assert generate_id("One two three four five six") == "one-two-three-four-five"

    def test_add_feature_creates_file(self, tmp_project):
        """Test add_feature creates backlog.json if missing."""
        feature = add_feature(
            description="New feature",
            project_dir=tmp_project
        )
        assert feature.id == "new-feature"

        # File should exist now
        path = get_features_path(tmp_project)
        assert path.exists()

    def test_add_feature_with_custom_id(self, tmp_project):
        """Test add_feature with custom ID."""
        feature = add_feature(
            description="Some feature",
            feature_id="custom-id",
            project_dir=tmp_project
        )
        assert feature.id == "custom-id"

    def test_add_feature_duplicate_id(self, tmp_project):
        """Test add_feature fails on duplicate ID."""
        add_feature(description="First", project_dir=tmp_project)
        with pytest.raises(DuplicateFeatureError):
            add_feature(description="First", project_dir=tmp_project)

    def test_add_feature_all_options(self, tmp_project):
        """Test add_feature with all options."""
        feature = add_feature(
            description="Complete feature",
            skill="investigation",
            category="infrastructure",
            skill_args={"mode": "deep"},
            verification=["passes lint", "tests green"],
            context_ref="ROADMAP.org#section",
            project_dir=tmp_project
        )
        assert feature.skill == "investigation"
        assert feature.category == "infrastructure"
        assert feature.verification == ["passes lint", "tests green"]

    def test_update_feature(self, sample_features_json):
        """Test update_feature modifies existing feature."""
        feature = update_feature(
            "rate-limiting",
            project_dir=sample_features_json,
            status="in_progress",
            workspace=".orch/workspace/rate-limiting"
        )
        assert feature.status == "in_progress"
        assert feature.workspace == ".orch/workspace/rate-limiting"

        # Verify persisted
        loaded = get_feature("rate-limiting", sample_features_json)
        assert loaded.status == "in_progress"

    def test_update_feature_not_found(self, sample_features_json):
        """Test update_feature raises for non-existent feature."""
        with pytest.raises(FeatureNotFoundError):
            update_feature("nonexistent", project_dir=sample_features_json, status="blocked")

    def test_get_feature(self, sample_features_json):
        """Test get_feature returns correct feature."""
        feature = get_feature("fix-auth-bug", sample_features_json)
        assert feature.description == "Fix authentication token refresh"
        assert feature.category == "bug"

    def test_get_feature_not_found(self, sample_features_json):
        """Test get_feature raises for non-existent feature."""
        with pytest.raises(FeatureNotFoundError):
            get_feature("nonexistent", sample_features_json)

    def test_list_features_all(self, sample_features_json):
        """Test list_features returns all features."""
        features = list_features(sample_features_json)
        assert len(features) == 3

    def test_list_features_by_status(self, sample_features_json):
        """Test list_features filters by status."""
        pending = list_features(sample_features_json, status="pending")
        assert len(pending) == 1
        assert pending[0].id == "rate-limiting"

        in_progress = list_features(sample_features_json, status="in_progress")
        assert len(in_progress) == 1
        assert in_progress[0].id == "fix-auth-bug"

    def test_list_features_by_category(self, sample_features_json):
        """Test list_features filters by category."""
        bugs = list_features(sample_features_json, category="bug")
        assert len(bugs) == 1
        assert bugs[0].id == "fix-auth-bug"

    def test_list_features_combined_filters(self, sample_features_json):
        """Test list_features with multiple filters."""
        # Add another pending bug
        add_feature(
            description="Another bug",
            category="bug",
            project_dir=sample_features_json
        )

        pending_bugs = list_features(sample_features_json, status="pending", category="bug")
        assert len(pending_bugs) == 1
        assert pending_bugs[0].id == "another-bug"


# ============================================================================
# Convenience function tests
# ============================================================================

class TestConvenienceFunctions:
    def test_start_feature(self, sample_features_json):
        """Test start_feature sets status and timestamps."""
        feature = start_feature(
            "rate-limiting",
            workspace_path=".orch/workspace/rate-limiting",
            project_dir=sample_features_json
        )
        assert feature.status == "in_progress"
        assert feature.workspace == ".orch/workspace/rate-limiting"
        assert feature.started_at is not None

    def test_complete_feature(self, sample_features_json):
        """Test complete_feature sets status and timestamp."""
        feature = complete_feature("fix-auth-bug", project_dir=sample_features_json)
        assert feature.status == "complete"
        assert feature.completed_at is not None

    def test_block_feature(self, sample_features_json):
        """Test block_feature sets status."""
        feature = block_feature("rate-limiting", project_dir=sample_features_json)
        assert feature.status == "blocked"


# ============================================================================
# CLI tests
# ============================================================================

class TestFeaturesCLI:
    def test_features_list_no_file(self, cli_runner, tmp_path, monkeypatch):
        """Test 'orch features' when no backlog.json exists."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".orch").mkdir()

        result = cli_runner.invoke(cli, ['features'])
        assert result.exit_code == 0
        assert "No backlog.json found" in result.output

    def test_features_list_with_features(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features' lists features."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features'])
        assert result.exit_code == 0
        assert "Features (3)" in result.output
        assert "rate-limiting" in result.output
        assert "fix-auth-bug" in result.output

    def test_features_list_filter_status(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features --pending' filters by status."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features', '--pending'])
        assert result.exit_code == 0
        assert "rate-limiting" in result.output
        assert "fix-auth-bug" not in result.output

    def test_features_list_filter_category(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features --category bug' filters by category."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features', '--category', 'bug'])
        assert result.exit_code == 0
        assert "fix-auth-bug" in result.output
        assert "rate-limiting" not in result.output

    def test_features_list_json_format(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features --format json' outputs JSON."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features', '--format', 'json'])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert "features" in data
        assert data["total"] == 3

    def test_features_add(self, cli_runner, tmp_path, monkeypatch):
        """Test 'orch features add' creates feature."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".orch").mkdir()

        result = cli_runner.invoke(cli, ['features', 'add', 'New test feature'])
        assert result.exit_code == 0
        assert "Feature added" in result.output
        assert "new-test-feature" in result.output

        # Verify file created
        features = load_features(tmp_path)
        assert len(features) == 1
        assert features[0].description == "New test feature"

    def test_features_add_with_options(self, cli_runner, tmp_path, monkeypatch):
        """Test 'orch features add' with all options."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".orch").mkdir()

        result = cli_runner.invoke(cli, [
            'features', 'add', 'Bug fix',
            '--category', 'bug',
            '--id', 'custom-bug-id',
            '--context-ref', 'issues/123'
        ])
        assert result.exit_code == 0
        assert "custom-bug-id" in result.output
        assert "Category: bug" in result.output

    def test_features_add_duplicate(self, cli_runner, tmp_path, monkeypatch):
        """Test 'orch features add' fails on duplicate."""
        from orch.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".orch").mkdir()

        # Add first feature
        cli_runner.invoke(cli, ['features', 'add', 'First feature'])

        # Try to add duplicate
        result = cli_runner.invoke(cli, ['features', 'add', 'First feature'])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_features_show(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features show' displays feature details."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features', 'show', 'fix-auth-bug'])
        assert result.exit_code == 0
        assert "fix-auth-bug" in result.output
        assert "authentication token refresh" in result.output
        assert "in_progress" in result.output
        assert "bug" in result.output

    def test_features_show_not_found(self, cli_runner, sample_features_json, monkeypatch):
        """Test 'orch features show' for non-existent feature."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)

        result = cli_runner.invoke(cli, ['features', 'show', 'nonexistent'])
        assert result.exit_code == 1
        assert "not found" in result.output


# ============================================================================
# Spawn integration tests
# ============================================================================

class TestSpawnFeatureIntegration:
    """Tests for spawn --feature integration with backlog.json."""

    def test_spawn_config_has_feature_id(self):
        """Test SpawnConfig has feature_id field."""
        from orch.spawn import SpawnConfig
        from pathlib import Path

        config = SpawnConfig(
            task="test task",
            project="test-project",
            project_dir=Path("/tmp/test"),
            workspace_name="test-workspace",
            feature_id="test-feature"
        )
        assert config.feature_id == "test-feature"

    def test_spawn_config_feature_id_default_none(self):
        """Test SpawnConfig feature_id defaults to None."""
        from orch.spawn import SpawnConfig
        from pathlib import Path

        config = SpawnConfig(
            task="test task",
            project="test-project",
            project_dir=Path("/tmp/test"),
            workspace_name="test-workspace"
        )
        assert config.feature_id is None

    def test_registry_stores_feature_id(self, tmp_path, monkeypatch):
        """Test registry stores feature_id when provided."""
        from orch.registry import AgentRegistry

        # Use temp file for registry
        registry_path = tmp_path / "agents.json"

        registry = AgentRegistry(registry_path=registry_path)

        agent = registry.register(
            agent_id="test-agent",
            task="test task",
            window="workers:1",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test",
            feature_id="test-feature-id"
        )

        assert agent.get('feature_id') == "test-feature-id"

        # Verify persisted
        registry2 = AgentRegistry(registry_path=registry_path)
        loaded = registry2.find("test-agent")
        assert loaded.get('feature_id') == "test-feature-id"

    def test_registry_feature_id_optional(self, tmp_path, monkeypatch):
        """Test registry works without feature_id."""
        from orch.registry import AgentRegistry

        registry_path = tmp_path / "agents.json"

        registry = AgentRegistry(registry_path=registry_path)

        agent = registry.register(
            agent_id="test-agent-no-feature",
            task="test task",
            window="workers:1",
            project_dir=str(tmp_path),
            workspace=".orch/workspace/test"
            # No feature_id
        )

        assert 'feature_id' not in agent

    def test_start_feature_updates_status(self, sample_features_json):
        """Test start_feature updates status and sets timestamps."""
        feature = start_feature(
            "rate-limiting",
            workspace_path=".orch/workspace/test-workspace",
            project_dir=sample_features_json
        )

        assert feature.status == "in_progress"
        assert feature.workspace == ".orch/workspace/test-workspace"
        assert feature.started_at is not None

        # Verify persisted
        loaded = get_feature("rate-limiting", sample_features_json)
        assert loaded.status == "in_progress"

    def test_complete_feature_updates_status(self, sample_features_json):
        """Test complete_feature updates status and sets timestamp."""
        # First start the feature
        start_feature(
            "rate-limiting",
            workspace_path=".orch/workspace/test-workspace",
            project_dir=sample_features_json
        )

        # Then complete it
        feature = complete_feature("rate-limiting", sample_features_json)

        assert feature.status == "complete"
        assert feature.completed_at is not None

        # Verify persisted
        loaded = get_feature("rate-limiting", sample_features_json)
        assert loaded.status == "complete"


# ============================================================================
# Spawn CLI feature option tests
# ============================================================================

class TestSpawnFeatureCLI:
    """Tests for spawn --feature CLI option."""

    def test_spawn_feature_option_exists(self, cli_runner):
        """Test spawn command has --feature option."""
        from orch.cli import cli

        result = cli_runner.invoke(cli, ['spawn', '--help'])
        assert '--feature' in result.output
        assert 'backlog.json' in result.output

    def test_spawn_feature_not_found(self, cli_runner, sample_features_json, monkeypatch):
        """Test spawn --feature fails for non-existent feature."""
        from orch.cli import cli

        monkeypatch.chdir(sample_features_json)
        # Clear worker context so spawn is allowed
        monkeypatch.delenv('CLAUDE_CONTEXT', raising=False)

        result = cli_runner.invoke(cli, ['spawn', '--feature', 'nonexistent', '-y'])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_spawn_feature_no_features_file(self, cli_runner, tmp_path, monkeypatch):
        """Test spawn --feature fails when backlog.json doesn't exist."""
        from orch.cli import cli

        (tmp_path / ".orch").mkdir()
        monkeypatch.chdir(tmp_path)
        # Clear worker context so spawn is allowed
        monkeypatch.delenv('CLAUDE_CONTEXT', raising=False)

        result = cli_runner.invoke(cli, ['spawn', '--feature', 'some-feature', '-y'])
        assert result.exit_code != 0
        assert "backlog.json not found" in result.output


# ============================================================================
# Backlog.json rename tests (features.json → backlog.json)
# ============================================================================

class TestBacklogRename:
    """Tests for the rename from features.json to backlog.json."""

    def test_backlog_filename_constant(self):
        """Test BACKLOG_FILENAME constant is 'backlog.json'."""
        assert BACKLOG_FILENAME == "backlog.json"

    def test_get_features_path_returns_backlog_json(self, tmp_project):
        """Test get_features_path returns path to backlog.json."""
        path = get_features_path(tmp_project)
        assert path.name == "backlog.json"
        assert path == tmp_project / ".orch" / "backlog.json"

    def test_load_features_error_mentions_backlog(self, tmp_project):
        """Test error message mentions backlog.json when file not found."""
        with pytest.raises(FeaturesNotFoundError) as exc_info:
            load_features(tmp_project)
        assert "backlog.json" in str(exc_info.value)

    def test_save_features_creates_backlog_file(self, tmp_project):
        """Test save_features creates backlog.json file."""
        features = [
            Feature(id="test", description="Test", skill="feature-impl")
        ]
        save_features(features, tmp_project)

        # Verify file is named backlog.json
        backlog_path = tmp_project / ".orch" / "backlog.json"
        assert backlog_path.exists()

        # Verify old filename doesn't exist
        features_path = tmp_project / ".orch" / "features.json"
        assert not features_path.exists()


# ============================================================================
# New schema fields tests (type, investigation, resolution, related)
# ============================================================================

class TestNewSchemaFields:
    """Tests for new schema fields: type, investigation, resolution, related."""

    def test_feature_has_type_field(self):
        """Test Feature dataclass has type field with default 'feature'."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl"
        )
        assert hasattr(feature, 'type')
        assert feature.type == "feature"  # default value

    def test_feature_type_can_be_set(self):
        """Test type field can be set to bug or improvement."""
        bug = Feature(
            id="fix-bug",
            description="Fix a bug",
            skill="feature-impl",
            type="bug"
        )
        assert bug.type == "bug"

        improvement = Feature(
            id="improve-perf",
            description="Improve performance",
            skill="feature-impl",
            type="improvement"
        )
        assert improvement.type == "improvement"

    def test_feature_has_investigation_field(self):
        """Test Feature dataclass has investigation field (nullable)."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl"
        )
        assert hasattr(feature, 'investigation')
        assert feature.investigation is None  # default

        # Can set investigation link
        feature_with_inv = Feature(
            id="test2",
            description="Test with investigation",
            skill="feature-impl",
            investigation=".orch/investigations/simple/2025-11-28-topic.md"
        )
        assert feature_with_inv.investigation == ".orch/investigations/simple/2025-11-28-topic.md"

    def test_feature_has_resolution_field(self):
        """Test Feature dataclass has resolution field (nullable)."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl"
        )
        assert hasattr(feature, 'resolution')
        assert feature.resolution is None  # default

        # Can set resolution
        feature_with_resolution = Feature(
            id="bug-fix",
            description="Fixed bug",
            skill="feature-impl",
            resolution="fix"
        )
        assert feature_with_resolution.resolution == "fix"

    def test_feature_has_related_field(self):
        """Test Feature dataclass has related field (array of IDs)."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl"
        )
        assert hasattr(feature, 'related')
        assert feature.related == []  # default empty array

        # Can set related items
        feature_with_related = Feature(
            id="test2",
            description="Related feature",
            skill="feature-impl",
            related=["other-feature", "another-feature"]
        )
        assert feature_with_related.related == ["other-feature", "another-feature"]

    def test_feature_to_dict_includes_new_fields(self):
        """Test Feature.to_dict() includes new fields."""
        feature = Feature(
            id="test",
            description="Test",
            skill="feature-impl",
            type="bug",
            investigation=".orch/investigations/test.md",
            resolution="fix",
            related=["related-1"]
        )
        d = feature.to_dict()
        assert d["type"] == "bug"
        assert d["investigation"] == ".orch/investigations/test.md"
        assert d["resolution"] == "fix"
        assert d["related"] == ["related-1"]

    def test_feature_from_dict_with_new_fields(self):
        """Test Feature.from_dict() handles new fields."""
        data = {
            "id": "from-dict",
            "description": "From dict",
            "skill": "feature-impl",
            "type": "improvement",
            "investigation": ".orch/investigations/test.md",
            "resolution": "workaround",
            "related": ["feature-a", "feature-b"]
        }
        feature = Feature.from_dict(data)
        assert feature.type == "improvement"
        assert feature.investigation == ".orch/investigations/test.md"
        assert feature.resolution == "workaround"
        assert feature.related == ["feature-a", "feature-b"]

    def test_feature_from_dict_defaults_new_fields(self):
        """Test Feature.from_dict() uses defaults for missing new fields."""
        # Simulates loading old data without new fields
        data = {
            "id": "old-feature",
            "description": "Old feature without new fields",
            "skill": "feature-impl",
            "status": "pending"
        }
        feature = Feature.from_dict(data)
        assert feature.type == "feature"  # default
        assert feature.investigation is None  # default
        assert feature.resolution is None  # default
        assert feature.related == []  # default

    def test_add_feature_with_new_fields(self, tmp_project):
        """Test add_feature can set new fields."""
        feature = add_feature(
            description="New feature with type",
            project_dir=tmp_project,
            type="bug",
            investigation=".orch/investigations/test.md",
            resolution=None,
            related=["other-feature"]
        )
        assert feature.type == "bug"
        assert feature.investigation == ".orch/investigations/test.md"
        assert feature.related == ["other-feature"]

        # Verify persisted
        loaded = get_feature(feature.id, tmp_project)
        assert loaded.type == "bug"
        assert loaded.investigation == ".orch/investigations/test.md"
        assert loaded.related == ["other-feature"]

    def test_validate_schema_accepts_new_fields(self):
        """Test validate_schema accepts data with new fields."""
        data = {
            "version": "1.0",
            "features": [
                {
                    "id": "test",
                    "description": "Test",
                    "skill": "feature-impl",
                    "type": "bug",
                    "investigation": ".orch/investigations/test.md",
                    "resolution": "fix",
                    "related": ["other"]
                }
            ]
        }
        validate_schema(data)  # Should not raise

    def test_validate_schema_invalid_type(self):
        """Test validate_schema fails on invalid type value."""
        data = {
            "version": "1.0",
            "features": [
                {
                    "id": "test",
                    "description": "Test",
                    "skill": "feature-impl",
                    "type": "invalid-type"  # Invalid!
                }
            ]
        }
        with pytest.raises(FeaturesValidationError, match="invalid type"):
            validate_schema(data)

    def test_validate_schema_valid_types(self):
        """Test validate_schema accepts all valid type values."""
        for valid_type in ["feature", "bug", "improvement"]:
            data = {
                "version": "1.0",
                "features": [
                    {
                        "id": f"test-{valid_type}",
                        "description": "Test",
                        "skill": "feature-impl",
                        "type": valid_type
                    }
                ]
            }
            validate_schema(data)  # Should not raise

    def test_validate_schema_invalid_resolution(self):
        """Test validate_schema fails on invalid resolution value."""
        data = {
            "version": "1.0",
            "features": [
                {
                    "id": "test",
                    "description": "Test",
                    "skill": "feature-impl",
                    "resolution": "invalid-resolution"  # Invalid!
                }
            ]
        }
        with pytest.raises(FeaturesValidationError, match="invalid resolution"):
            validate_schema(data)

    def test_validate_schema_valid_resolutions(self):
        """Test validate_schema accepts all valid resolution values."""
        # null (None) is valid
        data_null = {
            "version": "1.0",
            "features": [
                {
                    "id": "test-null",
                    "description": "Test",
                    "skill": "feature-impl",
                    "resolution": None
                }
            ]
        }
        validate_schema(data_null)  # Should not raise

        # "fix" and "workaround" are valid
        for valid_resolution in ["fix", "workaround"]:
            data = {
                "version": "1.0",
                "features": [
                    {
                        "id": f"test-{valid_resolution}",
                        "description": "Test",
                        "skill": "feature-impl",
                        "resolution": valid_resolution
                    }
                ]
            }
            validate_schema(data)  # Should not raise
