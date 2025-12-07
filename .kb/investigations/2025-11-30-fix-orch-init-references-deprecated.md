---
Type: systems
Question: Why does orch init fail with deprecated command and missing templates?
Started: 2025-11-30
Status: complete
Confidence: high
Resolution-Status: Resolved
---

# Investigation: Fix orch init references deprecated command

## TLDR

`orch init` fails due to two issues:
1. Calls non-existent `build-orchestrator-context` command (line 220 of init.py)
2. Missing `templates/project-CLAUDE.md.template` file (required at line 277)

## Root Cause Analysis

### Issue 1: Missing `build-orchestrator-context` command

**Location:** `src/orch/init.py:207-236`

The function `build_orch_context_for_project()` calls:
```python
subprocess.run(
    [sys.executable, '-m', 'orch.cli', 'build-orchestrator-context', '--project', str(project_dir)],
    ...
)
```

**Evidence:** Running `orch --help` shows no `build-orchestrator-context` command. The available build subcommands are: `skills`, `readme`, `global`.

**Hypothesis:** This command was planned but never implemented, or was deprecated without updating `init.py`.

### Issue 2: Missing template file

**Location:** `src/orch/init.py:277`

```python
template_content = read_template("project-CLAUDE.md.template")
```

This expects a file at `orch-cli/templates/project-CLAUDE.md.template`.

**Evidence:**
- No `templates/` directory exists in orch-cli repo
- `ls /Users/dylanconlin/Documents/personal/orch-cli/templates/` returns "No such file or directory"

### Reproduction Steps

```bash
mkdir -p /tmp/test-orch-init
cd /tmp/test-orch-init
orch init --name "Test" --purpose "Testing init" --yes
```

**Actual output:**
```
⚠️  Warning: Failed to build orchestrator context
   Error: No such command 'build-orchestrator-context'.

✗ Error initializing project orchestration: Template not found: .../templates/project-CLAUDE.md.template
```

## Pattern Analysis

### What init SHOULD do:

1. Create `.orch/` directory structure ✓ (works)
2. Create `.orch/CLAUDE.md` with template markers ✓ (works)
3. Build orchestrator context from templates ✗ (calls non-existent command)
4. Create project `CLAUDE.md` from template ✗ (missing template file)
5. Update `.gitignore` (not reached due to earlier failure)
6. Set up hooks (not reached)

### Why `.orch/CLAUDE.md` creates successfully:

The `create_orch_claude_md()` function at line 123 generates content inline (hardcoded), so it works. Only the later template-dependent steps fail.

## Fix Approach

**Recommended: Create missing template + make build step graceful**

1. Create `templates/project-CLAUDE.md.template` with minimal content
2. Modify `build_orch_context_for_project()` to log warning but not block init
3. Remove references to non-existent `orch build --orchestrator` in comments

**Not recommended:**
- Creating `build-orchestrator-context` command (adds complexity, unclear value)
- Removing template system entirely (the `.orch/CLAUDE.md` with markers works fine)

## Evidence

- Traceback from reproduction shows exact failure points
- Code inspection confirms missing command and template
- `orch --help` confirms available commands

## Resolution

**Changes made:**

1. **Created `templates/project-CLAUDE.md.template`** - Minimal template for project CLAUDE.md with proper variable substitution

2. **Modified `build_orch_context_for_project()` in `src/orch/init.py`** - Replaced subprocess call to non-existent command with graceful message explaining that orchestration guidance comes from runtime skill

3. **Updated inline NOTE** - Changed the NOTE in generated .orch/CLAUDE.md from referencing non-existent `orch build --orchestrator` to explaining that markers are placeholders and guidance comes from orchestrator skill

**Verification:**
- `orch init` now completes successfully
- All 20 tests pass (1 skipped for deprecated feature)
- Generated files contain correct content
