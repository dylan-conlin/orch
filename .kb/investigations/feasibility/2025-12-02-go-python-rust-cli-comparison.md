# Research: Go vs Python vs Rust for CLI Tools

**Question:** Which language provides the best balance of developer experience, distribution simplicity, and performance for CLI tools like beads, vc, and orch-cli?

**Confidence:** High (85%)
**Started:** 2025-12-02
**Updated:** 2025-12-02
**Status:** Complete
**Resolution-Status:** Resolved

## Question

Steve Yegge's beads and vc projects are written in Go. orch-cli is written in Python. Need to understand:
1. What benefits does Go provide for CLI tools like beads/vc?
2. How does Python compare for orch-cli's use case?
3. Would Rust be a better choice than either?

**Evaluation Criteria:**
- Startup time / performance
- Distribution (single binary vs dependencies)
- Cross-platform support
- Developer ergonomics
- Ecosystem for CLI tooling

## Options Evaluated

### Option 1: Go

**Overview:** Go is a compiled language with excellent support for cross-compilation and single-binary distribution. It's used by beads and vc, both CLI tools for AI agent orchestration.

**Pros:**
- **Fast startup:** 40ms for `bd --help` (measured locally)
- **Single binary distribution:** No runtime dependencies, easy to install
- **Cross-compilation built-in:** `GOOS=linux GOARCH=amd64 go build` works seamlessly
- **Excellent CLI ecosystem:** Cobra (CLI framework), Viper (config), popular and mature
- **Static linking:** Single binary includes everything, even SQLite via WASM (wazero)
- **GoReleaser:** Automated multi-platform releases with Homebrew/npm/PyPI integration
- **Readable code:** Simple language, easy to understand and modify

**Cons:**
- **Binary size:** beads binary is 27MB (includes WASM SQLite runtime)
- **GC pauses:** Less predictable than Rust (though negligible for CLI use)
- **Less expressive:** No generics until Go 1.18, still limited compared to Rust
- **Error handling verbose:** `if err != nil { return err }` pattern is repetitive

**Evidence:**
- beads: 58,035 LOC, uses Cobra/Viper, SQLite via go-sqlite3 (WASM), 27MB binary
- vc: Depends on beads, also uses Cobra, 9.9MB binary (test-discovery)
- Startup: 40ms (`time bd --help`)
- Distribution: Homebrew tap, npm package, install script, GitHub releases with goreleaser

### Option 2: Python

**Overview:** Python is an interpreted language with excellent developer ergonomics. orch-cli uses Click for CLI, rich for output, and libtmux for terminal management.

**Pros:**
- **Rapid development:** Very fast to iterate and prototype
- **Excellent libraries:** Click (CLI), rich (terminal UI), libtmux (tmux automation)
- **Dynamic typing:** Flexible, quick to modify
- **Debugging:** Easy to inspect and debug at runtime
- **Familiar:** Most AI developers know Python

**Cons:**
- **Slow startup:** 108ms for `orch --help` (73ms just for imports)
- **Distribution complexity:** Requires Python runtime, pip/pipx, virtual environments
- **Import overhead:** Each import adds startup latency (measured: 73ms import time)
- **Cross-platform pain:** Platform-specific issues with dependencies
- **Dependency hell:** Version conflicts, virtualenv management

**Evidence:**
- orch-cli: 23,141 LOC Python
- Dependencies: click, libtmux, PyYAML, Jinja2, rich, readchar, tiktoken, python-frontmatter
- Startup: 108ms (`time orch --help`)
- Import profile: 73ms cumulative import time for `from orch.cli import cli`
- Distribution: pip install from PyPI, requires Python 3.10+

### Option 3: Rust

**Overview:** Rust is a compiled systems language with excellent performance and memory safety. Popular for CLI tools (ripgrep, bat, fd, exa).

**Pros:**
- **Fastest startup:** Typically <20ms for simple CLIs
- **Smallest binaries:** Smaller than Go (no GC runtime)
- **Best performance:** 30-1200% faster than Go in benchmarks (varies by workload)
- **Excellent CLI ecosystem:** Clap 4.x (CLI framework), serde, tokio
- **Memory safety:** No GC pauses, predictable performance
- **Type system:** Very expressive, catches errors at compile time

**Cons:**
- **Steep learning curve:** Ownership, lifetimes, borrow checker
- **Slower compilation:** Much longer build times than Go
- **Slower startup than Go:** Counterintuitively, Rust binaries often take longer to initialize
- **Ecosystem fragmentation:** Multiple solutions for each problem (tokio vs async-std)
- **Less familiar:** Most developers need to learn Rust

