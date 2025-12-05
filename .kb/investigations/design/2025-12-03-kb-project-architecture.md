---
date: "2025-12-03"
status: "Complete"
type: "design"
---

# kb Project Architecture Design

**TLDR:** Recommend Go (like beads), standalone kb-cli repo, keep `.orch/` directory structure (no migration to `.kb/`), per-project operation with optional global search. Clean extraction of knowledge artifact tooling from orch-cli.

---

## Design Question

How should we architect the `kb` project for knowledge artifact management, extracted from orch-cli?

**Sub-questions:**
1. What language? Go vs Python
2. What repository structure? Standalone vs subfolder vs inside orch-knowledge
3. What directory structure? `.kb/` vs `.orch/`
4. How does kb relate to orch-knowledge?
5. What command design?
6. How do we migrate?

---

## Problem Framing

### Context

The five concerns architecture decision (2025-12-01-five-concerns-architecture.md) established:

| Tool | Layer | Storage | Purpose |
|------|-------|---------|---------|
| `bd` | Memory | `.beads/` | Task state, dependencies, execution log |
| `kb` | Knowledge | `.kb/` | Investigations, decisions, patterns |
| `skills` | Guidance | `~/.claude/skills/` | Agent behavioral procedures |
| `orch` | Lifecycle | (stateless) | Spawn, monitor, complete, verify |
| `tmux` | Session | (runtime) | Persistence, attach, output |

orch-cli currently has knowledge artifact code that belongs in kb:
- `investigations.py` (~220 LOC) - Create investigation files from templates
- `decisions.py` (~130 LOC) - Create decision files from templates
- `artifact_search.py` (~630 LOC) - Search with reference counting, metadata extraction

**Total to extract:** ~1000 LOC Python

### Success Criteria

1. **Fast startup** - CLI tools need <50ms startup (Go achieves 40ms, Python 108ms)
2. **Simple distribution** - Single binary, no Python runtime dependency
3. **Works with existing artifacts** - 299 investigations, 68 decisions in orch-knowledge
4. **Complements beads** - Task tracking (beads) vs knowledge (kb) are distinct
5. **Solo developer simplicity** - Dylan works alone, minimize overhead

### Constraints

1. Must work with existing `.orch/` directory structure across multiple projects
2. Templates currently at `~/.orch/templates/` - need migration path
3. `orch search` has sophisticated features (reference counting, interactive mode)
4. Dylan uses orch-knowledge as personal knowledge archive

---

## Exploration

### Question 1: Language (Go vs Python)

**Prior research:** `.orch/investigations/feasibility/2025-12-02-go-python-rust-cli-comparison.md`

| Criterion | Go | Python |
|-----------|-----|--------|
| **Startup time** | 40ms | 108ms |
| **Distribution** | Single binary | pip + Python |
| **Cross-platform** | Excellent | Good (with work) |
| **Developer speed** | Fast | Fastest |
| **CLI ecosystem** | Cobra/Viper | Click/rich |

**Recommendation: Go**

**Why:**
- 2.7x faster startup (40ms vs 108ms)
- Single binary distribution (like beads)
- Aligns with bd (beads CLI) which is also Go
- No Python version/virtualenv issues

**Trade-off accepted:** Slightly slower initial development than Python.

---

### Question 2: Repository Structure

**Option A: Standalone kb-cli repo**
- Pro: Clean separation, independent versioning
- Pro: Can be installed independently of orch-cli
- Pro: Follows beads pattern (standalone vc, bd repos)
- Con: Another repo to maintain

**Option B: Subfolder of orch-cli**
- Pro: Single repo, simpler coordination
- Con: Mixes Go and Python (orch-cli is Python)
- Con: Harder to install kb without orch

**Option C: Inside orch-knowledge**
- Pro: Knowledge tooling with knowledge archive
- Con: orch-knowledge is Dylan's personal archive, not a tool
- Con: Confuses tool vs content

**Recommendation: Option A (standalone kb-cli repo)**

**Why:**
- Clean separation of concerns
- Can be installed independently (like `bd`)
- Future: `brew install kb` or `go install github.com/dylanconlin/kb-cli`
- Follows successful beads pattern

---

### Question 3: Directory Structure (.kb/ vs .orch/)

**Option A: New .kb/ directory**
```
project/
  .beads/           # Tasks
  .kb/              # Knowledge
    investigations/
    decisions/
    patterns/
```

**Pros:**
- Cleaner separation - each tool owns its directory
- Matches five concerns model
- `.kb/` is intuitive for "knowledge base"

**Cons:**
- **Migration burden**: Must move 367+ existing artifacts
- **Breaking change**: All path references break
- **Dual system during migration**: Confusing period
- **Git history disruption**: `git mv` loses file history connection

**Option B: Keep .orch/ directory**
```
project/
  .beads/           # Tasks
  .orch/            # Knowledge (name is legacy but works)
    investigations/
    decisions/
    knowledge/
```

