**TLDR:** Question: How can beads-ui better reflect agent work state and progress? Answer: Orch-cli already sends critical data (phase updates, workspace links, investigation paths, agent metadata) to beads via comments/notes, but monitor-webui doesn't parse or display it. Recommendation: Add phase column to UI by parsing "Phase: X" comments - provides 80% of value with minimal effort. High confidence (85%) - verified by examining actual code and testing beads CLI.

---

# Investigation: Beads-UI Enhancement Opportunities

**Question:** How can beads-ui better reflect agent work state, implementation progress, and workspace links based on data available from orch-cli beads integration?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Investigation agent (inv-beads-enhancement-06dec)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (85%)

---

## Findings

### Finding 0: Status vs Phase - Important Distinction

**Evidence:**
- **Status (beads lifecycle):** orch DOES update this - open → in_progress → closed
  - `orch spawn --issue <id>` sets status="in_progress" (spawn_commands.py:241)
  - `orch complete` sets status="closed" (complete.py:1235)
  - UI displays status in table view (app.js:131)
- **Phase (agent work progress):** orch sends via comments, UI does NOT display
  - Planning → Implementing → Validating → Complete (changes many times)
  - Stored in comments: `"Phase: Planning - description"` (beads_integration.py:311-332)
  - Not parsed or displayed by UI (app.js has no comment parsing)

**Source:**
- src/orch/spawn_commands.py:241 (status update at spawn)
- src/orch/complete.py:1235 (status update at complete)
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:131 (status rendering)
- Test: `bd list --status=in_progress --json` shows 4 issues with status="in_progress"

**Significance:** Status tracking works correctly - the gap is **phase** (granular work progress) not being displayed. Users can see "in_progress" in UI, but can't distinguish between "Planning" vs "Implementing" vs "Complete" phases.

---

### Finding 1: Agent Phase Information is Sent but Not Displayed

**Evidence:**
- Orch-cli sends phase updates via `bd comment <id> "Phase: Planning - description"` (beads_integration.py:311-332)
- Agents report phase in comments like: `{"text": "Phase: Planning - Exploring codebase...", "created_at": "2025-12-07T04:19:29Z"}`
- Monitor WebUI does not parse or display phase information from comments (app.js:210-222)
- UI shows status (open/in_progress/closed) but not phase (Planning/Implementing/Complete)
- Phase parsing exists in orch-cli (beads_integration.py:197-245) but not in beads-ui

**Source:**
- src/orch/beads_integration.py:197-245, 311-332
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:210-222
- Test: `bd comments orch-cli-cdu --json` showed phase comments exist

**Significance:** Users cannot see granular agent work progress (Planning → Implementing → Complete) in the web UI. They only see coarse lifecycle status (in_progress). This is the highest-impact enhancement opportunity.

---

### Finding 2: Workspace and Investigation Paths Are Hidden in Comments

**Evidence:**
- Workspace links stored in beads notes field: `workspace: .orch/workspace/{name}` (beads_integration.py:134-146)
- Investigation paths sent via comments: `investigation_path: /path/to/file.md` (beads_integration.py:261-309)
- Monitor WebUI displays notes field in detail modal (app.js:220) but doesn't parse workspace links
- Investigation paths in comments are not displayed at all in UI
- Notes field shows raw text: "workspace: .orch/workspace/inv-beads-enhancement-06dec"

**Source:**
- src/orch/beads_integration.py:134-146 (workspace link), 261-309 (investigation path)
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:220
- Test: `bd show orch-cli-cdu --json | jq '.[] | .notes'` confirmed workspace path in notes

**Significance:** Users cannot easily navigate to workspaces or investigation artifacts from the UI. Would require manual copy-paste of paths from notes field.

---

### Finding 3: Agent Metadata is in Comments, Not in Beads Issue Fields

**Evidence:**
- Agent metadata (agent_id, window_id, skill, project_dir) stored as JSON in comments: `agent_metadata: {"agent_id": "...", "window_id": "...", ...}` (beads_integration.py:334-372)
- Comments API returns: `{"text": "agent_metadata: {...}", "created_at": "..."}`
- Beads issue model has assignee, labels fields that are used for other purposes
- Monitor WebUI doesn't fetch or display comments except in mutations (app.js:76-82)
- Skill name and project directory are not visible anywhere in UI

**Source:**
- src/orch/beads_integration.py:334-372 (add_agent_metadata, get_agent_metadata)
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:76-82, 206-228
- Test: Verified no comments displayed in issue detail modal

