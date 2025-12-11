**TLDR:** Question: Are BUILTIN_MCP_SERVERS package names correct? Answer: Yes - already fixed in commit ba6900d (Dec 10). All three packages verified via npm and all 18 MCP tests pass.

---

# Investigation: Verify BUILTIN_MCP_SERVERS Fix

**Question:** Are the BUILTIN_MCP_SERVERS npm package names correct in claude.py?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (100%)

---

## Findings

### Finding 1: Fix Already Applied

**Evidence:**
```bash
$ git show ba6900d --oneline
ba6900d fix(mcp): use correct npm package names in BUILTIN_MCP_SERVERS
```

Commit `ba6900d` (Dec 10, 2025) already fixed the package names:
- `@playwright/mcp` (was `@anthropic/mcp-playwright`)
- `browser-use-mcp` (was `@anthropic/mcp-browser-use`)
- `@modelcontextprotocol/server-puppeteer` (was `@anthropic/mcp-puppeteer`)

**Source:** Git history, `src/orch/backends/claude.py:19-32`

**Significance:** The bug reported in beads issue orch-cli-3o5 was already resolved. The issue wasn't closed properly after the fix.

---

### Finding 2: Current Package Names Verified

**Evidence:**
```bash
$ npm view @playwright/mcp version
0.0.52

$ npm view browser-use-mcp version
1.3.0

$ npm view @modelcontextprotocol/server-puppeteer version
2025.5.12
```

**Source:** npm registry queries (Dec 11, 2025)

**Significance:** All three packages exist in npm registry with current versions.

---

### Finding 3: All Tests Pass

**Evidence:**
```bash
$ python -m pytest tests/test_backends_claude.py -v -k mcp
18 passed, 13 deselected in 0.09s
```

**Source:** Test run Dec 11, 2025

**Significance:** No regressions from the fix.

---

## Synthesis

**Answer to Investigation Question:**

Yes, the BUILTIN_MCP_SERVERS package names are correct. The fix was applied in commit `ba6900d` on December 10, 2025. This beads issue (`orch-cli-3o5`) should have been closed at that time but wasn't, leading to this duplicate spawn.

**Root Cause of Process Issue:**
The previous worker completed Phase: Complete in the investigation file but didn't run `bd close` or the orchestrator didn't verify and close the issue.

---

## References

**Files Examined:**
- `src/orch/backends/claude.py:19-32` - BUILTIN_MCP_SERVERS (verified correct)
- `.kb/investigations/2025-12-10-debug-fix-playwright-mcp-package-name.md` - Original fix investigation

**Commits:**
- `ba6900d` - fix(mcp): use correct npm package names in BUILTIN_MCP_SERVERS

---

## Investigation History

**2025-12-11 13:10:** Investigation started
- Spawned to fix BUILTIN_MCP_SERVERS issue
- Found fix already applied in commit ba6900d

**2025-12-11 13:12:** Verification complete
- All npm packages verified
- All 18 MCP tests pass
- Status: Complete (duplicate/already-fixed)
