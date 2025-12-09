**TLDR:** Question: How to add kb search integration to spawn prompts? Answer: Created `load_kb_context()` function in spawn_prompt.py that searches kb for relevant investigations/decisions using task keywords, returns formatted markdown with paths and excerpts (not full content), and injects a "PRIOR INVESTIGATIONS (from kb)" section. High confidence (95%) - implemented with TDD, all 33 tests pass.

---

# Investigation: Add load_kb_context() for spawn prompt enrichment

**Question:** How to add kb search integration to spawn prompts to surface prior investigations and decisions?

**Started:** 2025-12-08
**Updated:** 2025-12-08
**Owner:** Worker agent (orch-cli-1u8)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Existing load_kn_context() pattern provides template

**Evidence:** The existing `load_kn_context()` function (spawn_prompt.py:133-199) provides an established pattern:
- Checks if directory exists (.kn)
- Extracts keywords from task using `extract_meaningful_words()`
- Tries progressively fewer keywords until match found
- Returns formatted markdown section or None

**Source:** src/orch/spawn_prompt.py:133-199

**Significance:** Following the same pattern ensures consistency and reduces risk. The progressive keyword reduction strategy handles cases where specific queries don't match.

---

### Finding 2: kb search supports JSON output format

**Evidence:** `kb search` command supports `--format json` which returns structured data:
```json
{
  "Name": "filename.md",
  "Path": "/full/path/to/file.md",
  "Title": "Document Title",
  "Type": "investigations",
  "Matches": ["10: matching line text"]
}
```

**Source:** `kb search --help` and manual testing

**Significance:** JSON output allows programmatic parsing and formatting of results, enabling extraction of paths and excerpts without full file content.

---

### Finding 3: Integration point is in build_spawn_prompt()

**Evidence:** The `build_spawn_prompt()` function already calls `load_kn_context()` at line 925 and appends result to `additional_parts`. Adding `load_kb_context()` immediately after follows the same pattern.

**Source:** src/orch/spawn_prompt.py:920-933

**Significance:** Minimal code changes required - just add the call and the function is automatically included in spawn prompts when results exist.

---

## Synthesis

**Key Insights:**

1. **Pattern reuse** - Following `load_kn_context()` pattern ensures consistent behavior and reduces bugs

2. **Result limiting** - Capping at 5 results and 200 chars per excerpt prevents context bloat

3. **Progressive keyword search** - Trying fewer keywords on no match increases chances of surfacing relevant content

**Answer to Investigation Question:**

Created `load_kb_context()` function that:
- Checks for .kb directory existence
- Extracts keywords from task description
- Runs `kb search` with JSON format
- Parses results and formats as markdown with paths and excerpts
- Limits to 5 results with 2 excerpts each (max 200 chars)
- Returns "## PRIOR INVESTIGATIONS (from kb)" section

Integrated into build_spawn_prompt() after kn context loading.

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

All tests pass (33 total including 12 new tests). Implementation follows established patterns. Edge cases handled (no .kb dir, empty task, no matches, timeout, invalid JSON).

**What's certain:**

- ✅ Function correctly parses kb search JSON output
- ✅ Results are formatted with paths and excerpts
- ✅ Context bloat prevented by limiting results and excerpt length
- ✅ Graceful degradation when kb unavailable or errors occur

**What's uncertain:**

- ⚠️ Real-world effectiveness depends on kb content quality
- ⚠️ Keyword extraction may not always surface best matches

---

## Implementation Details

**What was implemented:**
1. `load_kb_context()` function (spawn_prompt.py:26-130)
2. Integration into `build_spawn_prompt()` (spawn_prompt.py:929-933)
3. 12 unit tests for the function
4. 3 integration tests for spawn prompt inclusion

**Files changed:**
- src/orch/spawn_prompt.py - Added function and integration
- tests/test_spawn_prompt.py - Added 12 unit tests + 3 integration tests

**Success criteria met:**
- ✅ Function extracts keywords and searches kb
- ✅ Returns formatted markdown with paths and excerpts
- ✅ Integrated into spawn prompts automatically
- ✅ All tests pass (33 in test_spawn_prompt.py)

---

## References

**Files Examined:**
- src/orch/spawn_prompt.py - Main implementation file
- tests/test_spawn_prompt.py - Test file

**Commands Run:**
```bash
# Check kb search output format
kb search "spawn context" --format json

# Run tests
python -m pytest tests/test_spawn_prompt.py -v
```

---

## Investigation History

**2025-12-08 14:10:** Investigation started
- Initial question: How to add kb search integration to spawn prompts?
- Context: Orchestrator wants prior investigations surfaced automatically

**2025-12-08 14:15:** Found load_kn_context() pattern to follow

**2025-12-08 14:20:** Implemented load_kb_context() function

**2025-12-08 14:25:** Wrote 12 unit tests + 3 integration tests

**2025-12-08 14:30:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: load_kb_context() function implemented and tested, surfaces relevant kb content in spawn prompts
