# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-11-30

### 🚀 Features

- Add --version flag to CLI
- Add starter orchestrator skill for AI agents
- Add SessionStart hook and AI agent setup docs
- Add --discover flag to orch complete for capturing punted work
- Add beads integration with --issue flag for orch spawn
- Auto-close beads issue on orch complete

### 🐛 Bug Fixes

- Surface TLDRs in build-readme for context continuity

### 📚 Documentation

- Add Discovery Linking section to orchestrator skill
- Update project structure, remove outdated backlog.json reference

## [0.1.0] - 2025-11-29

### 🚀 Features

- Initial release
- Core CLI commands: spawn, status, check, tail, send, complete, clean
- tmux-based agent session management
- Registry for agent coordination
- Skill-based spawning system
- Workspace management for agent artifacts
