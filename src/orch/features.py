"""
backlog.json management for enumerable task execution.

This module provides:
- Feature data structure with typed fields
- Load/save operations for .orch/backlog.json
- Add/update/list operations with filtering
- Schema validation

Decision reference: .orch/decisions/2025-11-27-feature-list-format-design.md
Decision reference: .orch/decisions/2025-11-28-backlog-investigation-separation.md
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# ============================================================================
# CONSTANTS
# ============================================================================

FEATURES_VERSION = "1.0"
BACKLOG_FILENAME = "backlog.json"

# Valid status values
VALID_STATUSES = {"pending", "in_progress", "complete", "blocked"}

# Valid type values for backlog items
VALID_TYPES = {"feature", "bug", "improvement"}

# Valid resolution values (null is also valid, handled separately)
# Extended to support investigation outcomes and decision states
VALID_RESOLUTIONS = {"fix", "workaround", "not-adopted", "no-action-needed", "deferred"}

# Default categories (informational, not enforced)
DEFAULT_CATEGORIES = {"feature", "bug", "infrastructure", "fix"}


# ============================================================================
# EXCEPTIONS
# ============================================================================

class FeaturesError(Exception):
    """Base exception for features module."""
    pass


class FeaturesNotFoundError(FeaturesError):
    """Raised when backlog.json doesn't exist."""
    pass


class FeaturesValidationError(FeaturesError):
    """Raised when backlog.json fails validation."""
    pass


class FeatureNotFoundError(FeaturesError):
    """Raised when a specific feature is not found."""
    pass


