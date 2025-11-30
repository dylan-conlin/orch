"""Backend abstraction layer for multi-backend support (Claude Code, Codex CLI, etc.)."""

from .base import Backend
from .claude import ClaudeBackend
from .codex import CodexBackend

__all__ = ["Backend", "ClaudeBackend", "CodexBackend"]
