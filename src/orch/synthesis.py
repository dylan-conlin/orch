"""Synthesis promotion workflow - close the synthesis→action loop."""

from pathlib import Path
from typing import Optional, Tuple
import re
from datetime import datetime


def parse_synthesis_file(synthesis_path: Path) -> dict:
    """Parse synthesis file to extract metadata and recommendation.

    Returns:
        dict with keys: status, decision, recommendation, source_investigations, title
    """
    if not synthesis_path.exists():
        raise FileNotFoundError(f"Synthesis file not found: {synthesis_path}")

    content = synthesis_path.read_text()

    # Extract metadata from frontmatter
    status_match = re.search(r'\*\*Status:\*\*\s+(\w+)', content)
    status = status_match.group(1) if status_match else None

    decision_match = re.search(r'\*\*Decision:\*\*\s+`([^`]+)`', content)
    decision = decision_match.group(1) if decision_match else None

    # Extract title
    title_match = re.search(r'^#\s+Pattern Synthesis:\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else synthesis_path.stem

    # Extract recommendation section
    recommendation_match = re.search(
        r'### Recommendation\s+(.+?)(?=^##|\Z)',
        content,
        re.MULTILINE | re.DOTALL
    )
    recommendation = recommendation_match.group(1).strip() if recommendation_match else None

    # Extract source investigations from Pattern section
    source_pattern = r'investigations/[^)]+\.md'
    source_investigations = list(set(re.findall(source_pattern, content)))  # Deduplicate

    return {
        'status': status,
        'decision': decision,
        'title': title,
        'recommendation': recommendation,
        'source_investigations': source_investigations,
        'content': content
    }


def create_decision_document(synthesis_data: dict, synthesis_path: Path, project_dir: Path) -> Tuple[Path, str]:
    """Auto-generate decision document from synthesis.

    Returns:
        Tuple of (decision_path, decision_content)
    """
    # Generate decision filename from synthesis
    date = datetime.now().strftime("%Y-%m-%d")
    synthesis_name = synthesis_path.stem
    # Extract topic from synthesis filename (remove date prefix)
    topic = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', synthesis_name)
    decision_name = f"{date}-{topic}"

    decision_path = project_dir / ".orch" / "decisions" / f"{decision_name}.md"

    # Extract key information from synthesis
    title = synthesis_data['title']
    recommendation = synthesis_data['recommendation'] or "[Extract from synthesis]"
    source_investigations = synthesis_data['source_investigations']

    # Generate decision document
    decision_content = f"""# Decision: {title}

**Date:** {date}
**Status:** Accepted
**Context:** Synthesis of recurring pattern
**Synthesis:** `.orch/synthesis/{synthesis_path.name}`

---

## Decision

[Auto-generated from synthesis - review and edit as needed]

{recommendation}

---

## Context

### The Problem

Multiple investigations revealed a recurring pattern. Synthesis applied frame-breaking analysis to identify the root cause.

**Source investigations:**
{chr(10).join(f"- {inv}" for inv in source_investigations)}

### Synthesis Verdict

See synthesis document for complete frame-breaking analysis:
`.orch/synthesis/{synthesis_path.name}`

---

## Implementation

[Extract implementation steps from synthesis recommendation section]

1. [Step 1]
2. [Step 2]
3. [Step 3]
4. Validation: [Test criteria]

---

## Alternatives Considered

[Extract from synthesis Taxonomy Survey section]

---

## Rationale

[Extract from synthesis "Why this solves the pattern" section]

---

## Consequences

### Positive

- [Benefit 1]
- [Benefit 2]

### Negative

- [Risk 1 - mitigation]

### Neutral

- [Observation 1]

---

## Validation Plan

**Success metrics:**
1. [Metric 1]
2. [Metric 2]

**Failure triggers:**
- [Condition 1] → [Action]
- [Condition 2] → [Action]

**Timeline:** [Estimate]

---

## Related Artifacts

**Synthesis:** `.orch/synthesis/{synthesis_path.name}`

**Investigations (Superseded):**
{chr(10).join(f"- {inv}" for inv in source_investigations)}

**Implementation:** TBD - ROADMAP item created

---

## Notes

[Add key insights from synthesis Meta-Learning section]
"""

    return decision_path, decision_content


def create_roadmap_item(synthesis_data: dict, decision_path: Path) -> str:
    """Generate ROADMAP item text from synthesis.

    Returns:
        Formatted ROADMAP item ready to insert
    """
    title = synthesis_data['title']
    date = datetime.now().strftime("%Y-%m-%d")

    roadmap_item = f"""** TODO [P1] {title} :phase-4::synthesis:
:PROPERTIES:
:Created: {date}
:Project: orch-knowledge
:Synthesis: .orch/synthesis/[FILENAME]
:Decision: {decision_path}
:Priority: 1
:Estimated-effort: [ESTIMATE]
:Type: synthesis implementation
:END:

**Problem:** [Extract from synthesis]
**Root Cause:** Frame problem identified via synthesis
**Solution:** [Extract from synthesis recommendation]
**Implementation:**
1. [Step 1]
2. [Step 2]
3. [Step 3]
**Success criteria:**
- [Criteria from synthesis]
**Superseded investigations:**
{chr(10).join(f"- {inv}" for inv in synthesis_data.get('source_investigations', []))}
**Meta-learning:** [Extract from synthesis]

"""
    return roadmap_item


def mark_investigations_superseded(investigation_paths: list[str], synthesis_path: Path, project_dir: Path) -> list[Path]:
    """Update investigation files to mark them as superseded.

    Returns:
        List of paths that were updated
    """
    updated_files = []

    for inv_path_str in investigation_paths:
        # Convert relative path to absolute
        inv_path = project_dir / ".orch" / inv_path_str

        if not inv_path.exists():
            print(f"⚠️  Investigation not found: {inv_path}")
            continue

        content = inv_path.read_text()

        # Check if already superseded
        if 'Status: Superseded' in content or 'Status:** Superseded' in content:
            print(f"  ℹ️  Already superseded: {inv_path.name}")
            continue

        # Find Status field and update it
        # Pattern 1: **Status:** Complete
        pattern1 = r'(\*\*Status:\*\*\s+)(Complete|In-Progress|Blocked)'
        replacement1 = r'\1Superseded\n**Superseded-By:** `.orch/synthesis/' + synthesis_path.name + '`\n**Confidence:** [ORIGINAL] (at time of writing) - See synthesis for complete analysis'

        # Pattern 2: **Status:** In Progress
        pattern2 = r'(\*\*Status:\*\*\s+)(In Progress)'
        replacement2 = r'\1Superseded\n**Superseded-By:** `.orch/synthesis/' + synthesis_path.name + '`'

        new_content = re.sub(pattern1, replacement1, content)
        if new_content == content:
            new_content = re.sub(pattern2, replacement2, content)

        if new_content != content:
            inv_path.write_text(new_content)
            updated_files.append(inv_path)
            print(f"  ✅ Superseded: {inv_path.name}")
        else:
            print(f"  ⚠️  Could not update Status field: {inv_path.name}")

    return updated_files


def update_synthesis_status(synthesis_path: Path, status: str, decision_path: Optional[Path] = None) -> None:
    """Update synthesis file status and decision link.

    Args:
        synthesis_path: Path to synthesis file
        status: New status (Accepted, Rejected, Deferred)
        decision_path: Path to decision document (for Accepted status)
    """
    content = synthesis_path.read_text()
    date = datetime.now().strftime("%Y-%m-%d")

    # Update Status field
    content = re.sub(
        r'\*\*Status:\*\*\s+\w+',
        f'**Status:** {status}',
        content
    )

    # Add/update Decision field if provided
    if decision_path:
        decision_line = f'**Decision:** `.kb/decisions/{decision_path.name}`'
        if '**Decision:**' in content:
            content = re.sub(
                r'\*\*Decision:\*\*[^\n]+',
                decision_line,
                content
            )
        else:
            # Add after Status line
            content = re.sub(
                r'(\*\*Status:\*\*[^\n]+)',
                f'\\1\n{decision_line}',
                content
            )

    # Add Accepted date
    if status == 'Accepted':
        accepted_line = f'**Accepted:** {date}'
        if '**Accepted:**' not in content:
            content = re.sub(
                r'(\*\*Decision:\*\*[^\n]+)',
                f'\\1\n{accepted_line}',
                content
            )

    synthesis_path.write_text(content)


def update_synthesis_resolution_status(synthesis_path: Path) -> None:
    """Update Resolution Status section checkboxes in synthesis file."""
    content = synthesis_path.read_text()
    date = datetime.now().strftime("%Y-%m-%d")

    # Update checkboxes in Resolution Status section
    updates = [
        (r'- \[ \] Recommendation accepted', f'- [x] Recommendation accepted ({date})'),
        (r'- \[ \] Decision document created', f'- [x] Decision document created (`.kb/decisions/...`)'),
        (r'- \[ \] ROADMAP item created', f'- [x] ROADMAP item created (See ROADMAP.org)'),
    ]

    for pattern, replacement in updates:
        content = re.sub(pattern, replacement, content)

    synthesis_path.write_text(content)
