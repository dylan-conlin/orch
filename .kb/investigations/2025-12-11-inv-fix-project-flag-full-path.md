**TLDR:** Question: Why does --project with a full path create invalid tmuxinator config? Answer: spawn.py passes the raw path string as project name to ensure_tmuxinator_config() instead of extracting basename, creating filenames like `workers-/Users/.../project.yml`. High confidence (95%) - clear data flow trace through code.

---

# Investigation: Fix --project flag with full path creates invalid tmuxinator config

**Question:** Why does `orch spawn SKILL --project /full/path/to/project "task"` create invalid tmuxinator config?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** worker
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Findings

### Finding 1: `project` variable is set to raw input without normalization

**Evidence:** In `spawn_with_skill()` at lines 1534-1538, when `--project` is provided but `project_dir` is not:
```python
else:
    # Explicit project name provided without directory - resolve it
    project_dir = get_project_dir(project)
    if not project_dir:
        raise ValueError(format_project_not_found_error(project, "--project"))
```
The `project_dir` is resolved correctly, but `project` remains the raw input (e.g., `/Users/dylanconlin/Documents/personal/orch-cli`).

**Source:** `src/orch/spawn.py:1534-1538`

**Significance:** This is the root cause - the project name should be extracted from the resolved path.

---

### Finding 2: `config.project` used directly in tmuxinator config

**Evidence:** At line 1568-1570, `SpawnConfig` is created with `project=project`, and later at line 545:
```python
ensure_tmuxinator_config(config.project, config.project_dir)
```
The `project_name` parameter to `ensure_tmuxinator_config()` is used directly to create filenames.

**Source:** `src/orch/spawn.py:545`, `src/orch/spawn.py:1568-1570`

**Significance:** The raw path flows through to tmuxinator, creating invalid config files.

---

### Finding 3: `ensure_tmuxinator_config()` uses project_name in filename without sanitization

**Evidence:** In `tmuxinator.py:62`:
```python
config_path = config_dir / f"workers-{project_name}.yml"
```
If `project_name` is `/Users/dylanconlin/Documents/personal/orch-cli`, this creates:
`~/.tmuxinator/workers-/Users/dylanconlin/Documents/personal/orch-cli.yml`

**Source:** `src/orch/tmuxinator.py:62`

**Significance:** Confirms the bug manifests here, but fix should be upstream where project name is set.

---

## Synthesis

**Key Insights:**

1. **Project name not normalized after path resolution** - When `get_project_dir()` resolves a full path, the original `project` variable is not updated to extract just the basename.

2. **Two spawn functions affected** - Both `spawn_with_skill()` and `spawn_interactive()` have the same bug in the `else` branch where explicit project is provided.

3. **Fix is upstream, not at tmuxinator** - The fix should be at the point where project name is derived, not in `ensure_tmuxinator_config()` which correctly expects a project name.

**Answer to Investigation Question:**

The bug occurs because when `--project /full/path/to/project` is passed, the `project` variable retains the raw path string even after `get_project_dir()` resolves it to a valid `Path`. This raw path is then passed to `ensure_tmuxinator_config()` which uses it directly in the config filename, creating invalid filenames like `workers-/Users/.../project.yml`.

---

## Fix Implemented

**Changes made:**
1. `src/orch/spawn.py:1539-1542` - Added normalization in `spawn_with_skill()` to extract basename when input contains `/`
2. `src/orch/spawn.py:1081-1084` - Added same normalization in `spawn_interactive()`
3. `tests/test_spawn_project.py` - Added `TestProjectNameNormalization` test class with 4 regression tests

**Code change:**
```python
# If input was a path (contains /), extract project name from resolved directory
# This prevents invalid tmuxinator configs like "workers-/Users/.../project.yml"
if '/' in project:
    project = project_dir.name
```

---

## References

**Files Examined:**
- `src/orch/spawn.py` - Main spawn logic where bug occurs
- `src/orch/spawn_commands.py` - CLI command definitions
- `src/orch/tmuxinator.py` - tmuxinator config creation
- `src/orch/project_resolver.py` - Project resolution logic

---

## Investigation History

**2025-12-11:** Investigation started
- Initial question: Why does --project with full path create invalid tmuxinator config?
- Root cause identified: project variable not normalized after path resolution

**2025-12-11:** Fix implemented and investigation complete
- Added basename extraction in spawn_with_skill() and spawn_interactive()
- Added 4 regression tests
- All tests passing
- Final confidence: Very High (95%+)
- Status: Complete
- Key outcome: Fixed project name normalization in spawn_with_skill() and spawn_interactive() to prevent invalid tmuxinator config filenames
