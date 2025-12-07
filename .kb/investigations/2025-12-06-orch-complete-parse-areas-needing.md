**TLDR:** Question: How should orch complete parse "Areas needing further investigation" sections and prompt orchestrator to create follow-up issues? Answer: Extract items from investigation files using regex pattern similar to existing `extract_recommendations_section()`, then prompt orchestrator to create beads issues via `bd create --discovered-from`. High confidence (85%) - follows established patterns in codebase.

---

# Investigation: Parse Areas Needing Investigation in orch complete

**Question:** How to implement parsing of "Areas needing further investigation" sections from investigation files during `orch complete` and prompt orchestrator to create follow-up beads issues?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Existing pattern for section extraction exists

**Evidence:** The `extract_recommendations_section()` function in `src/orch/complete.py:204-240` already parses markdown sections using regex patterns:
```python
patterns = [
    r'## Recommendations\n(.*?)(?=\n## |\Z)',
    r'## Next Steps\n(.*?)(?=\n## |\Z)',
    r'## Implementation Recommendations\n(.*?)(?=\n## |\Z)',
]
```

**Source:** `src/orch/complete.py:229-233`

**Significance:** Can follow same pattern to extract "Areas needing further investigation" section. Regex pattern would be: `r'\*\*Areas needing further investigation:\*\*\n(.*?)(?=\n\*\*|\n## |\Z)'` to handle subsection within Implementation Recommendations.

---

### Finding 2: Investigation template contains the target section

**Evidence:** The kb investigation template includes the section:
```markdown
**Areas needing further investigation:**
- [Questions that arose but weren't in scope]
- [Uncertainty areas that might affect implementation]
- [Optional deep-dives that could improve the solution]
```

**Source:** `.kb/investigations/2025-12-06-orch-complete-parse-areas-needing.md:162-165` (the template used to create investigation files)

**Significance:** Section is a subsection (bold header, not H2) within "Implementation Recommendations". Need regex that handles both standalone H2 and subsection formats.

---

### Finding 3: Discovery capture mechanism exists for beads integration

**Evidence:** `src/orch/complete.py:866-1020` has discovery capture functions:
- `prompt_for_discoveries()` - Interactive prompt for items
- `create_beads_issue()` - Creates issue via `bd create --discovered-from`
- `process_discoveries()` - Processes list of items into beads issues

**Source:** `src/orch/complete.py:893-996`

**Significance:** Can reuse `create_beads_issue()` and `process_discoveries()` functions. Main work is extracting items from investigation file and presenting them to orchestrator for confirmation.

---

## Synthesis

**Key Insights:**

1. **Pattern follows existing extraction logic** - The new function can mirror `extract_recommendations_section()` with different regex patterns for the "Areas needing further investigation" subsection.

2. **Two-phase approach** - First extract items from file, then present to orchestrator for confirmation before creating beads issues (defense-in-depth pattern from kn-57afc0).

3. **Reuse existing beads creation** - The `create_beads_issue()` function already handles `--discovered-from` linking.

**Answer to Investigation Question:**

Implementation approach:
1. Add `extract_areas_needing_investigation()` function with regex pattern for subsection
2. Add `surface_areas_needing_investigation()` to call during `complete_agent_work()`
3. Present extracted items to orchestrator, confirm which to create as beads issues
4. Use existing `process_discoveries()` for beads creation with `--discovered-from` linking

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**
Implementation complete and validated with 13 passing tests. Regex patterns work for both bold subsection and H2 formats.

**What's certain:**
- ✅ `extract_areas_needing_investigation()` parses both format variants
- ✅ `surface_areas_needing_investigation()` integrates with existing patterns
- ✅ Integration in both sync and async complete paths works
- ✅ All 89 complete-related tests pass (no regressions)

**What's uncertain:**
- ⚠️ Real-world usage patterns haven't been tested yet
- ⚠️ Edge cases in markdown formatting may exist

---

## Implementation Recommendations

### Recommended Approach ⭐

**TDD implementation with new extraction function** - Add extraction and surfacing functions following existing patterns

**Why this approach:**
- Consistent with existing `extract_recommendations_section()` pattern
- Reuses existing beads integration code
- Follows defense-in-depth pattern (orchestrator confirms before creating issues)

**Implementation sequence:**
1. Write failing tests for `extract_areas_needing_investigation()`
2. Implement extraction function with regex
3. Write failing tests for surfacing in `complete_agent_work()`
4. Integrate into complete flow with orchestrator confirmation

---

## References

**Files Examined:**
- `src/orch/complete.py` - Main completion logic, extraction patterns
- `tests/test_complete_recommendations.py` - Test patterns to follow
- `.kb/investigations/*.md` - Template structure

