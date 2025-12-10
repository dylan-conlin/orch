**TLDR:** Question: How do errors get aggregated across orch, kb, bd, and kn CLIs? Answer: Only orch has error aggregation (via ~/.orch/errors.jsonl). kb, bd, and kn print errors to stderr without logging. High confidence (90%) - verified by testing all CLIs and examining source code.

---

# Investigation: Unified Error Aggregation Across CLI Tools

**Question:** What is the current state of error aggregation across orch, kb, bd, and kn CLIs, and what would unified error aggregation look like?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: orch has comprehensive error logging

**Evidence:**
- orch logs all errors to `~/.orch/errors.jsonl` (currently 87KB)
- Error taxonomy defined in `ErrorType` enum: AGENT_NOT_FOUND, VERIFICATION_FAILED, BEADS_ERROR, SPAWN_FAILED, etc.
- Stats aggregation available via `orch errors` command showing error counts by type and command
- Sample output shows 124 errors in last day, 75% UNEXPECTED_ERROR, 100% from `orch complete`

**Source:**
- `src/orch/error_logging.py:28-39` - ErrorType enum
- `src/orch/error_logging.py:74-151` - ErrorLogger class
- `src/orch/error_commands.py:19-82` - `orch errors` command
- `~/.orch/errors.jsonl` - Error log file

**Significance:** orch has the foundation for error aggregation already built. The schema and aggregation patterns can serve as a model for other CLIs.

---

### Finding 2: bd (beads) has no error logging

**Evidence:**
- `cmd/bd/errors.go` contains only simple helpers: `FatalError()`, `WarnError()`, `FatalErrorWithHint()`
- These print to stderr and exit - no logging to files
- No `~/.beads/errors.jsonl` or similar file exists
- Test: `bd show nonexistent-issue-xyz` prints error to stderr, exits 1, logs nothing

**Source:**
- `/Users/dylanconlin/Documents/personal/beads/cmd/bd/errors.go:21-53`
- `ls -la ~/.beads/` - no errors file

**Significance:** bd errors are invisible to aggregation. When bd fails during orchestration workflows, we lose visibility.

---

### Finding 3: kb has no error logging

**Evidence:**
- Go source uses cobra's RunE pattern - errors returned bubble up to cobra
- No error logging infrastructure found in codebase (grep found no matches for error log patterns)
- Test: `kb create investigation` (missing args) prints error to stderr, exits 1, logs nothing

**Source:**
- `/Users/dylanconlin/Documents/personal/kb-cli/cmd/kb/create.go` - standard cobra error handling
- Grep search for "errors.jsonl" in kb-cli: no results

**Significance:** kb errors equally invisible. Investigation/decision creation failures go untracked.

---

### Finding 4: kn has no error logging

**Evidence:**
- Small Go codebase with no error logging files
- Test: `kn decide "test"` (missing --reason) prints error to stderr, exits 1, logs nothing

**Source:**
- `/Users/dylanconlin/Documents/personal/kn/` - no error logging files
- Command test showing basic stderr output

**Significance:** Knowledge tracking errors untracked - pattern is consistent across Go CLIs.

---

## Synthesis

**Key Insights:**

1. **Asymmetric visibility** - orch errors are tracked and aggregated; bd/kb/kn errors vanish after stderr output. This creates blind spots in debugging orchestration failures - when orch calls bd and bd fails, we see the error in stderr but can't trend it.

2. **Language boundary** - orch is Python, bd/kb/kn are Go. Sharing orch's error_logging.py directly isn't possible. Unification requires either: (a) Go CLIs write to same JSONL format, or (b) wrapper scripts capture all CLI output.

3. **Schema already exists** - orch's JSONL schema (`timestamp`, `command`, `subcommand`, `error_type`, `message`, `context`) is mature and works. Go CLIs could adopt the same format.

**Answer to Investigation Question:**

Currently, error aggregation exists only in orch via `~/.orch/errors.jsonl`. The Go CLIs (bd, kb, kn) have no error logging - they print to stderr and exit. Unified error aggregation would require:

1. **Option A: Shared log file** - All CLIs write to `~/.orch/errors.jsonl` using same schema (requires Go implementation of logging)
2. **Option B: Per-tool logs with unified reader** - Each CLI writes to own file (`~/.bd/errors.jsonl`, etc.) and `orch errors` aggregates across all
3. **Option C: Wrapper-based capture** - Shell wrappers around Go CLIs capture stderr and log to orch format (simplest, least invasive)

Recommendation: Option A is cleanest but highest effort. Option C could be a quick win for immediate visibility.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Verified all four CLIs through source code examination and command testing. The patterns are clear and consistent.

**What's certain:**

