**TLDR:** Question: Why do workspace names collide across different projects? Answer: Workspace names use `[skill]-[task]-[date]` pattern without project identifier, but the agent registry is global (`~/.orch/agent-registry.json`), causing collisions when different projects spawn similar tasks on the same day. High confidence (95%) - directly traced through code.

---

# Investigation: Workspace Name Collision Across Projects

**Question:** Why do workspace names collide when spawning agents across different projects with similar task descriptions?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** Implement fix - add project prefix to workspace names
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Workspace names don't include project identifier

**Evidence:**
```python
# workspace_naming.py:73-152
def create_workspace_adhoc(task: str, skill_name: Optional[str] = None, project_dir: Optional[Path] = None) -> str:
    # Get compact date suffix (e.g., "30nov", "15dec")
    date_suffix = datetime.now().strftime("%d%b").lower()

    # Extract meaningful words
    words = extract_meaningful_words(task)

    # Build name with skill prefix if provided
    if skill_name and skill_name in SKILL_PREFIXES:
        prefix = SKILL_PREFIXES[skill_name]
        slug_words = [prefix] + filtered_words
    else:
        slug_words = words if words else ['workspace']

    slug = '-'.join(slug_parts)
    name = f"{slug}-{date_suffix}"  # No project identifier!
```

**Source:** `src/orch/workspace_naming.py:73-139`

**Significance:** The workspace name pattern is `[skill_prefix]-[task_keywords]-[date]` with NO project identifier. Two different projects spawning similar tasks on the same day will generate identical names.

---

### Finding 2: Collision detection only checks local workspace directory

**Evidence:**
```python
# workspace_naming.py:142-150
# Check for collision if project_dir provided
if project_dir:
    workspace_path = project_dir / ".orch" / "workspace" / name
    if workspace_path.exists():
        # Add hash suffix on collision (truncate slug to make room)
        task_hash = abs(hash(task)) % 10000  # 4-digit hash (shorter)
        ...
```

This collision check only looks in the **local project's** `.orch/workspace/` directory.

**Source:** `src/orch/workspace_naming.py:142-150`

**Significance:** Even though collision detection exists, it only prevents same-project collisions. Cross-project collisions are not detected at workspace name generation time.

---

### Finding 3: Agent registry is global and uses workspace name as agent ID

**Evidence:**
```python
# registry.py:30-32
def __init__(self, registry_path: Path = None):
    if registry_path is None:
        registry_path = Path.home() / '.orch' / 'agent-registry.json'  # GLOBAL!

# registry.py:210-213
def register(...):
    # Check for duplicate by agent ID only (not beads_id)
    existing = self._find_by_id(agent_id)  # agent_id = workspace_name
    if existing:
        raise ValueError(f"Agent '{agent_id}' already registered.")
```

**Source:** `src/orch/registry.py:30-32, 210-213`

**Significance:** The agent registry is stored globally at `~/.orch/agent-registry.json` and checks for duplicate agent IDs (which are workspace names) across ALL projects. This is where the collision manifests.

---

### Finding 4: Beads IDs use project prefix for global uniqueness

**Evidence:**
From the beads issue comment:
```
orch-cli-2h6: Workspace name collision across projects
```

Beads issue IDs follow the pattern `{project}-{unique_suffix}` (e.g., `orch-cli-2h6`, `pw-1a2`), ensuring global uniqueness by embedding the project name.

**Source:** `bd show orch-cli-2h6` output, beads CLI behavior

**Significance:** Beads already solved this problem by including the project prefix in IDs. Workspace names should follow the same pattern.

---

## Synthesis

**Key Insights:**

1. **Scope mismatch** - Workspace name collision detection is scoped to a single project's `.orch/workspace/`, but the agent registry is global at `~/.orch/agent-registry.json`.

2. **Missing project identifier** - The workspace naming pattern `[skill]-[task]-[date]` has no project component, making cross-project collisions inevitable for similar tasks.

3. **Beads pattern is the solution** - Beads already solved global uniqueness with `{project}-{suffix}` pattern. Workspace names should include abbreviated project prefix.

**Answer to Investigation Question:**

Workspace names collide across projects because:

1. **Naming pattern lacks project context**: `create_workspace_adhoc()` generates names using `[skill]-[task]-[date]` without any project identifier

2. **Collision detection is local**: The workspace directory collision check only looks within the current project's `.orch/workspace/`, not globally

3. **Registry is global**: Agent registration happens in `~/.orch/agent-registry.json`, which enforces uniqueness across all projects

When Project A and Project B both spawn an investigation about "bug handling analysis" on the same day, both generate `inv-bug-handling-analysis-11dec`. The first registers successfully; the second fails with "Agent 'inv-bug-handling-analysis-11dec' already registered."

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct code tracing through three key files shows the exact gap between local workspace collision detection and global registry uniqueness enforcement.

**What's certain:**

- ✅ Workspace names don't include project identifier (`workspace_naming.py:73-139`)
- ✅ Collision detection only checks local `.orch/workspace/` directory (`workspace_naming.py:142-150`)
- ✅ Agent registry is global at `~/.orch/agent-registry.json` (`registry.py:30-32`)
- ✅ Registry rejects duplicate agent IDs (workspace names) globally (`registry.py:210-213`)

