**TLDR:** What is the current state of OpenCode compatibility in orch-cli and orch-knowledge? OpenCode backend is well-integrated in orch-cli (spawn, send, tail work), but orchestrator skill documentation has zero OpenCode references. High confidence (85%) - comprehensive code audit across 54 source files.

---

# Investigation: OpenCode Compatibility Audit for orch-cli and orch-knowledge

**Question:** What is the current state of OpenCode compatibility in orch-cli? What gaps exist between OpenCode and Claude Code backend support?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Claude (codebase-audit agent)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: OpenCode Backend Implementation is Comprehensive

**Evidence:** The OpenCode backend (`src/orch/backends/opencode.py`, 603 lines) implements:
- Full HTTP API client with REST endpoints for session management
- SSE (Server-Sent Events) support for real-time event streaming
- Session lifecycle: create, list, get, delete sessions
- Message handling: send messages (sync and async), retrieve messages
- Tool call tracking and status queries
- Model resolution with aliases (opus, sonnet, haiku variants)
- Server discovery across common ports (4096, 53615, 8080)

**Source:** 
- `src/orch/backends/opencode.py:1-603` (full file)
- Key classes: `OpenCodeClient`, `OpenCodeBackend`, `OpenCodeSession`, `ToolCall`, `Message`

**Significance:** The core OpenCode integration is production-ready. All fundamental backend operations are implemented and align with the `Backend` abstract base class interface.

---

### Finding 2: Spawn Command Fully Supports OpenCode Backend

**Evidence:** The spawn flow for OpenCode (`spawn_with_opencode()` in `spawn.py:757-963`) creates:
- Tmux window for the OpenCode TUI
- SPAWN_CONTEXT.md with full prompt (same as Claude)
- Agent registration with session_id tracking
- Support for both "attach mode" (existing server) and "standalone mode"
- Model resolution via `resolve_opencode_model()`
- Readiness detection via `_wait_for_opencode_ready()` checking TUI indicators

CLI options properly include opencode:
```python
# spawn_commands.py:134
@click.option('--backend', type=click.Choice(['claude', 'codex', 'opencode']))

# work_commands.py:83
@click.option('--backend', type=click.Choice(['claude', 'codex', 'opencode']))
```

**Source:**
- `src/orch/spawn.py:757-963` (`spawn_with_opencode()`)
- `src/orch/spawn_commands.py:134`
- `src/orch/work_commands.py:83`

**Significance:** Users can spawn OpenCode agents with `--backend opencode`. The spawn infrastructure is complete and consistent with other backends.

---

### Finding 3: Monitoring Commands (send, tail) Support OpenCode

**Evidence:** Both `send.py` and `tail.py` have explicit OpenCode branches:

`send.py:27-64` - OpenCode message sending:
```python
if agent.get('backend') == 'opencode':
    _send_message_opencode(agent, message)
```

`tail.py:31-68` - OpenCode output capture:
```python
if agent.get('backend') == 'opencode':
    return _tail_opencode(agent, lines)
```

Both functions:
- Check for session_id (required for OpenCode agents)
- Discover server via `discover_server()`
- Use `OpenCodeClient` API for operations
- Fall back to tmux operations for non-OpenCode backends

**Source:**
- `src/orch/send.py:27-64` (`_send_message_opencode`)
- `src/orch/tail.py:31-105` (`_tail_opencode`, `_format_opencode_messages`)

**Significance:** Core monitoring commands work with OpenCode agents without modifications.

---

### Finding 4: Registry Reconciliation Skips OpenCode Agents

**Evidence:** In `registry.py:308-343`, the `reconcile()` method explicitly skips OpenCode agents:
```python
for agent in self._agents:
    if agent['status'] == 'active':
        # Skip non-tmux backends
        if agent.get('backend') == 'opencode':
            continue
```

Comment at `monitoring_commands.py:244-245`:
```python
# Note: reconcile_opencode() removed in lifecycle simplification
# OpenCode agents tracked via beads, not separate reconciliation
```

**Source:**
- `src/orch/registry.py:321-322`
- `src/orch/monitoring_commands.py:244-245`

**Significance:** OpenCode agents rely on beads for lifecycle tracking, not tmux window state. This is a design decision, not a gap, but means `orch status` won't automatically detect closed OpenCode sessions.

---

### Finding 5: Interactive Mode Explicitly Blocks OpenCode

