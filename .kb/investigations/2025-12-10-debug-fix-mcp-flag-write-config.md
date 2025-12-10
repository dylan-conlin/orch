**TLDR:** Question: Why does --mcp flag cause issues with complex MCP server configs? Answer: The MCP config JSON is passed inline to `--mcp-config`, which can fail with shell escaping issues and command length limits. Fix: Write config to temp file in workspace directory and pass the file path instead. High confidence (90%) - code path is clear and fix is straightforward.

---

# Investigation: Fix --mcp flag to write config to temp file

**Question:** How should we refactor the --mcp flag to write config to a temp file instead of passing inline JSON?

**Started:** 2025-12-10
**Updated:** 2025-12-10
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: MCP config passed inline causes shell issues

**Evidence:** In `backends/claude.py:146`:
```python
parts.append(f"--mcp-config {shlex.quote(mcp_config_json)}")
```

The JSON config is passed directly on the command line, which can cause:
1. Shell escaping failures with complex JSON containing quotes, special chars
2. Command length limits (shell limits vary by OS, typically 128KB-2MB)
3. Difficulty debugging (long inline JSON obscures the actual command)

**Source:** `src/orch/backends/claude.py:107-152` - `build_command()` method

**Significance:** This is the root cause of issues with complex MCP server configs.

---

### Finding 2: Workspace path is available at spawn time

**Evidence:** In `spawn.py:546-548`:
```python
workspace_path = config.project_dir / ".orch" / "workspace" / config.workspace_name
workspace_path.mkdir(parents=True, exist_ok=True)
context_file = workspace_path / "SPAWN_CONTEXT.md"
```

The workspace directory is already created before `build_command()` is called in `spawn_in_tmux()`.

**Source:** `src/orch/spawn.py:459-704` - `spawn_in_tmux()` method

**Significance:** We can write the MCP config to a file in the workspace directory without needing additional setup.

---

### Finding 3: Backend options include project context

**Evidence:** In `spawn.py:613-621`:
```python
backend_options = {}
if config.model:
    backend_options['model'] = config.model
if agent_name:
    backend_options['agent_name'] = agent_name
if config.mcp_servers:
    backend_options['mcp_servers'] = config.mcp_servers
backend_cmd = backend.build_command(minimal_prompt, backend_options if backend_options else None)
```

The current flow doesn't pass workspace path to `build_command()`. We need to add it.

**Source:** `src/orch/spawn.py:613-621`

**Significance:** We need to pass workspace_path as an option so `build_command()` can write the file there.

---

## Synthesis

**Key Insights:**

1. **File-based config is more robust** - Writing MCP config to a file in the workspace directory avoids shell escaping issues, command length limits, and improves debuggability.

2. **Backward compatibility maintained** - The `resolve_mcp_servers()` function now accepts an optional `workspace_path` parameter. When provided, it writes to file; when not provided, it returns JSON string for backward compatibility.

3. **Integration is seamless** - The workspace directory already exists before `build_command()` is called in `spawn_in_tmux()`, so no additional setup is required.

**Answer to Investigation Question:**

The fix involves three changes:
1. `spawn.py:619-622`: Pass `workspace_path` in `backend_options` when `mcp_servers` is specified
2. `backends/claude.py:35-104`: Modify `resolve_mcp_servers()` to accept `workspace_path` and write config to `mcp-config.json` in that directory
3. `backends/claude.py:156-161`: Update `build_command()` to pass `workspace_path` to `resolve_mcp_servers()`

This approach writes the MCP config to `.orch/workspace/{name}/mcp-config.json` and passes the file path to `--mcp-config` instead of inline JSON.

---

## Confidence Assessment

**Current Confidence:** [Level] ([Percentage])

**Why this level?**

[Explanation of why you chose this confidence level - what evidence supports it, what's strong vs uncertain]

**What's certain:**

- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]
- ✅ [Thing you're confident about with supporting evidence]

**What's uncertain:**

- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]
- ⚠️ [Area of uncertainty or limitation]

**What would increase confidence to [next level]:**

- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]
- [Specific additional investigation or evidence needed]

**Confidence levels guide:**
- **Very High (95%+):** Strong evidence, minimal uncertainty, unlikely to change
- **High (80-94%):** Solid evidence, minor uncertainties, confident to act
- **Medium (60-79%):** Reasonable evidence, notable gaps, validate before major commitment
- **Low (40-59%):** Limited evidence, high uncertainty, proceed with caution
- **Very Low (<40%):** Highly speculative, more investigation needed

---

## Implementation Recommendations

**Purpose:** Bridge from investigation findings to actionable implementation using directive guidance pattern (strong recommendations + visible reasoning).

### Recommended Approach ⭐

**[Approach Name]** - [One sentence stating the recommended implementation]

**Why this approach:**
- [Key benefit 1 based on findings]
- [Key benefit 2 based on findings]
- [How this directly addresses investigation findings]

**Trade-offs accepted:**
- [What we're giving up or deferring]
- [Why that's acceptable given findings]

**Implementation sequence:**
1. [First step - why it's foundational]
2. [Second step - why it comes next]
3. [Third step - builds on previous]

### Alternative Approaches Considered

**Option B: [Alternative approach]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended - reference findings]
- **When to use instead:** [Conditions where this might be better]

**Option C: [Alternative approach]**
- **Pros:** [Benefits]
- **Cons:** [Why not recommended - reference findings]
- **When to use instead:** [Conditions where this might be better]

**Rationale for recommendation:** [Brief synthesis of why Option A beats alternatives given investigation findings]

---

### Implementation Details

**What to implement first:**
- [Highest priority change based on findings]
- [Quick wins or foundational work]
- [Dependencies that need to be addressed early]

**Things to watch out for:**
- ⚠️ [Edge cases or gotchas discovered during investigation]
- ⚠️ [Areas of uncertainty that need validation during implementation]
- ⚠️ [Performance, security, or compatibility concerns to address]

**Areas needing further investigation:**
- [Questions that arose but weren't in scope]
- [Uncertainty areas that might affect implementation]
- [Optional deep-dives that could improve the solution]

**Success criteria:**
- ✅ [How to know the implementation solved the investigated problem]
- ✅ [What to test or validate]
- ✅ [Metrics or observability to add]

---

## References

**Files Examined:**
- [File path] - [What you looked at and why]
- [File path] - [What you looked at and why]

**Commands Run:**
```bash
# [Command description]
[command]

# [Command description]
[command]
```

**External Documentation:**
- [Link or reference] - [What it is and relevance]

**Related Artifacts:**
- **Decision:** [Path to related decision document] - [How it relates]
- **Investigation:** [Path to related investigation] - [How it relates]
- **Workspace:** [Path to related workspace] - [How it relates]

---

## Investigation History

**[YYYY-MM-DD HH:MM]:** Investigation started
- Initial question: [Original question as posed]
- Context: [Why this investigation was initiated]

**[YYYY-MM-DD HH:MM]:** [Milestone or significant finding]
- [Description of what happened or was discovered]

**[YYYY-MM-DD HH:MM]:** Investigation completed
- Final confidence: [Level] ([Percentage])
- Status: [Complete/Paused with reason]
- Key outcome: [One sentence summary of result]
