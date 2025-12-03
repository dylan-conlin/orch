# Skills Source Structure

This document describes the structure of skill source directories used by the `skills` CLI.

## Directory Structure

```
skills/src/
├── worker/                    # Skills for worker agents
│   ├── feature-impl/          # Feature implementation skill
│   │   ├── SKILL.md          # Built output (auto-generated for templated skills)
│   │   ├── src/              # Source files (templated skills)
│   │   │   ├── SKILL.md.template
│   │   │   └── phases/
│   │   │       ├── investigation.md
│   │   │       ├── design.md
│   │   │       └── implementation.md
│   │   └── reference/        # Reference materials
│   │       └── examples.md
│   ├── investigation/         # Simple skill (no template)
│   │   └── SKILL.md
│   └── systematic-debugging/
│       └── SKILL.md
├── shared/                    # Skills for any agent type
│   ├── session-transition/
│   │   └── SKILL.md
│   └── record-decision/
│       └── SKILL.md
├── meta/                      # Skills about skills
│   ├── writing-skills/
│   │   └── SKILL.md
│   └── audit-claude-md/
│       └── SKILL.md
├── utilities/                 # Reference/utility skills
│   └── testing-anti-patterns/
│       └── SKILL.md
└── policy/                    # Policy/orchestrator skills
    └── orchestrator/
        └── SKILL.md
```

## Skill Types

### Simple Skills

Simple skills have a single `SKILL.md` file:

```
skill-name/
└── SKILL.md
```

### Templated Skills

Complex skills use a template system for modular content:

```
skill-name/
├── SKILL.md              # Built output (auto-generated)
├── src/
│   ├── SKILL.md.template # Template with placeholders
│   └── phases/           # Phase content files
│       ├── planning.md
│       ├── implementation.md
│       └── validation.md
└── reference/            # Optional reference materials
    └── examples.md
```

## Template Markers

Templates use HTML comment markers:

```markdown
<!-- SKILL-TEMPLATE: phase-name -->
<!-- /SKILL-TEMPLATE -->
```

When building, these markers are replaced with content from `phases/{phase-name}.md`.

## SKILL.md Frontmatter

Every skill has YAML frontmatter:

```yaml
---
name: skill-name
skill-type: procedure          # procedure, policy, reference
audience: worker               # worker, shared, meta, utilities, policy
spawnable: true                # Can be spawned via 'orch spawn'
description: Short description

deliverables:
  workspace:
    required: true
    description: "Workspace file"
  investigation:
    required: false
    description: "Investigation file"

verification:
  requirements:
    - "All tests pass"
    - "Documentation updated"
---
```

## Categories (Audiences)

| Category | Purpose | Spawnable |
|----------|---------|-----------|
| worker | Agents doing specific work | Yes |
| shared | Any agent type | Varies |
| meta | Skills about the skill system | Varies |
| utilities | Reference and helpers | No |
| policy | Orchestrator guidance | No |

## CLI Commands

```bash
# List deployed skills
skills list
skills list --category worker

# Build skills from templates
skills build --source ./skills/src

# Deploy to ~/.claude/skills/
skills deploy --source ./skills/src

# Create new skill
skills new worker/my-skill
skills new worker/complex-skill --template
```

## Deployment

Skills are deployed to `~/.claude/skills/`:

```
~/.claude/skills/
├── worker/
│   └── feature-impl/
│       └── SKILL.md
├── shared/
│   └── session-transition/
│       └── SKILL.md
├── feature-impl -> worker/feature-impl    # Symlink for discovery
└── session-transition -> shared/session-transition
```

Top-level symlinks enable Claude Code's skill discovery mechanism.
