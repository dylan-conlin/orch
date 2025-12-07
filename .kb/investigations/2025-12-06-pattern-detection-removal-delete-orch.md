**TLDR:** Dead code cleanup for pattern_detection.py - deleting src/orch/pattern_detection.py, src/orch/backlog_resolution.py (only dependency), tests/test_backlog_resolution.py, and removing references from spawn_commands.py and pyproject.toml. High confidence (95%) - traced all imports and dependencies.

---

# Investigation: pattern_detection.py Removal - Dead Code Cleanup

**Question:** What files need to be deleted and modified to remove pattern_detection.py dead code?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%+)

---

## Findings

### Finding 1: pattern_detection.py dependencies

**Evidence:**
- `pattern_detection.py` (1130 lines) provides `PatternDetector` class for investigation pattern analysis
- Only consumers: `spawn_commands.py` (lines 376, 440 - investigation thrashing detection and artifact hint project detection)
- Imports `backlog_resolution.py` which is only used by pattern_detection

**Source:** `grep pattern_detection src/orch/`, `grep backlog_resolution src/orch/`

**Significance:** Both files can be safely deleted together since backlog_resolution has no other consumers.

---

### Finding 2: spawn_commands.py references

**Evidence:**
- Lines 373-434: Investigation thrashing detection using PatternDetector.analyze_pattern()
- Lines 436-464: Uses PatternDetector._detect_project_dir() for artifact hint project detection

**Source:** `src/orch/spawn_commands.py:373-464`

**Significance:** Investigation thrashing detection removed entirely. Artifact hint functionality preserved by inlining simple project directory detection (walk up from cwd looking for .orch/).

---

### Finding 3: pyproject.toml and tests

**Evidence:**
- pyproject.toml line 125: `"orch.pattern_detection",` in mypy overrides list
- `tests/test_backlog_resolution.py`: Tests for the deleted backlog_resolution module

**Source:** `grep pattern_detection pyproject.toml`, `ls tests/test_backlog*`

**Significance:** Both references removed cleanly.

---

## Synthesis

**Files deleted:**
1. `src/orch/pattern_detection.py` (1130 lines)
2. `src/orch/backlog_resolution.py` (~150 lines)
3. `tests/test_backlog_resolution.py`

**Files modified:**
1. `pyproject.toml` - Removed `"orch.pattern_detection",` from mypy overrides
2. `src/orch/spawn_commands.py` - Removed PatternDetector usage, kept artifact_hint with inline project detection

**Verification:**
- All spawn-related tests pass (46 passed)
- CLI modules import successfully
- No remaining references to deleted modules

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
