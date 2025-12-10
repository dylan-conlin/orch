**TLDR:** Question: How can spawned agents push completion notifications to the orchestrator? Answer: Recommend file-based signals over tmux send-keys. tmux send-keys works but has race conditions and security concerns when orchestrator is mid-input. File-based signals via fswatch are cleaner, non-intrusive, and integrate naturally with existing beads workflow. High confidence (85%) - tested tmux mechanisms and analyzed existing architecture.

---

# Investigation: Agent-to-Orchestrator Completion Notification

**Question:** How can spawned agents proactively notify the orchestrator when they complete, instead of requiring polling or manual checks?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: Agents have full tmux context available

**Evidence:** From within an agent's tmux window, we can access:
- `TMUX_PANE=%218` - Current pane identifier
- `tmux display-message -p "#{session_name}"` returns `workers-orch-cli`
- `tmux display-message -p "#{window_id}"` returns current window ID
- Registry stores spawn window info: `{"window": "workers-orch-cli:4", "window_id": "@213"}`

**Source:**
- Environment variables in agent session
- `tmux display-message` commands tested
- `~/.orch/agent-registry.json` structure in `src/orch/registry.py:224-235`

**Significance:** Agents CAN determine their tmux context and could theoretically target the orchestrator. However, the registry only stores the agent's own window, not the orchestrator's window.

---

### Finding 2: orch send already exists and works bidirectionally

**Evidence:** The `orch send` command in `src/orch/monitoring_commands.py:908-980` sends messages to agents via:
```python
def send(agent_id, message):
    """Send a message to a spawned agent."""
    from orch.send import send_message_to_agent
    send_message_to_agent(agent, message)
```

The underlying `src/orch/send.py:67-107` uses:
```python
subprocess.run(["tmux", "send-keys", "-t", target, message])
time.sleep(1)  # Wait for paste
subprocess.run(["tmux", "send-keys", "-t", target, "Enter"])
```

**Source:**
- `src/orch/send.py:1-107`
- `src/orch/monitoring_commands.py:908-980`

**Significance:** The mechanism for tmux-based messaging already exists. An inverse command (`orch notify` or agent calling `orch send` targeting orchestrator) is technically feasible using the same pattern.

---

### Finding 3: Orchestrator window identification is non-trivial

**Evidence:** The orchestrator runs across multiple project windows:
```
tmux list-windows -t orchestrator:
1:dotfiles:/Users/dylanconlin/dotfiles
2:orch-knowledge-2:/Users/dylanconlin/orch-knowledge
3:beads-ui-svelte-2:/Users/dylanconlin/Documents/personal/beads-ui-svelte
4:orch-cli-2:/Users/dylanconlin/Documents/personal/orch-cli
5:price-watch-2:/Users/dylanconlin/Documents/personal/price-watch
```

When agent spawns, we know the project (e.g., `orch-cli`) but not which orchestrator window is "active" or relevant.

**Source:**
- `tmux list-windows -t orchestrator -F "#{window_index}:#{window_name}:#{pane_current_path}"`
- `src/orch/tmuxinator.py:122-154` - `get_orchestrator_current_project()` exists but only for switching workers client

**Significance:** To send to orchestrator, we need to either:
1. Store orchestrator window at spawn time in registry
2. Match by project path at notification time
3. Broadcast to all orchestrator windows (noisy)

---

### Finding 4: Race conditions with tmux send-keys are real

**Evidence:** The `time.sleep(1)` in `src/orch/send.py:99` acknowledges the race condition:
```python
# Wait for message to be pasted into terminal buffer
# Without this sleep, Enter gets processed before message is fully pasted
time.sleep(1)
```

If orchestrator is mid-input when agent sends, the notification would:
- Interrupt typing
- Potentially corrupt the partial command
- Insert text at cursor position

**Source:**
- `src/orch/send.py:97-99`
- tmux send-keys documentation

**Significance:** tmux send-keys is intrusive. Unlike notifications that appear in a separate UI element, send-keys injects directly into the terminal buffer. This is acceptable for explicit `orch send` commands (user initiated) but problematic for unsolicited agent notifications.

