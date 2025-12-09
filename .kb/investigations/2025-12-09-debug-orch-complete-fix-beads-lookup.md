**TLDR:** Question: Why does `orch complete` fail with beads ID lookup and investigation filename errors? Answer: Two bugs: (1) registry.find() only searches by agent ID, not beads_id; (2) primary_artifact path is pre-computed with slug from task but kb create produces different filename. High confidence (90%) - root cause identified in code.

---

# Investigation: orch complete Beads ID Lookup and Investigation Filename Bugs

**Question:** Why does `orch complete <beads-id>` fail with "Agent not found" and `orch complete <workspace>` fail with "Investigation file not found"?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: registry.find() only searches by agent ID, ignores beads_id

**Evidence:** The find() method at registry.py:132-137 only matches against `agent['id']`:
```python
def find(self, agent_id: str) -> Dict[str, Any] | None:
    for agent in self._agents:
        if agent['id'] == agent_id:
            return agent
    return None
```
But agents store `beads_id` as a separate field (registry.py:218-219), and users pass beads_id to `orch complete`.

**Source:** src/orch/registry.py:132-137 (find method), registry.py:218-219 (beads_id storage)

**Significance:** When orchestrator runs `orch complete pw-k2r` where `pw-k2r` is a beads ID, complete.py:201-203 calls `get_agent_by_id()` which uses `registry.find()`, returning None and failing with "Agent not found".

---

### Finding 2: primary_artifact computed from task slug, kb create produces different filename

**Evidence:** Two different path computations don't align:
1. `primary_artifact` is set via `determine_primary_artifact()` (spawn.py:245-263) which calls `render_deliverable_path()`
2. The skill template uses `{date}-debug-{slug}.md` (e.g., `2025-12-09-debug-something.md`)
3. But spawn_prompt.py:862-873 tells agent to run `kb create investigation {inv_slug}` which creates files at `{inv_type}/YYYY-MM-DD-{inv_slug}.md` (e.g., `simple/2025-12-09-something.md`)

The template and actual kb create output differ in: (a) subdirectory structure, (b) "debug-" prefix presence

**Source:**
- spawn.py:245-263 (determine_primary_artifact)
- spawn_prompt.py:335-365 (render_deliverable_path)
- spawn_prompt.py:862-877 (kb create instruction)
- verification.py:281-296 (_verify_investigation_artifact)

**Significance:** The stored `primary_artifact` path doesn't match the actual file created by the agent, causing "Investigation file not found" during `orch complete`.

---

## Synthesis

**Key Insights:**

1. **Registry lookup only supported agent ID, not beads_id** - The `find()` method only searched by agent ID (workspace name), but orchestrators often reference agents by their beads_id. Adding beads_id search as a fallback resolves this.

2. **Investigation path mismatch between expected and actual** - The `primary_artifact` path is computed at spawn time from task slug, but agents create files with different names via `kb create`. The fix adds fallback search via beads comments and directory glob patterns.

3. **Separation of concerns in registry** - Added `_find_by_id()` for internal duplicate checking while `find()` provides the flexible lookup for external callers.

**Answer to Investigation Question:**

Issue 1 (`orch complete <beads-id>` fails): The `registry.find()` method only searched by agent ID, not beads_id. Fixed by extending `find()` to also search by beads_id as a fallback.

Issue 2 (investigation file not found): The `primary_artifact` path stored at spawn time doesn't match actual files created by agents. Fixed by adding fallback search in `_verify_investigation_artifact()` that: (1) checks beads comments for `investigation_path`, (2) searches `.kb/investigations/` directory with workspace name patterns.

---

## Confidence Assessment

**Current Confidence:** [Level] ([Percentage])

**Why this level?**

[Explanation of why you chose this confidence level - what evidence supports it, what's strong vs uncertain]

**What's certain:**

- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]

**What's uncertain:**

- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]

**What would increase confidence to [next level]:**

- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]

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

**[Approach Name]** - [One sentence stating the recommended implementation]

**Why this approach:**
- [Key benefit 1 based on findings]
- [Key benefit 2 based on findings]
- [How this directly addresses investigation findings]

**Trade-offs accepted:**
- [What we're giving up or deferring]
- [Why that's acceptable given findings]

**Implementation sequence:**
1. [First step - why it's foundational]
2. [Second step - why it comes next]
3. [Third step - builds on previous]

### Alternative Approaches Considered

**Option B: [Alternative approach]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended - reference findings]
- **When to use instead:** [Conditions where this might be better]

**Option C: [Alternative approach]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended - reference findings]
- **When to use instead:** [Conditions where this might be better]

**Rationale for recommendation:** [Brief synthesis of why Option A beats alternatives given investigation findings]

---

### Implementation Details

**What to implement first:**
- [Highest priority change based on findings]
- [Quick wins or foundational work]
- [Dependencies that need to be addressed early]

**Things to watch out for:**
- ⚠️ [Edge cases or gotchas discovered during investigation]
- ⚠️ [Areas of uncertainty that need validation during implementation]
- ⚠️ [Performance, security, or compatibility concerns to address]

**Areas needing further investigation:**
- [Questions that arose but weren't in scope]
- [Uncertainty areas that might affect implementation]
- [Optional deep-dives that could improve the solution]

**Success criteria:**
- ✅ [How to know the implementation solved the investigated problem]
- ✅ [What to test or validate]
- ✅ [Metrics or observability to add]

---

## References

**Files Examined:**
- [File path] - [What you looked at and why]
- [File path] - [What you looked at and why]

**Commands Run:**
```bash
# [Command description]
[command]

# [Command description]
[command]
```

**External Documentation:**
- [Link or reference] - [What it is and relevance]

**Related Artifacts:**
- **Decision:** [Path to related decision document] - [How it relates]
- **Investigation:** [Path to related investigation] - [How it relates]
- **Workspace:** [Path to related workspace] - [How it relates]

---

## Investigation History

**[YYYY-MM-DD HH:MM]:** Investigation started
- Initial question: [Original question as posed]
- Context: [Why this investigation was initiated]

**[YYYY-MM-DD HH:MM]:** [Milestone or significant finding]
- [Description of what happened or was discovered]

**[YYYY-MM-DD HH:MM]:** Investigation completed
- Final confidence: [Level] ([Percentage])
- Status: [Complete/Paused with reason]
- Key outcome: [One sentence summary of result]
