# Decision: Eliminate WORKSPACE.md from orch-cli

**Status:** Accepted
**Date:** 2025-12-06
**Author:** Agent

## Context

WORKSPACE.md was originally used as the coordination artifact for tracking agent state (phase, progress, verification checkboxes). With the adoption of beads for work tracking, WORKSPACE.md became redundant. The decision to deprecate it was made on 2025-12-05 (see orch-knowledge ok-2gq investigation).

## Decision

Remove all WORKSPACE.md creation, parsing, and checking from orch-cli. Beads is now the sole source of truth for agent state tracking.

## Changes Made

### Files Modified

1. **src/orch/workspace.py** - Reduced to only workspace naming utilities:
   - Kept: `ABBREVIATIONS`, `apply_abbreviations()`, `truncate_at_word_boundary()`
   - Removed: All WORKSPACE.md parsing, creation, and validation functions

2. **src/orch/markdown_utils.py** (new) - Generic markdown utilities:
   - Moved: `extract_tldr()` function (used for decisions/investigations, not WORKSPACE.md)

3. **src/orch/registry.py** - Simplified reconciliation:
   - Agents with `primary_artifact`: Check artifact for completion
   - Agents without `primary_artifact`: Trust window closure as completion

4. **src/orch/patterns.py** - Deprecated:
   - Returns empty list (pattern checking based on WORKSPACE.md no longer applicable)

5. **src/orch/resume.py** - Simplified:
   - Now reads from SPAWN_CONTEXT.md instead of WORKSPACE.md
   - `update_workspace_timestamps()` is now a no-op

6. **src/orch/context_capture.py** - Simplified:
   - Removed WORKSPACE.md parsing, returns workspace path only

7. **src/orch/monitoring_commands.py** - Cleaned up:
   - Removed WORKSPACE.md display logic from `orch check`

8. **src/orch/cli.py** - Updated imports:
   - Changed to import `extract_tldr` from `markdown_utils`

### Tests Updated

1. **tests/test_registry.py** - Rewrote reconciliation tests for new behavior
2. **tests/test_complete.py** - Removed `TestWorkspaceSafeReading` class
3. **tests/test_resume.py** - Updated to test SPAWN_CONTEXT.md instead of WORKSPACE.md
4. **tests/test_workspace_name_length.py** - Kept only naming utility tests
5. **tests/test_workspace_html_comments.py** - Deleted (tested removed functionality)

## Consequences

### Positive

- Simpler codebase with clear source of truth (beads)
- Removed ~900 lines of WORKSPACE.md infrastructure
- No more race conditions from concurrent WORKSPACE.md access
- Agent state changes tracked via beads comments (auditable)

### Negative

- Existing workspaces with WORKSPACE.md files are ignored (not parsed)
- Legacy agents without beads tracking have weaker verification

## References

- Investigation: `.kb/investigations/2025-12-06-eliminate-workspace-entirely-from-orch.md`
- Related: orch-knowledge ok-2gq investigation (deprecation decision)
