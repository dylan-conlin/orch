# Design: orch build opencode command

**Date:** 2025-12-13
**Status:** Implemented
**Author:** Worker agent (ok-yvr3)

## Problem Statement

With OpenCode adoption, projects now have `opencode.json` configuration files that define instructions, MCP servers, and other settings. These files need validation to catch:

1. Missing or invalid JSON syntax
2. References to non-existent instruction files
3. Invalid glob patterns in instructions array
4. Potential schema violations

Currently there's no way to validate OpenCode configuration as part of the build pipeline.

### Success Criteria

- [ ] `orch build opencode` validates opencode.json files
- [ ] Reports missing instruction files clearly
- [ ] Supports glob patterns in instructions array
- [ ] Integrates with existing `orch build` command group
- [ ] Works in --dry-run and --check modes

## Approach

Add a new `opencode` subcommand to the `orch build` group that validates OpenCode configuration files.

### Command Interface

```bash
# Subcommand style (preferred)
orch build opencode              # Validate opencode.json in current project
orch build opencode --dry-run    # Preview validation without changes
orch build opencode --check      # Exit with error if validation fails

# Flag style (for consistency with other build targets)
orch build --opencode            # Equivalent to 'orch build opencode'
```

### Validation Checks

1. **File existence**: Check for `opencode.json` or `opencode.jsonc` in project root
2. **JSON syntax**: Parse JSON/JSONC and report syntax errors
3. **Schema validation** (optional): Validate against https://opencode.ai/config.json
4. **Instruction file resolution**:
   - Resolve each path in `instructions` array
   - Support glob patterns (e.g., `.cursor/rules/*.md`)
   - Report missing files/directories
   - Support home directory expansion (`~`)
5. **MCP server validation** (future): Validate MCP server configurations

### Output Format

```
$ orch build opencode

opencode validation...
  opencode.json found at /path/to/project/opencode.json
  Instructions:
    ~/.claude/skills/policy/orchestrator/SKILL.md: exists
    docs/guidelines.md: MISSING
    .cursor/rules/*.md: 3 files matched
  
Validation FAILED: 1 missing instruction file(s)
```

## Data Model

No persistent data model changes. Validation is stateless.

## Testing Strategy

1. **Unit tests**: Test instruction path resolution, glob expansion, JSONC parsing
2. **Integration tests**: Test full command execution with sample configs
3. **Smoke test**: Run against actual orch-knowledge/opencode.json

## Security Considerations

- File path traversal: Validate paths don't escape project directory
- No execution: Only reads files, doesn't execute MCP servers or commands

## Alternatives Considered

### Alternative 1: Standalone command `orch validate-opencode`

**Rejected because:** Doesn't fit with existing `orch build` group pattern. Build commands handle validation of various artifacts.

### Alternative 2: Add to `orch lint`

**Rejected because:** Lint focuses on CLAUDE.md and skill validation. OpenCode config is build-time concern.

## Implementation Plan

1. Add `opencode` subcommand to `build` group in `cli.py`
2. Implement JSON/JSONC parsing with error handling
3. Implement instruction file resolution with glob support
4. Add `--opencode` flag to main `build` command for flag-style invocation
5. Write tests and documentation

## References

- OpenCode config documentation: https://opencode.ai/docs/config/
- Schema: https://opencode.ai/config.json