**Pros:**
- Zero migration - existing artifacts work immediately
- All path references preserved
- No dual-system confusion
- Git history intact

**Cons:**
- `.orch/` name implies "orchestration" but contains knowledge
- Slight conceptual mismatch

**Recommendation: Option B (keep .orch/)**

**Why:**
- **Principle: Session amnesia** - This design should help the next Claude resume, not create migration chaos
- Migration burden is high (367+ files across multiple projects)
- The `.orch/` name is "good enough" - users learn what it means
- Pragmatism over purity

**When this would change:**
- Greenfield project with no existing artifacts
- Major breaking change window where migration is acceptable

---

### Question 4: Relationship to orch-knowledge

**Current state:**
- orch-knowledge contains Dylan's personal knowledge archive
- Has `.orch/investigations/`, `.orch/decisions/`, etc.
- Also has `skills/`, `templates-src/`, `patterns-src/`

**Question:** Does kb operate globally (one knowledge base) or per-project?

**Option A: Per-project (like beads)**
```bash
cd ~/project-a
kb create investigation auth-flow
# Creates ~/project-a/.orch/investigations/...

cd ~/project-b
kb create investigation auth-flow
# Creates ~/project-b/.orch/investigations/...
```

**Option B: Global (single knowledge base)**
```bash
kb create investigation auth-flow
# Always creates ~/.orch/investigations/...
```

**Recommendation: Per-project with global search**

