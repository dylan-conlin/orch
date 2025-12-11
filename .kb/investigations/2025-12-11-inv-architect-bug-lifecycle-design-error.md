**TLDR:** Question: How should we design bug lifecycle to address error linkage, repro verification, and regression detection? Answer: Three-phase implementation - (1) Error IDs in beads via `error_ref` field, (2) Mandatory repro sections with `--verify-repro` flag on bug closure, (3) Error fingerprinting for regression detection via pattern matching. High confidence (80%) - design builds on existing infrastructure but repro verification workflow needs user testing.

---

# Investigation: Bug Lifecycle Architecture Design

**Question:** How should orch-cli's bug lifecycle be designed to address error→issue linkage, repro verification, and regression detection?

**Started:** 2025-12-11
**Updated:** 2025-12-11
**Owner:** inv-architect-bug-lifecycle-11dec
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (80%)

---

## Context

Prior investigation (`.kb/investigations/2025-12-11-inv-bug-handling-analysis-orch-cli.md`) identified three critical gaps:

1. **No error→issue linkage**: Errors logged but not connected to beads issues
2. **No repro verification**: Bug closure only checks Phase: Complete, not actual fix
3. **No regression detection**: Same bugs can recur undetected

This design addresses all three gaps while building on existing infrastructure.

---

## Findings

### Finding 1: Existing Error Infrastructure is Sufficient

**Evidence:**
- `~/.orch/errors.jsonl` already captures structured errors:
  ```json
  {
    "timestamp": "2025-12-09T11:06:53Z",
    "command": "orch complete ...",
    "error_type": "AGENT_NOT_FOUND",
    "message": "Agent 'xyz' not found",
    "context": {"agent_id": "xyz"}
  }
  ```
- Error types are consistent: AGENT_NOT_FOUND, UNEXPECTED_ERROR, VERIFICATION_FAILED, BEADS_ERROR
- `agentlog_integration.py` provides ErrorEntry dataclass and query methods

**Source:**
- `~/.orch/errors.jsonl` - 110+ error entries with consistent schema
- `src/orch/agentlog_integration.py:19-30` - ErrorEntry dataclass

**Significance:** No new error logging infrastructure needed. The linkage problem is purely relational - connecting errors to issues.

---

### Finding 2: BeadsIssue Notes Field Supports JSON Metadata

**Evidence:**
- `BeadsIssue.notes` field already stores JSON:
  ```python
  def update_agent_notes(self, issue_id, agent_id=None, window_id=None,
                         phase=None, skill=None, project_dir=None, investigation_path=None):
      # Merges updates into existing JSON notes
  ```
- Notes already contain: agent_id, window_id, phase, skill, project_dir, investigation_path

**Source:**
- `src/orch/beads_integration.py:618-679` - update_agent_notes() implementation

**Significance:** Can add `error_ref` field to notes without schema migration. Extends existing pattern.

---

### Finding 3: Bug Closure Verification is Single-Check

**Evidence:**
- `close_beads_issue()` only checks phase:
  ```python
  if verify_phase:
      current_phase = beads.get_phase_from_comments(beads_id)
      if not current_phase or current_phase.lower() != "complete":
          raise BeadsPhaseNotCompleteError(beads_id, current_phase)
  ```
- No validation of:
  - Repro steps executed
  - Test results
  - Original error no longer occurring

**Source:**
- `src/orch/complete.py:93-127` - close_beads_issue() function

**Significance:** Verification is extensible - can add repro check as additional validation layer.

---

### Finding 4: Error Similarity Can Use Message Fingerprinting

**Evidence:**
- Error messages have consistent structure: `[error_type]: [message]`
- Message content varies but core patterns repeat:
  - "Git validation error: uncommitted changes..."
  - "Agent 'X' not found..."
  - "Beads issue 'X' not found..."
- Context dict provides structured matching (agent_id, file paths, etc.)

**Source:**
- `~/.orch/errors.jsonl` - analyzed 20 sample errors

**Significance:** Can fingerprint errors using normalized message + error_type for regression matching.

---

## Synthesis

**Key Insights:**

1. **Build on notes field** - BeadsIssue.notes already supports JSON metadata. Adding error_ref is a natural extension.

