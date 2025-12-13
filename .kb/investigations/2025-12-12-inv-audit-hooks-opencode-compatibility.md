**TLDR:** Question: Are existing orch-cli hooks compatible with OpenCode? Answer: No - Claude Code uses command-based hooks with JSON stdin/stdout protocol while OpenCode uses a JavaScript/TypeScript plugin system with event subscriptions. The `load-orchestration-context.py` hook has partial OpenCode support via `--opencode` flag but `block-bd-close.py` has no OpenCode equivalent. High confidence (90%) - validated against OpenCode documentation and actual hook tests.

---

# Investigation: Audit Hooks for OpenCode Compatibility

**Question:** Are the hooks in orch-cli/hooks/ compatible with OpenCode, and what changes are needed for full compatibility?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Fundamentally Different Hook Architectures

**Evidence:** 

Claude Code hooks use:
- **Command-based execution**: External scripts triggered by lifecycle events
- **JSON protocol**: Input via stdin, output via stdout with specific JSON structure
- **Matcher-based filtering**: `"matcher": "Bash"` to filter which tools trigger hooks
- **Hook types**: `SessionStart`, `SessionEnd`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`

OpenCode plugins use:
- **JavaScript/TypeScript modules**: Code running inside the OpenCode process
- **Event subscriptions**: Functions registered to event names
- **Direct API access**: `client`, `$` (shell), `project` context passed to plugin
- **Event types**: `session.created`, `session.idle`, `tool.execute.before`, `tool.execute.after`, etc.

**Source:** 
- OpenCode docs: https://opencode.ai/docs/plugins/
- Claude Code settings: `~/.claude/settings.json:114-236`
- Hooks in repo: `hooks/load-orchestration-context.py`, `hooks/block-bd-close.py`

**Significance:** These are incompatible systems. Existing Python hooks cannot be directly used with OpenCode - they need to be rewritten as JavaScript/TypeScript plugins or wrapped in a plugin that calls them externally.

---

### Finding 2: load-orchestration-context.py Has Partial OpenCode Support

**Evidence:**

The repo version (`hooks/load-orchestration-context.py:22-34`) includes OpenCode installation instructions:
```python
# Installation (OpenCode):
#   Add to opencode.json in project root:
#   {
#     "experimental": {
#       "hook": {
#         "session_started": [
#           {
#             "command": ["python3", "hooks/load-orchestration-context.py", "--opencode"]
#           }
#         ]
#       }
#     }
#   }
```

And implements `--opencode` flag (line 139-141, 195-206):
- Skips JSON stdin parsing when `--opencode` is set
- Outputs plain text instead of JSON protocol

**Test result:**
```bash
$ python3 hooks/load-orchestration-context.py --opencode 2>&1 | head -50
# Orchestration Context
*Auto-loaded via session hook (OpenCode)*
[... orchestrator skill content ...]
```

**Source:** `hooks/load-orchestration-context.py:22-35, 139-141, 148-158, 195-206`

**Significance:** This hook has OpenCode support, BUT:
1. Uses `experimental.hook.session_started` which may not exist in current OpenCode (docs only show plugin system)
2. The deployed version in `~/.orch/hooks/` does NOT have this OpenCode support
3. Current `opencode.json` in repo doesn't configure this hook - only has `instructions`

---

### Finding 3: block-bd-close.py Has No OpenCode Support and Python Compatibility Issue

**Evidence:**

1. **No OpenCode support**: The hook only handles Claude Code's JSON protocol:
   ```python
   # line 78-84
   def main():
       try:
           input_data = json.load(sys.stdin)  # Claude Code protocol
       except json.JSONDecodeError:
           sys.exit(0)
   ```

2. **Python version compatibility issue**: Uses `dict | None` syntax (line 37) which requires Python 3.10+:
   ```
   $ python3 hooks/block-bd-close.py
   TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
   ```
   System Python is 3.9.6.

3. **OpenCode equivalent would need**: A plugin using `tool.execute.before` event to intercept Bash commands.

**Source:** 
- `hooks/block-bd-close.py:37, 78-84`
- `~/.orch/hooks/gate-bd-close.py` (deployed version uses `#!/opt/homebrew/bin/python3.12`)

**Significance:** This hook:
- Cannot work with OpenCode without being rewritten as a plugin
- Has Python compatibility issues in the repo version
- The deployed version (`~/.orch/hooks/gate-bd-close.py`) is a different implementation with Python 3.12 shebang

