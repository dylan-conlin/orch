**TLDR:** Question: Why does orch complete verification fail to find investigation files? Answer: THREE distinct naming/path mismatches exist: (1) skill frontmatter says `.orch/` but spawn_prompt tells agents to use `.kb/`, (2) skill frontmatter specifies `simple/` subdirectory but kb creates in root, (3) verification fallback looks for `workspace_name.md` (e.g., `inv-orch-complete-06dec.md`) but actual files are `YYYY-MM-DD-slug.md`. Recommend Option C: store actual filename in registry at spawn time. High confidence (95%) - directly traced through code.

---

# Investigation: orch complete verification filename mismatch

**Question:** Why does orch complete verification look for `workspace_name.md` when spawn tells agents to create `YYYY-MM-DD-topic.md`?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Findings

### Finding 1: Verification fallback uses workspace_name.md pattern

**Evidence:**
```python
# verification.py:86-91
workspace_name = workspace_path.name
pattern = f"**/{workspace_name}.md"
matching_files = list(investigations_dir.glob(pattern))
```

When `primary_artifact` is not set or doesn't exist, verification looks for files matching `workspace_name.md` (e.g., `inv-orch-complete-06dec.md`).

**Source:** `src/orch/verification.py:73-93`

**Significance:** This is the core bug - workspace names are short slugs like `inv-orch-complete-06dec`, but actual investigation files use long descriptive names like `2025-12-06-orch-complete-verification-filename-mismatch.md`.

---

### Finding 2: Spawn prompt tells agents to create files in .kb/ with kb create command

**Evidence:**
```python
# spawn_prompt.py:764-766
coordination_check = (
    f"**SET UP investigation file:** Run `kb create investigation {inv_slug}` to create from template\n"
    f"   - This creates: `.kb/investigations/{inv_type}/YYYY-MM-DD-{inv_slug}.md`\n"
```

The spawn prompt tells agents to use `kb create investigation {slug}` which creates files in `.kb/investigations/`.

**Source:** `src/orch/spawn_prompt.py:758-768`

**Significance:** The spawn prompt correctly guides agents to use `kb create` and correctly describes the YYYY-MM-DD-slug.md format. However, this differs from the skill frontmatter.

---

### Finding 3: Skill frontmatter defines path using .orch/ not .kb/

**Evidence:**
```yaml
# investigation SKILL.md frontmatter
deliverables:
- type: investigation
  path: "{project}/.orch/investigations/simple/{date}-{slug}.md"
  required: true
```

The investigation skill's frontmatter specifies `.orch/investigations/simple/` as the deliverable path.

**Source:** `~/.claude/skills/worker/investigation/SKILL.md` (lines 20-23)

**Significance:** There's a mismatch between:
1. What spawn_prompt tells agents (`.kb/investigations/`)
2. What skill frontmatter declares (`.orch/investigations/simple/`)
3. What kb actually creates (`.kb/investigations/YYYY-MM-DD-slug.md` - no subdirectory!)

---

### Finding 4: primary_artifact is derived from skill frontmatter path

**Evidence:**
```python
# spawn.py:465-483
def determine_primary_artifact(config: SpawnConfig) -> Optional[Path]:
    if not config.deliverables:
        return None
    for deliverable in config.deliverables:
        if deliverable.type == "investigation" and deliverable.required:
            rendered = render_deliverable_path(deliverable.path, config)
            return Path(rendered)
    return None
```

The `primary_artifact` stored in the registry comes from rendering the skill frontmatter's deliverable path template.

**Source:** `src/orch/spawn.py:465-483`, `src/orch/spawn_prompt.py:228-258`

**Significance:** Since skill frontmatter says `.orch/investigations/simple/`, the `primary_artifact` gets set to that path, but the actual file is created in `.kb/investigations/` by `kb create`.

---

### Finding 5: Verification checks primary_artifact first

**Evidence:**
```python
# verification.py:77-81
if agent_info and agent_info.get('primary_artifact'):
    primary_path = Path(agent_info['primary_artifact']).expanduser()
    if not primary_path.is_absolute():
        primary_path = (project_dir / primary_path).resolve()
    return primary_path.exists()
```