2. **Phase verification pattern** - The Phase: Complete check pattern can be extended to include repro verification.

3. **Error fingerprinting** - Normalizing error messages (removing IDs, timestamps) enables regression detection via pattern matching.

4. **Incremental implementation** - Each of the three features can be implemented independently.

**Answer to Investigation Question:**

The bug lifecycle should be designed with three independent but connected features:

1. **Error→Issue Linkage**: Add `error_ref` field to beads notes containing error fingerprint
2. **Repro Verification**: Add `--verify-repro` flag to `orch complete` requiring test/command validation
3. **Regression Detection**: Match new errors against historical fingerprints via `orch errors match`

---

## Architecture Design

### 1. Error→Issue Linkage

**Data Model:**
```python
# New field in BeadsIssue notes JSON
{
    "error_ref": {
        "fingerprint": "GIT_VALIDATION_ERROR:uncommitted_changes",
        "original_error_id": "err_2025120911065382",
        "error_type": "UNEXPECTED_ERROR",
        "first_seen": "2025-12-09T11:06:53Z"
    },
    # ... existing fields
}
```

**API Changes:**

```python
# beads_integration.py additions
def link_error_to_issue(self, issue_id: str, error_fingerprint: str,
                        error_id: Optional[str] = None) -> None:
    """Link an error to a beads bug issue."""

def get_error_ref(self, issue_id: str) -> Optional[dict]:
    """Get error reference from issue notes."""
```

**CLI Integration:**
```bash
# Create bug with error linkage
bd create "Fix git validation error" --type=bug
orch bug link orch-cli-xyz --error-id=err_123

# Or automatically during error
# (errors.jsonl entry includes beads_id if in bug-fix context)
```

**Implementation Steps:**
1. Add `error_ref` field to notes schema
2. Add `link_error_to_issue()` method to BeadsIntegration
3. Add `orch bug link` command
4. Auto-link when errors occur during bug-fix work

---

### 2. Repro Verification

**Concept:** Bug closure requires either:
- Running repro command that now succeeds (expected exit code)
- Running test that now passes
- Explicit `--skip-repro` flag with reason

**Data Model:**
```python
# Bug issue description template
"""
## Bug: [title]

### Repro Steps
```bash
cd /project
command-that-fails
# Expected: exit 0, Actual: exit 1
```

### Repro Command
`command-that-fails`

### Expected After Fix
Exit code 0 (or specific output)
"""
```

**API Changes:**

```python
# complete.py additions
def verify_bug_repro(issue_id: str, project_dir: Path) -> tuple[bool, str]:
    """
    Verify bug is fixed by running repro command.

    Returns:
        (passed, message) - whether repro validation passed
    """
    beads = BeadsIntegration()
    issue = beads.get_issue(issue_id)

    if issue.issue_type != "bug":
        return (True, "Not a bug issue, skipping repro verification")

    repro_cmd = extract_repro_command(issue.description)
    if not repro_cmd:
        return (False, "Bug has no repro command in description")

    # Run repro command
    result = subprocess.run(repro_cmd, shell=True, capture_output=True)

    # Bug should now NOT reproduce (success exit)
    if result.returncode == 0:
        return (True, f"Repro command succeeded (bug fixed)")
    else:
        return (False, f"Repro command still fails: {result.stderr[:200]}")
```

**CLI Flow:**
```bash
# Bug creation enforces repro template
orch bug create "Fix database timeout" --repro "python test_db.py"

# Bug closure validates repro
orch complete agent-xyz
# Output: "Running repro verification..."
# Output: "✅ Repro command 'python test_db.py' now passes"

# Skip with explicit reason
orch complete agent-xyz --skip-repro "Manual UI testing verified"
```

**Implementation Steps:**
1. Add repro command extraction from description
2. Add `verify_bug_repro()` function
3. Integrate into `complete_agent_work()` for bug issues
4. Add `--skip-repro` flag with required reason
5. Log repro verification results

---

### 3. Regression Detection

**Concept:** When an error occurs, check if it matches a previously-fixed bug.

