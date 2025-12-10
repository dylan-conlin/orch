**TLDR:** Question: Why does the --mcp flag cause prompts to be consumed as config arguments? Answer: The `--mcp-config <configs...>` CLI option is variadic, consuming all subsequent arguments until another option or `--` separator is encountered. Without `--`, the prompt was being interpreted as an MCP config path. Fix: Add `--` separator before the prompt in build_command(). Very High confidence (95%) - fix is minimal and targeted.

---

# Investigation: Fix --mcp flag: add -- separator before prompt

**Question:** Why does using `--mcp` with `orch spawn` cause prompt parsing issues?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: --mcp-config is a variadic option

**Evidence:** From `claude --help`:
```
--mcp-config <configs...>  Load MCP servers from JSON files or strings (space-separated)
```

The `<configs...>` notation indicates this is a variadic option that accepts multiple space-separated values until it encounters:
1. Another option flag (starting with `-`)
2. The POSIX end-of-options separator `--`
3. End of arguments

**Source:** `claude --help` output

**Significance:** This explains why the prompt following `--mcp-config` was being consumed as part of the MCP config arguments rather than as the positional prompt argument.

---

### Finding 2: build_command() added prompt directly after options

**Evidence:** In `backends/claude.py:163-167` (before fix):
```python
# Shell-quote the prompt for safety
quoted_prompt = shlex.quote(prompt)
parts.append(quoted_prompt)

return " ".join(parts)
```

The prompt was appended directly after any options, with no `--` separator.

**Source:** `src/orch/backends/claude.py:163-167`

**Significance:** This is the root cause - without `--`, the variadic `--mcp-config` option would consume the prompt as another config value.

---

### Finding 3: Fix is minimal and POSIX-standard

**Evidence:** The POSIX convention for signaling end of options is to use `--`. This is universally supported by argument parsers and is the standard solution for this class of problem.

Generated command now looks like:
```
~/.orch/scripts/claude-code-wrapper.sh --allowed-tools '*' --dangerously-skip-permissions --mcp-config '/path/to/config.json' -- 'Your prompt here'
```

**Source:** POSIX convention, Claude CLI documentation

**Significance:** The fix is minimal (single line addition), follows established conventions, and doesn't require changes to the Claude CLI itself.

---

## Synthesis

**Key Insights:**

1. **Variadic options consume until stopped** - Options like `--mcp-config <configs...>` will consume all following arguments unless explicitly stopped with `--`.

2. **POSIX `--` is the standard solution** - Adding `--` before positional arguments is the established convention for preventing option parsing issues.

3. **Fix is defensive** - Even though the bug only manifests with `--mcp-config`, adding `--` before the prompt protects against similar issues with any future variadic options.

**Answer to Investigation Question:**

The `--mcp` flag causes prompt parsing issues because it uses `--mcp-config <configs...>`, a variadic option that consumes multiple space-separated values. Without a `--` separator, the prompt following the config path was being interpreted as another config value. The fix adds `--` before the prompt in `build_command()` to explicitly signal the end of options.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

The fix is minimal, follows POSIX conventions, and was verified with tests. The root cause is clearly understood based on Claude CLI documentation.

**What's certain:**

- ✅ `--mcp-config <configs...>` is variadic (confirmed via `claude --help`)
- ✅ Adding `--` before prompt prevents the issue (POSIX standard)
- ✅ All 28 tests pass including new regression test

**What's uncertain:**

- ⚠️ Haven't manually tested with live Claude CLI invocation (though this would be caught in integration testing)

**What would increase confidence to 100%:**

- Manual end-to-end test with actual `orch spawn --mcp` invocation

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add `--` separator before prompt** - Single line fix that follows POSIX conventions.

**Why this approach:**
- Minimal change (1 line)
- Follows established conventions
- Defensive against future variadic options

**Trade-offs accepted:**
- Command is slightly longer (4 characters)
- This is acceptable - clarity > brevity

**Implementation sequence:**
1. Add `--` separator in `build_command()` ✅
2. Add regression test ✅
3. Run tests to verify ✅

---

## References

**Files Examined:**
- `src/orch/backends/claude.py:119-172` - build_command() method
- `tests/test_backends_claude.py` - Existing test coverage

**Commands Run:**
```bash
# Check Claude CLI help
claude --help

# Run tests
python -m pytest tests/test_backends_claude.py -v
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-10-debug-fix-mcp-flag-write-config.md` - Related MCP config issue (file-based config)

---

## Investigation History

**2025-12-10 10:15:** Investigation started
- Initial question: Why does --mcp flag cause prompt parsing issues?
- Context: Bug reported in orch-cli spawn command

**2025-12-10 10:20:** Root cause identified
- Found --mcp-config is variadic option
- POSIX `--` separator needed

**2025-12-10 10:25:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Fix implemented - add `--` separator before prompt in build_command()
