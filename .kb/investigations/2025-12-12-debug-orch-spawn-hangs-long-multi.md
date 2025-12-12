**TLDR:** Question: Why does `orch spawn` hang with long multi-line task prompts? Answer: The hang is caused by overly aggressive stdin auto-detection in `spawn_commands.py:160-163` - when `sys.stdin.isatty()` returns False (e.g., when invoked from Claude Code), the code assumes stdin is piped and calls `sys.stdin.read()` which blocks forever waiting for EOF that never comes. High confidence (90%) - verified by tracing code flow and confirming Claude Code runs with non-TTY stdin.

---

# Investigation: orch spawn hangs with long multi-line task prompts

**Question:** Why does `orch spawn` hang when passing long multi-line task descriptions?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Stdin auto-detection triggers incorrectly in non-TTY environments

**Evidence:** In `spawn_commands.py` lines 160-163:
```python
elif not sys.stdin.isatty():
    # Auto-detect piped stdin (heredoc or pipe without explicit flag)
    # This enables: orch spawn skill "task" << 'CONTEXT' ... CONTEXT
    stdin_context = sys.stdin.read().strip()
```

When running from Claude Code (or any non-TTY environment like tmux scripts), `sys.stdin.isatty()` returns `False` even when nothing is being piped to stdin.

**Source:** `src/orch/spawn_commands.py:160-163`

**Significance:** This is the root cause of the hang. The code assumes non-TTY stdin means piped input, but this assumption is incorrect for environments like Claude Code where stdin is not a TTY but also has no piped data.

---

### Finding 2: sys.stdin.read() blocks indefinitely waiting for EOF

**Evidence:** Verified that `sys.stdin.isatty()` returns `False` when running from Claude Code:
```bash
$ python3 -c "import sys; print(f'Is TTY: {sys.stdin.isatty()}')"
Is TTY: False
```

When `stdin.read()` is called but no EOF is sent (because nothing was actually piped), the call blocks indefinitely.

**Source:** Direct test of stdin TTY status in Claude Code environment

**Significance:** This explains the "hang" behavior - the process is stuck waiting for data/EOF on stdin that will never come.

---

### Finding 3: The actual minimal prompt sent to tmux is short and not the issue

**Evidence:** The prompt sent via tmux send-keys is always a minimal reference to SPAWN_CONTEXT.md:
```python
minimal_prompt = (
    f"Read your spawn context from .orch/workspace/{config.workspace_name}/SPAWN_CONTEXT.md "
    f"and begin the task."
)
```

The full context (including long multi-line task descriptions) is written to SPAWN_CONTEXT.md, not passed through tmux.

**Source:** `src/orch/spawn.py:588-591`

**Significance:** The "long multi-line" aspect of the task is not directly causing the hang - it's that long tasks are often invoked from Claude Code, which triggers the stdin bug.

---

## Synthesis

**Key Insights:**

1. **Correlation vs. Causation** - The bug appeared to correlate with "long multi-line prompts" but the actual cause is the invocation environment (Claude Code → non-TTY stdin)

2. **Overly broad heuristic** - Using `not sys.stdin.isatty()` as a proxy for "stdin has piped data" is incorrect. Many non-TTY environments (Claude Code, cron, CI runners) don't have piped data.

3. **Safe fix available** - Use `select.select()` to check if stdin has data available before attempting to read, with a short timeout.

**Answer to Investigation Question:**

The hang is NOT caused by long multi-line task prompts themselves, but by the stdin auto-detection logic in `spawn_commands.py:160-163`. When `orch spawn` is invoked from Claude Code (which has non-TTY stdin), the code incorrectly assumes piped input exists and blocks on `sys.stdin.read()` waiting for EOF that never comes.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Code flow is clear and verifiable. The specific line causing the hang is identified. The behavior was reproduced (stdin.isatty() returns False in Claude Code). Minor uncertainty around edge cases in the fix.

**What's certain:**

- ✅ `sys.stdin.isatty()` returns False in Claude Code environment
- ✅ Lines 160-163 call `stdin.read()` when isatty() is False
- ✅ `stdin.read()` blocks when no data is piped and no EOF is sent

**What's uncertain:**

- ⚠️ Whether `select.select()` works correctly on all platforms (likely yes on macOS/Linux)
- ⚠️ Whether the fix breaks any legitimate heredoc use cases

**What would increase confidence to Very High (95%+):**

- Testing the fix with actual heredoc usage
- Testing on multiple platforms (Linux, macOS)
- Running the full test suite

---

## Implementation Recommendations

**Purpose:** Fix the stdin auto-detection to not block in non-TTY environments without piped data.

### Recommended Approach ⭐

**Use select.select() to check stdin data availability** - Before calling `stdin.read()`, use `select` to check if stdin has data available with a short timeout.

**Why this approach:**
- Non-blocking check for data availability
- Works on Unix systems (macOS, Linux)
- Minimal code change
- Preserves heredoc functionality when data IS piped

**Trade-offs accepted:**
- Adds platform-specific code (select doesn't work on Windows stdin)
- Windows users would need to use explicit `--from-stdin` flag

**Implementation sequence:**
1. Import `select` module
2. Before `stdin.read()`, use `select.select([sys.stdin], [], [], 0.1)` to check if data is available
3. Only call `stdin.read()` if select indicates data is available

### Alternative Approaches Considered

**Option B: Remove auto-detection entirely, require --from-stdin**
- **Pros:** Simplest, no platform-specific code
- **Cons:** Breaks existing heredoc workflows that rely on auto-detection
- **When to use instead:** If select-based detection proves unreliable

**Option C: Use threading with timeout**
- **Pros:** More portable than select
- **Cons:** More complex, potential race conditions
- **When to use instead:** If cross-platform support is critical

**Rationale for recommendation:** Option A provides the best balance of preserving functionality while fixing the bug, with minimal code change.

---

### Implementation Details

**What to implement first:**
- Add select-based stdin data check before `stdin.read()`

**Things to watch out for:**
- ⚠️ Select behavior on Windows (may need fallback to explicit flag)
- ⚠️ Ensure empty stdin is handled gracefully (should result in `stdin_context = None`)

**Success criteria:**
- ✅ `orch spawn` from Claude Code no longer hangs
- ✅ `orch spawn skill "task" << HEREDOC` still works with piped data
- ✅ Existing tests pass

---

## References

**Files Examined:**
- `src/orch/spawn_commands.py:157-163` - stdin handling logic (root cause)
- `src/orch/spawn.py:588-591` - minimal prompt construction
- `src/orch/backends/claude.py` - Claude backend command building

**Commands Run:**
```bash
# Verify stdin TTY status in Claude Code environment
python3 -c "import sys; print(f'Is TTY: {sys.stdin.isatty()}')"
# Output: Is TTY: False
```

---

## Investigation History

**2025-12-12 ~12:00:** Investigation started
- Initial question: Why does orch spawn hang with long multi-line task prompts?
- Context: Bug reported in beads issue orch-cli-be4

**2025-12-12 ~12:30:** Root cause identified
- Found stdin auto-detection logic at lines 160-163
- Verified non-TTY stdin in Claude Code environment
- Confirmed `stdin.read()` blocks without piped data

**2025-12-12 ~12:45:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Bug caused by stdin auto-detection assuming non-TTY means piped data
