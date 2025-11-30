---
# WORKSPACE TEMPLATE PHILOSOPHY
#
# This is a regular markdown file - no special skills needed to update it.
# Just use Write/Edit tool to modify as you work.
#
# Workflow:
# 1. Check TODO.org (or backlog) - Review what needs to be done
# 2. Identify theme - Group related TODOs (don't create 1:1 workspace per TODO!)
# 3. Create workspace directory: .claude/workspace/[theme-name]/
# 4. Copy this template to: .claude/workspace/[theme-name]/WORKSPACE.md
# 5. List TODOs as tasks - Add related items to workspace
# 6. Update naturally during work (at transitions, blockers, decisions)
# 7. Let understanding evolve - capture decisions/learnings IN the workspace
# 8. AFTER workspace complete: extract decisions/knowledge (extract-workspace-learnings skill)
# 9. Archive to .claude/workspace/archive/[name]/
#
# Workspace Scope Guidance:
# - Bundle related work (5-15 small tasks OR 1-3 large tasks)
# - Don't create one workspace per TODO item (causes workspace proliferation!)
# - Group by theme: "UX polish", "Auth refactor", "API improvements"
# - Add tasks as discovered during work (umbrella workspace pattern)
# - See AGENTS.md "Workspace Scope Guidelines" for details
#
# Directory structure:
# .claude/workspace/[name]/
# ├── WORKSPACE.md         # This file (required)
# ├── plan.md              # Implementation plan (optional)
# ├── notes.md             # Scratch notes (optional)
# ├── investigation-*.md   # Investigations (optional)
# └── design.md            # Design doc (optional)
#
# Workspace naming convention (Hybrid):
# - Pre-issue: Use descriptive name (e.g., "auth-refactor")
# - Post-issue: Rename with prefix (e.g., "GH-123-auth-refactor")
# - Keep base name consistent when adding issue prefix
#
# Key principle: Capture everything during work. Extract selectively after.
---
# Workspace Metadata
Name: csv-processor  # Base name without issue prefix
Type: Feature  # Feature | Investigation | Refactor | Bug-Fix
Owner: Dylan Conlin
Created: 2025-11-02
Last-Updated: 2025-11-02

# External References
External-References:
  ROADMAP-Phase: null  # Phase ID from docs/ROADMAP.md (e.g., "phase-2-multi-competitor")
  GitHub-Issue: null  # Issue number (without # prefix) if workspace tracks an Issue
  GitHub-Issues-Created: []  # Issues spawned from this workspace for delegation
  GitHub-PRs: []      # PR numbers when created
  Related-Issues: []  # Other related issues

# Field Descriptions:
# - ROADMAP-Phase: Link workspace to strategic phase (enables "show workspaces for Phase X")
# - GitHub-Issue: If this workspace tracks a major deliverable Issue Dylan created
# - GitHub-Issues-Created: Track Issues extracted for delegation during workspace work
# - GitHub-PRs: Pull requests associated with this workspace
# - Related-Issues: Other GitHub Issues related to this work

# Phase Tracking
Phase: Complete  # Planning | Implementing | Blocked | Paused | Integrating | Reviewing | Complete
Progress: "All tasks complete - CSV processor implemented with 9 passing tests"

# Conversation Tracking
# Tracks each time workspace is resumed in a new conversation
# Hook auto-appends timestamp, Claude adds summary during conversation
Conversations:
  - Resumed-At: 2025-10-29T10:00:00Z
    Summary: "Workspace created, initial planning"
    Phase-Before: null
    Phase-After: Planning

# Metrics (Auto-tracked - Legacy, superseded by Conversations)
Metrics:
  Created: 2025-10-29T00:00:00Z  # Auto-populated by create-workspace.sh
  Resumed-At: []  # Auto-appended by session-start.sh hook
  Time-To-Resume: []  # Auto-calculated (minutes from last-updated to resumed-at)
  Phase-Durations:
    Planning: null  # ISO duration (e.g., PT2H30M = 2h 30m)
    Implementing: null
    Integrating: null
    Reviewing: null
    Complete: null

# Outcome (Filled when archiving)
Outcome:
  Result: null  # Completed | Abandoned | Merged-Into-Other
  Abandonment-Reason: null  # Context-Lost | Requirements-Changed | Blocked | Other
  Archive-Date: null  # YYYY-MM-DD

# Workspace State
Summary:
  Current-Goal: "CSV processor implementation complete - all tests passing"
  Next-Step: null  # Task complete
  Blocking-Issue: null  # Any blockers preventing progress (null if not blocked)

