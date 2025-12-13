**TLDR:** Issue creation quality comes from understanding-first process, not validation gates. Recommend `issue-creation` skill for non-trivial work (produces rich beads issues), keep investigations as parallel knowledge system for complex understanding. Spawned deeper question: What is "AI-native knowledge management"?

---

# Investigation: Redesigning Issue Creation in orch Ecosystem

**Question:** How can we improve the issue creation process to achieve high-quality, forensic-level issue descriptions (609 char avg, P-S-E structure, file references)?

**Started:** 2025-12-13
**Updated:** 2025-12-13
**Owner:** Claude (architect) + Dylan (interactive)
**Phase:** Complete
**Next Step:** None - follow-up issue created for deeper knowledge system design
**Status:** Complete
**Confidence:** High (80%) - Clear recommendations for issue creation; spawned larger architectural question

---

## Findings

### Finding 1: Yegge's Quality Comes From Process, Not Validation

**Evidence:** Analysis of Steve Yegge's beads database (465 issues) shows:
- 609 character average descriptions
- 65% of issues have rich descriptions
- Problem-Solution-Evidence structure throughout
- Forensic bug reports with timestamps, commit hashes, file:line refs

**Source:** `.kb/investigations/2025-12-13-investigation-beads-issue-management-patterns.md`

**Significance:** The gap isn't in validation gates - it's in PROCESS. Yegge's issues are good because someone understood the problem deeply BEFORE creating the issue. Our current flow (bd create → shallow title → agent figures it out) inverts this.

---

### Finding 2: Current orch Ecosystem Has No "Understanding First" Path

**Evidence:** 
- `bd create "title" --type=task` - title only, no description enforcement
- `--auto-track` uses task as title, no description
- `beads_integration.create_issue()` accepts title + type only
- Spawn patterns assume issue already exists or create shallow ones

**Source:** 
- `orch spawn --help`
- `bd create --help`
- `src/orch/beads_integration.py`

**Significance:** No natural workflow forces or encourages deep understanding before issue creation. The tooling optimizes for velocity, not quality.

---

### Finding 3: Investigations and Beads Serve Different Purposes

**Evidence:** Comparison of systems:

| Dimension | Investigations | Beads Issues |
|-----------|----------------|--------------|
| Purpose | Preserve understanding | Track work |
| Lifecycle | Permanent reference | Complete and close |
| Size | Long-form (200+ lines) | Summary (~600 chars) |
| Scope | Cross-project | Per-repo |
| Search | Full-text grep | Field-based filters |

**Source:** 
- `.kb/investigations/` directory (137 files, avg 200 lines)
- `bd show --json` output structure
- Dylan's input on intended use

**Significance:** These are parallel systems, not hierarchical. Investigations shouldn't be a gateway to issues - they serve different needs. Forcing all issues through investigations adds overhead without proportional value.

---

### Finding 4: The Work Daemon Changes the Architecture

**Evidence:** `work_daemon.py` introduces:
- Polling for `triage:ready` labeled issues
- Auto-spawning via `orch work`
- Focus-based prioritization

**Source:** `src/orch/work_daemon.py:52` - `required_label: str = "triage:ready"`

**Significance:** Issues need proper labeling for daemon integration. An `issue-creation` skill must understand this and label appropriately. The daemon creates a quality gate: only well-formed issues get `triage:ready`.

---

### Finding 5: Deeper Question Emerged - "AI-Native Knowledge Management"

**Evidence:** Dylan identified a pattern across tools:
- `beads (bd)` - AI-native work tracker
- `kn` - Quick knowledge capture (decisions, constraints, attempts)
- `kb` - Knowledge base CLI (investigations, decisions)

The question: What is the AI-native equivalent for knowledge that beads is for work?

**Source:** Dylan's observation during session: "just like beads is an ai-native work tracker, i think i've been trying to create the ai-native 'knowledge ...something'"

**Significance:** This is a foundational architecture question that exceeds the scope of issue creation. It asks: How do AI agents build, access, and evolve institutional memory? This warrants its own deep design exploration.

---

## Synthesis

**Key Insights:**

1. **Understanding-first, not validation-first** - Quality issues come from deep understanding before creation, not from validation gates that enforce structure after the fact.

2. **Parallel systems, not hierarchical** - Investigations and beads issues serve different purposes (knowledge vs work). Neither should be prerequisite for the other. They link when useful, but have independent lifecycles.

3. **Issue-creation as a skill** - A specialized agent can bridge the gap: take a symptom, investigate to understand, produce a rich beads issue with P-S-E structure. The issue IS the deliverable.

4. **Dual-path model** - Trivial issues (obvious cause) can be created directly. Non-trivial issues (symptoms, unclear cause) should go through issue-creation skill.