**What's uncertain:**

- ⚠️ Exact frequency of this collision in practice (reported as one instance)
- ⚠️ Whether project abbreviation function handles edge cases (single-word names, long names)

**What would increase confidence to 100%:**

- Test reproduction with two projects spawning identical tasks
- Review `abbreviate_project_name()` edge cases

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**Option A: Add project prefix to workspace names** - Include abbreviated project name in workspace name pattern: `{project}-[skill]-[task]-[date]`

**Why this approach:**
- Follows beads pattern which already ensures global uniqueness
- Human-readable - can identify which project owns the workspace at a glance
- Simple implementation - `abbreviate_project_name()` already exists in `workspace_naming.py`

**Trade-offs accepted:**
- Workspace names become slightly longer (2-5 chars for prefix)
- May need to truncate task keywords more aggressively to fit within 35-char limit
- This is acceptable because uniqueness is more important than task detail

**Implementation sequence:**
1. Update `create_workspace_adhoc()` to prepend abbreviated project name
2. Adjust max length calculations to accommodate prefix
3. Test with multi-project spawning

### Alternative Approaches Considered

**Option B: Global collision detection in registry**
- **Pros:** No change to workspace naming pattern
- **Cons:**
  - Collision detection at registration is too late (workspace directory already created)
  - Hash suffix makes names unpredictable
  - Doesn't leverage existing `abbreviate_project_name()` function
- **When to use instead:** If we need backward compatibility with existing workspace names

**Option C: Use beads_id as agent_id when available**
- **Pros:** Beads IDs are already globally unique
- **Cons:**
  - Only works when spawning with beads integration
  - Interactive mode and ad-hoc spawns wouldn't benefit
  - Registry lookup semantics would change
- **When to use instead:** As additional safeguard alongside Option A

**Rationale for recommendation:** Option A addresses root cause (naming pattern lacks project context), uses existing infrastructure (`abbreviate_project_name`), and aligns with proven beads pattern.

---

### Implementation Details

**What to implement first:**
- Modify `create_workspace_adhoc()` in `workspace_naming.py` to include project prefix
- Pattern: `{abbrev_project}-[skill]-[task]-[date]` → e.g., `oc-inv-bug-handling-11dec`

**Example change:**
```python
def create_workspace_adhoc(task: str, skill_name: Optional[str] = None, project_dir: Optional[Path] = None) -> str:
    # Get compact date suffix
    date_suffix = datetime.now().strftime("%d%b").lower()

    # Get project prefix for global uniqueness
    project_prefix = ""
    if project_dir:
        project_name = project_dir.name
        project_prefix = abbreviate_project_name(project_name)

    # Extract meaningful words
    words = extract_meaningful_words(task)
    words = apply_abbreviations(words)

    # Build name with project prefix, skill prefix, and task
    if skill_name and skill_name in SKILL_PREFIXES:
        skill_prefix = SKILL_PREFIXES[skill_name]
        slug_words = [project_prefix, skill_prefix] + [w for w in words if w != skill_prefix]
    else:
        slug_words = [project_prefix] + words if words else [project_prefix, 'workspace']

    # Filter empty strings
    slug_words = [w for w in slug_words if w]
    ...
```

**Things to watch out for:**
- ⚠️ Max length is 35 chars - may need to reduce task word budget
- ⚠️ Project abbreviation for single-word projects (e.g., "beads" → "beads", not abbreviated)
- ⚠️ Existing workspaces won't be renamed - only affects new spawns

**Success criteria:**
- ✅ Two projects spawning identical tasks on same day get different workspace names
- ✅ Workspace names remain under 35 chars
- ✅ Window names (tmux) still human-readable
- ✅ Registry lookup by workspace name still works

---

## References

**Files Examined:**
- `src/orch/workspace_naming.py:73-152` - Workspace name generation logic
- `src/orch/workspace_naming.py:171-201` - `abbreviate_project_name()` function
- `src/orch/registry.py:30-32` - Global registry path
- `src/orch/registry.py:179-269` - `register()` function with duplicate check
- `src/orch/spawn.py:888-993` - `register_agent()` caller

**Commands Run:**
```bash
# View beads issue for bug details
bd show orch-cli-2h6
bd comments orch-cli-2h6
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-06-orch-complete-verification-filename-mismatch.md` - Related naming issues

---

## Investigation History

**2025-12-11 21:10:** Investigation started
- Initial question: Why do workspace names collide when spawning agents across different projects?
- Context: Bug report from Dylan - two different projects spawned identical workspace name `inv-bug-handling-analysis-11dec`

**2025-12-11 21:15:** Root cause identified
- Traced through `workspace_naming.py` → `registry.py`
- Found scope mismatch: local collision detection vs global registry

**2025-12-11 21:20:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Missing project identifier in workspace name pattern causes global registry collisions

---

## Self-Review

- [x] Root cause documented in investigation file
- [x] Fix approach recommended with implementation details
- [x] Verification requirements clear (success criteria listed)
- [x] No regression concerns (existing workspaces unaffected)