---

### Finding 5: File-based signaling infrastructure exists (fswatch available)

**Evidence:**
- `which fswatch` returns `/opt/homebrew/bin/fswatch` (macOS)
- Beads already uses file-based state via `.beads/issues.jsonl`
- Registry at `~/.orch/agent-registry.json` is file-based
- SessionStart hooks read `.beads/` for error summaries

**Source:**
- `fswatch` availability test
- `.beads/` directory structure
- `src/orch/beads_integration.py` for file access patterns

**Significance:** File-based signals would be:
1. Non-intrusive (no terminal buffer injection)
2. Atomic (write complete notification to file)
3. Queryable (orchestrator can check at will)
4. Compatible with existing patterns

---

### Finding 6: Current completion flow relies on beads comments

**Evidence:** The spawn prompt instructs agents:
```
🚨 SESSION COMPLETE PROTOCOL:
1. Run: `bd comment <beads-id> "Phase: Complete - [1-2 sentence summary]"`
2. Run: `/exit` to close the agent session
```

The `orch complete` command at `src/orch/complete.py:93-125` verifies:
```python
if verify_phase:
    current_phase = beads.get_phase_from_comments(beads_id)
    if not current_phase or current_phase.lower() != "complete":
        raise BeadsPhaseNotCompleteError(beads_id, current_phase)
```

**Source:**
- `.orch/workspace/inv-agent-orchestrator-10dec/SPAWN_CONTEXT.md`
- `src/orch/complete.py:93-125`

**Significance:** Completion status is already recorded via beads. What's missing is the *notification* aspect - telling orchestrator that the comment was written.

---

## Synthesis

**Key Insights:**

1. **Messaging mechanism exists, targeting is the gap** - `orch send` already handles tmux messaging. The challenge is knowing WHERE to send (which orchestrator window) and WHEN it's safe (not mid-input).

2. **Beads is already the state authority** - Agents write `Phase: Complete` to beads. The notification gap is just pushing an alert, not duplicating state tracking.

3. **File signals are more appropriate than terminal injection** - tmux send-keys is intrusive. A file-based signal that triggers a notification (bell, display message, or tmux display-popup) is cleaner.

**Answer to Investigation Question:**

The recommended approach is **file-based completion signals with optional tmux notification**:

1. Agent writes completion to a signal file (e.g., `~/.orch/completion-signals/{agent-id}.complete`)
2. Orchestrator optionally runs a watcher (`fswatch`) that:
   - Reads signal files
   - Shows non-intrusive notification (tmux display-popup or bell)
   - Auto-cleans processed signals

This avoids:
- Race conditions with mid-input (no terminal buffer injection)
- Complex orchestrator window targeting
- Security concerns (rogue message injection)

And provides:
- Non-blocking notifications
- Optional (orchestrator can ignore signals)
- Integration with existing beads workflow

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**

High confidence because:
1. Tested actual tmux mechanisms from agent context
2. Reviewed existing `orch send` implementation
3. Identified concrete race condition evidence in code
4. fswatch availability confirmed on target platform

**What's certain:**

- ✅ Agents can determine their tmux context (tested)
- ✅ `orch send` mechanism exists and could be inverted
- ✅ tmux send-keys has race conditions (acknowledged in existing code)
- ✅ File-based signaling (fswatch) is available on macOS
- ✅ Beads comments already track completion state

**What's uncertain:**

- ⚠️ User preference for notification style (popup vs bell vs status bar)
- ⚠️ Performance impact of fswatch daemon on large-scale use
- ⚠️ Cross-platform compatibility (inotify on Linux, polling on Windows)

**What would increase confidence to Very High (95%+):**

- Test file signal mechanism end-to-end with actual orchestrator
- Gather user feedback on notification style preference
- Benchmark fswatch with 50+ active agents

---

## Implementation Recommendations

### Recommended Approach ⭐

**File-Based Completion Signals** - Agents write signal files on completion; orchestrator watches for new signals and shows non-intrusive notifications.