- ✅ orch has mature error logging (`~/.orch/errors.jsonl`, ErrorType enum, stats aggregation)
- ✅ bd, kb, kn have no error logging (verified via source code and testing)
- ✅ All CLIs use stderr for error output, exit code 1 for failures
- ✅ Schema for orch error logging is documented and works well

**What's uncertain:**

- ⚠️ Whether Option C (wrapper-based) would capture all relevant error context
- ⚠️ Performance impact of Go CLIs writing to shared JSONL file
- ⚠️ Whether there's appetite for maintaining error logging in multiple codebases

**What would increase confidence to Very High:**

- Prototype implementation of one approach to validate feasibility
- Performance benchmarks if Go CLIs add file logging
- User feedback on which approach would be most useful

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation.

### Recommended Approach ⭐

**Option B: Per-tool logs with unified reader** - Each Go CLI adds JSONL logging to its own config directory, and orch aggregates across all sources.

**Why this approach:**
- Maintains independence of repos (no shared library needed)
- Allows each CLI to evolve its error taxonomy independently
- `orch errors` becomes the unified view across tools
- Simpler than shared file (no concurrent write coordination)

**Trade-offs accepted:**
- More code duplication (Go logging code in bd, kb, kn)
- `orch errors` needs to know about other CLI log locations

**Implementation sequence:**
1. Define unified JSONL schema (timestamp, cli_name, command, error_type, message, context)
2. Add error logging to bd (largest impact - most errors come from beads integration)
3. Update `orch errors` to read from `~/.beads/errors.jsonl` in addition to `~/.orch/errors.jsonl`
4. Add error logging to kb and kn (lower priority - less frequent errors)

### Alternative Approaches Considered

**Option A: Shared log file**
- **Pros:** Single file, simple aggregation
- **Cons:** Concurrent writes from multiple processes, Go CLIs need to write to Python-defined location
- **When to use instead:** If all CLIs were in same repo/language

**Option C: Wrapper-based capture**
- **Pros:** No changes to Go CLIs, immediate implementation
- **Cons:** Loses error context (just captures stderr text), fragile to output format changes
- **When to use instead:** Quick temporary solution while proper logging is implemented

**Rationale for recommendation:** Option B provides clean separation of concerns while achieving unified visibility. Each CLI manages its own logs but follows a shared schema.

---

### Implementation Details

**What to implement first:**
- Define JSONL schema spec (can use orch's existing schema as template)
- Add logging to bd (highest error volume, most integration impact)
- Update `orch errors --all` flag to aggregate across CLI logs

**Things to watch out for:**
- ⚠️ File rotation/cleanup needed (orch has max_entries=10000)
- ⚠️ Go error taxonomy may differ from Python (need mapping)
- ⚠️ Need to handle missing log files gracefully

**Areas needing further investigation:**
- Should error types be shared or per-CLI?
- Is JSONL the right format or should we use something more structured (SQLite)?
- Should there be a shared Go library for logging?

**Success criteria:**
- ✅ `orch errors` shows errors from all CLIs
- ✅ Error patterns visible across tool boundaries
- ✅ SessionStart hook can summarize errors across all tools

---

## References

**Files Examined:**
- `src/orch/error_logging.py` - orch error logging infrastructure
- `src/orch/error_commands.py` - `orch errors` command implementation
- `~/Documents/personal/beads/cmd/bd/errors.go` - bd error handling (no logging)
- `~/Documents/personal/kb-cli/cmd/kb/create.go` - kb error handling pattern
- `~/Documents/personal/kn/` - kn source structure

**Commands Run:**
```bash
# Test orch error aggregation
orch errors --days 1

# Test bd error handling
bd show nonexistent-issue-xyz

# Test kb error handling
kb create investigation

# Test kn error handling
kn decide "test"

# Check config directories for error logs
ls -la ~/.orch/ ~/.beads/ ~/.kb/ ~/.kn/
```

**Related Artifacts:**
- **Source:** `~/.orch/errors.jsonl` - Current orch error log (87KB sample data)

---

## Investigation History

**2025-12-10 10:11:** Investigation started
- Initial question: What is the current state of error aggregation across orch, kb, bd, and kn?
- Context: SessionStart shows errors only from orch; wanted to understand full landscape

**2025-12-10 10:15:** Found orch error infrastructure
- Discovered comprehensive error logging in `error_logging.py` with ErrorType enum and JSONL storage

**2025-12-10 10:25:** Verified Go CLIs have no error logging
- Examined bd, kb, kn source code
- Tested each CLI with invalid inputs to verify behavior

**2025-12-10 10:35:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Only orch has error aggregation; Go CLIs need logging added for unified visibility

---

## Self-Review

- [x] Real test performed (tested all 4 CLIs with error conditions)
- [x] Conclusion from evidence (based on source code and test results)
- [x] Question answered (current state documented, options provided)
- [x] File complete

**Self-Review Status:** PASSED