class DuplicateFeatureError(FeaturesError):
    """Raised when trying to add a feature with existing ID."""
    pass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Feature:
    """
    Represents a single item in backlog.json.

    Required fields:
        id: Unique identifier (kebab-case)
        description: What to do (one sentence)
        skill: Which skill to use
        status: pending, in_progress, complete, blocked

    Optional fields:
        type: Item type (feature, bug, improvement) - default: feature
        category: Grouping (feature, infrastructure, fix, bug)
        skill_args: Arguments passed to skill
        verification: Custom verification criteria (overrides skill default)
        context_ref: Pointer to additional context
        investigation: Link to investigation document (nullable)
        resolution: How the item was resolved (null, fix, workaround, not-adopted, no-action-needed, deferred) - set when complete
        related: Array of related item IDs
        workspace: Path to workspace when in_progress/complete
        started_at: ISO timestamp when work began
        completed_at: ISO timestamp when work finished
    """
    id: str
    description: str
    skill: str
    status: str = "pending"
    type: str = "feature"
    category: Optional[str] = None
    skill_args: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[List[str]] = None
    context_ref: Optional[str] = None
    investigation: Optional[str] = None
    resolution: Optional[str] = None
    related: List[str] = field(default_factory=list)
    workspace: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feature":
        """Create Feature from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            skill=data["skill"],
            status=data.get("status", "pending"),
            type=data.get("type", "feature"),
            category=data.get("category"),
            skill_args=data.get("skill_args", {}),
            verification=data.get("verification"),
            context_ref=data.get("context_ref"),
            investigation=data.get("investigation"),
            resolution=data.get("resolution"),
            related=data.get("related", []),
            workspace=data.get("workspace"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def get_features_path(project_dir: Optional[Path] = None) -> Path:
    """
    Get path to backlog.json for a project.

    Args:
        project_dir: Project directory (defaults to cwd)

    Returns:
        Path to .orch/backlog.json
    """
    if project_dir is None:
        project_dir = Path.cwd()
    return project_dir / ".orch" / BACKLOG_FILENAME


def load_features(project_dir: Optional[Path] = None) -> List[Feature]:
    """
    Load features from .orch/backlog.json.

    Args:
        project_dir: Project directory (defaults to cwd)

    Returns:
        List of Feature objects

    Raises:
        FeaturesNotFoundError: If backlog.json doesn't exist
        FeaturesValidationError: If file is malformed
    """
    features_path = get_features_path(project_dir)

    if not features_path.exists():
        raise FeaturesNotFoundError(
            f"backlog.json not found at {features_path}. "
            "Run 'orch features add' to create one."
        )

    try:
        with features_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise FeaturesValidationError(f"Invalid JSON in backlog.json: {e}")
    except Exception as e:
        raise FeaturesError(f"Error reading backlog.json: {e}")

    # Validate structure
    validate_schema(data)

    # Convert to Feature objects
    return [Feature.from_dict(item) for item in data.get("features", [])]


def load_features_safe(project_dir: Optional[Path] = None) -> List[Feature]:
    """
    Load features from .orch/backlog.json, returning empty list if not found.

    Unlike load_features(), this won't raise FeaturesNotFoundError.

    Args:
        project_dir: Project directory (defaults to cwd)

    Returns:
        List of Feature objects (empty if file doesn't exist)
    """
    try:
        return load_features(project_dir)
    except FeaturesNotFoundError:
        return []


def save_features(features: List[Feature], project_dir: Optional[Path] = None) -> None:
    """
    Save features to .orch/backlog.json.

    Creates the .orch directory if it doesn't exist.

    Args:
        features: List of Feature objects to save
        project_dir: Project directory (defaults to cwd)
    """
    features_path = get_features_path(project_dir)

    # Ensure .orch directory exists
    features_path.parent.mkdir(parents=True, exist_ok=True)

    # Build JSON structure
    data = {
        "version": FEATURES_VERSION,
        "features": [f.to_dict() for f in features]
    }

    # Write with pretty formatting
    with features_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  # Trailing newline


# ============================================================================
# VALIDATION
# ============================================================================

def validate_schema(data: Dict[str, Any]) -> None:
    """
    Validate backlog.json schema.

    Args:
        data: Parsed JSON data

    Raises:
        FeaturesValidationError: If validation fails
    """
    # Check version
    if "version" not in data:
        raise FeaturesValidationError("Missing 'version' field")

    # Check features array
    if "features" not in data:
        raise FeaturesValidationError("Missing 'features' array")

    if not isinstance(data["features"], list):
        raise FeaturesValidationError("'features' must be an array")

    # Validate each feature
    seen_ids = set()
    for i, item in enumerate(data["features"]):
        if not isinstance(item, dict):
            raise FeaturesValidationError(f"Feature at index {i} must be an object")

        # Required fields
        for required in ["id", "description", "skill"]:
            if required not in item:
                raise FeaturesValidationError(
                    f"Feature at index {i} missing required field '{required}'"
                )

        # Check for duplicate IDs
        feature_id = item["id"]
        if feature_id in seen_ids:
            raise FeaturesValidationError(f"Duplicate feature ID: {feature_id}")
        seen_ids.add(feature_id)

        # Validate status if present
        status = item.get("status", "pending")
        if status not in VALID_STATUSES:
            raise FeaturesValidationError(
                f"Feature '{feature_id}' has invalid status '{status}'. "
                f"Valid statuses: {', '.join(VALID_STATUSES)}"
            )

        # Validate type if present
        item_type = item.get("type", "feature")
        if item_type not in VALID_TYPES:
            raise FeaturesValidationError(
                f"Feature '{feature_id}' has invalid type '{item_type}'. "
                f"Valid types: {', '.join(VALID_TYPES)}"
            )

        # Validate resolution if present (null is valid)
        resolution = item.get("resolution")
        if resolution is not None and resolution not in VALID_RESOLUTIONS:
            raise FeaturesValidationError(
                f"Feature '{feature_id}' has invalid resolution '{resolution}'. "
                f"Valid resolutions: null, {', '.join(VALID_RESOLUTIONS)}"
            )


def validate_id(feature_id: str) -> None:
    """
    Validate feature ID format (kebab-case).

    Args:
        feature_id: ID to validate

    Raises:
        FeaturesValidationError: If ID is invalid
    """
    if not feature_id:
        raise FeaturesValidationError("Feature ID cannot be empty")

    # Allow kebab-case with lowercase letters, numbers, and hyphens
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', feature_id):
        raise FeaturesValidationError(
            f"Invalid feature ID '{feature_id}'. "
            "Must be kebab-case (lowercase letters, numbers, hyphens)"
        )


# ============================================================================
# CRUD OPERATIONS
# ============================================================================

def generate_id(description: str) -> str:
    """
    Generate a kebab-case ID from description.

    Args:
        description: Feature description

    Returns:
        Kebab-case ID
    """
    # Convert to lowercase
    text = description.lower()

    # Replace non-alphanumeric with spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)

    # Split into words and take first 5
    words = text.split()[:5]

    # Join with hyphens
    return '-'.join(words) if words else 'unnamed-feature'


def add_feature(
    description: str,
    skill: str = "feature-impl",
    type: str = "feature",
    category: Optional[str] = None,
    skill_args: Optional[Dict[str, Any]] = None,
    verification: Optional[List[str]] = None,
    context_ref: Optional[str] = None,
    investigation: Optional[str] = None,
    resolution: Optional[str] = None,
    related: Optional[List[str]] = None,
    feature_id: Optional[str] = None,
    project_dir: Optional[Path] = None
) -> Feature:
    """
    Add a new feature to backlog.json.

    Creates backlog.json if it doesn't exist.

    Args:
        description: Feature description
        skill: Skill to use (default: feature-impl)
        type: Item type (feature, bug, improvement) - default: feature
        category: Category (feature, bug, infrastructure, etc.)
        skill_args: Arguments to pass to skill
        verification: Custom verification criteria
        context_ref: Reference to additional context
        investigation: Link to investigation document
        resolution: Resolution type (null, fix, workaround)
        related: Array of related item IDs
        feature_id: Custom ID (auto-generated if not provided)
        project_dir: Project directory (defaults to cwd)

    Returns:
        Created Feature object

    Raises:
        DuplicateFeatureError: If feature with same ID exists
    """
    # Generate or validate ID
    if feature_id is None:
        feature_id = generate_id(description)
    else:
        validate_id(feature_id)

    # Load existing features (or empty list)
    features = load_features_safe(project_dir)

    # Check for duplicates
    existing_ids = {f.id for f in features}
    if feature_id in existing_ids:
        raise DuplicateFeatureError(f"Feature with ID '{feature_id}' already exists")

    # Create new feature
    feature = Feature(
        id=feature_id,
        description=description,
        skill=skill,
        status="pending",
        type=type,
        category=category,
        skill_args=skill_args or {},
        verification=verification,
        context_ref=context_ref,
        investigation=investigation,
        resolution=resolution,
        related=related or [],
    )

    # Add and save
    features.append(feature)
    save_features(features, project_dir)

    return feature


def update_feature(
    feature_id: str,
    project_dir: Optional[Path] = None,
    **updates
) -> Feature:
    """
    Update an existing feature.

    Args:
        feature_id: ID of feature to update
        project_dir: Project directory (defaults to cwd)
        **updates: Fields to update (status, workspace, started_at, etc.)

    Returns:
        Updated Feature object

    Raises:
        FeatureNotFoundError: If feature doesn't exist
    """
    features = load_features(project_dir)

    # Find feature
    feature = None
    feature_index = None
    for i, f in enumerate(features):
        if f.id == feature_id:
            feature = f
            feature_index = i
            break

    if feature is None:
        raise FeatureNotFoundError(f"Feature '{feature_id}' not found")

    # Validate status if being updated
    if "status" in updates:
        if updates["status"] not in VALID_STATUSES:
            raise FeaturesValidationError(
                f"Invalid status '{updates['status']}'. "
                f"Valid statuses: {', '.join(VALID_STATUSES)}"
            )

    # Apply updates
    for key, value in updates.items():
        if hasattr(feature, key):
            setattr(feature, key, value)

    # Save
    features[feature_index] = feature
    save_features(features, project_dir)

    return feature


def get_feature(feature_id: str, project_dir: Optional[Path] = None) -> Feature:
    """
    Get a specific feature by ID.

    Args:
        feature_id: Feature ID
        project_dir: Project directory (defaults to cwd)

    Returns:
        Feature object

    Raises:
        FeatureNotFoundError: If feature doesn't exist
    """
    features = load_features(project_dir)

    for feature in features:
        if feature.id == feature_id:
            return feature

    raise FeatureNotFoundError(f"Feature '{feature_id}' not found")


def list_features(
    project_dir: Optional[Path] = None,
    status: Optional[str] = None,
    category: Optional[str] = None
) -> List[Feature]:
    """
    List features with optional filtering.

    Args:
        project_dir: Project directory (defaults to cwd)
        status: Filter by status (pending, in_progress, complete, blocked)
        category: Filter by category (feature, bug, infrastructure, etc.)

    Returns:
        List of Feature objects matching filters
    """
    features = load_features_safe(project_dir)

    # Apply filters
    if status:
        features = [f for f in features if f.status == status]

    if category:
        features = [f for f in features if f.category == category]

    return features


def start_feature(
    feature_id: str,
    workspace_path: str,
    project_dir: Optional[Path] = None
) -> Feature:
    """
    Mark a feature as in_progress with workspace and timestamp.

    Args:
        feature_id: Feature ID
        workspace_path: Path to workspace directory
        project_dir: Project directory (defaults to cwd)

    Returns:
        Updated Feature object
    """
    return update_feature(
        feature_id,
        project_dir=project_dir,
        status="in_progress",
        workspace=workspace_path,
        started_at=datetime.now().isoformat(),
    )


def complete_feature(
    feature_id: str,
    project_dir: Optional[Path] = None
) -> Feature:
    """
    Mark a feature as complete with timestamp.

    Args:
        feature_id: Feature ID
        project_dir: Project directory (defaults to cwd)

    Returns:
        Updated Feature object
    """
    return update_feature(
        feature_id,
        project_dir=project_dir,
        status="complete",
        completed_at=datetime.now().isoformat(),
    )


def block_feature(
    feature_id: str,
    project_dir: Optional[Path] = None
) -> Feature:
    """
    Mark a feature as blocked.

    Args:
        feature_id: Feature ID
        project_dir: Project directory (defaults to cwd)

    Returns:
        Updated Feature object
    """
    return update_feature(
        feature_id,
        project_dir=project_dir,
        status="blocked",
    )


# ============================================================================
# CONTEXT REF OPERATIONS
# ============================================================================

def get_features_by_context_ref(
    context_ref: str,
    project_dir: Optional[Path] = None
) -> List[Feature]:
    """
    Get all features that have a specific context_ref.

    Args:
        context_ref: The context_ref value to search for
        project_dir: Project directory (defaults to cwd)

    Returns:
        List of Feature objects with matching context_ref
    """
    features = load_features_safe(project_dir)
    return [f for f in features if f.context_ref == context_ref]


def all_features_complete_for_context_ref(
    context_ref: str,
    project_dir: Optional[Path] = None
) -> bool:
    """
    Check if all features with a given context_ref are complete.

    Args:
        context_ref: The context_ref value to check
        project_dir: Project directory (defaults to cwd)

    Returns:
        True if all features with this context_ref have status='complete'
    """
    features = get_features_by_context_ref(context_ref, project_dir)
    if not features:
        return False
    return all(f.status == "complete" for f in features)