---

### Finding 4: OpenCode Uses Plugin System, Not Command Hooks

**Evidence:**

OpenCode documentation (https://opencode.ai/docs/plugins/) shows plugins are:
1. JavaScript/TypeScript modules in `.opencode/plugin/` or `~/.config/opencode/plugin/`
2. Export functions that return event handlers
3. Receive context: `{ project, client, $, directory, worktree }`

Example plugin structure:
```javascript
export const MyPlugin = async ({ project, client, $, directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath.includes(".env")) {
        throw new Error("Do not read .env files")
      }
    },
  }
}
```

The `experimental.hook` syntax mentioned in `load-orchestration-context.py` doesn't appear in current OpenCode docs.

**Source:** OpenCode plugins documentation, `hooks/load-orchestration-context.py:22-34`

**Significance:** The OpenCode hook documentation in `load-orchestration-context.py` may be outdated. Current OpenCode uses a pure plugin system.

---

### Finding 5: Deployed Hooks Diverge from Repo Hooks

**Evidence:**

| Hook | Repo Version | Deployed Version (~/.orch/hooks/) |
|------|--------------|-----------------------------------|
| `load-orchestration-context.py` | Has `--opencode` flag, 213 lines | No `--opencode` flag, 533 lines, more features |
| `block-bd-close.py` | Simple blocker, 105 lines | N/A - replaced by `gate-bd-close.py` |
| `gate-bd-close.py` | N/A | Skill-aware gating, Python 3.12 shebang |
| `inject-system-context.py` | N/A | Multi-repo context injection |
| `pre-commit-knowledge-gate.py` | N/A | Knowledge capture gate for commits |

**Source:** 
- `ls ~/.orch/hooks/` 
- `ls hooks/` in repo
- File content comparison

**Significance:** The repo's `hooks/` directory is out of sync with deployed hooks. This creates confusion about:
1. What hooks actually exist
2. Which version is authoritative
3. What OpenCode support actually exists

---

## Synthesis

**Key Insights:**

1. **Architecture mismatch is fundamental** - Claude Code and OpenCode use completely different extension mechanisms. Claude Code: command-based hooks with JSON I/O. OpenCode: JavaScript plugin system with event subscriptions. No compatibility layer exists.

2. **Partial OpenCode support is outdated** - The `--opencode` flag in `load-orchestration-context.py` references `experimental.hook.session_started` which doesn't appear in current OpenCode docs. OpenCode now uses a plugin-first architecture.

3. **Repo hooks are stale** - The deployed hooks in `~/.orch/hooks/` have evolved significantly beyond what's in the repo's `hooks/` directory. The repo version is essentially unmaintained sample code.

**Answer to Investigation Question:**

The existing hooks in `orch-cli/hooks/` are **not compatible** with OpenCode:

1. `load-orchestration-context.py` - Has partial, possibly outdated OpenCode support via `--opencode` flag, but uses `experimental.hook` API that may not exist in current OpenCode
2. `block-bd-close.py` - No OpenCode support at all, plus Python version compatibility issues

For OpenCode compatibility, hooks would need to be rewritten as JavaScript/TypeScript plugins using OpenCode's plugin system. The equivalent OpenCode patterns would be:

| Claude Code Hook | OpenCode Plugin Event |
|------------------|----------------------|
| `SessionStart` | `session.created` |
| `PreToolUse` | `tool.execute.before` |
| `PostToolUse` | `tool.execute.after` |
| `SessionEnd` | `session.idle` (closest) |

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Strong evidence from:
- Official OpenCode documentation clearly shows plugin architecture
- Actual test of hooks showed expected behavior and failures
- File content analysis confirms no OpenCode plugin implementations exist

**What's certain:**

- Claude Code and OpenCode use fundamentally different extension architectures
- Existing Python hooks cannot run as-is in OpenCode
- `load-orchestration-context.py` has `--opencode` flag but may use outdated API
- `block-bd-close.py` has no OpenCode support
- Deployed hooks diverge from repo hooks

**What's uncertain:**

- Whether `experimental.hook.session_started` still works in OpenCode (not documented)
- Whether OpenCode has any backward-compatibility mode for command hooks
- What the full scope of deployed hooks is (only examined subset)

**What would increase confidence to Very High (95%+):**

- Test `experimental.hook.session_started` in actual OpenCode instance
- Confirm with OpenCode team/discord whether command hooks are supported
- Create a working OpenCode plugin and verify event equivalence

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation.

### Recommended Approach: Plugin-Based Migration

**Recommended approach:** Create OpenCode plugins in TypeScript that wrap or reimplement hook functionality

**Why this approach:**
- Aligns with OpenCode's official extension mechanism
- Plugins have full access to OpenCode context (project, client, shell)
- Event system (`tool.execute.before`) provides equivalent PreToolUse capability

**Trade-offs accepted:**
- Must maintain two codebases (Python hooks for Claude Code, TS plugins for OpenCode)
- Plugin development requires Node/TypeScript tooling

**Implementation sequence:**
1. Create `.opencode/plugin/` directory in orch-cli
2. Implement `session-context.ts` plugin for SessionStart equivalent
3. Implement `bd-close-gate.ts` plugin for PreToolUse blocking
4. Test with OpenCode CLI

### Alternative Approaches Considered

**Option B: Shim layer (call Python from TS plugin)**
- **Pros:** Reuse existing Python code
- **Cons:** Adds complexity, process spawning overhead, two-language debugging
- **When to use:** If Python hooks are complex and well-tested

**Option C: Abandon repo hooks, document ~/.orch/hooks/**
- **Pros:** No development work, acknowledges deployed hooks as source of truth
- **Cons:** Loses OpenCode compatibility path, repo hooks remain misleading
- **When to use:** If OpenCode support is not a priority

**Rationale for recommendation:** OpenCode is increasingly important for orch-cli users. Native plugins provide best UX and maintainability.

---

### Implementation Details

**What to implement first:**
- Session context plugin (highest value - loads orchestrator skill at startup)
- Focus on `session.created` event equivalent to SessionStart

**Things to watch out for:**
- OpenCode plugin runs in Bun, not Node - use Bun APIs
- `tool.execute.before` can throw to block tools (different from JSON response)
- Plugin gets `$` shell helper - can call Python scripts if needed

**Areas needing further investigation:**
- Does OpenCode support blocking tool execution from plugins?
- What's the equivalent of `additionalContext` injection?
- How to detect worker vs orchestrator context in OpenCode?

**Success criteria:**
- OpenCode session in orch-cli project loads orchestrator skill automatically
- `bd close` is blocked for workers with helpful message
- Behavior matches Claude Code hooks

---

## References

**Files Examined:**
- `hooks/load-orchestration-context.py` - Repo version with --opencode flag
- `hooks/block-bd-close.py` - Repo version, no OpenCode support
- `~/.orch/hooks/load-orchestration-context.py` - Deployed version, no --opencode
- `~/.orch/hooks/gate-bd-close.py` - Deployed replacement
- `~/.claude/settings.json` - Claude Code hook configuration
- `opencode.json` - Current OpenCode config (instructions only)

**Commands Run:**
```bash
# Test OpenCode hook output
python3 hooks/load-orchestration-context.py --opencode 2>&1 | head -50

# Test block-bd-close (failed - Python version)
echo '{"tool_name": "Bash", "tool_input": {"command": "bd close test"}}' | CLAUDE_CONTEXT=worker python3 hooks/block-bd-close.py

# Check Python versions
python3 --version  # 3.9.6 (system)
# ~/.orch/hooks/ use #!/opt/homebrew/bin/python3.12
```

**External Documentation:**
- https://opencode.ai/docs/plugins/ - OpenCode plugin system
- https://opencode.ai/docs/config/ - OpenCode configuration

**Related Artifacts:**
- **Config:** `opencode.json` - Current OpenCode project config

---

## Self-Review

- [x] Real test performed (ran hooks, verified output)
- [x] Conclusion from evidence (docs + tests + file analysis)
- [x] Question answered (hooks are NOT compatible, need plugin rewrite)
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-12 17:50:** Investigation started
- Initial question: Are hooks in orch-cli/hooks/ compatible with OpenCode?
- Context: Spawned from beads issue orch-cli-bpeu to audit hook compatibility

**2025-12-12 18:00:** Documented architecture differences
- Found Claude Code uses command hooks, OpenCode uses JS plugins
- Identified key event mappings

**2025-12-12 18:10:** Tested actual hooks
- `load-orchestration-context.py --opencode` works but may use deprecated API
- `block-bd-close.py` has Python version issue, no OpenCode support

**2025-12-12 18:20:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Hooks need plugin rewrite for OpenCode compatibility