**Answer to Investigation Question:**

To achieve Yegge-level issue quality:

1. **Create an `issue-creation` skill** that investigates symptoms and produces rich beads issues (not investigations)
2. **Keep investigations for genuine knowledge needs** - complex understanding that outlives any single issue
3. **Use `triage:ready` label** as quality gate for daemon - only well-formed issues get auto-spawned
4. **Deprecate shallow paths** like `--auto-track` for non-trivial work

---

## Confidence Assessment

**Current Confidence:** High (80%)

**Why this level?**

Strong evidence for the issue-creation recommendations. The parallel systems model is validated by Dylan. Lower confidence on exact implementation details.

**What's certain:**

- ✅ Quality comes from understanding-first process (Yegge analysis proves this)
- ✅ Investigations and beads are parallel, not hierarchical (Dylan confirmed)
- ✅ `issue-creation` skill approach resonates with Dylan
- ✅ Daemon integration requires proper labeling

**What's uncertain:**

- ⚠️ Exact skill implementation details
- ⚠️ How `issue-creation` interacts with existing investigation skill
- ⚠️ The deeper "AI-native knowledge" question is unresolved

**What would increase confidence to Very High (95%):**

- Implement `issue-creation` skill and validate with real usage
- Resolve the broader knowledge architecture question
- Test daemon integration with issue-creation output

---

## Implementation Recommendations

### Recommended Approach ⭐

**Dual-path issue creation with `issue-creation` skill for non-trivial work**

**Why this approach:**
- Separates "understanding" from "fixing" (different cognitive modes)
- Agent incentive aligned with output (issue quality = success)
- Matches Yegge's implicit workflow
- Integrates with daemon via `triage:ready` label

**Trade-offs accepted:**
- Adds spawn overhead for non-trivial issues (10-30 min)
- Requires new skill development
- Doesn't solve the deeper knowledge architecture question

**Implementation sequence:**
1. Create `issue-creation` skill with P-S-E template
2. Update orchestrator skill with new spawn triggers
3. Add `triage:ready` / `triage:review` labeling guidance
4. (Optional) Add `orch triage` shortcut command

### Alternative Approaches Considered

**Option B: Push quality into beads itself**
- **Pros:** Single system, no new skill needed
- **Cons:** Doesn't solve the process problem - validation can be gamed
- **When to use instead:** If skill overhead proves too high

**Option C: Investigations as gateway to issues**
- **Pros:** Ensures deep understanding for all non-trivial work
- **Cons:** Overhead for simple issues; conflates knowledge and work
- **When to use instead:** Never - Dylan confirmed parallel model preferred

---

## Follow-Up Work

**Created:** Beads issue for deeper knowledge architecture exploration

The larger question - "What is AI-native knowledge management?" - requires its own investigation. This includes:
- What is the unit of knowledge?
- How do agents create, discover, update knowledge?
- How does knowledge link to work and other knowledge?
- What's the relationship between kn, kb, and potential future tools?

---

## References

**Files Examined:**
- `.kb/investigations/2025-12-13-investigation-beads-issue-management-patterns.md` - Yegge analysis
- `src/orch/work_daemon.py` - Daemon architecture
- `src/orch/spawn_commands.py` - Current spawn patterns
- `src/orch/beads_integration.py` - Beads integration

**Commands Run:**
```bash
# Check daemon label requirement
grep "required_label" src/orch/work_daemon.py

# Check bd create capabilities  
bd create --help

# Check kn and kb tools
kn --help
kb --help
```

**Related Artifacts:**
- **Investigation:** `.kb/investigations/2025-12-13-investigation-beads-issue-management-patterns.md` - Source analysis of Yegge's patterns

---

## Investigation History

**2025-12-13 11:48:** Investigation started
- Initial question: How to achieve Yegge-level issue quality?
- Context: Analysis of Yegge's beads database showed dramatically higher quality than ours

**2025-12-13 12:15:** Key insight identified
- Dylan: "The gap isn't in validation - it's in PROCESS"
- Shifted focus from gates to workflow

**2025-12-13 12:45:** Explored three approaches
- Issue-creation spawns (recommended)
- Investigation → issue promotion
- Gated issue creation

**2025-12-13 13:00:** Parallel systems model confirmed
- Dylan confirmed investigations and beads serve different purposes
- Neither should be prerequisite for other

**2025-12-13 13:30:** Deeper question emerged
- "AI-native knowledge management" identified as larger architectural question
- Decided to capture current findings and create follow-up issue

**2025-12-13 13:45:** Investigation completed
- Final confidence: High (80%)
- Status: Complete
- Key outcome: Recommend `issue-creation` skill + parallel systems model; spawned deeper knowledge architecture question