**Error Fingerprinting:**
```python
def fingerprint_error(error_type: str, message: str) -> str:
    """
    Create normalized fingerprint from error.

    Normalizations:
    - Remove UUIDs/hashes
    - Remove timestamps
    - Remove file paths (keep patterns)
    - Lowercase
    """
    normalized = message.lower()

    # Remove dynamic IDs
    normalized = re.sub(r'[a-f0-9]{8,}', '<ID>', normalized)
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '<DATE>', normalized)
    normalized = re.sub(r'/users/\w+/', '/users/<USER>/', normalized)

    return f"{error_type}:{hashlib.md5(normalized.encode()).hexdigest()[:12]}"
```

**Matching Algorithm:**
```python
def find_matching_bugs(fingerprint: str) -> List[BeadsIssue]:
    """
    Find closed bugs that match this error fingerprint.

    Returns bugs where error_ref.fingerprint matches.
    """
    beads = BeadsIntegration()

    # Query closed bugs
    closed_bugs = beads.list_issues(status="closed", issue_type="bug")

    matches = []
    for bug in closed_bugs:
        error_ref = beads.get_error_ref(bug.id)
        if error_ref and error_ref.get("fingerprint") == fingerprint:
            matches.append(bug)

    return matches
```

**CLI Integration:**
```bash
# Check for regression on new error
orch errors check-regression

# Output:
# ⚠️  Error matches previously-fixed bug:
#   orch-cli-abc: "Fix git validation race"
#   Closed: 2025-12-09
#   Repro: git validation error with .beads/ changes
#
# Consider reopening: bd reopen orch-cli-abc
```

**Implementation Steps:**
1. Add `fingerprint_error()` function
2. Store fingerprint when linking error to bug
3. Add `find_matching_bugs()` function
4. Add `orch errors check-regression` command
5. Optional: auto-check on every error log

---

## Confidence Assessment

**Current Confidence:** High (80%)

**Why this level?**
Design builds directly on existing infrastructure. Error logging exists, notes field exists, verification pattern exists. Main uncertainty is repro verification UX.

**What's certain:**

- ✅ **Notes field extensibility** - Already stores JSON, adding error_ref is straightforward
- ✅ **Error fingerprinting feasibility** - Analyzed error messages, patterns are normalizable
- ✅ **Verification integration point** - complete.py already has verification hooks

**What's uncertain:**

- ⚠️ **Repro command reliability** - May have environment dependencies
- ⚠️ **Fingerprint collision rate** - Needs testing with more error samples
- ⚠️ **User adoption of repro workflow** - Adds friction to bug closure

**What would increase confidence to Very High (95%+):**

- Implement Phase 1 (error linkage) and validate workflow
- Test fingerprinting on 100+ real errors
- User testing of repro verification workflow

---

## Implementation Recommendations

**Purpose:** Bridge from design to actionable implementation with clear priorities.

### Recommended Approach ⭐

**Phased Implementation** - Build error linkage first, then repro verification, then regression detection.

**Why this approach:**
- Each phase delivers standalone value
- Phase 1 enables Phase 3 (linkage needed for fingerprint storage)
- Phase 2 can be optional/gradual adoption

**Trade-offs accepted:**
- More implementation work than all-at-once
- Temporary partial solution state
- Acceptable because incremental value delivery

**Implementation sequence:**

**Phase 1: Error→Issue Linkage (1-2 days)**
1. Add `error_ref` to notes schema
2. Add `link_error_to_issue()` method
3. Add `orch bug link` command
4. Document workflow

**Phase 2: Repro Verification (2-3 days)**
1. Add repro extraction from description
2. Add `verify_bug_repro()` function
3. Integrate with `orch complete`
4. Add `--skip-repro` flag

**Phase 3: Regression Detection (2-3 days)**
1. Add `fingerprint_error()` function
2. Store fingerprint on error linkage
3. Add `find_matching_bugs()` function
4. Add `orch errors check-regression` command

### Alternative Approaches Considered

**Option B: External Bug Tracking Integration**
- **Pros:** Leverage existing tools (GitHub Issues, Jira)
- **Cons:** Adds dependency, breaks beads simplicity
- **When to use instead:** If beads is deprecated