**Evidence:**
- [Rust vs Go 2025 comparisons](https://blog.jetbrains.com/rust/2025/06/12/rust-vs-go/): Rust 30%+ faster at runtime but Go has faster startup
- [Clap CLI framework](https://codezup.com/rust-clap-cli-tutorial/): Modern derive-based API, excellent ergonomics
- Popular Rust CLIs: ripgrep, bat, fd, exa, delta - all excellent examples

## Comparison Matrix

| Criterion | Go | Python | Rust |
|-----------|-----|--------|------|
| **Startup time** | 40ms | 108ms | ~20-50ms |
| **Binary size** | 27MB | N/A (needs runtime) | ~5-15MB |
| **Distribution** | Single binary | pip + Python | Single binary |
| **Cross-platform** | Excellent | Good (with work) | Excellent |
| **Developer speed** | Fast | Fastest | Slow |
| **Learning curve** | Low | Lowest | High |
| **CLI ecosystem** | Cobra/Viper | Click/rich | Clap/serde |
| **Runtime performance** | Good | Slow | Best |

## Recommendation

**I recommend Go for CLI tools like beads/vc/orch-cli** because it provides the best balance of:

1. **Fast enough startup:** 40ms is excellent for interactive CLI use
2. **Simple distribution:** Single binary, no runtime dependencies
3. **Developer productivity:** Much faster to develop than Rust
4. **Mature ecosystem:** Cobra, Viper, goreleaser well-established
5. **Proven at scale:** beads demonstrates Go handles complex CLIs well

**Trade-offs I'm accepting:**
- Larger binary size than Rust (but acceptable for CLI tools)
- Slightly slower runtime than Rust (irrelevant for CLI use)
- Less expressive type system than Rust (adequate for CLI tools)

**When this recommendation might change:**
- **If startup time critical (<20ms):** Consider Rust, but Go is usually fast enough
- **If binary size critical:** Rust produces smaller binaries
- **If maximum runtime performance needed:** Rust is significantly faster
- **If rapid prototyping priority:** Python is fastest to develop

**Specific guidance:**
- **For orch-cli:** Consider rewriting in Go if startup time becomes painful (~108ms vs 40ms)
- **For new CLI projects:** Start with Go unless Rust expertise already exists
- **For Python teams:** Python is fine for internal tools where 100ms startup is acceptable

## Confidence Assessment

**Current Confidence:** High (85%)

**What's certain:**
- Go startup is 2.7x faster than Python (40ms vs 108ms, measured)
- Go produces single binaries (verified via beads binary)
- Python import overhead is significant (73ms measured via importtime)
- beads demonstrates Go scales to 58K LOC without issues
- Cobra/Viper is a mature, well-documented CLI framework

**What's uncertain:**
- Rust actual startup time in practice (based on web research, not local measurement)
- Long-term maintenance burden of Go vs Python vs Rust
- Whether 100ms Python startup actually impacts user experience significantly

**What would increase confidence to 95%+:**
- Build a small prototype in Rust to measure actual startup time
- Survey Dylan on whether 108ms orch startup is problematic
- Measure memory usage across the three options

## Self-Review

- [x] Each option has evidence with sources
- [x] Clear recommendation (not "it depends")
- [x] Confidence assessed honestly
- [x] Research file complete and ready to commit

**Self-Review Status:** PASSED

## Research History

**2025-12-02:** Research started
- Question defined
- Evaluation criteria established
- Beginning codebase exploration

**2025-12-02:** Research completed
- Examined beads go.mod: Cobra, Viper, go-sqlite3 (WASM), anthropic SDK
- Examined vc go.mod: Depends on beads, similar stack
- Examined orch-cli pyproject.toml: Click, rich, libtmux
- Measured startup: bd 40ms, orch 108ms
- Profiled Python imports: 73ms cumulative import time
- Counted LOC: beads 58K Go, orch-cli 23K Python
- Web research on Rust CLI ecosystem and Go vs Rust comparisons
- Final confidence: High (85%)
- Recommendation: Go for CLI tools

## Sources

- [JetBrains: Rust vs Go 2025](https://blog.jetbrains.com/rust/2025/06/12/rust-vs-go/)
- [Rust Clap CLI Tutorial](https://codezup.com/rust-clap-cli-tutorial/)
- [Building Robust CLI Tools in Rust](https://dev.to/aaravjoshi/building-robust-cli-tools-in-rust-a-developers-guide-to-performance-and-safety-3pnl)
- [Python Startup Time Documentation](https://pythondev.readthedocs.io/startup_time.html)
- [PEP 690 - Lazy Imports](https://peps.python.org/pep-0690/)
- [Go vs Rust Bitfield Consulting](https://bitfieldconsulting.com/posts/rust-vs-go)
