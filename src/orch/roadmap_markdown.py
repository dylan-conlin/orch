"""
ROADMAP.md parsing and management.

This module provides Markdown-based ROADMAP parsing to replace org-mode format.
Uses the same RoadmapItem dataclass as roadmap.py for compatibility.

Key features:
- Parse GitHub Flavored Markdown structure
- Extract priority from [P0], [P1], [P2] in headings
- Parse inline metadata (- Key: Value format)
- Extract backtick-wrapped tags
- Support fuzzy title matching
- Mark items done and move to Completed Work section

Design: .orch/workspace/2025-11-19-brainstorm-redesign-roadmap-structure-workflow-serve/design.md
Decision: .orch/decisions/2025-11-19-roadmap-format-markdown-for-open-source.md
Investigation: .orch/investigations/2025-11-19-roadmap-markdown-structure-and-parser-design.md
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import RoadmapItem from roadmap module (shared dataclass)
from orch.roadmap import RoadmapItem


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_roadmap_markdown(filepath: Path) -> List[RoadmapItem]:
    """
    Parse ROADMAP.md file and extract items.

    Expected structure:
    ```markdown
    ## Active Work

    ### [P0] Task title

    **Tags:** `tag1` `tag2` `tag3`

    **Metadata:**
    - Key1: value1
    - Key2: value2

    **Description:**

    Multi-line description content...

    ---

    ## Completed Work

    ### ✅ [P1] Completed task

    **Completed:** 2025-11-19

    **Tags:** `tag1`

    **Metadata:**
    - Key: value

    **Description:**

    Description...

    ---
    ```

    Args:
        filepath: Path to ROADMAP.md file

    Returns:
        List of RoadmapItem objects

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file structure is malformed
    """
    if not filepath.exists():
        return []

    content = filepath.read_text(encoding='utf-8')

    items = []
    current_item = None
    current_section = None  # Track "Active Work" vs "Completed Work"
    current_metadata = {}
    current_tags = []
    current_description_lines = []
    in_description = False

    # Regular expressions for parsing
    SECTION_RE = re.compile(r'^## (.+)$')
    ITEM_HEADING_RE = re.compile(r'^### (✅ )?\[P([0-2])\] (.+)$')
    TAGS_RE = re.compile(r'^\*\*Tags:\*\* (.+)$')
    TAG_EXTRACT_RE = re.compile(r'`([^`]+)`')
    METADATA_HEADER_RE = re.compile(r'^\*\*Metadata:\*\*$')
    METADATA_ITEM_RE = re.compile(r'^- ([^:]+): (.+)$')
    COMPLETED_RE = re.compile(r'^\*\*Completed:\*\* (.+)$')
    DESCRIPTION_HEADER_RE = re.compile(r'^\*\*Description:\*\*$')
    SEPARATOR_RE = re.compile(r'^---+$')

    lines = content.split('\n')
    for line_num, line in enumerate(lines, start=1):
        # Section header (## Active Work, ## Completed Work)
        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        # Item heading (### [P0] Title or ### ✅ [P0] Title)
        item_match = ITEM_HEADING_RE.match(line)
        if item_match:
            # Save previous item if exists
            if current_item:
                current_item.properties = current_metadata
                current_item.tags = current_tags
                current_item.description = '\n'.join(current_description_lines).strip()
                items.append(current_item)

            # Parse new item
            is_done_marker = item_match.group(1) is not None  # ✅ prefix
            priority = int(item_match.group(2))  # 0, 1, or 2
            title = item_match.group(3).strip()

            # Determine done status (from section or marker)
            is_done = is_done_marker or (current_section == "Completed Work")

            current_item = RoadmapItem(
                title=title,
                priority=priority,
                is_done=is_done
            )
            current_metadata = {}
            current_tags = []
            current_description_lines = []
            in_description = False
            continue

        # Skip if we haven't started an item yet
        if not current_item:
            continue

        # Separator (---) marks end of item
        if SEPARATOR_RE.match(line):
            # Save current item
            current_item.properties = current_metadata
            current_item.tags = current_tags
            current_item.description = '\n'.join(current_description_lines).strip()
            items.append(current_item)
            current_item = None
            continue

        # Completed date (**Completed:** YYYY-MM-DD)
        completed_match = COMPLETED_RE.match(line)
        if completed_match:
            current_item.closed_date = completed_match.group(1).strip()
            continue

        # Tags line (**Tags:** `tag1` `tag2`)
        tags_match = TAGS_RE.match(line)
        if tags_match:
            tags_content = tags_match.group(1)
            # Extract all backtick-wrapped tags
            current_tags = TAG_EXTRACT_RE.findall(tags_content)
            continue

        # Metadata header (**Metadata:**)
        if METADATA_HEADER_RE.match(line):
            # Just a header, actual items follow
            continue

        # Metadata item (- Key: Value)
        metadata_match = METADATA_ITEM_RE.match(line)
        if metadata_match and not in_description:
            key = metadata_match.group(1).strip()
            value = metadata_match.group(2).strip()
            current_metadata[key] = value
            continue

        # Description header (**Description:**)
        if DESCRIPTION_HEADER_RE.match(line):
            in_description = True
            continue

        # Description content (everything after **Description:** until separator)
        if in_description and line.strip():
            current_description_lines.append(line.rstrip())

    # Save last item if exists (file might not end with separator)
    if current_item:
        current_item.properties = current_metadata
        current_item.tags = current_tags
        current_item.description = '\n'.join(current_description_lines).strip()
        items.append(current_item)

    return items


def find_roadmap_item(
    title_query: str,
    roadmap_path: Optional[Path] = None
) -> Optional[RoadmapItem]:
    """
    Find ROADMAP item by title (fuzzy match, case-insensitive).

    Compatible with org-mode version - same interface.

    Args:
        title_query: Title to search for (case-insensitive substring match)
        roadmap_path: Optional path to ROADMAP.md (defaults to standard location)

    Returns:
        Matching RoadmapItem or None
    """
    if not roadmap_path:
        # Try default paths in order
        from orch.config import get_roadmap_paths
        for candidate in get_roadmap_paths():
            # Check for ROADMAP.md (Markdown) first, then ROADMAP.org (org-mode)
            md_path = candidate.parent / "ROADMAP.md"
            if md_path.exists():
                roadmap_path = md_path
                break
            if candidate.exists():
                roadmap_path = candidate
                break

        if not roadmap_path:
            return None

    items = parse_roadmap_markdown(roadmap_path)

    # Case-insensitive substring match (same as org-mode version)
    query_lower = title_query.lower()
    for item in items:
        if query_lower in item.title.lower():
            return item

    return None


def find_roadmap_item_for_workspace(
    workspace_name: str,
    roadmap_path: Path
) -> Optional[RoadmapItem]:
    """
    Find ROADMAP item that matches workspace name.

    Compatible with org-mode version - same interface.

    Args:
        workspace_name: Workspace name to search for
        roadmap_path: Path to ROADMAP.md file

    Returns:
        RoadmapItem if found, None otherwise
    """
    if not roadmap_path.exists():
        return None

    items = parse_roadmap_markdown(roadmap_path)

    # Find item with matching workspace property
    for item in items:
        if item.properties.get('Workspace') == workspace_name:
            return item

    return None


# ============================================================================
# UPDATE FUNCTIONS
# ============================================================================

def mark_roadmap_item_done(
    roadmap_path: Path,
    task_title: Optional[str] = None,
    workspace_name: Optional[str] = None,
    create_backup: bool = False
) -> bool:
    """
    Mark ROADMAP item as done and move to Completed Work section.

    Compatible with org-mode version - same interface.

    Implementation:
    1. Find item in Active Work section
    2. Add ✅ prefix to heading
    3. Add **Completed:** timestamp
    4. Move entire item block to Completed Work section

    Args:
        roadmap_path: Path to ROADMAP.md file
        task_title: Optional task title to find and mark done
        workspace_name: Optional workspace name to find and mark done
        create_backup: If True, create .md.backup file before modifying

    Returns:
        True if item was found and marked done, False otherwise

    Raises:
        ValueError: If neither task_title nor workspace_name provided
        FileNotFoundError: If file doesn't exist
    """
    if not task_title and not workspace_name:
        raise ValueError("Must provide either task_title or workspace_name")

    if not roadmap_path.exists():
        raise FileNotFoundError(f"ROADMAP file not found: {roadmap_path}")

    # Create backup if requested
    if create_backup:
        backup_path = roadmap_path.with_suffix(".md.backup")
        backup_path.write_text(roadmap_path.read_text())

    # Parse current items to find target
    items = parse_roadmap_markdown(roadmap_path)
    target_item = None

    for item in items:
        # Match by workspace name or title substring
        if workspace_name and item.properties.get('Workspace') == workspace_name:
            target_item = item
            break
        elif task_title and task_title.lower() in item.title.lower():
            target_item = item
            break

    if not target_item:
        return False

    # Read file content
    content = roadmap_path.read_text()
    lines = content.split('\n')

    # Find and modify the item in-place
    new_lines = []
    found = False
    in_target_item = False
    item_lines = []

    ITEM_HEADING_RE = re.compile(r'^### (✅ )?\[P([0-2])\] (.+)$')
    SEPARATOR_RE = re.compile(r'^---+$')

    for line in lines:
        # Check for item heading
        item_match = ITEM_HEADING_RE.match(line)
        if item_match:
            # If we were in target item, save those lines
            if in_target_item:
                # Don't write item_lines yet - we'll move them later
                in_target_item = False

            # Check if this is our target item
            title = item_match.group(3).strip()
            if title == target_item.title:
                # Found target - start collecting lines
                in_target_item = True
                found = True

                # Modify heading to add ✅ and preserve priority
                priority = target_item.priority if target_item.priority is not None else 1
                modified_heading = f"### ✅ [P{priority}] {title}"
                item_lines = [modified_heading]

                # Add completed timestamp as next line
                today = datetime.now().strftime("%Y-%m-%d")
                item_lines.append(f"\n**Completed:** {today}\n")
                continue

        # Collect lines for target item
        if in_target_item:
            # Stop at separator
            if SEPARATOR_RE.match(line):
                item_lines.append(line)
                in_target_item = False
                # Don't add to new_lines yet - we'll insert in Completed Work
                continue
            item_lines.append(line)
            continue

        # For non-target lines, add normally
        new_lines.append(line)

    if not found:
        return False

    # Insert completed item into Completed Work section
    # Find "## Completed Work" section
    completed_section_index = None
    for i, line in enumerate(new_lines):
        if line.strip() == "## Completed Work":
            completed_section_index = i
            break

    if completed_section_index is None:
        # No Completed Work section - add it before Phase Reference
        phase_ref_index = None
        for i, line in enumerate(new_lines):
            if line.strip() == "## Phase Reference":
                phase_ref_index = i
                break

        if phase_ref_index is None:
            # No Phase Reference either - add at end
            new_lines.append("\n## Completed Work\n")
            new_lines.extend(item_lines)
        else:
            # Insert before Phase Reference
            new_lines.insert(phase_ref_index, "\n## Completed Work\n")
            new_lines.insert(phase_ref_index + 1, "")
            for j, item_line in enumerate(item_lines):
                new_lines.insert(phase_ref_index + 2 + j, item_line)
            new_lines.insert(phase_ref_index + 2 + len(item_lines), "")
    else:
        # Insert after "## Completed Work" heading (index + 1 for blank line, + 2 for first item)
        insert_index = completed_section_index + 2
        for j, item_line in enumerate(item_lines):
            new_lines.insert(insert_index + j, item_line)
        new_lines.insert(insert_index + len(item_lines), "")

    # Write updated content
    roadmap_path.write_text('\n'.join(new_lines))

    return True