**Option C: Agentlog-First Architecture**
- **Pros:** External tool handles error correlation
- **Cons:** Feature depends on external development
- **When to use instead:** If agentlog adds issue linkage

**Rationale for recommendation:** Building on existing beads + orch infrastructure is simpler, has fewer dependencies, and delivers value faster.

---

### Implementation Details

**What to implement first:**
1. `error_ref` field in notes (foundation for linkage + regression)
2. `link_error_to_issue()` method (core linkage API)
3. `orch bug link` command (user-facing linkage)

**Things to watch out for:**
- ⚠️ **Notes field size limit** - Don't bloat with full error messages
- ⚠️ **Fingerprint stability** - Changing normalization breaks regression matching
- ⚠️ **Repro environment** - Commands may need working directory context

**Areas needing further investigation:**
- Optimal fingerprint normalization rules
- How to handle multi-cause bugs (multiple error types)
- Repro command timeout and output limits

**Success criteria:**
- ✅ Every closed bug can have linked error_ref
- ✅ Bug closure for bugs with repro requires passing repro OR explicit skip
- ✅ New errors matching closed bugs trigger warning
- ✅ False fix rate measurably decreases (track over 30 days)

---

## File Changes Required

### New Files
- `src/orch/bug_lifecycle.py` - Bug-specific functions (linkage, repro, regression)

### Modified Files
- `src/orch/beads_integration.py` - Add `link_error_to_issue()`, `get_error_ref()`
- `src/orch/complete.py` - Add repro verification for bug issues
- `src/orch/cli.py` - Add `orch bug` subcommand group

### New Commands
```
orch bug link <beads-id> --error-id=<id>  # Link error to bug
orch bug create "title" --repro "cmd"      # Create bug with repro
orch errors check-regression               # Check new errors for regressions
```

---

## References

**Files Examined:**
- `src/orch/beads_integration.py` - BeadsIssue dataclass, notes field handling
- `src/orch/complete.py` - Bug closure verification
- `src/orch/logging.py` - Error logging format
- `src/orch/agentlog_integration.py` - External error tool integration
- `~/.orch/errors.jsonl` - Error log structure and content

**Commands Run:**
```bash
# Error log analysis
head -20 ~/.orch/errors.jsonl

# Log format check
head -10 ~/.orch/logs/orch-2025-12.log
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-11-inv-bug-handling-analysis-orch-cli.md` - Gap analysis that prompted this design
- **Investigation:** `.kb/investigations/2025-12-10-design-orchestration-architecture-native-cli-optimal.md` - Identified bug lifecycle as needing separate design

---

## Investigation History

**2025-12-11 10:05:** Investigation started
- Initial question: How should bug lifecycle be designed?
- Context: Prior investigation identified gaps, design work needed

**2025-12-11 10:15:** Existing infrastructure analyzed
- Confirmed errors.jsonl structure
- Confirmed BeadsIssue.notes extensibility
- Confirmed verification integration points

**2025-12-11 10:30:** Architecture designed
- Error→Issue linkage via error_ref field
- Repro verification via verify_bug_repro()
- Regression detection via fingerprinting

**2025-12-11 10:45:** Investigation completed
- Final confidence: High (80%)
- Status: Complete
- Key outcome: Three-phase implementation plan with clear API design

---

## Self-Review

- [x] Real test performed (analyzed existing code, error logs, prior investigations)
- [x] Conclusion from evidence (design based on verified infrastructure capabilities)
- [x] Question answered (comprehensive architecture for all three gaps)
- [x] File complete
- [x] TLDR filled

**Self-Review Status:** PASSED

---

## Discovered Work

During this investigation, the following actionable items were identified:

1. **Task:** Implement Phase 1 - Error→Issue Linkage
   - Add error_ref field and linkage methods
   - Create via: `bd create "Implement error→issue linkage in bug lifecycle" --type=task`

2. **Task:** Implement Phase 2 - Repro Verification
   - Add repro extraction and verification
   - Create via: `bd create "Implement repro verification for bug closure" --type=task`

3. **Task:** Implement Phase 3 - Regression Detection
   - Add fingerprinting and matching
   - Create via: `bd create "Implement regression detection for bugs" --type=task`

These tasks should be created when ready to begin implementation.
