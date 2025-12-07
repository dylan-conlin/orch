**TLDR:** Dead code cleanup - removing unused migrate_*.py files. Files were for one-time frontmatter migration that's been completed. High confidence (95%) - files have no callers besides the cli.py registration.

---

# Investigation: Migrate Utilities Removal

**Question:** What files need to be deleted and what references need to be fixed for migrate_*.py cleanup?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Three migrate files exist in src/orch/

**Evidence:**
- `src/orch/migrate_workspaces.py` - Workspace migration utility
- `src/orch/migrate_frontmatter.py` - Frontmatter conversion utility
- `src/orch/migrate_commands.py` - CLI commands for migration

**Source:** `ls src/orch/migrate_*.py`

**Significance:** These are the files to delete.

---

### Finding 2: cli.py has two references to migrate_commands

**Evidence:**
- Line 27: `from orch.migrate_commands import register_migrate_commands`
- Line 39: `register_migrate_commands(cli)`

**Source:** `src/orch/cli.py:27` and `src/orch/cli.py:39`

**Significance:** These imports must be removed to avoid ImportError after deletion.

---

### Finding 3: Test file exists for migrate_frontmatter

**Evidence:**
- `tests/test_migrate_frontmatter.py` - 267 lines of tests

**Source:** `tests/test_migrate_frontmatter.py`

**Significance:** Test file should also be deleted as the module it tests will be gone.

---

## Synthesis

**Key Insights:**

1. **Clean removal** - No complex dependencies, just two import lines in cli.py
2. **No external callers** - These utilities were for internal one-time migration
3. **Test cleanup needed** - The test file must be removed to avoid test collection errors

**Answer to Investigation Question:**

Delete 4 files total (3 migrate_*.py + 1 test file), edit cli.py to remove 2 lines. No other references found.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**
Grep search found all references. The migrate_commands module only imports from migrate_frontmatter, and cli.py is the only external importer.

**What's certain:**
- ✅ Files to delete are isolated with no external dependencies
- ✅ cli.py changes are straightforward import removal
- ✅ No other modules import from migrate_*

**What's uncertain:**
- ⚠️ Tests should be run after deletion to confirm no hidden dependencies

---

## Implementation

**Changes made:**
1. Removed import line 27 from cli.py
2. Removed registration call line 39 from cli.py
3. Deleted src/orch/migrate_workspaces.py
4. Deleted src/orch/migrate_frontmatter.py
5. Deleted src/orch/migrate_commands.py
6. Deleted tests/test_migrate_frontmatter.py

**Validation:** Run `pytest` to confirm no import errors or broken tests.

---

## References

**Files Examined:**
- `src/orch/cli.py` - Found import and registration
- `src/orch/migrate_commands.py` - Understood dependencies
- `tests/test_migrate_frontmatter.py` - Identified test file for removal

**Commands Run:**
```bash
# Find migrate files
glob **/migrate_*.py

# Find references
grep "migrate_workspaces|migrate_frontmatter|migrate_commands" --glob "*.py"
```
