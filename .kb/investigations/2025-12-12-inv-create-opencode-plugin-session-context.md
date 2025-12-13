**TLDR:** Question: How to implement OpenCode plugin for session context loading equivalent to load-orchestration-context.py? Answer: Created `.opencode/plugin/session-context.ts` that uses `session.created` event and `client.session.prompt({ noReply: true })` API to inject orchestration context. High confidence (85%) - plugin syntax valid, but requires live OpenCode testing.

---

# Investigation: Create OpenCode Plugin for Session Context Loading

**Question:** How to implement an OpenCode plugin that loads orchestration context at session start, equivalent to the Claude Code SessionStart hook in load-orchestration-context.py?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: OpenCode Uses Plugin System, Not Command Hooks

**Evidence:**

OpenCode documentation (https://opencode.ai/docs/plugins/) shows plugins are:
1. JavaScript/TypeScript modules in `.opencode/plugin/` or `~/.config/opencode/plugin/`
2. Export functions that return event handlers
3. Receive context: `{ project, client, $, directory, worktree }`
4. Use `session.created` event for session start (equivalent to Claude Code's SessionStart hook)

Prior investigation confirmed: `.kb/investigations/2025-12-12-inv-audit-hooks-opencode-compatibility.md`

**Source:** 
- OpenCode docs: https://opencode.ai/docs/plugins/
- Prior investigation audit

**Significance:** Must implement as TypeScript plugin, not Python command hook. The `session.created` event is the equivalent trigger.

---

### Finding 2: Context Injection via session.prompt with noReply

**Evidence:**

OpenCode SDK (https://opencode.ai/docs/sdk/) shows:
```typescript
// Inject context without triggering AI response (useful for plugins)
await client.session.prompt({
  path: { id: session.id },
  body: {
    noReply: true,
    parts: [{ type: "text", text: "Context to inject" }],
  },
})
```

This is the equivalent of Claude Code's `additionalContext` field in the SessionStart hook response.

**Source:** OpenCode SDK documentation, Sessions API section

**Significance:** The `noReply: true` option allows injecting context as a user message without triggering an AI response - perfect for loading orchestration context at session start.

---

### Finding 3: Plugin Implementation Complete

**Evidence:**

Created `.opencode/plugin/session-context.ts` with:
- `session.created` event handler
- Detection of `.orch/` directory (orch project detection)
- Loading orchestrator skill from `~/.claude/skills/orchestrator/SKILL.md`
- Loading active agents via `orch status --format json`
- Loading recent kn entries via `kn recent --limit 10`
- Context injection via `client.session.prompt({ noReply: true })`

Plugin syntax validated with bun build - compiles successfully.

**Source:** `.opencode/plugin/session-context.ts`

**Significance:** Plugin is syntactically complete and follows OpenCode plugin patterns.

---

## Synthesis

**Key Insights:**

1. **API Parity Achieved** - The OpenCode plugin system provides equivalent functionality to Claude Code hooks via `session.created` event and `client.session.prompt({ noReply: true })`.

2. **Self-contained Types** - Defined inline types to avoid dependency on `@opencode-ai/plugin` package, making the plugin zero-dependency.

3. **Worker Detection** - Preserved `ORCH_WORKER` environment variable check to skip context loading for worker agents (they get skill embedded in SPAWN_CONTEXT.md).

**Answer to Investigation Question:**

The OpenCode plugin implementation uses:
- `session.created` event (equivalent to SessionStart hook)
- `client.session.prompt({ path: { id: sessionId }, body: { noReply: true, parts: [...] } })` for context injection
- Same logic as Python hook: detect orch project, load skill, load agents, load kn entries

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**

- Plugin syntax validated with bun build (compiles successfully)
- API usage matches OpenCode SDK documentation
- Logic mirrors existing Python hook (proven working)

**What's certain:**

- Plugin file location (`.opencode/plugin/`) is correct per docs
- Event name `session.created` is correct per docs
- `client.session.prompt({ noReply: true })` API exists per SDK docs
- TypeScript/Bun syntax is valid (build succeeds)

**What's uncertain:**

- Whether `event.properties?.sessionID` is populated correctly at runtime
- Whether `$` shell helper works as expected for subprocess calls
- Actual behavior when loaded by OpenCode (requires live testing)

**What would increase confidence to Very High (95%+):**

- Live testing with OpenCode CLI
- Verification that context appears in session
- Confirmation that `orch status` and `kn recent` commands execute correctly from plugin

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation.

### Recommended Approach: Plugin-Based Context Loading

**What was implemented:** `.opencode/plugin/session-context.ts`

**Why this approach:**
- Aligns with OpenCode's official extension mechanism
- Uses documented SDK APIs (`client.session.prompt`)
- Zero external dependencies (inline types)
- Mirrors existing Python hook logic for consistency

**Trade-offs accepted:**
- Must maintain two codebases (Python hook for Claude Code, TS plugin for OpenCode)
- Requires OpenCode runtime to test (can't unit test easily)

### Testing Approach

1. Install/update OpenCode to latest version
2. Start OpenCode in orch-cli directory: `opencode`
3. Verify plugin loads (check OpenCode logs for `[session-context]` messages)
4. Verify context appears in session

---

## References

**Files Created:**
- `.opencode/plugin/session-context.ts` - Main plugin implementation

**Files Examined:**
- `hooks/load-orchestration-context.py` - Reference Python implementation
- `.kb/investigations/2025-12-12-inv-audit-hooks-opencode-compatibility.md` - Prior investigation
- `opencode.json` - Current OpenCode config

**Commands Run:**
```bash
# Verify plugin syntax
bun build .opencode/plugin/session-context.ts --outdir /tmp/test-plugin

# Result: Bundled 3 modules - syntax valid
```

**External Documentation:**
- https://opencode.ai/docs/plugins/ - OpenCode plugin system
- https://opencode.ai/docs/sdk/ - OpenCode SDK (session.prompt API)

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-12-inv-audit-hooks-opencode-compatibility.md` - Hook compatibility audit

---

## Self-Review

- [x] Real test performed (bun build validation)
- [x] Conclusion from evidence (docs + code analysis)
- [x] Question answered (plugin implementation complete)
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-12 18:30:** Investigation started
- Initial question: How to implement OpenCode session context plugin?
- Context: Spawned from beads issue orch-cli-84ff

**2025-12-12 18:35:** Reviewed prior investigation and OpenCode docs
- Found `session.created` event equivalent to SessionStart
- Found `client.session.prompt({ noReply: true })` for context injection

**2025-12-12 18:45:** Implemented plugin
- Created `.opencode/plugin/session-context.ts`
- Validated syntax with bun build

**2025-12-12 18:50:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Plugin implementation complete, awaits live testing
