**TLDR:** Question: How to optimize orch spawn output for Claude Code display? Answer: Current show_preview() outputs 20+ line decorative box making key info hard to find; replace with compact first-line summary showing skill/project/task for non-interactive mode. High confidence (85%) - code analysis clear, needs testing.

---

# Investigation: Optimize orch spawn output for Claude Code display

**Question:** How can we make orch spawn output scannable with key info visible in first line?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** worker-agent
**Phase:** Synthesizing
**Next Step:** Implement compact summary output
**Status:** In Progress
**Confidence:** High (85%)

---

## Findings

### Finding 1: show_preview() outputs 20+ line decorative box

**Evidence:** The `show_preview()` function (lines 336-416 in spawn.py) outputs:
- Box border chars (╭╮╰╯│─)
- Project, Workspace, Skill on separate lines
- Task (can wrap to multiple lines)
- Empty spacer lines
- Deliverables section (3-5 lines)
- Context section (5-6 lines)
- More box borders

Total: ~22-28 lines depending on task length and deliverables.

**Source:** `src/orch/spawn.py:336-416`

**Significance:** This verbose output gets truncated/collapsed in Claude Code, burying key info.

---

### Finding 2: Key spawn info scattered across multiple lines

**Evidence:** Current output structure:
```
╭─ orch spawn ─────────...
│
│ Project:    orch-cli
│ Workspace:  feat-xyz-11dec
│ Skill:      🔧 feature-impl
│
│ Task:       Optimize spawn output...
│
│ Deliverables:
│   ✓ Investigation:  ...
│   ○ Tests:          ...
...
```

The most important info (skill, project, task) requires reading 6+ lines deep.

**Source:** `src/orch/spawn.py:354-376`

**Significance:** For quick scanning, need all key info in first 1-2 lines.

---

### Finding 3: Two spawn paths - interactive and non-interactive

**Evidence:**
- Non-interactive (from orchestrator): `yes=True` or auto-detected via `not sys.stdin.isatty()`
- Interactive (human): Shows preview, prompts for confirmation

Non-interactive path (lines 1439-1446) auto-skips confirmation but still shows full preview.

**Source:** `src/orch/spawn.py:1439-1446, 1603-1614`

**Significance:** Non-interactive mode doesn't need verbose preview - can show compact summary only.

---

## Synthesis

**Key Insights:**

1. **Output designed for humans, not AI agents** - Decorative box format suits terminal users who scan visually, not AI agents or collapsed CLI output

2. **Non-interactive mode should be compact** - When spawning from orchestrator, verbose preview provides no value and buries key info

3. **First-line summary pattern** - Other CLI tools use format like `✅ spawned: [skill] → [project] "task..."` for quick scanning

**Answer to Investigation Question:**

Replace verbose preview with compact first-line summary for non-interactive mode. Format: `✅ spawning: [emoji] [skill] → [project] "[task...]"`. Keep full preview for interactive mode since humans benefit from detailed view.

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**
Code analysis is clear about current behavior. Solution approach is straightforward refactoring.

**What's certain:**
- ✅ show_preview() is source of verbose output
- ✅ Non-interactive mode auto-detected via TTY check
- ✅ Key info is project, skill, task (already available)

**What's uncertain:**
- ⚠️ Exact formatting for compact summary (needs iteration)
- ⚠️ Whether to show any preview in non-interactive mode

---

## Implementation Recommendations

### Recommended Approach: Compact summary for non-interactive mode

**Why this approach:**
- Non-interactive spawns (from orchestrator) don't need verbose preview
- First-line summary enables quick scanning
- Preserves full preview for interactive human use

**Implementation sequence:**
1. Add `verbose` parameter to `show_preview()` (default True)
2. Create `show_compact_summary()` function for one-liner
3. Use compact summary when `yes=True` (non-interactive)

---

## References

**Files Examined:**
- `src/orch/spawn.py:336-416` - show_preview() function
- `src/orch/spawn.py:1439-1446` - non-interactive detection
- `src/orch/spawn.py:1668-1698` - final spawn output

---

## Investigation History

**2025-12-11 10:30:** Investigation started
- Initial question: How to optimize spawn output for Claude Code?
- Context: Issue orch-cli-8gq reports 29 lines collapsed, key info buried
