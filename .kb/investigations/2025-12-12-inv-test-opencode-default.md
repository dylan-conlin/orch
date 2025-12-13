**TLDR:** Question: Does OpenCode work correctly as the default backend when configured in ~/.orch/config.yaml? Answer: Yes - config correctly resolves `backend: opencode`, spawn dispatches to `spawn_with_opencode()`, and agents are successfully created with OpenCode TUI in tmux. High confidence (95%) - verified through config inspection, code path analysis, and actual spawn test with agent registration verification.

---

# Investigation: Test OpenCode Default Backend

**Question:** Does OpenCode work correctly as the default backend when `backend: opencode` is set in ~/.orch/config.yaml?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Config Correctly Resolves OpenCode Backend

**Evidence:** Running `get_backend()` from orch.config returns `opencode`:
```
Config: {'tmux_session': 'workers', ..., 'backend': 'opencode'}
Default backend: opencode
```

**Source:** 
- `~/.orch/config.yaml` - contains `backend: opencode`
- `src/orch/config.py:90-111` - `get_backend()` function with priority: CLI > config > default

**Significance:** The configuration layer correctly reads and returns the OpenCode backend setting.

---

### Finding 2: Spawn Code Correctly Dispatches to OpenCode Handler

**Evidence:** In `spawn.py:1789`, there's explicit handling for OpenCode:
```python
if config.backend == "opencode":
    spawn_info = spawn_with_opencode(config)
```

The `spawn_with_opencode()` function (lines 757-961):
- Creates tmux window
- Resolves OpenCode model format
- Builds OpenCode command with --prompt flag
- Optionally attaches to existing OpenCode server

**Source:** `src/orch/spawn.py:1789-1810` and `src/orch/spawn.py:757-961`

**Significance:** The spawn command correctly routes to the OpenCode-specific implementation when `backend: opencode` is configured.

---

### Finding 3: OpenCode Backend is Separate from spawn_in_tmux

**Evidence:** The `spawn_in_tmux()` function at lines 625-630 only handles `claude` and `codex`:
```python
if config.backend == "claude":
    backend = ClaudeBackend()
elif config.backend == "codex":
    backend = CodexBackend()
else:
    raise ValueError(f"Unsupported backend: {config.backend}...")
```

But this is correct - OpenCode is intentionally handled separately via `spawn_with_opencode()` before `spawn_in_tmux()` is ever called.

**Source:** `src/orch/spawn.py:625-630` and `src/orch/spawn.py:1788-1819`

**Significance:** This is the expected architecture - OpenCode has its own spawn path that runs in tmux like other backends but with OpenCode-specific command building.

---

### Finding 4: Actual Spawn Test Confirms End-to-End Functionality

**Evidence:** 
```
$ orch spawn investigation "verify opencode default test" -y
📍 Auto-detected project: orch-cli
🚀 spawning: 🔬investigation → orch-cli "verify opencode default test"

✅ Spawned (OpenCode): oc-inv-verify-opencode-12dec
   Window: workers-orch-cli:2
   Session: ses_4eaea0987ffesCyVFEf7pmkKfI
   Workspace: oc-inv-verify-opencode-12dec
```

Registry confirms `backend: opencode`:
```
Active agent backends:
  oc-inv-verify-opencode-12dec: opencode
```

**Source:** Direct command execution and registry inspection

**Significance:** End-to-end test confirms OpenCode is used as default backend without requiring `--backend opencode` flag.

---

## Test Performed

**Test:** Spawned an investigation agent without specifying `--backend` flag and verified the output messages and registry state

**Result:** 
- Spawn output shows "✅ Spawned (OpenCode): ..." 
- Session ID was assigned from OpenCode server: `ses_4eaea0987ffesCyVFEf7pmkKfI`
- tmux window created: `workers-orch-cli:2`
- Registry shows `backend: opencode` for the agent
- Agent successfully started in tmux

---

## Synthesis

**Key Insights:**

1. **Config layer works correctly** - `backend: opencode` in `~/.orch/config.yaml` is correctly read by `get_backend()` and returned as the default when no CLI override is provided.

2. **Dispatch logic is correct** - The spawn code at line 1789 explicitly checks for `opencode` backend and routes to `spawn_with_opencode()`, bypassing the `spawn_in_tmux()` function which only handles claude/codex.

3. **Architecture is intentional** - OpenCode has a separate spawn function because it builds different commands (opencode binary vs claude/codex CLI) and integrates with the OpenCode server via session IDs.

4. **End-to-end verification confirms functionality** - Actual spawn test with no `--backend` flag successfully used OpenCode as default, created proper tmux window, and registered agent with correct backend metadata.

**Answer to Investigation Question:**

Yes, OpenCode works correctly as the default backend when `backend: opencode` is configured in `~/.orch/config.yaml`. The test confirms:
- Config resolution: ✅
- Backend dispatch: ✅
- tmux window creation: ✅
- OpenCode session creation: ✅
- Agent registration with backend metadata: ✅

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**
Both code inspection and runtime testing confirm the implementation works correctly. The test was repeatable and produced expected results.

**What's certain:**
- ✅ Config file correctly contains `backend: opencode`
- ✅ `get_backend()` returns `opencode` when no CLI override
- ✅ Spawn code has explicit OpenCode handling path
- ✅ Actual spawn test created OpenCode agent successfully
- ✅ Registry shows correct `backend: opencode` metadata

**What's uncertain:**
- ⚠️ Long-running agent behavior (only tested spawn, not full lifecycle)
- ⚠️ Error handling if OpenCode server is down (not tested)

**What would increase confidence to 100%:**
- Test full agent lifecycle (spawn → work → complete)
- Test failure modes (server down, session timeout)

---

## Implementation Recommendations

N/A - This was a verification investigation, not a feature investigation. The OpenCode default backend is working correctly.

---

## References

**Files Examined:**
- `~/.orch/config.yaml` - Verified backend setting
- `src/orch/config.py:90-111` - Backend resolution logic
- `src/orch/spawn.py:1788-1819` - Backend dispatch logic
- `src/orch/spawn.py:757-961` - `spawn_with_opencode()` implementation
- `~/.orch/agent-registry.json` - Agent registration data

**Commands Run:**
```bash
# Check config
cat ~/.orch/config.yaml
# Output: backend: opencode

# Test backend resolution
uv run python3 -c "from orch.config import get_backend, get_config; print('Config:', get_config()); print('Default backend:', get_backend())"
# Output: Default backend: opencode

# Actual spawn test
orch spawn investigation "verify opencode default test" -y
# Output: ✅ Spawned (OpenCode): oc-inv-verify-opencode-12dec

# Verify registry
cat ~/.orch/agent-registry.json | python3 -c "..."
# Output: oc-inv-verify-opencode-12dec: opencode

# Cleanup
orch abandon oc-inv-verify-opencode-12dec -y
```

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-12 15:15:** Investigation started
- Initial question: Does OpenCode work as default backend?
- Context: Config has `backend: opencode` set, need to verify end-to-end

**2025-12-12 15:20:** Code inspection complete
- Found correct dispatch logic in spawn.py
- Config layer verified working

**2025-12-12 15:25:** Actual spawn test performed
- Spawned `oc-inv-verify-opencode-12dec`
- Confirmed backend: opencode in registry
- Test cleanup: agent abandoned

**2025-12-12 15:30:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: OpenCode default backend works correctly