**Why:**
- Per-project matches beads model (`.beads/` is per-project)
- Project-specific knowledge stays with project
- `kb search --global` can span projects (like `orch search --global`)
- orch-knowledge becomes just another project (Dylan's personal one)

**Implementation:**
- `kb create` writes to `$PWD/.orch/` (or `--project` flag)
- `kb search` defaults to current project
- `kb search --global` scans all known projects
- orch-knowledge is discoverable via registry or explicit path

---

### Question 5: Command Design

**Core commands (from beads issue):**
```bash
kb create investigation <slug>     # Create from template
kb create decision <slug>          # Create from template
kb create pattern <slug>           # Create from template
kb search <query>                  # Search artifacts
kb list investigations             # List by type
kb list decisions
kb list patterns
```

**Additional commands from current orch functionality:**
```bash
kb search <query> --global         # Cross-project search
kb search -i                       # Interactive fuzzy search
kb search --type decisions         # Filter by type
kb search --no-refs               # Skip reference counting (faster)
```

**Template management:**
```bash
kb templates list                  # Show available templates
kb templates path                  # Show template directory
```

**Migration helper:**
```bash
kb init                           # Create .orch/ structure (or verify existing)
```

**Explicit non-goals:**
- No `kb validate` - that's for orch to do when completing agents
- No `kb complete` - investigations aren't "completed" like tasks
- No `kb status` - knowledge doesn't have lifecycle states

---

### Question 6: Migration Path

**Phase 1: Create kb-cli**
- Implement Go CLI with Cobra
- Commands: `create`, `search`, `list`, `templates`
- Read from `.orch/` (not `.kb/`)
- Templates at `~/.kb/templates/` (kb's distribution)

**Phase 2: Template migration**
- Copy investigation/decision templates from `~/.orch/templates/` to `~/.kb/templates/`
- kb uses its own templates
- orch-cli templates become deprecated

**Phase 3: Deprecate orch commands**
- `orch create-investigation` prints deprecation warning, calls `kb create investigation`
- `orch search` prints warning, suggests `kb search`
- Add to orch-cli CHANGELOG

**Phase 4: Remove from orch-cli**
- Delete `investigations.py`, `decisions.py`, `artifact_search.py`
- Remove `orch create-investigation`, `orch create-decision` commands
- Keep `orch search` as alias to `kb search`? Or remove entirely?

**Timeline considerations:**
- Dylan works solo - can do hard cut if preferred
- No external users depending on `orch create-investigation`
- Deprecation period optional but good practice

---

## Synthesis

### Recommended Architecture

| Question | Recommendation | Rationale |
|----------|---------------|-----------|
| **Language** | Go | 2.7x faster startup, single binary |
| **Repository** | Standalone kb-cli | Clean separation, independent install |
| **Directory** | Keep `.orch/` | Zero migration, pragmatic |
| **Scope** | Per-project + global search | Matches beads model |
| **Commands** | create, search, list, templates | Core operations from issue |
| **Migration** | Deprecate → Remove | Clean transition |

### Architecture Diagram

```
User
  │
  ├── bd create "task"         → .beads/issues.jsonl
  ├── kb create investigation  → .orch/investigations/
  ├── skills build            → ~/.claude/skills/
  └── orch spawn              → tmux + agent lifecycle

Templates:
  ~/.kb/templates/            → Investigation, Decision templates
  ~/.claude/skills/           → Skill templates (separate tool)
  ~/.orch/templates/          → DEPRECATED (workspace templates stay until removed)
```

### Data Flow

```
kb create investigation auth-flow
    │
    ├── Read template: ~/.kb/templates/investigations/SIMPLE.md
    ├── Substitute: YYYY-MM-DD → today
    └── Write: .orch/investigations/simple/2025-12-03-auth-flow.md

kb search "authentication"
    │
    ├── Scan: .orch/investigations/**/*.md
    ├── Scan: .orch/decisions/*.md
    ├── Match: regex/fuzzy
    └── Output: results with metadata
```

---

## Recommendations

### Primary Recommendation

⭐ **RECOMMENDED:** Go, standalone repo, keep `.orch/`, per-project

**Why:**
- **Go**: Prior research proves 2.7x faster, single binary
- **Standalone**: Clean separation, follows beads pattern
- **Keep .orch/**: Zero migration burden, pragmatic choice
- **Per-project**: Consistent with beads model

**Trade-offs accepted:**
- `.orch/` name is slightly misleading (contains knowledge, not orchestration)
- New repo means another thing to maintain
- Go is slightly slower to develop than Python

**Expected outcome:**
- Fast CLI (`kb --help` in ~40ms)
- Simple install (`go install` or homebrew)
- Works immediately with existing 367+ artifacts
- Clean separation from orch-cli lifecycle concerns

### Alternative: Python in orch-cli

**When to choose:**
- If Go development is too slow
- If kb needs tight integration with orch-cli internals
- If Python startup time (108ms) is acceptable

**Why not recommended:**
- Breaks single-binary distribution
- Slower startup noticeable in interactive use
- Doesn't align with beads ecosystem direction

---

## Implementation Outline

### kb-cli Structure (Go)

```
kb-cli/
├── cmd/
│   └── kb/
│       ├── main.go
│       ├── create.go      # kb create investigation/decision/pattern
│       ├── search.go      # kb search with reference counting
│       ├── list.go        # kb list investigations/decisions
│       └── templates.go   # kb templates list/path
├── internal/
│   ├── artifact/
│   │   ├── create.go     # Template substitution
│   │   └── search.go     # Search with rg fallback
│   ├── config/
│   │   └── paths.go      # .orch/ detection, template paths
│   └── templates/
│       └── embed.go      # Embedded default templates
├── templates/            # Default templates (embedded)
│   ├── investigations/
│   │   └── SIMPLE.md
│   └── DECISION.md
├── go.mod
├── go.sum
└── README.md
```

### Key Implementation Details

1. **Template embedding**: Use Go's `embed` package to include default templates in binary
2. **Search**: Use `exec.Command("rg", ...)` for ripgrep, fallback to Go regex
3. **Interactive mode**: Use `github.com/charmbracelet/bubbletea` for TUI
4. **Config**: Look for `.orch/` walking up from cwd (like git)

### Migration Checklist

- [ ] Create kb-cli repo
- [ ] Implement core commands (create, search, list)
- [ ] Embed default templates
- [ ] Test with existing .orch/ directories
- [ ] Add to homebrew tap (optional)
- [ ] Deprecate orch create-investigation
- [ ] Remove from orch-cli
- [ ] Update documentation

---

## Principle Cited

**Session amnesia**: The decision to keep `.orch/` rather than migrate to `.kb/` prioritizes the next Claude's ability to resume work. Migration creates a confusing period where two systems coexist.

**Evolve by distinction**: kb separates "what we learned" (knowledge) from "what to do" (beads) and "how to do it" (skills). Three distinct concerns.

---

## Self-Review

- [x] Question clear - kb project architecture
- [x] Criteria defined - speed, distribution, compatibility, simplicity
- [x] Constraints identified - existing artifacts, templates, solo developer
- [x] Scope bounded - architecture not implementation details
- [x] 2+ approaches explored - 2-3 options per question
- [x] Trade-offs documented - pros/cons for each option
- [x] Evidence gathered - prior investigation, existing code analysis
- [x] Complexity assessed - migration effort, development effort
- [x] Recommendation clear - Go, standalone, keep .orch/, per-project
- [x] Reasoning explicit - why each choice over alternatives
- [x] Trade-offs acknowledged - .orch/ naming, new repo maintenance
- [x] Change conditions noted - when alternatives would make sense
- [x] Principle cited - session amnesia, evolve by distinction

---

## Open Questions for Dylan

1. **Deprecation period**: Hard cut or deprecation warnings first?
2. **Homebrew**: Worth setting up homebrew tap for kb?
3. **Interactive search**: Port the sophisticated `orch search -i` or start simpler?
4. **Reference counting**: Worth porting the reference count cache?

---

## Related Documents

- `.orch/decisions/2025-12-01-five-concerns-architecture.md` - The five concerns model
- `.orch/investigations/feasibility/2025-12-02-go-python-rust-cli-comparison.md` - Go vs Python research
- `.orch/investigations/design/2025-12-01-orch-cli-role-in-agent-ecosystem.md` - orch-cli positioning
- Beads issue: `orch-cli-qge` - kb project scope
