---
date: "2025-12-02"
status: "Complete"
resolution_status: "Resolved"
confidence: "high"
---

# orch spawn --issue fails with project not found

**TLDR:** `orch spawn --issue` fails because `spawn_commands.py` auto-detects `project` name but doesn't pass `project_dir` to `spawn_with_skill()`, which then re-resolves using `active-projects.md` instead of the new `initialized-projects.json`.

## Question

Why does `orch spawn --issue` fail with "Project 'orch-cli' not found" when:
1. User is in the orch-cli directory with `.orch/`
2. `orch projects scan` has cached orch-cli to `~/.orch/initialized-projects.json`

## What I tried

- Traced the spawn flow in `spawn_commands.py` for `--issue` mode
- Examined `get_project_dir()` in `spawn.py`
- Checked both project registries: `~/.orch/initialized-projects.json` and `~/.claude/active-projects.md`
- Traced `detect_project_from_cwd()` fallback behavior

## What I observed

**Two separate project registries:**
1. `~/.orch/initialized-projects.json` - Used by `orch projects scan/list`, contains orch-cli
2. `~/.claude/active-projects.md` - Used by spawn commands via `get_project_dir()`, only contains orch-knowledge

**Bug flow:**
1. User runs `orch spawn research --issue orch-cli-vny`
2. `spawn_commands.py` line 163-166: `detect_project_from_cwd()` returns `("orch-cli", project_dir)` as fallback
3. Line 223: `spawn_with_skill(project="orch-cli", ...)` - passes `project` but NOT `project_dir`
4. `spawn_with_skill()` line 1989-1993: Re-resolves via `get_project_dir("orch-cli")`
5. `get_project_dir()` checks only `active-projects.md` - orch-cli not found → error

**Root cause:** When `detect_project_from_cwd()` succeeds with fallback (project has `.orch/` but isn't in `active-projects.md`), the `project_dir` is known but not passed through to `spawn_with_skill()`.

## Test performed

**Test:** Code trace analysis - followed the exact code path with debugger-level precision

**Result:** Confirmed the disconnect:
- `spawn_commands.py:166`: `project_dir = Path("/Users/dylanconlin/Documents/personal/orch-cli")`
- `spawn_commands.py:223`: `spawn_with_skill(project=project, ...)` - project_dir not passed
- `spawn.py:1991`: `project_dir = get_project_dir(project)` - re-resolves, fails

## Conclusion

**Fix:** Pass `project_dir` from `spawn_commands.py` to `spawn_with_skill()` when already known from auto-detection. Two changes needed:
1. Add `project_dir` parameter to `spawn_with_skill()` (use when provided, skip re-resolution)
2. Update issue mode in `spawn_commands.py` to pass `project_dir`

This is a minimal, surgical fix that addresses the immediate issue without needing to unify the two project registries.

---

## Notes

- Related: Consider unifying `initialized-projects.json` and `active-projects.md` in a future cleanup
- The fallback in `detect_project_from_cwd()` (line 1453-1455) was designed for exactly this case but the result wasn't being used properly downstream