When `primary_artifact` is set, verification checks that exact path first before falling back to workspace_name matching.

**Source:** `src/orch/verification.py:77-81`

**Significance:** If `primary_artifact` is set correctly, verification should work. The bug is that `primary_artifact` points to `.orch/investigations/simple/` but the actual file is in `.kb/investigations/`.

---

## Synthesis

**Key Insights:**

1. **Three-way path mismatch** - There are THREE sources of truth that don't agree:
   - Skill frontmatter: `.orch/investigations/simple/{date}-{slug}.md`
   - Spawn prompt to agents: `.kb/investigations/{type}/YYYY-MM-DD-{slug}.md`
   - What kb actually creates: `.kb/investigations/YYYY-MM-DD-{slug}.md` (no subdirectory)

2. **Workspace name vs file name mismatch** - Even if paths matched, the names differ:
   - Workspace: `inv-orch-complete-06dec` (short, date-suffix)
   - Investigation file: `2025-12-06-orch-complete-verification-filename-mismatch` (long, date-prefix)

3. **primary_artifact is the correct fix point** - The registry stores `primary_artifact` which is checked first during verification. If this were set to the ACTUAL file path (not rendered from frontmatter), verification would work.

**Answer to Investigation Question:**

The verification fails because of a THREE-LAYER mismatch:

1. **Path mismatch**: `primary_artifact` is derived from skill frontmatter (`.orch/investigations/simple/`) but agents create files via `kb create` in `.kb/investigations/` (no subdirectory).

2. **Name mismatch**: The fallback search looks for `{workspace_name}.md` but files are named `YYYY-MM-DD-{slug}.md`.

3. **Root cause**: The `primary_artifact` is computed at spawn time by rendering the skill frontmatter template, which has an incorrect/outdated path. The actual file path depends on what `kb create` does at runtime.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct code tracing through the spawn and verification pipeline. Every finding is backed by specific file paths and line numbers. The three-way mismatch is unambiguous.

**What's certain:**

- ✅ Verification checks `primary_artifact` first, then falls back to `{workspace_name}.md` pattern (verification.py:77-93)
- ✅ `primary_artifact` is computed from skill frontmatter template at spawn time (spawn.py:465-483)
- ✅ Skill frontmatter says `.orch/investigations/simple/` but kb creates in `.kb/investigations/` (no subdirectory)
- ✅ Workspace names (`inv-X-06dec`) don't match file names (`2025-12-06-X.md`)

**What's uncertain:**

- ⚠️ Whether other skills have similar path mismatches (only checked investigation skill)
- ⚠️ Historical context for why `.orch/` vs `.kb/` diverged

**What would increase confidence to 100%:**

- Test with a real spawn/complete cycle to confirm the failure mode
- Check other investigation-producing skills for the same issue

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**Option C: Store actual filename in registry** - Have agents report their created file path back via beads comment, then update registry with actual path.

**Why this approach:**
- **Decouples spawn from kb tooling** - spawn doesn't need to know kb's exact output format
- **Handles any future kb changes** - if kb changes its output location, system adapts automatically
- **Single source of truth** - the actual file path IS the truth, not a computed prediction
- **Addresses root cause** - the real issue is that spawn predicts a path but actual path is determined at runtime

**Trade-offs accepted:**
- Requires agents to report file path (additional agent action required)
- Slight delay between file creation and registry update
- These are acceptable because agents already report via beads comments

**Implementation sequence:**
1. Update spawn prompt to instruct agents: after `kb create`, capture the output path
2. Add guidance to report path via `bd comment <id> "investigation_path: /path/to/file.md"`
3. Update `orch complete` to parse beads comments for `investigation_path:` prefix
4. Store extracted path in registry as `primary_artifact` (or update existing if set)
5. Verification continues to work via existing `primary_artifact` check

### Alternative Approaches Considered