# Update frequency: At every significant transition
# - Starting or completing a task
# - Getting blocked or unblocked
# - Phase transitions
# - Making significant decisions
# - Before taking breaks

Related-Files:
  Workspaces: []  # Links to related workspaces
  Plans: []  # Workspace-specific plans (plan.md in this directory) or cross-workspace plans
  Decisions: []  # Links added AFTER extraction (extract-workspace-learnings skill)
  Investigations: []  # Links added during work (when creating investigation files)
  Knowledge: []  # Links added AFTER extraction (extract-workspace-learnings skill)
  TODO-org-refs: []  # References to TODO.org items (discovered-in context)

# ⚠️ IMPORTANT: If plan.md exists in this directory, update it when updating workspace progress!
# plan.md contains detailed checklists - keep checkboxes in sync with Progress field above
---

# Python CSV Processor

## Context
Simple Python script to process CSV files and calculate column averages
- Test task to assess development workflow and prompts
- Requirements: Read CSV, calculate numeric column averages, write summary, error handling, unit tests
- No external dependencies beyond Python standard library

## TODO.org References
<!-- If this workspace was created from TODO.org items, list them here -->
<!-- Benefit: Traceability between backlog and implementation -->
<!-- Update TODO.org as you complete items: mark DONE, add workspace link, commit hash -->

**Theme:** [e.g., "UX polish based on stakeholder feedback"]

**TODO items addressed:**
- [ ] Item 1 (TODO.org line 272)
- [ ] Item 2 (TODO.org line 576)
- [ ] Item 3 (TODO.org line 577)

**Discovered during work:**
- [ ] Item 4 (found while fixing Item 1)

## Risk & Assumptions
- **Risks:** None significant - simple test task
- **Assumptions:** Python 3.x available, standard library CSV module sufficient

## Invariants
- Unit tests must pass
- Error handling for missing files required
- No external dependencies (standard library only)

---

## Decisions Made

<!-- Capture decisions and reasoning IN the workspace as you work -->
<!-- Extract to decision records AFTER workspace if they meet threshold -->
<!-- Threshold: architectural impact, cross-project, non-obvious trade-offs -->
<!-- Most decisions stay in workspace only - extract selectively -->

