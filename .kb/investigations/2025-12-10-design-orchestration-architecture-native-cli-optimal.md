**TLDR:** Question: Is AI-native CLI the optimal orchestration approach? Answer: The CLI architecture is sound, but the single-session orchestrator conflates two concerns (interactive + work processing). Recommended: Daemon + Interactive split - daemon continuously processes beads backlog while orchestrator remains available for Dylan. High confidence (85%) - validated through interactive design session, implementation details TBD.

---

# Investigation: Orchestration Architecture - Is AI-native CLI Optimal?

**Question:** Is orch-cli's "AI-native CLI + tmux orchestration" architecture optimal, or are there fundamentally better approaches for multi-agent orchestration?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Dylan + Architect agent (interactive session)
**Phase:** Complete
**Next Step:** None - follow-up issues created
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 1: Current architecture conflates interactive and work processing

**Evidence:** Dylan described the core pain point: "I want an orchestrator that is always free for me to talk to, but also an orchestrator that is constantly working through beads, queuing up things for me to read, questions to answer, etc."

Current model: Single Claude session handles both Dylan interaction AND work dispatch. When processing work, not available for Dylan. When waiting for Dylan, not processing work.

**Source:** Interactive design session with Dylan

**Significance:** This is an architectural gap, not an implementation bug. A single Claude Code session cannot simultaneously stay responsive to human input AND autonomously loop through work.

---

### Finding 2: Daemon + Interactive split resolves the core tension

**Evidence:** Proposed architecture that resonated with Dylan:

```
Interactive Orchestrator (Claude session)
  - Always available for Dylan
  - Ad-hoc requests, questions, exploration

Work Daemon (Python process)
  - Polls bd ready for next work
  - Spawns workers automatically
  - Monitors completion via beads comments
  - Queues items for Dylan's review
  - Respects capacity limits (max concurrent workers)
```

Communication via shared state: beads (issues, comments), registry (agent state).

**Source:** Interactive design session - Dylan confirmed "yes!" to this split

**Significance:** Separates concerns cleanly. Dylan gets responsive orchestrator. System gets autonomous work processing. beads-ui (already built) serves as the visibility layer.

---

### Finding 3: Review gates should be work-type specific, not universal

**Evidence:** Dylan clarified: "not all workers need my review either." Different work types have different needs:

- **Architect:** Always interactive, always needs review (exploration with Dylan)
- **Feature-impl (CLI):** Needs review - Dylan wants to understand how features work
- **Feature-impl (Web):** Needs Playwright AI test + Dylan manual test
- **Bug fixes:** Variable - depends on severity/confidence

Workers that hit questions should complete with partial work and flag for review, not block.

**Source:** Interactive session - Dylan described current workflow and preferences

**Significance:** Daemon needs skill/spawn-time metadata to know: auto-close or pending-review? This prevents the current problem where orchestrator closes workers before Dylan reviews.

---

### Finding 4: Verification chains vary by work type

**Evidence:** Dylan described the full lifecycle:

- CLI changes: pytest → AI manual CLI test → human review
- Web UI changes: vitest → Playwright AI test → human manual test
- Failures at any step: extract error from agentlog → worker sees error → worker fixes → retry

Key requirement: "any failures need to surface errors (agentlog) the AI can see and fix"

**Source:** Interactive session workflow mapping

**Significance:** The daemon doesn't just spawn and wait - it needs to understand verification chains and ensure each step passes before moving to review gate.

---

### Finding 5: Bug lifecycle is a separate, critical design problem

**Evidence:** Dylan described bug pain points:
- Multiple chaotic entry points ("is this wrong?", screenshots, "3rd time this happened")
- Root cause elusive - investigations point in different directions
- False fixes - "claims fixed, 2 hours later happens again"
- No error-to-issue linkage
- No regression detection
- agentlog exists but integration not sharp

**Source:** Interactive session - Dylan's detailed description of bug frustrations

**Significance:** This is a distinct problem from orchestration architecture. Needs its own design work focused on: error→issue linkage, repro-based verification, regression detection, pattern matching across time.

---

## Synthesis

**Key Insights:**

1. **The CLI architecture is sound** - tmux for visualization, beads for tracking, skills for task templates. The issue isn't the CLI, it's the single-session orchestrator model.

2. **Split architecture solves the core problem** - Daemon for autonomous work processing, interactive session for Dylan. beads-ui already provides visibility.

3. **Review gates need metadata** - Skills should declare `review: required | optional | none`. Daemon respects this, preventing premature closure.

4. **Verification is a chain, not a step** - Different work types have different verification sequences. Daemon orchestrates the full chain.

5. **Bug lifecycle is orthogonal** - Deserves separate design attention. Current "spawn fixer, claim fixed" model has no verification or regression tracking.

**Answer to Investigation Question:**

The AI-native CLI approach (orch-cli) is a good foundation. The architecture problem isn't "CLI vs something else" - it's that a single orchestrator session can't be both interactive AND autonomous.

