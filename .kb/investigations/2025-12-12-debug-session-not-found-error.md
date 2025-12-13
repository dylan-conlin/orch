**TLDR:** Question: Why does 'session not found' error occur during OpenCode spawn? Answer: The `orch spawn` code uses `--session` and `--model` flags with `opencode attach` that don't exist in the CLI - these are invalid flags that get ignored/error. High confidence (90%) - verified via CLI help output.

---

# Investigation: Debug 'session not found' error during OpenCode spawn

**Question:** Why does 'session not found' error occur when spawning an agent via orch spawn with OpenCode backend?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** worker-agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: OpenCode CLI `attach` command doesn't support `--session` or `--model` flags

**Evidence:** Running `opencode attach --help` shows only these options:
```
Options:
  -h, --help        show help
  -v, --version     show version number
      --print-logs  print logs to stderr
      --log-level   log level [choices: "DEBUG", "INFO", "WARN", "ERROR"]
      --dir         directory to run in
```

There is no `--session` or `--model` flag available.

**Source:** 
- CLI help output from `opencode attach --help`
- `src/orch/spawn.py:873` constructs command with non-existent flags:
  ```python
  opencode_cmd = f"{opencode_bin} attach {existing_server} --session {session.id} --model {shlex.quote(model_arg)} --dir {shlex.quote(str(config.project_dir))}"
  ```

**Significance:** The spawn code is passing invalid CLI flags to `opencode attach`. This explains the "session not found" error - OpenCode creates the session via API, but then the TUI attach command doesn't know how to connect to that specific session because the `--session` flag doesn't exist.

---

### Finding 2: Two-phase session creation causes orphaned sessions

**Evidence:** The spawn flow (lines 859-874):
1. Creates session via HTTP API: `backend.spawn_session()` - this actually sends the prompt
2. Tries to attach TUI with invalid flags: `opencode attach ... --session {id}`

The API call succeeds and starts processing the prompt, but the TUI can't connect to it.

**Source:** `src/orch/spawn.py:859-874`

**Significance:** This creates a race/orphan condition:
- Session is created and prompt is sent via API
- TUI launches but can't attach to the existing session
- TUI may create a NEW session, or fail to find the expected session
- The "session not found" error likely comes from OpenCode itself when the TUI doesn't see the session it expected

---

### Finding 3: Main `opencode` command vs `attach` subcommand have different flag sets

**Evidence:** 

Main `opencode [project]` command supports:
```
-m, --model       model to use in the format of provider/model
-c, --continue    continue the last session
-s, --session     session id to continue
-p, --prompt      prompt to use
    --agent       agent to use
```

`opencode attach <url>` command only supports:
```
--print-logs
--log-level
--dir
```

**Source:** `opencode . --help` and `opencode attach --help` output

**Significance:** 
- **Standalone mode is likely correct** - uses valid `--model` and `--prompt` flags
- **Attach mode is broken** - tries to use `--session` and `--model` which don't exist on the `attach` subcommand

The "session not found" error occurs because:
1. `spawn_session()` creates a session via API and sends the prompt
2. The attach command can't specify which session to connect to (no `--session` flag)
3. OpenCode TUI starts fresh without knowing about the API-created session
4. The TUI or internal logic reports "session not found" when trying to reconcile

---

## Synthesis

**Key Insights:**

1. **API mismatch in attach mode** - The code creates a session via HTTP API, then tries to attach the TUI with flags that don't exist (`--session`, `--model`). These flags are silently ignored or cause errors.

2. **Two incompatible modes** - OpenCode has two fundamentally different modes:
   - Standalone TUI with `--session` flag to continue existing sessions
   - Attach mode that connects to a server but lacks session-targeting capability

3. **Root cause is flag incompatibility** - `spawn_with_opencode()` was written assuming `opencode attach` supports the same flags as the main `opencode` command. It doesn't.

**Answer to Investigation Question:**

The "session not found" error occurs because `spawn_with_opencode()` in `src/orch/spawn.py:873` constructs an `opencode attach` command with non-existent flags `--session` and `--model`. 

When spawning with an existing OpenCode server:
1. A session is created via API and the prompt is sent
2. The TUI attach command is invoked with invalid flags
3. The TUI starts but can't connect to the existing session
4. OpenCode reports "session not found" because the TUI is disconnected from the API-created session

The fix is to either:
1. **Use standalone mode with `--session`** - Don't use `attach`, use `opencode <dir> --session <id>` which has the proper flags
2. **Fix OpenCode's attach mode** - Add `--session` flag to `opencode attach` (requires upstream change)
3. **Remove attach mode from orch** - Only support standalone mode until OpenCode's attach command is more complete

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

CLI help output definitively shows the available flags for each command. Code analysis shows exactly which flags are being used. The mismatch is clear and verifiable.

