**TLDR:** Remove `--dangerously-skip-permissions` flag from Claude Code spawn commands. This is P4 from the --agent flag migration plan; --agent with tool restrictions is now working, making this security improvement possible. High confidence (90%).

---

# Investigation: Remove --dangerously-skip-permissions from Spawn

**Question:** How do we remove the `--dangerously-skip-permissions` flag now that --agent flag with tool restrictions is working?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** worker
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (95%)

---

## Findings

### Finding 1: Flag is used in 3 locations

**Evidence:** grep found `--dangerously-skip-permissions` in:
- `src/orch/backends/claude.py:43,55` - ClaudeBackend.build_command()
- `src/orch/spawn.py:1176,1178` - spawn_interactive() hardcoded command

**Source:** `grep -n "dangerously-skip-permissions" src/`

**Significance:** Two separate code paths need updating - backend abstraction and legacy interactive spawn.

---

### Finding 2: Tests explicitly check for the flag

**Evidence:** Tests that will fail after removal:
- `tests/test_backends_claude.py:45` - `assert "--dangerously-skip-permissions" in command`
- `tests/test_backends_base.py:180` - `assert "--dangerously-skip-permissions" in cmd_with_opts`

**Source:** grep of tests directory

**Significance:** Tests need updating as part of TDD cycle (update test expectations first).

---

### Finding 3: --agent flag support already implemented

**Evidence:** ClaudeBackend.build_command() already supports `--agent` flag:
```python
if options and options.get('agent_name'):
    agent_name = options['agent_name']
    parts.append(f"--agent {agent_name}")
```

**Source:** `src/orch/backends/claude.py:48-51`

**Significance:** The prerequisite (P3: --agent flag) is complete. P4 (remove --dangerously-skip-permissions) can proceed.

---

## Implementation Plan

### Changes Required

| File | Change |
|------|--------|
| `src/orch/backends/claude.py` | Remove `skip_permissions` variable and `parts.append(skip_permissions)` |
| `src/orch/spawn.py` | Remove `--dangerously-skip-permissions` from interactive spawn commands |
| `tests/test_backends_claude.py` | Remove assertion for the flag |
| `tests/test_backends_base.py` | Remove `skip_permissions` from test options |

### TDD Sequence

1. Update tests to NOT expect `--dangerously-skip-permissions`
2. Run tests - expect failures
3. Remove flag from implementation
4. Run tests - expect pass

---

## References

**Prior Investigation:** `.kb/investigations/2025-12-05-claude-agent-flag-for-skills.md`
- P4 in the migration plan identified this work

**Beads Issue:** orch-cli-yth
