# Orchestration Patterns

Curated patterns for AI agent orchestration. These patterns emerged from real-world agent management and have been validated across multiple projects.

## What's Here

Patterns in this directory are:
- **Stable** - Validated through repeated use
- **Generic** - Applicable across projects and domains
- **Actionable** - Include concrete guidance, not just theory

## Pattern Categories

### Communication Patterns
Patterns for agent↔orchestrator communication.

- **directive-guidance** - Present options with clear recommendations + visible reasoning
- **sequential-plan-approval** - Present multi-step workflows as numbered plans

### Artifact Patterns
Patterns for structuring durable documents (investigations, decisions, knowledge).

- **tldr-structure** - 30-second resumption test for all artifacts
- **confidence-assessment** - Explicit confidence levels with evidence
- **amnesia-resilience** - Checklists enabling fresh agents to resume work

### Orchestration Patterns
Patterns for workflow decisions and agent management.

- **agent-salvage-vs-fresh** - When to redirect existing agent vs spawn fresh
- **multi-phase-validation** - Validation checkpoints between sequential phases
- **agent-post-mortem** - Systematic capture of agent failures for improvement

## Using These Patterns

Each pattern file includes:
- **Summary** - One-paragraph overview
- **When to Use** - Triggers and applicability
- **When NOT to Use** - Anti-patterns and alternatives
- **Examples** - Real-world application
- **Quick Reference** - Condensed checklist

Patterns are designed for **cold start** - a fresh agent can apply them without prior context.

## Contributing Patterns

Patterns are extracted from [orch-knowledge](https://github.com/dylan-conlin/orch-knowledge) after validation. To propose a new pattern:

1. Document the pattern in your project's `.orch/` directory
2. Validate through 3+ successful applications
3. Generalize by removing project-specific details
4. Submit PR to orch-knowledge for review
