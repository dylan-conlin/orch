**TLDR:** Question: How to add a flag to disable global MCP servers in orch spawn? Answer: Claude Code has `--strict-mcp-config` flag that makes it only use MCP servers from `--mcp-config`, ignoring all other configurations. Added `--mcp-only` option to `orch spawn` that passes this flag through. High confidence (95%) - implementation tested via unit tests.

---

# Investigation: Add --mcp-only flag to disable global MCP servers

**Question:** How to add an option to orch spawn that disables global MCP servers and only uses specified ones?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Claude Code has --strict-mcp-config flag

**Evidence:** `claude --help` shows:
```
--strict-mcp-config                               Only use MCP servers from --mcp-config, ignoring all other MCP configurations
```

**Source:** `claude --help` output

**Significance:** This is exactly the flag needed. We just need to pass it through when user specifies `--mcp-only`.

---

### Finding 2: Existing MCP handling in orch-cli

**Evidence:**
- `SpawnConfig` dataclass has `mcp_servers: Optional[str]` field (spawn.py:139)
- `spawn_commands.py` has `--mcp` option that takes comma-separated server names
- `ClaudeBackend.build_command()` resolves MCP servers and adds `--mcp-config` flag
- Backend options are passed via dict from spawn.py:619-622

**Source:**
- `src/orch/spawn.py:138-139`
- `src/orch/spawn_commands.py:97`
- `src/orch/backends/claude.py:154-161`

**Significance:** The existing infrastructure makes adding `mcp_only` straightforward - just add the field and pass it through the same path.

---

## Synthesis

**Key Insights:**

1. **Claude Code already supports this** - The `--strict-mcp-config` flag does exactly what's needed.

2. **Clean integration path** - Follow the same pattern as `mcp_servers`: add to SpawnConfig, spawn command, and ClaudeBackend.

3. **Independent of mcp_servers** - `--mcp-only` can be used with or without `--mcp` servers specified.

**Answer to Investigation Question:**

Add `--mcp-only` flag to `orch spawn` that passes `--strict-mcp-config` to Claude Code. Implementation requires changes in:
1. `SpawnConfig` dataclass (add `mcp_only: bool = False`)
2. `spawn_commands.py` (add `--mcp-only` click option)
3. `spawn.py` (pass `mcp_only` to backend_options)
4. `ClaudeBackend.build_command()` (add `--strict-mcp-config` when `mcp_only=True`)

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Implementation is straightforward, follows existing patterns, and all tests pass.

**What's certain:**

- Claude Code has the `--strict-mcp-config` flag
- The implementation follows existing MCP handling patterns
- All unit tests pass (18 MCP-related tests including 3 new ones)

**What's uncertain:**

- End-to-end testing wasn't performed (would require actual spawn)

---

## Implementation Recommendations

### Recommended Approach (Implemented)

**Add --mcp-only flag** - Pass through to Claude Code's `--strict-mcp-config`

**Implementation sequence:**
1. Add `mcp_only: bool = False` to SpawnConfig dataclass
2. Add `mcp_only: bool = False` parameter to `spawn_with_skill()` function
3. Add `--mcp-only` Click option to spawn command
4. Pass `mcp_only` through all 4 spawn call sites
5. Pass `mcp_only` to backend_options in spawn.py
6. Add `--strict-mcp-config` to command when `mcp_only=True` in ClaudeBackend

---

## References

**Files Modified:**
- `src/orch/spawn.py` - SpawnConfig, spawn_with_skill, backend_options
- `src/orch/spawn_commands.py` - --mcp-only option, 4 call sites
- `src/orch/backends/claude.py` - build_command with --strict-mcp-config
- `tests/test_backends_claude.py` - 3 new tests for mcp_only

**Commands Run:**
```bash
# Check Claude Code flags
claude --help | grep mcp

# Run tests
python -m pytest tests/ -v -k mcp
```

---

## Investigation History

**2025-12-10 10:36:** Investigation started
- Initial question: How to disable global MCP servers in orch spawn?
- Context: Feature request to add --mcp-only flag

**2025-12-10 10:40:** Found --strict-mcp-config flag in Claude Code
- Discovery: Claude Code already has the exact flag needed

**2025-12-10 10:55:** Implementation complete
- All changes made, tests written and passing
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Added --mcp-only flag that passes --strict-mcp-config to Claude Code
