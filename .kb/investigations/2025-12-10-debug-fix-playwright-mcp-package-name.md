**TLDR:** Question: Why do BUILTIN_MCP_SERVERS fail with "No such tool available"? Answer: All three package names were wrong - `@anthropic/mcp-*` packages don't exist. Fixed to use correct packages: `@playwright/mcp`, `browser-use-mcp`, `@modelcontextprotocol/server-puppeteer`. High confidence (95%) - verified via npm registry queries.

---

# Investigation: Fix BUILTIN_MCP_SERVERS Wrong NPM Package Names

**Question:** Why do built-in MCP server configurations fail to start?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: All @anthropic/mcp-* packages don't exist

**Evidence:**
```bash
$ npm view @anthropic/mcp-playwright version
# NOT FOUND

$ npm view @anthropic/mcp-browser-use version
# NOT FOUND

$ npm view @anthropic/mcp-puppeteer version
# NOT FOUND
```

**Source:** npm registry queries, `src/orch/backends/claude.py:19-32`

**Significance:** The BUILTIN_MCP_SERVERS dictionary used fictional package names. When Claude Code tried to run these via `npx -y`, the packages would fail to install, causing MCP server startup to fail entirely.

---

### Finding 2: Correct package names verified

**Evidence:**
```bash
$ npm view @playwright/mcp version
0.0.51

$ npm view browser-use-mcp version
1.3.0

$ npm view @modelcontextprotocol/server-puppeteer version
2025.5.12
```

**Source:** npm registry queries

**Significance:** All three correct packages exist and have active versions. These are the actual MCP server implementations for each browser automation tool.

---

### Finding 3: Prior investigation identified root cause

**Evidence:** `.kb/investigations/2025-12-10-inv-test-mcp-only-flag-use.md` documented:
- Test of `--mcp-only` flag failed
- Playwright MCP tools unavailable
- Package name mismatch identified via npm queries

**Source:** Prior investigation file

**Significance:** The root cause was already identified - this task was to implement the fix.

---

## Synthesis

**Key Insights:**

1. **Package naming pattern was wrong** - The code assumed Anthropic maintains MCP packages under `@anthropic/mcp-*` namespace, but actual packages are published by their respective tool maintainers.

2. **Cascading failure** - When MCP server startup fails, `--strict-mcp-config` causes Claude Code to disable ALL MCP tools, not just the failing ones.

3. **Simple fix** - Correcting the package names in the dictionary is sufficient; no structural changes needed.

**Answer to Investigation Question:**

Built-in MCP server configurations failed because all three package names were incorrect:
- `@anthropic/mcp-playwright@latest` → `@playwright/mcp@latest`
- `@anthropic/mcp-browser-use@latest` → `browser-use-mcp@latest`
- `@anthropic/mcp-puppeteer@latest` → `@modelcontextprotocol/server-puppeteer@latest`

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

Direct verification via npm registry queries confirms the packages exist and have versions.

**What's certain:**

- ✅ Old package names don't exist (verified via `npm view`)
- ✅ New package names exist with active versions
- ✅ All 31 tests pass after the fix

**What's uncertain:**

- ⚠️ Haven't verified MCP servers actually work end-to-end with spawned agents (requires manual test)

**What would increase confidence to 100%:**

- Manual test of `orch spawn --mcp-servers=playwright` confirming tools are available

---

## Implementation Recommendations

### Recommended Approach ⭐

**Update BUILTIN_MCP_SERVERS** - Change package names to correct npm packages

**Why this approach:**
- Root cause is confirmed
- Simple one-line-per-server fix
- No structural changes needed

**Trade-offs accepted:**
- Package names may change in future (acceptable, can update as needed)

**Implementation sequence:**
1. Update `src/orch/backends/claude.py` lines 19-32
2. Run tests to verify no regressions
3. Commit with descriptive message

### Implementation Details

**Changes made:**
- `@anthropic/mcp-playwright@latest` → `@playwright/mcp@latest`
- `@anthropic/mcp-browser-use@latest` → `browser-use-mcp@latest`
- `@anthropic/mcp-puppeteer@latest` → `@modelcontextprotocol/server-puppeteer@latest`

**Things to watch out for:**
- ⚠️ Future package renames would require updates here
- ⚠️ browser-use-mcp requires `~/.config/browseruse/config.json` for best results

**Success criteria:**
- ✅ All 31 backend tests pass
- ✅ Package names verified via npm registry

---

## References

**Files Examined:**
- `src/orch/backends/claude.py:19-32` - BUILTIN_MCP_SERVERS definition
- `.kb/investigations/2025-12-10-inv-test-mcp-only-flag-use.md` - Prior investigation identifying root cause

**Commands Run:**
```bash
# Verify correct packages exist
npm view @playwright/mcp version  # 0.0.51
npm view browser-use-mcp version  # 1.3.0
npm view @modelcontextprotocol/server-puppeteer version  # 2025.5.12

# Verify old packages don't exist
npm view @anthropic/mcp-playwright version  # NOT FOUND
npm view @anthropic/mcp-browser-use version  # NOT FOUND
npm view @anthropic/mcp-puppeteer version  # NOT FOUND

# Run tests
python -m pytest tests/test_backends_claude.py -v  # 31 passed
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-10-inv-test-mcp-only-flag-use.md` - Original identification of wrong package names

---

## Investigation History

**2025-12-10 ~11:00:** Investigation started
- Initial question: Why do built-in MCP servers fail?
- Context: Prior investigation identified wrong package names, this task implements fix

**2025-12-10 ~11:05:** Root cause verified
- Confirmed all @anthropic/mcp-* packages don't exist
- Identified correct package names via npm registry

**2025-12-10 ~11:08:** Fix implemented
- Updated BUILTIN_MCP_SERVERS in claude.py
- All 31 tests pass

**2025-12-10 ~11:10:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Fixed 3 package names in BUILTIN_MCP_SERVERS
