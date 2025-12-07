**TLDR:** Question: How to store agent metadata as JSON in notes field for real-time UI updates? Answer: Implemented 5 new methods (update_agent_notes, get_agent_notes, get_phase_from_notes, get_investigation_path_from_notes, update_phase) that read/write JSON to the notes field with automatic field merging and timestamp updates. High confidence (95%) - all 77 beads-related tests pass.

---

# Investigation: Notes-Based Agent Metadata Storage

**Question:** How should we migrate agent metadata from comments to notes field for real-time UI updates?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Dylan
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Current comment-based storage is inefficient for UI updates

**Evidence:** Agent metadata (phase, skill, agent_id, investigation_path) is stored across multiple comments that require parsing regex patterns to extract.

**Source:**
- `src/orch/beads_integration.py:197-245` - get_phase_from_comments
- `src/orch/beads_integration.py:261-309` - get_investigation_path_from_comments
- `src/orch/beads_integration.py:334-422` - add_agent_metadata, get_agent_metadata

**Significance:** Comments require iterating through all comments and regex parsing. Notes field is a direct issue field that can trigger WebSocket updates immediately.

---

### Finding 2: Notes field already used for workspace link

**Evidence:** `add_workspace_link()` writes plain text "workspace: {path}" to notes.

**Source:** `src/orch/beads_integration.py:134-146`

**Significance:** The new implementation must handle backward compatibility with existing plain-text notes.

---

### Finding 3: Multiple callers depend on comment-based methods

**Evidence:** The following files call comment-based methods:
- `spawn.py:1726` - add_agent_metadata
- `complete.py:888,1231` - get_investigation_path_from_comments, get_phase_from_comments
- `monitoring_commands.py:491` - get_phase_from_comments
- `cli.py:398` - get_phase_from_comments
- `monitor.py:135` - get_phase_from_comments

**Source:** Grep search across codebase

**Significance:** Existing comment-based methods should remain for backward compatibility. New notes-based methods provide an alternative for real-time UI needs.

---

## Implementation

Added 5 new methods to `BeadsIntegration`:

1. **`get_agent_notes(issue_id)`** - Reads JSON metadata from notes field
2. **`update_agent_notes(issue_id, **kwargs)`** - Writes/merges JSON to notes field
3. **`get_phase_from_notes(issue_id)`** - Extracts phase from notes
4. **`get_investigation_path_from_notes(issue_id)`** - Extracts investigation_path
5. **`update_phase(issue_id, phase)`** - Convenience method for phase updates

### Key Features

- **Automatic merging**: `update_agent_notes()` preserves existing fields when updating
- **Timestamp tracking**: `updated_at` field automatically updated on each write
- **Backward compatibility**: Returns None for non-JSON notes (legacy format)
- **Cross-repo support**: Respects `db_path` for cross-repository operations

### JSON Schema

```json
{
  "agent_id": "feat-test-06dec",
  "window_id": "@123",
  "phase": "Implementing",
  "skill": "feature-impl",
  "project_dir": "/path/to/project",
  "investigation_path": "/path/to/investigation.md",
  "updated_at": "2025-12-06T23:45:00Z"
}
```

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?** All 77 beads-related tests pass, including 11 new tests specifically for notes-based storage. Implementation follows existing patterns and uses well-tested underlying methods.

**What's certain:**
- ✅ Notes-based methods work correctly (11 tests pass)
- ✅ Backward compatibility preserved (existing 46 tests still pass)
- ✅ Field merging works correctly
- ✅ Cross-repo db_path support works

**What's uncertain:**
- ⚠️ Callers need to be updated to use new methods (future work)
- ⚠️ WebSocket integration not tested (requires beads-ui)

---

## References

**Files Modified:**
- `src/orch/beads_integration.py` - Added 5 new methods (+138 lines)
- `tests/test_beads_integration.py` - Added TestBeadsIntegrationNotesMetadata class (+337 lines)

**Commands Run:**
```bash
# TDD cycle
python -m pytest tests/test_beads_integration.py::TestBeadsIntegrationNotesMetadata -v

# Regression testing
python -m pytest tests/test_beads_integration.py tests/e2e/test_beads_workflow.py -v
```

---

## Investigation History

**2025-12-06 23:25:** Investigation started
- Initial question: How to store agent metadata in notes field for real-time UI updates

**2025-12-06 23:35:** Analysis complete
- Identified current comment-based architecture
- Found callers and dependencies

**2025-12-06 23:50:** Implementation complete
- TDD approach: wrote 11 failing tests, then implemented methods
- All 77 beads-related tests pass
- Status: Complete
