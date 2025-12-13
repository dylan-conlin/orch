"""
Skill discovery functionality for orch tool.

Handles discovering and parsing skill metadata from the hierarchical
skill directory structure:
  ~/.claude/skills/{category}/{skill}/SKILL.md

Example:
  ~/.claude/skills/worker/investigation/SKILL.md
  ~/.claude/skills/orchestrator/spawn-worker-agent/SKILL.md
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import yaml
import re
import functools
import os

logger = logging.getLogger(__name__)


# Data Classes
@dataclass
class SkillDeliverable:
    """Represents a deliverable defined by a skill."""
    type: str  # 'investigation', 'workspace', 'commit', etc.
    path: str  # Template path with {date}, {slug}, {workspace-name}
    required: bool = True
    description: str = ""


@dataclass
class SkillVerification:
    """Verification requirements for a skill."""
    requirements: str  # Markdown checklist of verification items
    required: bool = True  # Whether verification is required
    test_command: Optional[str] = None  # Optional test command to run
    timeout: int = 300  # Timeout for test execution (seconds)


@dataclass
class SkillMetadata:
    """Metadata parsed from skill SKILL.md frontmatter."""
    name: str
    triggers: List[str]
    deliverables: List['SkillDeliverable']
    verification: Optional[SkillVerification] = None  # Phase 3: Verification requirements
    category: Optional[str] = None  # Category (audience): worker, orchestrator, shared, meta, utilities
    description: Optional[str] = None  # Short description of skill purpose
    allowed_tools: Optional[List[str]] = None  # Tools the skill is allowed to use
    disallowed_tools: Optional[List[str]] = None  # Tools the skill should NOT use
    default_model: Optional[str] = None  # Default model for spawning (haiku, sonnet, opus)
    review: Optional[str] = None  # Review gate: 'required', 'optional', or 'none'


# Constants
DEFAULT_DELIVERABLES = [
    SkillDeliverable(
        type="workspace",
        path="",  # No file path - workspace tracking via beads comments
        required=True,
        description="Progress tracked via beads comments (bd comment <beads-id>)"
    )
]


# Skill Discovery
@functools.lru_cache(maxsize=1)
def _discover_skills_cached(skills_dir_mtime: float) -> Dict[str, SkillMetadata]:
    """
    Cached implementation of skill discovery.

    Scans hierarchical skill structure:
    - ~/.claude/skills/worker/*/SKILL.md
    - ~/.claude/skills/shared/*/SKILL.md
    - ~/.claude/skills/orchestrator/*/SKILL.md
    - etc.

    Args:
        skills_dir_mtime: Modification time of skills directory (for cache invalidation)

    Returns:
        Dictionary mapping skill directory name to SkillMetadata
    """
    skills = {}
    skills_dir = Path.home() / ".claude" / "skills"

    if not skills_dir.exists():
        logger.warning(f"Skills directory not found: {skills_dir}")
        return skills

    # Scan hierarchical structure: category/skill/SKILL.md
    for category_dir in skills_dir.iterdir():
        if not category_dir.is_dir():
            continue

        # Skip hidden directories and symlinks
        if category_dir.name.startswith('.'):
            continue

        # Scan for skills within this category
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                content = skill_file.read_text()
                metadata = parse_skill_metadata(content, skill_dir.name)
                # Use frontmatter category if present (skill-type), else directory category (audience)
                if not metadata.category:
                    metadata.category = category_dir.name
                skills[skill_dir.name] = metadata
            except Exception as e:
                logger.warning(f"Failed to parse {skill_file}: {e}")
                # Graceful degradation - use defaults
                skills[skill_dir.name] = SkillMetadata(
                    name=skill_dir.name,
                    triggers=[],
                    deliverables=DEFAULT_DELIVERABLES,
                    category=category_dir.name
                )

    return skills


def discover_skills() -> Dict[str, SkillMetadata]:
    """
    Discover skills from hierarchical structure with caching.

    Scans ~/.claude/skills/{category}/{skill}/SKILL.md
    (e.g., ~/.claude/skills/worker/investigation/SKILL.md)

    Cache is invalidated when the skills directory mtime changes (new/modified skills).

    Returns:
        Dictionary mapping skill directory name to SkillMetadata
    """
    skills_dir = Path.home() / ".claude" / "skills"

    # Get mtime for cache invalidation (0 if directory doesn't exist)
    try:
        mtime = os.path.getmtime(skills_dir)
    except (OSError, FileNotFoundError):
        mtime = 0

    return _discover_skills_cached(mtime)


def parse_skill_metadata(content: str, skill_dir_name: str) -> SkillMetadata:
    """
    Parse YAML frontmatter from skill SKILL.md file.

    Args:
        content: Full content of SKILL.md file
        skill_dir_name: Directory name (fallback for skill name)

    Returns:
        SkillMetadata object
    """
    # Extract YAML frontmatter (between --- markers)
    yaml_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)

    if not yaml_match:
        # No frontmatter - use defaults
        return SkillMetadata(
            name=skill_dir_name,
            triggers=[],
            deliverables=DEFAULT_DELIVERABLES
        )

    try:
        frontmatter = yaml.safe_load(yaml_match.group(1))
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {skill_dir_name}: {e}")
        return SkillMetadata(
            name=skill_dir_name,
            triggers=[],
            deliverables=DEFAULT_DELIVERABLES
        )

    # Parse deliverables (supports both list and dict formats)
    deliverables = DEFAULT_DELIVERABLES
    if 'deliverables' in frontmatter:
        deliverables = []
        d_config = frontmatter['deliverables']

        if isinstance(d_config, list):
            # List format: [{type: workspace, path: ..., required: true}, ...]
            for d in d_config:
                deliverables.append(SkillDeliverable(
                    type=d.get('type', 'unknown'),
                    path=d.get('path', ''),
                    required=d.get('required', True),
                    description=d.get('description', '')
                ))
        elif isinstance(d_config, dict):
            # Dict format: {workspace: {required: true, description: ...}, ...}
            for deliverable_type, config in d_config.items():
                if isinstance(config, dict):
                    deliverables.append(SkillDeliverable(
                        type=deliverable_type,
                        path=config.get('path', ''),
                        required=config.get('required', True),
                        description=config.get('description', '')
                    ))
                else:
                    # Fallback for simple format
                    deliverables.append(SkillDeliverable(
                        type=deliverable_type,
                        path='',
                        required=True,
                        description=str(config) if config else ''
                    ))

    # Phase 3: Parse verification requirements
    verification = None
    if 'verification' in frontmatter:
        v = frontmatter['verification']
        if isinstance(v, dict) and 'requirements' in v:
            # Handle both string and list formats for requirements
            reqs = v['requirements']
            if isinstance(reqs, list):
                # Convert list to markdown checklist string
                reqs = '\n'.join(f"- [ ] {req}" for req in reqs)
            verification = SkillVerification(
                requirements=reqs,
                required=v.get('required', True),
                test_command=v.get('test_command'),
                timeout=v.get('timeout', 300)
            )

    return SkillMetadata(
        name=frontmatter.get('skill', frontmatter.get('name', skill_dir_name)),
        triggers=frontmatter.get('triggers', []),
        deliverables=deliverables,
        verification=verification,
        category=frontmatter.get('category'),  # Read skill-type category from frontmatter
        description=frontmatter.get('description'),  # Short description of skill purpose
        allowed_tools=frontmatter.get('allowed_tools'),  # Tool whitelist
        disallowed_tools=frontmatter.get('disallowed_tools'),  # Tool blacklist
        default_model=frontmatter.get('default_model'),  # Default model for spawning
        review=frontmatter.get('review')  # Review gate: 'required', 'optional', or 'none'
    )