**What's certain:**

- ✅ `opencode attach` does NOT support `--session` or `--model` flags (verified via `--help`)
- ✅ `spawn_with_opencode()` constructs commands using these non-existent flags (verified in code)
- ✅ The main `opencode` command DOES support these flags (verified via `--help`)

**What's uncertain:**

- ⚠️ Exact error message text - didn't capture the original error output
- ⚠️ Whether "session not found" comes from OpenCode TUI or server
- ⚠️ Whether the agent "recovered" by starting a fresh session or the prompt somehow reached it

**What would increase confidence to Very High (95%+):**

- Reproduce the exact error scenario and capture the error message
- Test the proposed fix (standalone mode with `--session`) works correctly
- Verify the API-created session is orphaned after attach failure

**Confidence levels guide:**
- **Very High (95%+):** Strong evidence, minimal uncertainty, unlikely to change
- **High (80-94%):** Solid evidence, minor uncertainties, confident to act
- **Medium (60-79%):** Reasonable evidence, notable gaps, validate before major commitment
- **Low (40-59%):** Limited evidence, high uncertainty, proceed with caution
- **Very Low (<40%):** Highly speculative, more investigation needed

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**Unify on standalone mode with API pre-creation** - Remove attach mode, use main `opencode` command with `--session` flag to connect to API-created sessions.

**Why this approach:**
- Main `opencode` command supports all needed flags (`--session`, `--model`, `--prompt`)
- Maintains the benefit of API-based session creation (prompt sent immediately)
- Minimal code change - swap command construction, keep session creation logic

**Trade-offs accepted:**
- Not using `attach` mode (but it doesn't support session targeting anyway)
- May need to handle server port coordination differently

**Implementation sequence:**
1. Change attach mode branch to use `opencode <dir> --session <id> --model <model>` instead of `opencode attach`
2. Test that this successfully connects to the API-created session
3. Consider fallback behavior if server isn't available (standalone-only mode)

### Alternative Approaches Considered

**Option B: Remove server/attach mode entirely**
- **Pros:** Simplest fix, only use standalone mode
- **Cons:** Loses API-based session creation which provides faster prompt delivery
- **When to use instead:** If the complexity of coordinating API + TUI isn't worth it

**Option C: Wait for OpenCode to add `--session` to attach command**
- **Pros:** Cleaner separation of concerns
- **Cons:** Depends on upstream changes, timing unknown
- **When to use instead:** If this is a temporary workaround and upstream fix is imminent

**Rationale for recommendation:** Option A is the right balance - it uses OpenCode's existing supported flags while keeping the performance benefit of API session creation. The code change is minimal and the fix is entirely within orch-cli.

---

### Implementation Details

**What to implement first:**
- Fix `spawn_with_opencode()` at line 873 to use proper command format
- Change from `opencode attach {server} --session {id}` to `opencode {dir} --session {id} --model {model}`
- Ensure the server URL is still passed appropriately (may need `OPENCODE_URL` env var)

**Things to watch out for:**
- ⚠️ The main `opencode` command starts its own server by default - need to verify it connects to existing server
- ⚠️ May need `--port` or other coordination to connect to existing server
- ⚠️ Test both paths: with existing server and without

**Areas needing further investigation:**
- How does `opencode <dir> --session <id>` behave when a server is already running?
- Does it connect to the running server or start a new one?
- May need to set `OPENCODE_URL` environment variable or use different approach

**Success criteria:**
- ✅ `orch spawn --backend opencode` successfully creates and connects to a session
- ✅ No "session not found" errors during spawn
- ✅ Agent receives the prompt and begins working
- ✅ Both existing-server and standalone modes work correctly

---

## References

**Files Examined:**
- `src/orch/spawn.py:757-960` - `spawn_with_opencode()` function with the broken attach command
- `src/orch/backends/opencode.py` - OpenCode backend API client

**Commands Run:**
```bash
# Check opencode attach flags
opencode attach --help

# Check main opencode flags
opencode . --help
```

**External Documentation:**
- OpenCode CLI built-in help - Verified available flags for each command

**Related Artifacts:**
- None directly related

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: Why does 'session not found' error occur during OpenCode spawn?
- Context: Orchestrator observed error during `orch spawn` with OpenCode backend

**2025-12-12:** Root cause identified
- Discovered `opencode attach` command doesn't support `--session` or `--model` flags
- Code constructs invalid command, causing session lookup to fail

**2025-12-12:** Investigation complete
- Final confidence: High (90%)
- Status: Complete - root cause identified and fix implemented
- Key outcome: `spawn_with_opencode()` was using non-existent flags (`--session`, `--model`) on `opencode attach` command
- Fix: Changed attach mode to start TUI first, then create session via API after TUI is ready
