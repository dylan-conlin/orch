**TLDR:** How should OpenCode plugin setup be documented for orch-cli? Created comprehensive docs/opencode-setup.md covering plugin directory structure, opencode.json configuration, session events, and differences from Claude Code hooks. High confidence (90%) - based on official OpenCode documentation and existing orch-cli patterns.

---

# Investigation: Document OpenCode Plugin Setup for orch-cli

**Question:** What documentation is needed for users to set up OpenCode plugin integration with orch-cli?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Claude (feature-impl agent)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: OpenCode Uses Different Extension Model Than Claude Code

**Evidence:** OpenCode uses a plugin-based extension system with JavaScript/TypeScript modules, while Claude Code uses JSON-configured hooks.

- OpenCode plugins: `.opencode/plugin/*.js` or `~/.config/opencode/plugin/`
- Claude Code hooks: `~/.claude/settings.json` with `hooks.SessionStart`

**Source:**
- https://opencode.ai/docs/plugins/ - Official plugin documentation
- https://opencode.ai/docs/config/ - Configuration reference
- `hooks/load-orchestration-context.py:9-34` - Existing dual-mode implementation

**Significance:** Users need different setup instructions for each agent type. The existing hook script already supports both modes via `--opencode` flag.

---

### Finding 2: OpenCode Has Built-in Instructions Feature

**Evidence:** OpenCode's `opencode.json` supports an `instructions` array that automatically loads instruction files into context:

```json
{
  "instructions": ["~/.claude/skills/orchestrator/SKILL.md"]
}
```

This is simpler than writing a plugin for basic context loading.

**Source:**
- https://opencode.ai/docs/config/#instructions
- https://opencode.ai/docs/rules/

**Significance:** For basic orchestrator skill loading, users don't need to write any plugin code - just add the instruction path to opencode.json.

---

### Finding 3: Plugin Events Map to Claude Code Hook Events

**Evidence:** OpenCode's event system includes `session.created` which maps to Claude Code's `SessionStart` hook:

| Claude Code | OpenCode |
|-------------|----------|
| SessionStart | session.created |
| (N/A) | session.idle |
| (N/A) | tool.execute.before |
| (N/A) | tool.execute.after |

**Source:** https://opencode.ai/docs/plugins/#events

**Significance:** The existing `load-orchestration-context.py` script can be wrapped in an OpenCode plugin that listens for `session.created` to achieve the same behavior as the Claude Code hook.

---

### Finding 4: Existing orch-cli opencode.json Is Minimal

**Evidence:** Current `opencode.json` in orch-cli root:
```json
{
  "instructions": [
    "~/.claude/skills/orchestrator/SKILL.md"
  ],
  "$schema": "https://opencode.ai/config.json"
}
```

**Source:** `/Users/dylanconlin/Documents/personal/orch-cli/opencode.json`

**Significance:** The project already uses the simplest form of OpenCode integration. Documentation should show both this simple approach and advanced plugin-based approach.

---

## Synthesis

**Key Insights:**

1. **Two-tier documentation needed** - Simple setup (just `opencode.json`) for basic use, advanced setup (plugin) for dynamic context like active agents.

2. **Existing infrastructure supports both** - The `load-orchestration-context.py` script already has `--opencode` mode, just needs documentation and a wrapper plugin.

3. **Environment detection works** - The `ORCH_WORKER` environment variable prevents workers from redundantly loading orchestrator context.

**Answer to Investigation Question:**

Documentation should cover:
1. Plugin directory structure (`.opencode/plugin/`)
2. Configuration via `opencode.json` with `instructions` array (recommended for most users)
3. Environment detection for worker vs orchestrator
4. Differences from Claude Code hooks (key comparison table)
5. Troubleshooting common issues

Created `docs/opencode-setup.md` with comprehensive coverage of all these areas.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Based on official OpenCode documentation and cross-referenced with existing orch-cli implementation patterns.

**What's certain:**

- ✅ OpenCode plugin structure and location (verified in official docs)
- ✅ `opencode.json` instructions feature (verified in official docs)
- ✅ Event names and plugin API (verified in official docs)
- ✅ Existing orch-cli patterns work (existing code)

**What's uncertain:**

- ⚠️ Plugin execution timing (not tested in production)
- ⚠️ Error handling behavior (documented but not tested)

**What would increase confidence to Very High (95%+):**

- End-to-end testing with OpenCode
- User feedback on documentation clarity
- Testing the example plugin code

---

## Implementation Recommendations

**Purpose:** Provide clear, tested documentation for OpenCode users.

### Recommended Approach

**Two-tier documentation** - Simple `opencode.json` for basic needs, plugin approach for advanced users.

**Why this approach:**
- Most users just need the orchestrator skill loaded
- `instructions` array is zero-code solution
- Plugin approach available for power users who want active agents, kn integration, etc.

**Trade-offs accepted:**
- Plugin approach is more complex but more powerful
- Documentation covers both rather than picking one

**Implementation sequence:**
1. Created `docs/opencode-setup.md` with complete guide
2. Updated README.md with quick reference
3. Both link to official OpenCode docs for deep dives

### Implementation Details

**What was implemented:**
- `docs/opencode-setup.md` - Comprehensive OpenCode setup guide
- README.md update - Added OpenCode section alongside Claude Code

**Success criteria:**
- ✅ Users can configure basic context loading via opencode.json
- ✅ Advanced users have plugin template for dynamic context
- ✅ Differences from Claude Code clearly documented

---

## References

**Files Examined:**
- `hooks/load-orchestration-context.py` - Existing dual-mode hook
- `opencode.json` - Existing configuration
- `README.md` - Existing documentation

**External Documentation:**
- https://opencode.ai/docs/plugins/ - Official plugin documentation
- https://opencode.ai/docs/config/ - Configuration reference
- https://opencode.ai/docs/rules/ - Custom instructions with AGENTS.md

**Related Artifacts:**
- **Prior Investigation:** `.kb/investigations/2025-12-12-audit-opencode-compatibility-orch-cli.md` - OpenCode compatibility audit

---

## Investigation History

**2025-12-12 17:30:** Investigation started
- Initial question: What documentation is needed for OpenCode plugin setup?
- Context: Spawned from beads issue orch-cli-7unf

**2025-12-12 17:45:** Research completed
- Fetched OpenCode docs for plugins, config, and rules
- Identified two-tier approach (simple vs advanced)

**2025-12-12 18:00:** Implementation completed
- Created docs/opencode-setup.md
- Updated README.md
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Comprehensive documentation for OpenCode plugin setup
