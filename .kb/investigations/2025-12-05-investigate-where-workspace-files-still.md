**TLDR:** Question: Where are WORKSPACE.md files still being created? Answer: WORKSPACE.md files are NOT being created by orch spawn anymore (fixed in commit fbec053 on Dec 4). Existing files are from spawns before that date - agents were being told to create/update WORKSPACE.md via spawn prompt instructions. Very High confidence (95%) - verified current code, git history, and tested with my own spawn context.

---

# Investigation: Where WORKSPACE.md Files Are Still Being Created

**Question:** Where in the codebase are WORKSPACE.md files being created, and what needs to change to stop this?

**Started:** 2025-12-05
**Updated:** 2025-12-05
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: spawn.py stopped creating WORKSPACE.md - beads is source of truth

**Evidence:** In spawn.py, three locations have comments saying "WORKSPACE.md no longer created - beads is source of truth":
- Line 1156 (spawn_with_skill)
- Line 1577 (spawn_interactive)
- Line 2062 (spawn_interactive_skill)

All three locations now only create the workspace **directory**, not the WORKSPACE.md file.

**Source:** src/orch/spawn.py:1156, 1577, 2062

**Significance:** The spawn command itself does NOT create WORKSPACE.md files anymore. This was the correct change per the "beads-first" architecture.

---

### Finding 2: spawn_prompt.py was fixed on Dec 4 to stop instructing agents to create WORKSPACE.md

**Evidence:** Commit fbec053 (Dec 4, 2025) titled "fix(spawn_prompt): remove legacy WORKSPACE.md instructions" removed:
- WORKSPACE.md references from fallback_template()
- Instructions telling agents to create/update WORKSPACE.md
- "Workspace still tracks detailed work state" note
- COORDINATION ARTIFACT POPULATION section
- Status update instructions that mentioned workspace Phase field

**Source:** `git show fbec053` - commit message and diff

**Significance:** This is the fix. Before this commit, spawn_prompt.py was telling agents to create WORKSPACE.md even though spawn.py wasn't creating it. Agents would then create WORKSPACE.md files themselves based on these instructions.

---

### Finding 3: Existing WORKSPACE.md files are from spawns before Dec 4

**Evidence:** Checked modification dates of WORKSPACE.md files in .orch/workspace/:
- Dec 4 files exist (created before fbec053 commit)
- Dec 3 files exist (before the fix)
- My Dec 5 workspace has NO WORKSPACE.md - only SPAWN_CONTEXT.md

Verified my SPAWN_CONTEXT.md only mentions WORKSPACE.md in:
1. The task description itself
2. A note saying investigation file "replaces WORKSPACE.md" (correct messaging)

**Source:** `ls -lt .orch/workspace/*/WORKSPACE.md`, grep of my SPAWN_CONTEXT.md

**Significance:** The fix is working. New spawns after Dec 4 do NOT create WORKSPACE.md files and don't instruct agents to create them.

---

### Finding 4: Dead code exists but is harmless

**Evidence:** The function `create_workspace()` in workspace.py (line 959) still creates WORKSPACE.md files when called. However, grep shows **nothing calls this function** in the src/orch directory - it's dead code.

**Source:** `grep -r "create_workspace(" src/orch` returns only the function definition

**Significance:** The dead code doesn't cause problems but could be cleaned up for clarity. Low priority.

---

### Finding 5: Several skills still reference WORKSPACE.md in metadata/docs

**Evidence:** grep found WORKSPACE.md references in many skill files:
- `~/.claude/skills/*/SKILL.md` files have deliverables mentioning WORKSPACE.md path
- orchestrator skill says "Spawn creates: Workspace at .orch/workspace/{name}/WORKSPACE.md"
- Various utility skills reference WORKSPACE.md locations

**Source:** `grep -r "WORKSPACE.md" ~/.claude/skills/`

**Significance:** These are documentation references that should be updated to reflect beads-first architecture. Not functionally harmful but misleading. Creates beads issue for cleanup.

---

## Synthesis

**Key Insights:**

1. **The problem was already fixed** - Commit fbec053 on Dec 4 removed WORKSPACE.md creation instructions from spawn_prompt.py. The question was asked because we saw recent WORKSPACE.md files, but those were created BEFORE the fix.

2. **Two-part problem** - spawn.py stopped creating the file earlier, but spawn_prompt.py kept telling agents to create/update WORKSPACE.md. Agents followed instructions literally and created the files themselves.

3. **kb-cli is clean** - No WORKSPACE.md creation code found in kb-cli (no matches for grep).