**Why this approach:**
- Non-intrusive: No terminal buffer injection, works while orchestrator types
- Simple: Agent just creates a file, no complex targeting needed
- Reliable: No race conditions with tmux input
- Optional: Orchestrator can ignore signals if busy

**Trade-offs accepted:**
- Requires daemon (fswatch) running - but could be lazy-started
- Additional file I/O - minimal, one small file per completion

**Implementation sequence:**
1. Define signal file format and location (`~/.orch/completion-signals/`)
2. Add `orch notify --completion` command for agents to write signal
3. Add `orch watch` daemon that uses fswatch + tmux display-popup
4. Integrate signal write into completion protocol instructions

### Alternative Approaches Considered

**Option B: Direct tmux send-keys to orchestrator**
- **Pros:** Simple, no daemon required, immediate
- **Cons:** Race conditions with mid-input, intrusive, complex targeting
- **When to use instead:** If notifications must be instant and orchestrator is in a dedicated "waiting for agents" state

**Option C: tmux status bar update**
- **Pros:** Completely non-intrusive, visible at glance
- **Cons:** Requires tmux config changes, limited space, notifications could be missed
- **When to use instead:** For passive monitoring without any interruption

**Option D: Use existing beads hooks**
- **Pros:** No new infrastructure, leverages existing patterns
- **Cons:** Would require modifying beads itself, cross-project dependency
- **When to use instead:** If beads adds native completion notification feature

**Rationale for recommendation:** File-based signals provide the best balance of reliability (no race conditions), non-intrusiveness (no terminal injection), and simplicity (agent just writes a file).

---

### Implementation Details

**What to implement first:**
- Signal file format: `~/.orch/completion-signals/{agent-id}.json`
- Contents: `{"agent_id": "...", "beads_id": "...", "completed_at": "...", "summary": "..."}`
- Agent command: `orch notify --type completion --summary "Fixed bug X"`

**Things to watch out for:**
- ⚠️ Clean up old signal files (add TTL or cleanup on read)
- ⚠️ Handle missing fswatch gracefully (fall back to polling)
- ⚠️ Don't block agent if orchestrator is not running watcher

**Areas needing further investigation:**
- Optimal polling interval if fswatch unavailable
- tmux display-popup vs display-message vs bell for notification style
- Integration with future beads UI

**Success criteria:**
- ✅ Agent completion visible to orchestrator within 5 seconds
- ✅ No interference with orchestrator typing
- ✅ Works with 10+ concurrent agents

---

## References

**Files Examined:**
- `src/orch/send.py` - Existing tmux messaging implementation
- `src/orch/monitoring_commands.py` - orch send command
- `src/orch/complete.py` - Completion verification flow
- `src/orch/registry.py` - Agent registry structure
- `src/orch/tmuxinator.py` - Per-project session management
- `src/orch/spawn.py` - Spawn flow and context

**Commands Run:**
```bash
# Check tmux context from agent
tmux display-message -p "session: #{session_name} window: #{window_index}"

# List orchestrator windows
tmux list-windows -t orchestrator -F "#{window_index}:#{window_name}:#{pane_current_path}"

# Check fswatch availability
which fswatch

# View agent registry
cat ~/.orch/agent-registry.json | python3 -c "..."
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-01-investigate-opencode-backend-implementation-orch.md` - send command support
- **Investigation:** `.kb/investigations/2025-12-01-investigate-whether-orch-cli-use.md` - tmux vs native sessions

---

## Investigation History

**2025-12-10 09:39:** Investigation started
- Initial question: How can agents push completion notifications to orchestrator?
- Context: Currently orchestrator polls or waits for user to say "agent is done"

**2025-12-10 10:00:** Key findings documented
- tmux messaging mechanism analyzed
- Race conditions identified in existing code
- File-based alternative explored

**2025-12-10 10:30:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Recommend file-based signals over tmux send-keys for reliability and non-intrusiveness

---

## Self-Review

- [x] Real test performed (not code review) - tested tmux commands, checked env vars, verified fswatch
- [x] Conclusion from evidence (not speculation) - based on actual code analysis and command output
- [x] Question answered - provided design options with tradeoffs and recommendation
- [x] File complete

**Self-Review Status:** PASSED