**Significance:** Important agent context (skill type, project, tmux window) is invisible in UI. Users must use `bd comments <id> --json` to see this data.

---

### Finding 4: Rich Agent State Data Available in Orch Registry Not Sent to Beads

**Evidence:**
- Agent registry tracks: status (active/completed/terminated), spawned_at, updated_at, backend, is_interactive (registry.py:301-312)
- Only status changes reported to beads are: in_progress (at spawn) → closed (at complete)
- No intermediate status updates (e.g., "completed but not yet orch-completed", "abandoned", "terminated")
- Context usage, git state, verification results not sent to beads at all
- Orch status command shows phase, but beads UI does not (monitor.py:110-187)

**Source:**
- src/orch/registry.py:301-312 (agent registration)
- src/orch/spawn.py:1715-1731 (beads integration at spawn)
- src/orch/monitoring_commands.py:96-287 (orch status displays phase)
- Test: `orch status --json` shows phase field, `bd list --json` does not

**Significance:** Beads UI shows less information than `orch status`, making it less useful for monitoring agent work. Users still need to use orch CLI for complete picture.

---

### Finding 5: Beads Comments Could Support Structured Data for Progress Tracking

**Evidence:**
- Comments are plain text with no schema enforcement
- Orch-cli uses convention: "Phase: X - description" and "investigation_path: /path"
- Comments API returns chronological list, latest must be parsed (beads_integration.py:235-244)
- No standard format for progress updates, validation status, or phase transitions
- Multiple comment types mixed together (phase updates, investigation paths, agent metadata)

**Source:**
- src/orch/beads_integration.py:197-245 (phase parsing uses regex)
- Test: `bd comments <id> --json` shows unstructured text field
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:76-82 (mutations only)

**Significance:** UI would need complex parsing logic to extract meaningful data from comments. A more structured approach (e.g., JSON fields in beads issue model or typed comment system) would enable richer UI features.

---

## Synthesis

**Key Insights:**

1. **Data Exists But UI Doesn't Display It** - Orch-cli is already sending critical progress information (phase updates, workspace links, investigation paths, agent metadata) to beads via comments and notes. However, the monitor-webui doesn't parse or display this data. This is a UI enhancement opportunity rather than a data collection problem. (Findings 1, 2, 3)

2. **Comments Are Overloaded and Unstructured** - Beads comments serve multiple purposes (phase tracking, investigation paths, agent metadata, user notes) with no schema. This makes parsing difficult and creates ambiguity about data types. A more structured approach (dedicated JSON fields on beads issues or typed comment system) would make UI integration easier. (Finding 5)

3. **Orch Registry Has Richer State Than Beads** - The orch agent registry tracks lifecycle states (active/completed/terminated/abandoned), timestamps, backend type, and runtime metadata that aren't reflected in beads. This creates a gap where `orch status` shows more information than beads-ui. (Finding 4)

**Answer to Investigation Question:**

Beads-ui can be enhanced to better reflect agent work state and progress by:

**High-Impact (UI-side changes):**
1. **Parse and display phase from comments** - Add "Phase" column to table view showing latest phase (Planning/Implementing/Complete). Requires parsing comments for "Phase: X" pattern.
2. **Link to workspace and investigation artifacts** - Parse notes field and investigation_path comments to display clickable links or prominent paths in detail view.
3. **Show agent metadata in detail view** - Parse agent_metadata comments to display skill, project_dir, window_id in a dedicated "Agent Info" section.

**Medium-Impact (orch-cli enhancements):**
4. **Send lifecycle state updates** - Have orch-cli report agent state transitions (spawned → active → completed → terminated) as comments, not just phase changes.
5. **Send structured progress for multi-phase work** - For feature-impl skills with phases (design/implementation/validation), send structured phase completion updates.

**Lower-Impact (beads data model changes):**
6. **Add dedicated fields for agent data** - Instead of comments, use beads issue fields (labels, notes, or new custom fields) for workspace path, current phase, skill type. This would be more performant than parsing comments.

**Not Recommended:**
- Git commit tracking in beads-ui (out of scope for issue tracker)
- Real-time context usage monitoring (performance cost, limited value)
- TMux window integration (too tightly coupled to orch-cli)

---

## Confidence Assessment

**Current Confidence:** High (85%)

**Why this level?**