**Option A: Change verification to search by date pattern**
- **Pros:** Quick fix, no agent changes needed
- **Cons:**
  - Still doesn't know exact path - has to search
  - Date prefix search could match multiple files (e.g., `2025-12-06-*.md`)
  - Doesn't address `.kb/` vs `.orch/` path confusion
  - Workaround rather than fix
- **When to use instead:** If we need an immediate stopgap while implementing Option C

**Option B: Change spawn to use workspace name**
- **Pros:** Aligns spawn and verification patterns
- **Cons:**
  - Would require changing `kb create` behavior or how spawn calls it
  - Workspace names are less descriptive (`inv-foo-06dec` vs `2025-12-06-foo.md`)
  - Breaks existing conventions and kb's standard naming
  - Couples spawn too tightly to kb internals
- **When to use instead:** If we want to standardize all artifacts to use workspace name

**Rationale for recommendation:** Option C fixes the root cause (spawn predicts path but actual is runtime-determined) without coupling to kb internals or requiring workaround searches. It uses existing infrastructure (beads comments) and follows the principle that the actual file path should be the source of truth.

---

### Implementation Details

**What to implement first:**
- Update spawn_prompt.py to instruct agents to capture `kb create` output
- Define the beads comment format (e.g., `investigation_path: /path/to/file.md`)
- Add parsing in orch complete to extract path from beads comments

**Things to watch out for:**
- ⚠️ Backward compatibility - agents spawned before this change won't have the comment
- ⚠️ Need fallback when comment not found (existing heuristic search)
- ⚠️ Update skill frontmatter to match reality (`.kb/` not `.orch/`) as separate cleanup

**Areas needing further investigation:**
- Other skills (systematic-debugging, codebase-audit) may have similar path issues
- Whether skill frontmatter should be source of truth or just documentation
- Migration strategy for existing agents/workspaces

**Success criteria:**
- ✅ `orch complete` succeeds for investigation agents without manual path fixing
- ✅ `primary_artifact` in registry matches actual file path
- ✅ Works for both existing agents (fallback) and new agents (comment-based)

---

## References

**Files Examined:**
- `src/orch/verification.py:56-121` - `_check_deliverable_exists()` function showing workspace_name pattern
- `src/orch/spawn.py:465-483` - `determine_primary_artifact()` function showing frontmatter-based path derivation
- `src/orch/spawn_prompt.py:758-768` - coordination_check showing kb create instructions
- `src/orch/spawn_prompt.py:228-258` - `render_deliverable_path()` showing template variable substitution
- `~/.claude/skills/worker/investigation/SKILL.md` - skill frontmatter with `.orch/investigations/simple/` path
- `src/orch/complete.py:309-327` - `surface_investigation_recommendations()` showing primary_artifact usage

**Commands Run:**
```bash
# List kb investigation directory to see actual file structure
ls -la .kb/investigations/

# Check kb create output format
kb create investigation orch-complete-verification-filename-mismatch
# Output: Created investigation: .kb/investigations/2025-12-06-orch-complete-verification-filename-mismatch.md
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-06-fix-primary-artifact-set-non.md` - Related issue with primary_artifact not being set

---

## Investigation History

**2025-12-06 18:15:** Investigation started
- Initial question: Why does orch complete look for `workspace_name.md` when spawn tells agents to create `YYYY-MM-DD-topic.md`?
- Context: Bug 3 from ok-5cl audit of orch complete verification failures

**2025-12-06 18:20:** Found three-way path mismatch
- Skill frontmatter: `.orch/investigations/simple/`
- Spawn prompt: `.kb/investigations/{type}/`
- Actual kb output: `.kb/investigations/` (no subdirectory)

**2025-12-06 18:30:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Three mismatched sources of truth (skill frontmatter, spawn prompt, kb output) cause verification to search for wrong filename

---

## Self-Review

- [x] Real test performed (code tracing with specific file paths and line numbers)
- [x] Conclusion from evidence (based on direct code examination)
- [x] Question answered (clear explanation of three-way mismatch)
- [x] File complete

**Self-Review Status:** PASSED