### 2025-11-02 Decision Title
**Why:** [Reasoning - be specific about factors that influenced this choice]
**Alternatives:** [What else was considered and why not chosen]
**Trade-offs:** [What you're accepting/giving up with this choice]
**Link:** [file://.claude/decisions/YYYYMMDD-decision.md] (added AFTER extraction)

---

## Learnings

<!-- Capture understanding as it emerges during work -->
<!-- Extract to knowledge files AFTER workspace if they meet threshold -->
<!-- Threshold: will need again, complex to forget, foundational, non-obvious -->
<!-- Focus on HOW things work, patterns, gotchas, "aha moments" -->

### [Topic/Pattern Name]
**What:** [What did you learn?]
**Why it matters:** [Why is this understanding important?]
**Gotchas:** [Surprises, edge cases, non-obvious behavior]
**Link:** [file://.claude/knowledge/topic.md] (added AFTER extraction)

---

## Stable Components
[What's working and doesn't need revisiting]
- ✅ JWT signing/verification
- ✅ Token validation middleware
- ✅ Core auth tests passing

## Current Issues
[Active problems being worked]
- ❌ Redis connection pooling timeouts
  - Evidence: [link to investigation]
  - Status: [Investigating|Fix in progress]

## Tried and Failed
[Critical: what didn't work and why]
- **HTTP-only cookies for refresh tokens**
  - Why it failed: Broke mobile app (can't access cookies)
  - Reverted: commit abc123
  - Learning: Mobile needs different auth strategy

---

## Validation Evidence

<!-- REQUIRED before marking Phase: Complete -->
<!-- Document evidence that your work actually works -->
<!-- Meta-orchestrators need evidence to verify claims without re-testing -->

**Tests written and passing:**
```
test_calculate_averages_mixed_data (__main__.TestCSVProcessor.test_calculate_averages_mixed_data)
Test calculating averages with mixed numeric/non-numeric data. ... ok
test_calculate_averages_numeric_columns (__main__.TestCSVProcessor.test_calculate_averages_numeric_columns)
Test calculating averages for numeric columns. ... ok
test_process_csv_end_to_end (__main__.TestCSVProcessor.test_process_csv_end_to_end)
Test complete CSV processing workflow. ... ok
test_process_csv_missing_file_error (__main__.TestCSVProcessor.test_process_csv_missing_file_error)
Test error handling for missing input file. ... ok
test_read_csv_empty_file (__main__.TestCSVProcessor.test_read_csv_empty_file)
Test that ValueError is raised for empty CSV files. ... ok
test_read_csv_file_not_found (__main__.TestCSVProcessor.test_read_csv_file_not_found)
Test that FileNotFoundError is raised for missing files. ... ok
test_read_csv_no_data_rows (__main__.TestCSVProcessor.test_read_csv_no_data_rows)
Test that ValueError is raised for CSV with headers but no data. ... ok
test_read_csv_success (__main__.TestCSVProcessor.test_read_csv_success)
Test reading a valid CSV file. ... ok
test_write_summary (__main__.TestCSVProcessor.test_write_summary)
Test writing summary to CSV file. ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.004s

OK
```

**Scripts/code executable and working:**
```
$ python3 csv_processor.py products.csv
Processed products.csv
Summary written to summary.csv

Column averages:
  price: 18.33
  quantity: 72.50

$ cat summary.csv
column,average
price,18.33
quantity,72.50
```

**What I validated:**
- [x] Tests pass (9 tests, all passing)
- [x] Code runs without errors (successfully processed products.csv)
- [x] Feature works as expected (calculates averages correctly, writes summary)
- [x] Error handling works (tests verify FileNotFoundError and ValueError handling)

**Evidence location:** Run `python3 test_csv_processor.py -v` or `python3 csv_processor.py products.csv`

**Why this section exists:**
- Evidence hierarchy: Visual > Command output > Claims
- Prevents "tested successfully" claims without proof
- Enables meta-orchestrators to spot-check without re-running everything
- Workers self-validate (saves time), meta spot-checks (ensures quality)

---

## Next Steps
1. [Concrete action]
2. [Concrete action]
3. [Concrete action]

---

## Related Files
- **Code:** src/auth/jwt.js, src/auth/middleware.js
- **Tests:** tests/auth.test.js
- **Docs:** docs/auth-architecture.md
- **Investigations:** file://.claude/investigations/redis-timeout.md
- **Decisions:** file://.claude/decisions/20250125-use-redis.md

---

## Template Usage Notes

### Progress Field Guide
- Keep Phase strict for AI parsing (state machine values only)
- Use Progress for natural language context
- Examples:
  - "2/5 tasks complete - just finished duplicate removal"
  - "Executing Task 3: Add logging to completion module"
  - "Implementation complete, tests passing, ready for review"

### Summary Best Practices
- **Current Goal** should be specific enough to understand 3 days later
  - ✅ "Implementing user authentication with JWT tokens"
  - ✅ "Task 2 complete, ready for Task 3 (add logging)"
  - ✅ "Debugging test failures in payment processing"
  - ❌ "Working on stuff"
  - ❌ "Almost done"
  - ❌ "2 of 5 complete" (use Progress field instead)

- **Next Step** must be actionable
  - ✅ "Run integration tests to verify auth flow"
  - ✅ "Continue with Task 3: Add error handling"
  - ✅ "Ask user about preferred caching strategy"
  - ❌ "Keep working"
  - ❌ "Figure it out"

- **Update Summary at every significant transition:**
  - Starting a task
  - Completing a task
  - Getting blocked
  - Unblocked and resuming

### Metrics Field
- **Created:** Timestamp when workspace was first created (ISO 8601)
- **Resumed-At:** Array of timestamps when workspace was resumed
- **Time-To-Resume:** Array of minutes between last update and resume
- **Phase-Durations:** Time spent in each phase (ISO 8601 duration format)

These metrics are auto-tracked by hooks when yq is available. Manual updates are fine if hooks not configured.

## Cross-Workspace Issues (Optional)

<!-- Use this section for quick capture of issues that belong to OTHER workspaces or are out-of-scope -->
<!-- Better: Use TODO.org for quick capture (see AGENTS.md § Information Architecture) -->

**Pattern:**
- Discovered issue in workspace B while working in workspace A?
- Quick capture to TODO.org with :discovered-in: metadata
- Triage later: add to workspace B, create new workspace, or quick fix

**Example:**
```org
* TODO workspace B needs plan.md file
  :PROPERTIES:
  :discovered-in: workspace/current-workspace-name
  :discovered-at: YYYY-MM-DD HH:MM
  :category: Documentation
  :scope: workspace/workspace-b
  :END:
```

See AGENTS.md § "Information Architecture & Quick Capture" for full workflow.

---
