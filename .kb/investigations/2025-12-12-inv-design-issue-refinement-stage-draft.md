**TLDR:** Question: How should issues transition from draft to ready for daemon-compatible autonomous intake? Answer: Introduce a lightweight "readiness gate" pattern - issues need a `triage: ready` label (or `triage: draft` for incomplete) plus optional `scope:` labels. Daemon only spawns issues with `triage: ready`. Implementation via beads labels (no status change), enforced in daemon polling. High confidence (85%) - uses existing beads primitives, minimal complexity.

---

# Investigation: Issue Refinement Stage (draft → ready) for Daemon Intake

**Question:** How should issues transition from "created" to "actionable" state so the work daemon can autonomously spawn high-quality work?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** worker-agent
**Phase:** Complete
**Next Step:** None - design ready for implementation
**Status:** Complete
**Confidence:** High (85%)

---

## Context

The work daemon (orch-cli-56b) will autonomously poll `bd ready` and spawn workers. But `bd ready` returns all unblocked open issues - including vague, poorly-scoped, or incomplete ones. If the daemon spawns on low-quality issues, it wastes tokens and produces poor results.

**The gap:** There's no distinction between "issue exists" and "issue is actionable for autonomous processing."

---

## Findings

### Finding 1: Current beads status model has no "draft" or "triage" concept

**Evidence:** From beads `internal/types/types.go:111-117`:
```go
const (
    StatusOpen       Status = "open"
    StatusInProgress Status = "in_progress"
    StatusBlocked    Status = "blocked"
    StatusClosed     Status = "closed"
)
```

Four statuses only. No "draft" or "needs triage" status.

**Source:** `/Users/dylanconlin/Documents/personal/beads/internal/types/types.go:111-117`

**Significance:** Adding a new status would require beads changes. But beads supports custom statuses via config and labels for metadata. Both are lower-lift alternatives.

---

### Finding 2: beads supports custom statuses but labels are more flexible

**Evidence:** From beads types.go:128-142:
```go
// IsValidWithCustom checks if the status is valid, including custom statuses.
// Custom statuses are user-defined via bd config set status.custom "status1,status2,..."
func (s Status) IsValidWithCustom(customStatuses []string) bool {
```

And from Issue struct (line 34):
```go
Labels             []string       `json:"labels,omitempty"`
```

**Source:** `/Users/dylanconlin/Documents/personal/beads/internal/types/types.go:128-142, 34`

**Significance:** Two options exist:
1. Custom status: `bd config set status.custom "draft,triage"` → issues can be status=draft
2. Labels: `bd label <id> triage:draft` → status stays open, label marks readiness

Labels are better because:
- No status migration needed for existing issues
- `bd ready` already works (filters by status=open, not blocked)
- Daemon can filter by label in its polling logic
- Labels are already used for metadata (e.g., `target:repo`, `urgent`)

---

### Finding 3: The daemon needs simple readiness detection, not complex triage

**Evidence:** From the unified daemon design (`orch-knowledge/.kb/investigations/2025-12-12-design-unified-meta-orchestration-daemon-architecture.md:182`):
```
2. **Minimal daemon** - Loop: `bd ready` → `orch spawn` → monitor completion → respect review gate
```

The daemon is intentionally simple. It polls `bd ready`, filters, spawns. Complex triage logic would add failure modes.

**Source:** Design investigation from Dec 12 architect session

**Significance:** The refinement stage should be:
- **Simple:** Binary ready/not-ready decision
- **External:** Determined before daemon polling, not by daemon
- **Explicit:** Visible in issue metadata (label)

---

### Finding 4: Skill inference already validates issue quality implicitly

**Evidence:** From `orch work` command (`src/orch/work_commands.py:93-135`):
```python
# Skill inference mapping
SKILL_INFERENCE = {
    "bug": "systematic-debugging",
    "feature": "feature-impl",
    "task": "investigation",
    "epic": "architect"
}
```

When `orch work <id>` runs, skill inference maps issue type → skill. If an issue is too vague, the spawned agent will struggle (visible in completion quality).

**Source:** `src/orch/work_commands.py:93-135`

**Significance:** The skill system provides implicit validation. A vague feature issue spawned to `feature-impl` will either:
1. Produce a QUESTION phase (agent asks for clarification)
2. Produce low-quality output (detected at completion)

The daemon can use completion quality as a feedback signal. But preventing bad spawns upfront is still valuable.

---

### Finding 5: Dylan's workflow includes manual triage before spawning

**Evidence:** From the orchestrator skill and daemon design sessions, Dylan:
1. Reviews `bd ready` output manually
2. Picks issues that have clear scope
3. Spawns with explicit skill + context

The daemon wants to replicate this judgment. But judgment is hard to automate. The simplest approach: require Dylan to mark issues ready.

**Source:** Orchestrator skill patterns, daemon design session

**Significance:** The refinement stage is Dylan's quality gate externalized as a label. Rather than "daemon decides if ready," it's "Dylan marks ready, daemon trusts label."

---

## Synthesis

**Key Insights:**

1. **Labels over custom statuses** - Labels are more flexible, don't require status migration, and work with existing `bd ready` command.

2. **Binary readiness, not complex triage** - The daemon doesn't need to understand WHY an issue is ready. It just needs to filter on a ready signal.

3. **Dylan gates, daemon executes** - The refinement stage is Dylan (or orchestrator) marking issues ready. The daemon trusts the mark. This keeps daemon logic simple.

4. **Failure feedback exists** - If a bad issue slips through, the agent will QUESTION or produce low-quality output. `orch complete` catches this. Not perfect, but acceptable for v1.

**Answer to Investigation Question:**

