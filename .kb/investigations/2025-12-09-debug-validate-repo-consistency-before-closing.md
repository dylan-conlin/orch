**TLDR:** Question: Why do cross-repo beads closures fail in orch complete? Answer: No validation that agent's project_dir matches cwd when closing beads issues - allows closing issues from wrong repository. High confidence (85%) - traced code path, clear bug in complete.py:278-301.

---

# Investigation: Validate repo consistency before closing beads issues

**Question:** Why do cross-repo beads operations fail, and how should repo consistency be validated before closing issues?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** debug-validate-repo-09dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: No project_dir validation in complete_agent_work()

**Evidence:**
- `complete_agent_work()` receives `project_dir` as parameter (line 204)
- Agent's stored `project_dir` retrieved from registry via `agent.get('beads_db_path')` (line 281)
- NO validation comparing passed `project_dir` against agent's stored `project_dir`
- Beads closure proceeds using `beads_db_path` without repo consistency check (line 290)

**Source:** `src/orch/complete.py:202-301`

**Significance:** This allows scenarios where:
- Agent spawned in repo A with issue from repo B
- Agent works in wrong directory
- `orch complete` closes issue using cross-repo path without verifying agent worked in correct repo

---

### Finding 2: Cross-repo support was added but validation was not

**Evidence:**
- `BeadsIntegration.__init__()` accepts optional `db_path` parameter (line 56)
- `_build_command()` adds `--db` flag when `db_path` is set (line 77-78)
- This enables cross-repo operations but creates potential for misuse
- Error log shows: "Beads issue 'beads-ui-svelte-ig2' cannot be closed: agent has not reported 'Phase: Complete'"
  - Agent spawned in orch-cli trying to close issue from beads-ui-svelte project

**Source:**
- `src/orch/beads_integration.py:56-80`
- Prior investigation `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` Finding 3

**Significance:** Cross-repo feature was designed for legitimate use cases but lacks guard rails. The `db_path` parameter makes cross-repo possible but validation is responsibility of caller.

---

### Finding 3: Agent stores project_dir in registry

**Evidence:**
- Spawned agents store `project_dir` in registry (spawning flow)
- `agent.get('project_dir')` should return the directory where agent was spawned
- This value can be compared against the current working directory for validation

**Source:**
- `src/orch/spawn.py` (spawning stores project_dir)
- `src/orch/registry.py` (registry stores agent data)

**Significance:** The data needed for validation already exists - just not used during completion.

---

## Synthesis

**Key Insights:**

1. **Validation gap between spawn and complete** - Agents are spawned with specific project_dir but completion doesn't verify agent worked there

2. **Cross-repo feature lacks consistency check** - The `beads_db_path` enables cross-repo but assumes caller validates repo consistency

3. **Simple fix available** - Compare `Path(cwd).resolve()` against `Path(agent['project_dir']).resolve()` before closing

**Answer to Investigation Question:**

Cross-repo beads closures fail because `complete_agent_work()` doesn't validate that the agent's stored `project_dir` matches the actual project directory. The fix is to add validation before closing beads issues:

```python
# Before closing beads issues
if beads_db_path:
    agent_project = Path(agent.get('project_dir', '')).resolve()
    current_project = project_dir.resolve()
    if agent_project != current_project:
        result['errors'].append(
            f"Repo mismatch: agent was spawned in {agent_project} but orch complete "
            f"was called in {current_project}. Cannot close cross-repo beads issue."
        )
        return result
```

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**

Clear code path traced from complete_agent_work() through beads closure. The gap in validation is obvious - no comparison between agent's stored project_dir and current working directory.

**What's certain:**

- ✅ No validation exists in complete.py before beads closure
- ✅ Cross-repo db_path is passed directly to BeadsIntegration
- ✅ Agent registry stores project_dir from spawn time

**What's uncertain:**

- ⚠️ Edge cases where project_dir comparison might fail (symlinks, etc.)
- ⚠️ Whether there are legitimate cross-repo completion scenarios

**What would increase confidence to Very High (95%+):**

- Test with actual cross-repo spawning scenario
- Verify project_dir is always stored in registry

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add repo consistency validation before beads closure** - Simple comparison of project directories

**Why this approach:**
- Directly addresses the root cause
- Minimal code change (~10 lines)
- Uses existing data (agent's project_dir)
- Provides clear error message when mismatch detected

**Trade-offs accepted:**
- May block some legitimate cross-repo scenarios (but these are edge cases)
- Symlinks could cause false positives (use Path.resolve())

**Implementation sequence:**
1. Add validation check after `beads_db_path = agent.get('beads_db_path')`
2. Compare resolved paths to handle symlinks
3. Return error with clear message if mismatch

### Alternative Approaches Considered

**Option B: Warn but continue**
- **Pros:** Non-breaking, allows edge cases
- **Cons:** Doesn't prevent incorrect closures
- **When to use instead:** If legitimate cross-repo scenarios are common

**Rationale for recommendation:** Errors are preferable to silently closing wrong issues. Users can re-run with correct context.

---

## References

**Files Examined:**
- `src/orch/complete.py:202-301` - Main completion flow, beads closure logic
- `src/orch/beads_integration.py:56-80` - db_path parameter, cross-repo support
- `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` - Prior analysis

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-09-inv-orch-complete-error-patterns-110.md` - Finding 3 identified this issue

---

## Investigation History

**2025-12-09 21:45:** Investigation started
- Initial question: Why do cross-repo beads closures fail?
- Context: Prior investigation identified 11% of orch complete errors from cross-repo access

**2025-12-09 21:50:** Root cause identified
- Traced code path through complete.py
- Found missing validation between agent project_dir and current cwd
- Ready to implement fix

**2025-12-09 22:05:** Investigation completed
- Implemented repo consistency validation in complete.py:283-296
- Added test for cross-repo mismatch detection
- All 42 complete-related tests pass
- Key outcome: Cross-repo beads closures now validated against agent's project_dir
