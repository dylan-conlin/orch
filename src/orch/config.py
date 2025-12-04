"""Lightweight configuration loader for orch.

Reads optional settings from ~/.orch/config.yaml with safe defaults.

Supported keys:
- tmux_session: default tmux session name (default: 'orchestrator')
- active_projects_file: path to active-projects.md (default: ~/orch-config/.orch/active-projects.md)
- roadmap_paths: list of paths to search for ROADMAP.org (default: [~/orch-config/.orch/ROADMAP.org])
- roadmap_format: preferred ROADMAP format - 'org' or 'markdown' (default: 'org')
- cdd_docs_path: path to CDD docs (used in prompts only)
- backend: default AI backend - 'claude' or 'codex' (default: 'claude')
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _defaults() -> Dict[str, Any]:
    home = Path.home()
    return {
        'tmux_session': 'workers',
        'active_projects_file': str(home / 'orch-config' / '.orch' / 'active-projects.md'),
        'roadmap_paths': [str(home / 'orch-config' / '.orch' / 'ROADMAP.org')],
        'cdd_docs_path': str(home / 'orch-config' / 'docs' / 'cdd-essentials.md'),
        'roadmap_format': 'org',
        'backend': 'claude',
    }


def get_config() -> Dict[str, Any]:
    """Load config.yaml once and cache the result."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    cfg_path = Path.home() / '.orch' / 'config.yaml'
    data: Dict[str, Any] = {}
    if cfg_path.exists():
        try:
            loaded = yaml.safe_load(cfg_path.read_text())
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            # Ignore malformed configs; fall back to defaults
            data = {}

    # Merge defaults where missing
    merged = {**_defaults(), **data}
    _CONFIG_CACHE = merged
    return merged


def get_tmux_session_default() -> str:
    return str(get_config().get('tmux_session', _defaults()['tmux_session']))


def get_active_projects_file() -> Path:
    return Path(get_config().get('active_projects_file', _defaults()['active_projects_file']))


def get_roadmap_paths() -> List[Path]:
    paths = get_config().get('roadmap_paths', _defaults()['roadmap_paths'])
    return [Path(p).expanduser() for p in (paths or [])]


def get_cdd_docs_path() -> Path:
    return Path(get_config().get('cdd_docs_path', _defaults()['cdd_docs_path']))


def get_initialized_projects_cache() -> Path:
    """Get path to initialized projects cache file."""
    return Path.home() / '.orch' / 'initialized-projects.json'


def get_roadmap_format() -> str:
    """
    Get preferred ROADMAP format from config.

    Returns:
        'org' or 'markdown' - defaults to 'org' if not specified
    """
    return str(get_config().get('roadmap_format', _defaults()['roadmap_format']))


def get_backend(cli_backend: Optional[str] = None) -> str:
    """
    Get backend selection with priority: CLI flag > config file > default.

    Args:
        cli_backend: Backend specified via CLI --backend flag (highest priority)

    Returns:
        Backend name ('claude', 'codex', etc.) - defaults to 'claude' if not specified

    Priority:
        1. CLI flag (--backend): Highest priority, overrides everything
        2. Config file (~/.orch/config.yaml): Used if no CLI flag
        3. Default ('claude'): Used if neither CLI nor config file specify backend
    """
    # Priority 1: CLI flag overrides everything
    if cli_backend is not None:
        return cli_backend

    # Priority 2: Config file
    # Priority 3: Default (handled by get_config() merging with _defaults())
    return str(get_config().get('backend', _defaults()['backend']))