The solution is **architectural separation**: keep the interactive orchestrator for Dylan, add a work daemon for autonomous processing, use beads as the communication bus. This preserves everything that works (tmux visibility, skill system, beads tracking) while enabling continuous work processing.

Alternative architectures explored (event-driven, declarative, SDK-based) don't solve the core interactive/autonomous tension better than the daemon split. The SDK could enhance the daemon (hooks, monitoring) but isn't a replacement architecture.

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**
Design validated through interactive session with Dylan. Core pain points clearly identified and addressed. Implementation path is clear conceptually.

**What's certain:**

- The interactive/autonomous tension is real and architectural
- Daemon + Interactive split addresses Dylan's stated needs
- beads-ui already exists as visibility layer
- Review gates need to be configurable per work type

**What's uncertain:**

- Daemon implementation details (polling interval, capacity management, error handling)
- How daemon starts/stops (manual vs auto vs launchd)
- Exact skill metadata schema for review requirements
- Integration complexity with existing spawn.py

**What would increase confidence to Very High (95%+):**

- Build minimal daemon prototype and validate with real work
- Define skill metadata schema for review/verification
- Test daemon + interactive orchestrator running simultaneously
- Validate beads-ui can display daemon state effectively

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation.

### Recommended Approach: Daemon + Interactive Split

**Daemon-based work processing** - Python daemon per project that continuously processes beads backlog while interactive orchestrator remains available for Dylan.

**Why this approach:**
- Directly addresses "always available + always working" requirement
- Preserves existing architecture (tmux, beads, skills, registry)
- Incremental - can build daemon without changing existing spawn flow
- Dylan already has visibility via beads-ui

**Trade-offs accepted:**
- Two processes to manage (daemon + orchestrator)
- Daemon needs its own monitoring/restart logic
- Some duplication of spawn logic initially

**Implementation sequence:**
1. **Skill metadata for review gates** - Add `review: required | optional` to skill YAML
2. **Minimal daemon** - Loop: `bd ready` → `orch spawn` → monitor completion → respect review gate
3. **Daemon lifecycle** - `orch daemon start/stop/status` commands
4. **Verification chains** - Daemon runs test → AI test → human gate sequence

### Alternative Approaches Considered

**Option B: SDK-based event-driven orchestrator**
- **Pros:** Hooks could enable pseudo-concurrency, programmatic control
- **Cons:** Doesn't solve interactive/autonomous split - still one process
- **When to use instead:** As enhancement to daemon for monitoring/intervention

**Option C: Single orchestrator with explicit modes**
- **Pros:** Simpler - no daemon process
- **Cons:** Dylan has to toggle modes, can't do both simultaneously
- **When to use instead:** If daemon complexity proves too high

**Rationale for recommendation:** Daemon split is the only architecture that allows truly concurrent interactive + autonomous operation. SDK and mode-switching are partial solutions.

---

### Implementation Details

**What to implement first:**
- Skill metadata schema (`review: required | optional | none`)
- Basic daemon loop (poll → spawn → monitor → gate)
- `orch daemon start` command

**Things to watch out for:**
- Daemon and orchestrator both calling `orch spawn` - need coordination
- Registry state must be daemon-aware
- Daemon crashes should be recoverable (resume from beads state)

**Areas needing further investigation:**
- Bug lifecycle design (separate investigation)
- Verification chain implementation details
- beads-ui enhancements for daemon visibility

**Success criteria:**
- Dylan can talk to orchestrator while daemon spawns workers
- Workers complete → pending-review (not auto-closed)
- Dylan sees queue of items to review in beads-ui
- Daemon recovers cleanly from restart

---

## References

**Files Examined:**
- `.kb/investigations/2025-12-01-investigate-whether-orch-cli-use.md` - Prior tmux vs native sessions analysis
- `.kb/investigations/2025-12-10-inv-claude-agent-sdk-integration-possibilities.md` - SDK capabilities analysis
- `/Users/dylanconlin/Documents/personal/beads-ui-svelte/src/server/tmux-follower.ts` - Existing tmux monitoring in beads-ui

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-01-investigate-whether-orch-cli-use.md` - Concluded tmux is correct for orch-cli
- **Investigation:** `.kb/investigations/2025-12-10-inv-claude-agent-sdk-integration-possibilities.md` - SDK could enhance daemon

---

## Investigation History

**2025-12-10 ~23:15:** Investigation started
- Initial question: Is AI-native CLI optimal for orchestration?
- Context: Spawned as interactive architect session

**2025-12-10 ~23:20:** Problem reframed
- Dylan clarified actual pain points: partial completion, monitoring gaps, verification
- Identified core tension: single session can't be interactive AND autonomous

**2025-12-10 ~23:30:** Daemon architecture emerged
- Proposed Daemon + Interactive split
- Dylan confirmed: "yes!"

**2025-12-10 ~23:40:** Review gates and verification chains mapped
- Different work types need different gates
- Bug lifecycle identified as separate problem

**2025-12-10 ~23:50:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Daemon + Interactive split recommended; bug lifecycle needs separate design
