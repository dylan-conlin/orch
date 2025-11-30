# orch-cli

CLI tools for AI agent orchestration.

## Cross-Repo Sync Requirements

**When adding or changing CLI commands:**

Update the orchestrator skill in orch-knowledge to reflect the changes:
- Source: `orch-knowledge/skills/src/orchestrator/SKILL.md`
- Deployed to: `~/.claude/skills/orchestrator/SKILL.md`

This prevents amnesia gaps where new commands exist but future sessions don't know about them.

**Validation:** `orch lint --skills` (jt9) validates skill CLI references against actual commands.

## Development

```bash
pip install -e .
pytest
```

## Versioning & Releases

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Conventional commit format (required for changelog)
- Semantic versioning policy
- Release process with git-cliff

## Related Repos

- **orch-knowledge** - Knowledge archive (decisions, investigations, skill sources)
