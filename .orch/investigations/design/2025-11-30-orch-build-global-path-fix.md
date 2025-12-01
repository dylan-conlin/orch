# Investigation: Fix orch build global Path Detection

**Date:** 2025-11-30
**Type:** Design Investigation
**Status:** Complete

---

## TLDR

Fixed `orch build global` to work from any directory by hard-coding canonical templates path (`~/orch-knowledge/templates-src/`) instead of using project-local detection. Simple 2-line change eliminates directory-specific failures.

---

## Problem Framing

### Design Question

How should `orch build global` find the canonical templates source directory when run from any project?

### Context

**Current behavior:**
- `orch build global` syncs templates from `templates-src/` to `~/.orch/templates/`
- Uses `find_orch_root()` to locate templates (finds nearest `.orch/` directory)
- Fails when run from projects like orch-cli (has `.orch/` but no `templates-src/`)
- Only works when run from orch-knowledge directory

**Root cause:**
- Conflating "project root with .orch/" with "canonical templates location"
- Templates are global infrastructure, not project-local
- `find_orch_root()` is project-detection, not templates-discovery

**File system reality:**
- Canonical location: `/Users/dylanconlin/orch-knowledge/templates-src/`
- `~/meta-orchestration` is symlink to `~/orch-knowledge` (both resolve to same path)
- Help text already documents `{orch-knowledge}` as source (line 1937)

### Success Criteria

- Works from any directory (orch-cli, orch-knowledge, anywhere)
- Clear error messages if templates-src cannot be found
- Simple and maintainable solution
- Doesn't break existing workflows

### Constraints

- Must not require complex configuration
- Should fail fast with clear errors
- Minimal code changes preferred

---

## Exploration

### Option 1: Hard-code Canonical Path ⭐

**Mechanism:** Replace `find_orch_root()` call with `Path.home() / 'orch-knowledge' / 'templates-src'`

**Pros:**
- Simplest implementation (2-line change)
- No ambiguity - always knows where to look
- Fast (no search, no config)
- Matches help text's documented location

**Cons:**
- Breaks if orch-knowledge is renamed/moved
- Not portable to other users without same directory structure
- No override mechanism if needed

**Complexity:** Very Low | **Effort:** 5 minutes

---

### Option 2: Add --source Flag

**Mechanism:** `orch build global --source ~/custom/templates-src`

**Pros:**
- Flexible - can point anywhere
- Explicit - user controls location per invocation
- Good for testing alternative template sources

**Cons:**
- User must specify every time (friction)
- Doesn't solve "works from anywhere" goal (still requires flag)
- Easy to forget or mistype path

**Complexity:** Low | **Effort:** 15 minutes

---

### Option 3: Environment Variable with Fallback

**Mechanism:** Check `ORCH_TEMPLATES_SRC` env var, fall back to `~/orch-knowledge/templates-src`

**Pros:**
- Flexible for different setups (can override via env)
- Sensible default works for standard setup
- Set once in shell profile - no per-invocation friction
- Good for CI/automation
- Discoverable via help text

**Cons:**
- Environment variable to manage
- Can be misconfigured or forgotten
- Not as simple as hard-code

**Complexity:** Low | **Effort:** 10 minutes

---

### Option 4: Search Known Locations

**Mechanism:** Try these in order: 1) `~/orch-knowledge/templates-src`, 2) `~/meta-orchestration/templates-src`, 3) fail with clear error

**Pros:**
- Handles both canonical name and symlink automatically
- No configuration needed
- Discoverable

**Cons:**
- Order matters (which to check first?)
- If both exist as separate dirs (not symlinked), which wins?
- Slightly slower (multiple filesystem checks)
- More complex logic than hard-code

**Complexity:** Low | **Effort:** 10 minutes

---

## Synthesis & Recommendation

### Recommended Approach

⭐ **Option 1: Hard-code canonical path**

**Why this approach:**

1. **Aligns with operation semantics:** `orch build global` is a global operation (syncs to `~/.orch/`). It should use a canonical global source, not project-local detection.

