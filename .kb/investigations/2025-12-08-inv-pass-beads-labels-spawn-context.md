# Investigation: Pass Beads Labels to SPAWN_CONTEXT

**Status:** Complete
**Created:** 2025-12-08
**Issue:** orch-cli-8yz

## Summary

Added labels field to BeadsIssue dataclass and included labels in SPAWN_CONTEXT metadata section when using `--issue` flag. This enables cross-repo routing (e.g., 'target:orch-cli' label signals work belongs in different repo) and categorization for spawned agents.

## Changes Made

### 1. BeadsIssue dataclass (`src/orch/beads_integration.py`)

Added `labels` field to the dataclass:
```python
@dataclass
class BeadsIssue:
    # ... existing fields ...
    labels: Optional[list] = None  # List of label strings (e.g., ["P1", "target:orch-cli"])
```

### 2. get_issue() method (`src/orch/beads_integration.py`)

Added labels parsing from `bd show` JSON output:
```python
# Parse labels if present
labels = issue_data.get("labels")  # None if key missing, [] if empty array

return BeadsIssue(
    # ... existing fields ...
    labels=labels,
)
```

### 3. Spawn commands (`src/orch/spawn_commands.py`)

Added labels to issue context when spawning with `--issue` flag:
```python
# Build beads issue context (added to full prompt, not replacing it)
issue_context = f"BEADS ISSUE: {issue_id}\n"
if issue.description:
    issue_context += f"\nIssue Description:\n{issue.description}\n"
if issue.labels:
    labels_str = ", ".join(issue.labels)
    issue_context += f"\nLabels: {labels_str}\n"
if issue.notes:
    issue_context += f"\nNotes:\n{issue.notes}\n"
```

## Test Coverage

All tests pass (16/16):

### BeadsIssue dataclass tests:
- `test_beads_issue_creation` - Verifies labels defaults to None
- `test_beads_issue_with_labels` - Verifies labels can be set
- `test_beads_issue_labels_defaults_to_none` - Verifies default behavior

### get_issue() parsing tests:
- `test_get_issue_parses_labels` - Labels parsed from JSON
- `test_get_issue_labels_empty_array` - Empty array preserved
- `test_get_issue_labels_not_in_json` - Backwards compatibility (None when missing)

### Spawn context tests:
- `test_labels_included_in_additional_context` - Labels included in spawn context
- `test_no_labels_section_when_labels_empty` - No Labels section when None
- `test_no_labels_section_when_labels_empty_list` - No Labels section when empty list

## Example Usage

When spawning from a beads issue with labels:
```bash
orch spawn --issue orch-cli-8yz
```

The SPAWN_CONTEXT will include:
```
BEADS ISSUE: orch-cli-8yz

Issue Description:
Add labels field to BeadsIssue dataclass...

Labels: P2, beads-integration, target:orch-cli
```

## Backwards Compatibility

- Issues without labels field in JSON will have `labels=None` (existing behavior)
- No changes to bd CLI required (just reads existing `labels` field from JSON output)