**Evidence:** In `spawn.py:1169-1174`:
```python
# Check backend - opencode not yet supported for interactive mode
if resolved_backend == "opencode":
    raise RuntimeError(
        "Interactive mode (-i) not yet supported with OpenCode backend.\n"
        "Use: orch spawn SKILL_NAME 'task' --backend opencode"
    )
```

**Source:** `src/orch/spawn.py:1169-1174`

**Significance:** This is a documented limitation. Interactive spawning (`orch spawn -i`) doesn't work with OpenCode. Users must use skill-based spawning.

---

### Finding 6: Complete Command Has No Special OpenCode Handling

**Evidence:** The `complete.py` module (335 lines) uses tmux-specific functions for cleanup:
```python
from orch.tmux_utils import (
    has_active_processes,
    graceful_shutdown_window,
    list_windows,
)
```

The `clean_up_agent()` function (lines 136-199) checks `window_id` and uses tmux commands:
- `send_exit_command()` uses `tmux send-keys`
- `graceful_shutdown_window()` sends Ctrl+C via tmux
- `tmux kill-window` for cleanup

No OpenCode-specific branches exist for agent completion.

**Source:** `src/orch/complete.py:26-31, 136-199`

**Significance:** OpenCode agents can complete (beads tracking works), but tmux cleanup logic will silently fail or be skipped. The agent gets marked completed in registry, but window cleanup is tmux-specific.

---

### Finding 7: Orchestrator Skill Has Zero OpenCode Documentation

**Evidence:** Searching `~/.claude/skills/orchestrator/SKILL.md` (62,290 bytes):
- No matches for "opencode" or "OpenCode"
- No matches for "--backend"
- No documentation about backend choice or OpenCode-specific workflows

Also checked orch-knowledge:
- Found OpenCode references only in POC files (test scripts, experimental code)
- No OpenCode mentions in docs, skills, or templates-src directories

**Source:**
```bash
rg -c "opencode|OpenCode|--backend" ~/.claude/skills/orchestrator/SKILL.md
# No matches
```

**Significance:** Orchestrators following SKILL.md have no guidance on using OpenCode. This is a significant documentation gap since the backend option exists but isn't documented.

---

## Synthesis

**Key Insights:**

1. **OpenCode Backend is Code-Complete** - The implementation in `backends/opencode.py` is comprehensive with HTTP API client, SSE support, session management, and full integration with spawn/send/tail commands. The code quality matches Claude/Codex backends.

2. **Documentation-Implementation Gap** - OpenCode exists as a fully functional `--backend` option but isn't mentioned in the orchestrator skill that guides all spawning decisions. This means agents and orchestrators won't know to use it.

3. **Lifecycle Tracking Divergence** - OpenCode agents bypass tmux-based reconciliation, relying on beads for lifecycle tracking. This is intentional but creates different behavior from Claude/Codex agents in `orch status`.

4. **Interactive Mode Disabled** - OpenCode explicitly doesn't support `-i` (interactive) mode. This is the only explicit feature limitation.

5. **Completion Cleanup Gap** - While completion logic works (beads closes, registry updates), the tmux window cleanup code doesn't have OpenCode-specific handling. OpenCode windows stay open after completion.

**Answer to Investigation Question:**

OpenCode compatibility in orch-cli is **functionally complete** for core workflows:
- ✅ Spawning agents (`orch spawn --backend opencode`)
- ✅ Sending messages (`orch send`)
- ✅ Tailing output (`orch tail`)
- ✅ Registry tracking with beads integration
- ✅ Model selection (opus, sonnet, haiku aliases)

Gaps exist in:
- ❌ Documentation (orchestrator skill has no OpenCode guidance)
- ❌ Interactive mode support (explicitly disabled)
- ⚠️ Completion cleanup (works but tmux-specific cleanup fails silently)
- ⚠️ Status reconciliation (skipped for OpenCode agents)

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**

Comprehensive code audit of 54 source files in `src/orch/` with explicit pattern matching for "opencode", "OpenCode", and "backend" references. Every occurrence was examined and categorized.

**What's certain:**

- ✅ OpenCode backend implementation is complete (verified `opencode.py` implementation)
- ✅ Spawn, send, tail commands have explicit OpenCode support (code branches exist)
- ✅ Registry skips OpenCode reconciliation by design (explicit comment)
- ✅ Orchestrator skill has zero OpenCode documentation (verified search)

**What's uncertain:**

- ⚠️ Runtime behavior in production (code audit only, no live testing)
- ⚠️ OpenCode server compatibility with current API client (API may have evolved)
- ⚠️ Edge cases in SSE event handling and message formatting

**What would increase confidence to Very High (95%+):**