I examined actual code in both orch-cli and beads monitor-webui, tested the beads CLI to see data structures, and verified that the data flow works as documented. The findings are based on concrete evidence (code, API responses, test commands) rather than speculation.

**What's certain:**

- ✅ Orch-cli sends phase updates via comments - verified in beads_integration.py:311-332 and tested with `bd comments <id> --json`
- ✅ Monitor-webui doesn't parse or display comments - confirmed by reading app.js:76-82, 206-228
- ✅ Workspace links are in notes field - verified in beads_integration.py:134-146 and tested with `bd show <id> --json`
- ✅ Agent metadata stored in comments as JSON - confirmed in beads_integration.py:334-372
- ✅ Beads issue schema includes notes, status, priority, labels - verified with `bd list --json`

**What's uncertain:**

- ⚠️ **Usage patterns** - Don't know how often Dylan actually uses beads-ui vs `orch status`. If UI is rarely used, enhancement value is lower.
- ⚠️ **Beads data model constraints** - Unclear if beads can add custom fields or if comments are the only extension point. May require beads-core changes.
- ⚠️ **UI framework** - Only examined the example monitor-webui. Don't know if Dylan uses a different beads UI or plans to build one.

**What would increase confidence to Very High (95%+):**

- Test the recommendations with a prototype (add phase column to monitor-webui and verify it works)
- Confirm with Dylan which UI is actually used (monitor-webui vs other)
- Check beads schema to see if custom fields are supported (would affect recommendation #6)

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**Phase-First UI Enhancement** - Start by adding phase display to monitor-webui, then iterate on additional features based on usage.

**Why this approach:**
- Highest impact per effort - phase tracking is already implemented in orch-cli, UI just needs to parse comments (Finding 1)
- Addresses the most critical gap - users can't see agent progress without CLI (Finding 1)
- Low risk - purely additive UI change, no orch-cli or beads-core modifications needed
- Validates the parsing approach before investing in more complex features

**Trade-offs accepted:**
- Still uses unstructured comments rather than dedicated beads fields (defer beads-core changes)
- Doesn't address all gaps at once (iteration over big-bang rewrite)
- UI must maintain parsing logic in sync with orch-cli comment format

**Implementation sequence:**
1. **Add phase parsing to monitor-webui** - Fetch comments for each issue, extract latest "Phase: X" using regex (similar to beads_integration.py:237-243). Display in new "Phase" column in table view.
2. **Add workspace/investigation links to detail view** - Parse notes field for "workspace: X" and comments for "investigation_path: X". Display as clickable file:// links or prominent text in detail modal.
3. **Add agent metadata section to detail view** - Parse agent_metadata JSON from comments, display skill, project_dir, window_id in "Agent Info" section of detail modal.
4. **Measure usage** - See if Dylan actually uses the UI features. If not used, stop here. If heavily used, consider next iteration.
5. **Optional: Send richer progress data from orch-cli** - For feature-impl multi-phase work, send structured phase completion updates. Only pursue if step 4 shows value.

### Alternative Approaches Considered

**Option B: Beads-Core Schema Extension**
- **Pros:** More performant (no comment parsing), cleaner data model, type-safe
- **Cons:** Requires changes to beads core (Finding 5), higher complexity, affects all beads users not just orch integration
- **When to use instead:** If beads is being refactored anyway, or if performance becomes an issue with comment parsing at scale

**Option C: Orch-CLI API Endpoint**
- **Pros:** Could provide richer data than beads (context usage, git state, verification status from Finding 4)
- **Cons:** Creates dependency on orch-cli being running, duplicates beads-ui's purpose, doesn't work for historical/completed issues
- **When to use instead:** If real-time monitoring during active agent execution is the primary use case

**Option D: Do Nothing (Stick with `orch status`)**
- **Pros:** No implementation cost, orch status already shows all needed info
- **Cons:** Requires CLI access, no team visibility, no historical view
- **When to use instead:** If beads-ui is rarely used or team collaboration isn't needed

**Rationale for recommendation:** Phase-First UI Enhancement provides immediate value (Finding 1 shows data exists, just needs display) with minimal risk (pure UI change). It validates whether beads-ui is actually valuable before investing in orch-cli changes (Option C) or beads-core changes (Option B). Option D abandons the beads-ui vision entirely.

---

### Implementation Details

**What to implement first:**
1. **Phase column in table view** - Fetch comments for each issue on page load, extract phase using regex `Phase:\s*(\w+)`, display in new column. This alone provides 80% of the value.
2. **Workspace link in detail modal** - Parse notes field for "workspace: {path}" pattern, display in modal. Low effort, high value for navigating to agent workspaces.
3. **Investigation path in detail modal** - Parse comments for "investigation_path: {path}", display alongside workspace link.

**Things to watch out for:**
- ⚠️ **Performance with many issues** - Fetching comments for 50+ issues on page load could be slow. Consider lazy loading (fetch on row click) or caching.
- ⚠️ **Stale phase data** - Comments are chronological, must find latest "Phase: X" comment. If agent reports multiple phase updates, need to parse correctly (Finding 1).
- ⚠️ **Comment format changes** - If orch-cli changes "Phase: X" format to something else, UI parsing breaks. Need coordination or version detection.
- ⚠️ **Mixed comment types** - Agent metadata, phase, investigation_path all in same comments stream. Parsing must distinguish them (Finding 5).
- ⚠️ **File:// links may not work** - Clickable file:// links only work if browser is on same machine as files. May need to show paths as text instead.

**Areas needing further investigation:**
- **Beads custom fields support** - Check if beads issue schema can be extended with custom fields (phase, workspace_path, agent_metadata as first-class fields). Would enable cleaner data model than comment parsing.
- **Real-time phase updates** - Investigate if beads daemon WebSocket broadcasts comment mutations. If yes, UI can update phase in real-time. If no, phase will only update on page refresh.
- **Multi-phase progress tracking** - For feature-impl with design/implementation/validation phases, could display progress bar if orch-cli sends structured updates. Needs design work.

**Success criteria:**
- ✅ User can see agent phase (Planning/Implementing/Complete) in beads-ui table view without using CLI
- ✅ User can click on issue and see workspace path + investigation path (if applicable) in detail modal
- ✅ Phase display updates when agent reports new phase (either real-time or on page refresh)
- ✅ No performance regression - page still loads quickly with 50+ issues
- ✅ Parsing handles edge cases - multiple phase updates, missing phases, malformed comments

---

## References

**Files Examined:**
- src/orch/beads_integration.py:1-478 - Complete beads integration module, shows all data sent to beads
- src/orch/spawn.py:1715-1731 - How beads integration is called at spawn time
- src/orch/registry.py:1-150, 301-312 - Agent registry data model
- src/orch/monitoring_commands.py:96-287 - orch status command implementation
- src/orch/monitor.py:68-189 - Phase detection logic from coordination artifacts
- ~/Documents/personal/beads/examples/monitor-webui/README.md - Monitor WebUI documentation
- ~/Documents/personal/beads/examples/monitor-webui/web/index.html - UI structure
- ~/Documents/personal/beads/examples/monitor-webui/web/static/js/app.js:1-300 - UI rendering and data handling

**Commands Run:**
```bash
# Check beads issue JSON schema
bd list --json | jq '.[0] | keys'

# Check beads comment structure
bd comments orch-cli-cdu --json

# Verify phase comments exist
bd comments orch-cli-cdu --json | jq '.[0]'

# Check workspace path in notes field
bd show orch-cli-cdu --json | jq '.[] | .notes'

# Compare orch status vs beads data
orch status --json
bd list --status=in_progress --json
```

**External Documentation:**
- Beads monitor-webui README.md - Confirms UI architecture and data sources

**Related Artifacts:**
- **Related Issues:** This investigation informs potential beads-ui enhancement work and orch-cli integration improvements

---

## Investigation History

**[2025-12-06 22:01]:** Investigation started
- Initial question: How can beads-ui better reflect agent work state, implementation progress, and workspace links?
- Context: Investigating opportunities to enhance beads UI based on data available from orch-cli beads integration

**[2025-12-06 22:05]:** Examined orch-cli beads integration
- Discovered all key data (phase, workspace, investigation paths, agent metadata) is already being sent to beads via comments/notes
- Identified gap: monitor-webui doesn't parse or display this data

**[2025-12-06 22:15]:** Examined beads monitor-webui code
- Confirmed UI only displays basic issue fields (ID, title, status, priority, type, assignee)
- Found that comments are fetched for mutations but not displayed
- Identified parsing as the main implementation need

**[2025-12-06 22:30]:** Investigation completed
- Final confidence: High (85%)
- Status: Complete
- Key outcome: Beads-ui can be enhanced primarily through UI-side changes (parsing comments) rather than orch-cli or beads-core changes