2. **Matches existing documentation:** Help text (line 1937) already says `Source: {orch-knowledge}/templates-src/` - we're making code match docs.

3. **Session amnesia principle:** Simplest to understand - future Claude reads one line of code and knows exactly where templates live. No env vars to track, no search logic to follow.

4. **Personal tool context:** This is Dylan's orchestration system. The orch-knowledge directory is foundational infrastructure. If this becomes distributed, setup docs can explain the expected structure.

5. **Simplicity wins:** 2-line code change vs. environment variable management or search logic. Code change is more explicit and easier to debug than misconfigured env vars.

**Trade-offs accepted:**

- **Not portable without setup:** If someone else uses orch-cli, they need `~/orch-knowledge/templates-src/`
  - **Why acceptable:** This is personal tooling; minimal setup is reasonable. Better than env var they might forget to set.

- **Can't override without code edit:** No runtime configuration mechanism
  - **Why acceptable:** Template source should be stable. Changing it is rare enough that editing code is fine and makes the change explicit.

- **Breaks if directory renamed:** Hard-codes "orch-knowledge" name
  - **Why acceptable:** Renaming that directory breaks many other assumptions (it's referenced in docs, skills, etc.). It's foundational.

**Principle cited:** **Session amnesia** - Simpler code → easier for future Claude to understand and resume from.

**When this recommendation would change:**

- If orch-cli becomes distributed tool with multiple users → reconsider Option 3 (env var)
- If Dylan needs frequent template source switching → add Option 2 (--source flag)
- If template sources become multi-repo → need discovery mechanism

---

## Implementation

### Changes Made

**File:** `src/orch/cli.py` (lines 1948-1954)

**Before:**
```python
# Find orch root (where templates-src/ lives)
orch_root = find_orch_root()
if not orch_root:
    click.echo("❌ Not in a meta-orchestration directory", err=True)
    raise click.Abort()

templates_src = Path(orch_root) / 'templates-src'
if not templates_src.exists():
    click.echo(f"❌ Templates source not found: {templates_src}", err=True)
    click.echo("   Expected: meta-orchestration/templates-src/", err=True)
    raise click.Abort()
```

**After:**
```python
# Use canonical templates location (global operation → global source)
templates_src = Path.home() / 'orch-knowledge' / 'templates-src'
if not templates_src.exists():
    click.echo("❌ Templates source not found: ~/orch-knowledge/templates-src/", err=True)
    click.echo("   This is the canonical location for orchestration templates.", err=True)
    click.echo("   Ensure orch-knowledge repository exists in your home directory.", err=True)
    raise click.Abort()
```

### Testing

**Test:** Run `orch build global --dry-run` from orch-cli directory (where it previously failed)

**Result:** ✅ Success
```
🔨 Syncing global templates...
   Source: /Users/dylanconlin/orch-knowledge/templates-src
   Target: /Users/dylanconlin/.orch/templates

  📁 investigations/

📋 Dry-run: 0 file(s) would be synced, 12 up-to-date
```

---

## Key Insights

1. **Global operations need global sources:** Commands that sync to `~/.orch/` shouldn't use project-local detection.

2. **Distinction matters:** Separating "find project root" from "find canonical templates" eliminates a class of failures.

3. **Simplicity compounds:** Hard-coding canonical path is easier to understand, debug, and maintain than search/config mechanisms.

4. **Help text as specification:** The help text already documented the intended behavior - we just made code match.

---

## Related Work

- **Architecture context:** `.orch/CLAUDE.md` - Per-project orchestrators pattern
- **Spawn context:** `SPAWN_CONTEXT.md` - Problem statement and initial options

---

## Verification

- [x] All 4 phases completed (Problem Framing, Exploration, Synthesis, Externalization)
- [x] Recommendation made with trade-off analysis
- [x] Feature list reviewed (no feature list exists for this project)
- [x] Investigation artifact produced
- [x] Implementation complete and tested
- [x] Changes committed