- End-to-end testing: spawn, monitor, complete cycle with OpenCode
- API compatibility check against current OpenCode server
- User feedback from actual OpenCode usage

---

## Implementation Recommendations

**Purpose:** Address the documentation gap and minor implementation issues to make OpenCode a first-class citizen.

### Recommended Approach ⭐

**Documentation-First** - Add OpenCode to orchestrator skill documentation before fixing minor code gaps.

**Why this approach:**
- Documentation gap is the highest-impact issue (users don't know the feature exists)
- Code implementation is already complete for core workflows
- Small documentation addition has outsized impact on discoverability

**Trade-offs accepted:**
- Delaying code fixes for completion cleanup
- Users may hit edge cases until cleanup is fixed

**Implementation sequence:**
1. Add `--backend opencode` examples to orchestrator SKILL.md
2. Document OpenCode-specific workflows (server discovery, session management)
3. Add completion cleanup for OpenCode sessions (lower priority)

### Alternative Approaches Considered

**Option B: Code-First Fixes**
- **Pros:** Addresses all gaps, more complete solution
- **Cons:** Users still won't know feature exists; effort disproportionate to value
- **When to use instead:** If OpenCode becomes default backend

**Option C: Feature Parity with Interactive Mode**
- **Pros:** Full feature parity with Claude backend
- **Cons:** Complex UI integration work; uncertain value-add
- **When to use instead:** If interactive spawning is heavily used with OpenCode

**Rationale for recommendation:** Documentation gap creates largest friction. Users can't use what they don't know exists. Code works well enough for early adopters.

---

### Implementation Details

**What to implement first:**
- Add to orchestrator SKILL.md sections on spawning:
  - Backend selection: when to use OpenCode vs Claude
  - Example: `orch spawn --backend opencode SKILL "task"`
  - Note about interactive mode limitation

**Things to watch out for:**
- ⚠️ OpenCode server must be running (`discover_server()` checks common ports)
- ⚠️ Model aliases differ slightly from Claude (opus-4.5 vs opus-4-5-20251101)
- ⚠️ Session cleanup is manual for OpenCode (tmux window stays open)

**Areas needing further investigation:**
- OpenCode API version compatibility
- SSE event handling in long-running sessions
- Model cost tracking for OpenCode sessions

**Success criteria:**
- ✅ Orchestrator skill mentions OpenCode as backend option
- ✅ Users can successfully spawn OpenCode agents following docs
- ✅ `orch status` behavior documented for OpenCode agents

---

## References

**Files Examined:**
- `src/orch/backends/opencode.py` - Full OpenCode backend implementation
- `src/orch/spawn.py` - spawn_with_opencode() function and interactive mode check
- `src/orch/spawn_commands.py` - CLI options for backend
- `src/orch/work_commands.py` - CLI options for backend
- `src/orch/send.py` - OpenCode message sending
- `src/orch/tail.py` - OpenCode output capture
- `src/orch/registry.py` - Agent reconciliation logic
- `src/orch/complete.py` - Completion cleanup logic
- `src/orch/monitoring_commands.py` - Status command and reconciliation
- `~/.claude/skills/orchestrator/SKILL.md` - Orchestrator documentation

**Commands Run:**
```bash
# Find all OpenCode references
rg "opencode|OpenCode" src/orch/ --type py

# Find backend choice options
rg "click.Choice\(\['claude" src/orch/ --type py

# Check orchestrator skill for OpenCode
rg -c "opencode|OpenCode|--backend" ~/.claude/skills/orchestrator/SKILL.md

# Check orch-knowledge for OpenCode references
rg -l "opencode|OpenCode" ~/orch-knowledge/
```

**External Documentation:**
- OpenCode repository for API reference (not audited in this investigation)

**Related Artifacts:**
- **Prior Investigation:** `.kb/investigations/2025-12-05-claude-agent-flag-for-skills.md` - Mentions codebase-audit allowed tools

---

## Investigation History

**2025-12-12 16:30:** Investigation started
- Initial question: What is the current state of OpenCode compatibility in orch-cli and orch-knowledge?
- Context: Spawned as codebase-audit task

**2025-12-12 16:45:** Pattern search completed
- Found 100+ OpenCode references across codebase
- Identified all backend integration points

**2025-12-12 17:00:** Documentation gap identified
- Orchestrator skill has zero OpenCode references
- POC files in orch-knowledge only location with OpenCode mentions

**2025-12-12 17:15:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: OpenCode implementation is code-complete but undocumented; documentation gap is highest priority fix