4. **orch-knowledge is clean** - Only backup files and documentation references, no creation code.

**Answer to Investigation Question:**

WORKSPACE.md files are no longer being created by current code (post-Dec 4). The existing files in workspaces were created by:
1. Spawns before Dec 4 when spawn_prompt.py still instructed agents to create/update WORKSPACE.md
2. Agents following those instructions literally

No code changes needed - the fix is already in place. The remaining cleanup is:
- Remove dead `create_workspace()` function from workspace.py
- Update skill documentation that still references WORKSPACE.md
- Remove WORKSPACE.md template from ~/.orch/templates/ (optional)

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Strong evidence from multiple sources:
- Git history shows exact commit that fixed the issue
- Code inspection confirms current behavior
- My own spawn context demonstrates the fix is working
- Consistent findings across all three repos

**What's certain:**

- ✅ spawn.py does NOT create WORKSPACE.md (verified code lines 1156, 1577, 2062)
- ✅ spawn_prompt.py no longer instructs agents to create WORKSPACE.md (commit fbec053)
- ✅ New spawns work correctly (my workspace has no WORKSPACE.md)
- ✅ kb-cli has no WORKSPACE.md creation code

**What's uncertain:**

- ⚠️ Whether any edge cases in interactive mode still reference WORKSPACE.md
- ⚠️ Whether all skill docs have been updated (many still reference WORKSPACE.md)

**What would increase confidence to 100%:**

- Test multiple spawn types (skill-based, interactive, beads-based)
- Verify no users are manually creating WORKSPACE.md files

---

## Implementation Recommendations

**Purpose:** The investigation found the problem was already fixed. Recommendations are for cleanup only.

### Recommended Approach ⭐

**No urgent changes needed** - The fix is already in place (commit fbec053).

**Why this approach:**
- Current code works correctly
- New spawns don't create WORKSPACE.md
- Existing files are legacy from before the fix

**Trade-offs accepted:**
- Existing WORKSPACE.md files remain (manual cleanup optional)
- Some documentation still references old pattern

### Cleanup Tasks (Low Priority)

1. **Remove dead code** - Delete `create_workspace()` function from workspace.py (~100 lines of unused code)

2. **Update skill documentation** - Update skills that still reference WORKSPACE.md:
   - `~/.claude/skills/policy/orchestrator/SKILL.md` (says spawn creates WORKSPACE.md)
   - Various utility skills with WORKSPACE.md paths in deliverables

3. **Clean up template** - Consider removing `~/.orch/templates/WORKSPACE.md` since it's no longer used

4. **Purge old workspaces** - Optional: Remove WORKSPACE.md files from existing workspaces (or leave as historical)

---

## References

**Files Examined:**
- src/orch/spawn.py - Lines 1156, 1577, 2062 (workspace directory creation)
- src/orch/spawn_prompt.py - Lines 668-696, 951-957 (coordination artifact instructions)
- src/orch/workspace.py - Lines 959-1041 (create_workspace function - dead code)
- ~/.orch/templates/WORKSPACE.md - Template file (still exists, unused)
- ~/.orch/templates/SPAWN_PROMPT.md - Template with placeholders

**Commands Run:**
```bash
# Search for WORKSPACE.md creation across repos
grep -r "WORKSPACE\.md" src/orch/
grep -r "WORKSPACE\.md" ~/orch-knowledge/
grep -r "WORKSPACE\.md" ~/Documents/personal/kb-cli/

# Check git history for fix
git log --oneline --since="2025-11-25" --grep="beads" -- src/orch/spawn.py
git show fbec053 --stat

# Verify current workspace contents
ls -la .orch/workspace/inv-inv-where-workspace-files-05dec/
```

**Related Artifacts:**
- **Investigation:** .kb/investigations/design/2025-12-04-post-mortem-worker-double-tracking.md - Identified the spawn_prompt.py issue

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-05 12:30:** Investigation started
- Initial question: Where are WORKSPACE.md files still being created?
- Context: Orchestrator noticed WORKSPACE.md files exist despite "beads is source of truth"

**2025-12-05 12:45:** Found spawn.py correctly doesn't create WORKSPACE.md
- All three spawn functions have "beads is source of truth" comments
- workspace.py has dead create_workspace() function

**2025-12-05 13:00:** Discovered commit fbec053 fixed spawn_prompt.py
- Dec 4 commit removed WORKSPACE.md instructions
- Explains why Dec 3 spawns have WORKSPACE.md but mine doesn't

**2025-12-05 13:05:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Problem already fixed. Existing WORKSPACE.md files are legacy from pre-Dec 4 spawns.
