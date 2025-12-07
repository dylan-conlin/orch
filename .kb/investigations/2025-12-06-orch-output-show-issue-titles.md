**TLDR:** Question: How can orch status/check commands show beads issue titles alongside agent IDs? Answer: Agents spawned with --issue have a beads_id field. Fetch issue via BeadsIntegration.get_issue() and display title. High confidence (90%) - straightforward implementation, clear data flow.

---

# Investigation: orch output show issue titles

**Question:** How can orch status and check commands display beads issue titles alongside agent workspace hashes?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Claude (feat-orch-output-show-issue-06dec)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: Agents have beads_id field when spawned from issues

**Evidence:**
- `src/orch/registry.py:238` - register() method accepts `beads_id` parameter
- `src/orch/spawn.py:666,1025,2067` - beads_id is passed during agent registration
- `src/orch/complete.py:685-710` - Code checks for `agent.get('beads_id')` and uses it to close issues

**Source:**
- Grepped for `beads_id` across src/orch/*.py
- Read registry.py lines 223-241
- Read complete.py lines 685-710

**Significance:** The infrastructure already exists to link agents to beads issues. We just need to use this field to fetch and display issue titles.

---

### Finding 2: BeadsIntegration can fetch issue titles

**Evidence:**
- `src/orch/beads_integration.py:68-109` - get_issue() method returns BeadsIssue dataclass with title field
- `src/orch/monitoring_commands.py:426-476` - check command already uses BeadsIntegration to fetch issue data
- Line 467 shows: `click.echo(f"Title: {issue.title}")`

**Source:**
- Read beads_integration.py lines 27-109
- Read monitoring_commands.py lines 409-476

**Significance:** The check command already demonstrates the pattern - we can reuse BeadsIntegration to fetch titles in status command.

---

### Finding 3: Current status command only shows agent IDs

**Evidence:**
- Line 297: `click.echo(f"  {agent['id']} (window {agent['window'].split(':')[1]})")`
- Line 311: `click.echo(f"  {agent['id']}{window_info}")`
- Line 324: `click.echo(f"  {agent['id']} (window {agent['window'].split(':')[1]}) - Phase: {status_obj.phase}")`
- Line 341: `click.echo(f"  {agent['id']} - Phase: {status_obj.phase}{context_str}")`

**Source:**
- Read monitoring_commands.py lines 287-351 (status command human format display)

**Significance:** We need to modify these lines to also display issue title when agent has beads_id.

---

## Synthesis

**Key Insights:**

1. **Data already exists** - Agents spawned with `--issue` already have beads_id stored in registry (Finding 1), and BeadsIntegration already provides get_issue() method (Finding 2). No new infrastructure needed.

2. **Pattern already implemented** - The check command (lines 426-476) already demonstrates the exact pattern: use BeadsIntegration to fetch issue and display title. We can copy this approach (Finding 2).

3. **Modification scope is small** - Only need to modify status command display lines (4 locations in human format, lines 297/311/324/341) and potentially JSON format (Finding 3).

**Answer to Investigation Question:**

To show beads issue titles alongside agent IDs in orch status/check:
1. Create a helper function to fetch issue title from beads_id (using BeadsIntegration.get_issue())
2. Modify status command to call helper when agent has beads_id
3. Update display format to show: `agent_id - Title: issue_title` (or similar)
4. Handle errors gracefully (beads CLI not found, issue not found)

Limitation: Only works for agents spawned with `--issue`. Ad-hoc agents won't have issue titles (which is expected behavior).

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

All data structures and methods needed already exist in codebase. The check command demonstrates the exact pattern we need. Implementation is straightforward with clear precedent.

**What's certain:**

- ✅ Agents have beads_id field when spawned with --issue (confirmed via code inspection)
- ✅ BeadsIntegration.get_issue() works and returns title (used in check command)
- ✅ Exact modification points identified (lines 297/311/324/341 in status command)

**What's uncertain:**

- ⚠️ Performance impact of fetching issue titles for multiple agents (need to consider caching)
- ⚠️ Error handling strategy when beads CLI unavailable (fail silently vs show warning)
- ⚠️ Display format preference (inline vs separate line, truncation strategy for long titles)

**What would increase confidence to Very High:**

- Manual testing with real agents spawned from issues
- Confirmation of desired display format from orchestrator
- Performance testing with 10+ agents to validate no slowdown

---

## Implementation Recommendations

### Recommended Approach ⭐

**Fetch and display inline with caching** - Add a helper function to fetch issue title with basic caching, display inline after agent ID.

**Why this approach:**
- Minimal code changes - reuse existing BeadsIntegration pattern from check command (Finding 2)
- No UI complexity - simple inline display: `agent-id - "Issue title"` format
- Performance-conscious - cache fetched titles to avoid repeated bd calls for same issue

**Trade-offs accepted:**
- Cache invalidation complexity deferred (titles rarely change mid-session)
- Long titles not truncated initially (can add if becomes problem)
- Error handling is silent (fails gracefully to just showing agent ID)

**Implementation sequence:**
1. Add helper function `_get_issue_title(beads_id, db_path)` - returns title or None on error
2. Build cache dict at start of status command from all agent beads_ids
3. Modify display lines to append ` - "title"` when title available
4. Test with mixed agents (some with issues, some without)

---

### Implementation Details

**What to implement first:**
1. Helper function `_get_issue_title(beads_id, db_path=None)` at module level (before status command)
   - Try BeadsIntegration(db_path=db_path).get_issue(beads_id)
   - Return issue.title on success, None on BeadsCLINotFoundError or BeadsIssueNotFoundError
   - Keep simple - no logging, silent failure
2. Build title cache in status command (after filtering agents, before display)
   - Dict[str, str] mapping beads_id -> title
   - Only fetch for agents that have beads_id
3. Update display format in 4 locations (lines 297, 311, 324, 341)
   - Check if agent has beads_id and beads_id in cache
   - Append ` - "{title}"` to display string

**Things to watch out for:**
- ⚠️ Multiple agents might reference same beads_id (cache prevents redundant fetches)
- ⚠️ beads_db_path from agent metadata must be passed to BeadsIntegration
- ⚠️ check command already fetches issue - don't break that flow when adding helper
- ⚠️ JSON output format might also want titles - consider adding to JSON serialization

**Areas needing further investigation:**
- Should JSON format also include issue titles? (separate from human display)
- Truncation strategy for very long titles (>50 chars?)
- Icon/emoji to distinguish issue-based vs ad-hoc agents visually?

**Success criteria:**
- ✅ `orch status` shows titles for agents spawned with --issue
- ✅ Ad-hoc agents (no beads_id) display normally without errors
- ✅ Errors (beads CLI not found, issue not found) fail silently without breaking status output
- ✅ No noticeable performance degradation with 10+ agents

---

## References

**Files Examined:**
- `src/orch/monitoring_commands.py` - Status and check commands, display logic
- `src/orch/beads_integration.py` - BeadsIntegration class and get_issue() method
- `src/orch/registry.py` - Agent registration with beads_id field
- `src/orch/spawn.py` - How beads_id is passed during spawn
- `src/orch/complete.py` - Usage of beads_id for closing issues

**Commands Run:**
```bash
# Check for beads_id usage
grep -n "beads_id" src/orch/*.py

# Verify project location
pwd

# Find monitoring-related files
grep -E "def (status|check|tail|output)" src/orch/*.py --files-with-matches
```

**Related Artifacts:**
- **Workspace:** `.orch/workspace/feat-orch-output-show-issue-06dec/` - Current agent workspace

---

## Investigation History

**2025-12-06 (start):** Investigation started
- Initial question: How can orch status/check show beads issue titles alongside agent IDs?
- Context: Improve readability of agent listings by showing issue titles

**2025-12-06:** Investigation complete
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Straightforward implementation - fetch titles via BeadsIntegration, cache, and display inline