Use a label-based readiness gate:
- `triage: ready` - Issue is actionable, daemon can spawn
- `triage: draft` (or no label) - Issue needs refinement, daemon skips

Daemon polling becomes: `bd ready --label triage:ready` (or equivalent filter in polling logic).

Dylan's workflow:
1. Create issue (implicitly draft)
2. Refine description, acceptance criteria, context
3. `bd label <id> triage:ready`
4. Daemon picks it up on next poll

This is the minimal change that enables autonomous daemon operation while preserving quality.

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**
Uses existing beads primitives (labels). Minimal complexity. Clear implementation path. Validated against daemon design requirements.

**What's certain:**

- ✅ Labels are the right primitive (flexible, no migration)
- ✅ Binary ready/draft is sufficient for daemon v1
- ✅ Dylan as gatekeeper keeps daemon simple
- ✅ Failure feedback via agent questions/completion exists

**What's uncertain:**

- ⚠️ Exact label naming (`triage:ready` vs `ready` vs `actionable`)
- ⚠️ Whether to default new issues to draft or require explicit labeling
- ⚠️ Integration with `orch work` interactive picker (should it filter too?)

**What would increase confidence to Very High (95%):**

- Test the pattern with 10+ issues in real daemon operation
- Validate label filtering performance at scale
- Get Dylan's confirmation on labeling ergonomics

---

## Implementation Recommendations

**Purpose:** Bridge from investigation to actionable implementation.

### Recommended Approach ⭐

**Label-based readiness gate with `triage:ready` convention**

**Why this approach:**
- Uses existing beads labels (zero beads changes needed)
- Simple daemon filter: only spawn if `triage:ready` label present
- Dylan can refine issues at any pace, then mark ready
- Visible in beads-ui (labels shown on issues)

**Trade-offs accepted:**
- Requires Dylan to label issues (small friction)
- No automation of readiness detection (but that's complex and error-prone)
- Issues without label are implicitly "draft" (could confuse existing backlog)

**Implementation sequence:**
1. **Document convention** - Update orchestrator skill to include `bd label <id> triage:ready` pattern
2. **Daemon polling** - Add label filter to daemon's `bd ready` call
3. **Backlog migration (optional)** - Bulk-label existing ready issues

### Alternative Approaches Considered

**Option B: Custom status `draft`**
- **Pros:** Status is first-class, visible in `bd list`
- **Cons:** Requires `bd config set status.custom draft`, status migration for existing issues, `bd ready` may need adjustment
- **When to use instead:** If labels prove too invisible or filtering is problematic

**Option C: Structured description template**
- **Pros:** Forces quality upfront (title, description, acceptance criteria required)
- **Cons:** Doesn't help with existing issues, over-engineers the problem
- **When to use instead:** If issue quality is consistently poor and needs structural enforcement

**Rationale for recommendation:** Labels are the lightest-weight solution that solves the problem. Start simple, iterate if needed.

---

### Implementation Details

**What to implement first:**
- Add label filter to daemon polling (`triage:ready` only)
- Document the convention in orchestrator skill
- Test with 2-3 issues manually

**Things to watch out for:**
- ⚠️ Existing issues won't have labels - need migration strategy or "unlabeled = ready for now" grace period
- ⚠️ Label typos (`triage: ready` vs `triage:ready`) could cause issues
- ⚠️ Bulk labeling many issues might be tedious

**Areas needing further investigation:**
- Should `orch work` (interactive) also filter by readiness?
- Should there be a `bd triage` command for convenience?
- How to visualize draft vs ready in beads-ui?

**Success criteria:**
- ✅ Daemon only spawns issues with `triage:ready` label
- ✅ Spawned agents have clear context (issues are refined)
- ✅ Dylan can control pace of work by labeling
- ✅ No beads changes required

---

## References

**Files Examined:**
- `/Users/dylanconlin/Documents/personal/beads/internal/types/types.go` - Issue and Status types
- `src/orch/work_commands.py` - orch work command and skill inference
- `orch-knowledge/.kb/investigations/2025-12-12-design-unified-meta-orchestration-daemon-architecture.md` - Unified daemon design

**Commands Run:**
```bash
# Check issue structure
bd ready --json | head -50
bd blocked --json | head -50
bd show orch-cli-56b

# Check beads types
rg "type Issue struct|type Status|draft|ready" --type go /Users/dylanconlin/Documents/personal/beads/internal
```

**Related Artifacts:**
- **Investigation:** `orch-cli:.kb/investigations/2025-12-10-design-orchestration-architecture-native-cli-optimal.md` - Original daemon design
- **Investigation:** `orch-knowledge:.kb/investigations/2025-12-12-design-unified-meta-orchestration-daemon-architecture.md` - Unified architecture
- **Issue:** `orch-cli-56b` - Daemon MVP (blocked by this design)

---

## Investigation History

**2025-12-12 21:05:** Investigation started
- Initial question: How should issues transition from draft to ready for daemon intake?
- Context: orch-cli-56b (daemon) blocked by this design issue

**2025-12-12 21:20:** Explored beads data model
- Found: 4 statuses only (open, in_progress, blocked, closed)
- Found: Custom statuses supported via config
- Found: Labels provide flexible metadata

**2025-12-12 21:35:** Synthesized approach
- Decision: Labels over custom statuses
- Convention: `triage:ready` for actionable issues
- Daemon filters on this label

**2025-12-12 21:45:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Label-based readiness gate using `triage:ready` convention

---

## Self-Review

- [x] Real test performed (examined actual beads data model and daemon requirements)
- [x] Conclusion from evidence (design based on actual beads capabilities)
- [x] Question answered (clear readiness gate pattern defined)
- [x] File complete

**Self-Review Status:** PASSED
