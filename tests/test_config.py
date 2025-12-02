"""Tests for config.py - Configuration loader."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import yaml

from orch import config


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache before each test to ensure isolation."""
    config._CONFIG_CACHE = None
    yield
    config._CONFIG_CACHE = None


def test_defaults():
    """Test _defaults() returns expected structure."""
    defaults = config._defaults()

    assert 'tmux_session' in defaults
    assert 'active_projects_file' in defaults
    assert 'roadmap_paths' in defaults
    assert 'cdd_docs_path' in defaults

    assert defaults['tmux_session'] == 'workers'
    assert 'orch-config' in defaults['active_projects_file']
    assert isinstance(defaults['roadmap_paths'], list)
    assert len(defaults['roadmap_paths']) > 0


def test_get_config_no_file():
    """Test get_config() with no config file returns defaults."""
    with patch('pathlib.Path.exists', return_value=False):
        cfg = config.get_config()

        assert cfg['tmux_session'] == 'workers'
        assert 'orch-config' in cfg['active_projects_file']
        assert isinstance(cfg['roadmap_paths'], list)


def test_get_config_with_custom_values(tmp_path):
    """Test get_config() with custom config.yaml."""
    custom_config = {
        'tmux_session': 'custom-session',
        'active_projects_file': '/custom/path/active-projects.md',
        'roadmap_paths': ['/custom/roadmap1.org', '/custom/roadmap2.org'],
        'cdd_docs_path': '/custom/cdd-docs.md'
    }

    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            cfg = config.get_config()

            assert cfg['tmux_session'] == 'custom-session'
            assert cfg['active_projects_file'] == '/custom/path/active-projects.md'
            assert cfg['roadmap_paths'] == ['/custom/roadmap1.org', '/custom/roadmap2.org']
            assert cfg['cdd_docs_path'] == '/custom/cdd-docs.md'


def test_get_config_partial_override():
    """Test get_config() with partial config file (merge with defaults)."""
    partial_config = {
        'tmux_session': 'my-session'
    }

    config_yaml = yaml.dump(partial_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            cfg = config.get_config()

            # Custom value
            assert cfg['tmux_session'] == 'my-session'

            # Defaults for non-overridden values
            assert 'orch-config' in cfg['active_projects_file']
            assert isinstance(cfg['roadmap_paths'], list)


def test_get_config_malformed_yaml():
    """Test get_config() with malformed YAML falls back to defaults."""
    malformed_yaml = "invalid: yaml: content:\n  - broken"

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=malformed_yaml):
            cfg = config.get_config()

            # Should fall back to defaults
            assert cfg['tmux_session'] == 'workers'
            assert 'orch-config' in cfg['active_projects_file']


def test_get_config_non_dict_yaml():
    """Test get_config() with non-dict YAML falls back to defaults."""
    non_dict_yaml = yaml.dump(['list', 'of', 'items'])

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=non_dict_yaml):
            cfg = config.get_config()

            # Should fall back to defaults
            assert cfg['tmux_session'] == 'workers'


def test_get_config_caching():
    """Test get_config() caches result and doesn't reload."""
    config_yaml = yaml.dump({'tmux_session': 'cached-session'})

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml) as mock_read:
            # First call
            cfg1 = config.get_config()
            assert cfg1['tmux_session'] == 'cached-session'
            assert mock_read.call_count == 1

            # Second call should use cache
            cfg2 = config.get_config()
            assert cfg2['tmux_session'] == 'cached-session'
            assert mock_read.call_count == 1  # Not called again


def test_get_tmux_session_default():
    """Test get_tmux_session_default() returns correct value."""
    with patch('pathlib.Path.exists', return_value=False):
        session = config.get_tmux_session_default()
        assert session == 'workers'


def test_get_tmux_session_default_custom():
    """Test get_tmux_session_default() with custom config."""
    custom_config = {'tmux_session': 'my-custom-session'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            session = config.get_tmux_session_default()
            assert session == 'my-custom-session'


def test_get_active_projects_file():
    """Test get_active_projects_file() returns Path object."""
    with patch('pathlib.Path.exists', return_value=False):
        projects_file = config.get_active_projects_file()

        assert isinstance(projects_file, Path)
        assert 'active-projects.md' in str(projects_file)


def test_get_roadmap_paths():
    """Test get_roadmap_paths() returns list of Path objects."""
    with patch('pathlib.Path.exists', return_value=False):
        roadmap_paths = config.get_roadmap_paths()

        assert isinstance(roadmap_paths, list)
        assert len(roadmap_paths) > 0
        assert all(isinstance(p, Path) for p in roadmap_paths)


def test_get_roadmap_paths_custom():
    """Test get_roadmap_paths() with custom config."""
    custom_config = {
        'roadmap_paths': ['~/custom/roadmap1.org', '/absolute/roadmap2.org']
    }
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            roadmap_paths = config.get_roadmap_paths()

            assert len(roadmap_paths) == 2
            assert all(isinstance(p, Path) for p in roadmap_paths)
            # expanduser() should have been called
            assert not any('~' in str(p) for p in roadmap_paths)


def test_get_roadmap_paths_empty():
    """Test get_roadmap_paths() with empty list returns empty list."""
    custom_config = {'roadmap_paths': []}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            roadmap_paths = config.get_roadmap_paths()

            assert roadmap_paths == []


def test_get_cdd_docs_path():
    """Test get_cdd_docs_path() returns Path object."""
    with patch('pathlib.Path.exists', return_value=False):
        cdd_path = config.get_cdd_docs_path()

        assert isinstance(cdd_path, Path)
        assert 'cdd-essentials.md' in str(cdd_path)


def test_get_initialized_projects_cache():
    """Test get_initialized_projects_cache() returns correct path."""
    cache_path = config.get_initialized_projects_cache()

    assert isinstance(cache_path, Path)
    assert str(cache_path).endswith('.orch/initialized-projects.json')
    assert str(cache_path).startswith(str(Path.home()))


def test_get_roadmap_format_default():
    """Test get_roadmap_format() returns 'org' by default."""
    with patch('pathlib.Path.exists', return_value=False):
        format_type = config.get_roadmap_format()
        assert format_type == 'org'


def test_get_roadmap_format_custom_org():
    """Test get_roadmap_format() with explicit 'org' config."""
    custom_config = {'roadmap_format': 'org'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            format_type = config.get_roadmap_format()
            assert format_type == 'org'


def test_get_roadmap_format_custom_markdown():
    """Test get_roadmap_format() with 'markdown' config."""
    custom_config = {'roadmap_format': 'markdown'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            format_type = config.get_roadmap_format()
            assert format_type == 'markdown'


def test_get_backend_default():
    """Test get_backend() returns 'claude' by default."""
    with patch('pathlib.Path.exists', return_value=False):
        backend = config.get_backend()
        assert backend == 'claude'


def test_get_backend_from_config_file():
    """Test get_backend() with 'backend' in config file."""
    custom_config = {'backend': 'codex'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            backend = config.get_backend()
            assert backend == 'codex'


def test_get_backend_with_cli_override():
    """Test get_backend() with CLI flag overriding config file."""
    custom_config = {'backend': 'codex'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            # CLI flag 'claude' should override config file 'codex'
            backend = config.get_backend(cli_backend='claude')
            assert backend == 'claude'


def test_get_backend_cli_only():
    """Test get_backend() with CLI flag and no config file."""
    with patch('pathlib.Path.exists', return_value=False):
        backend = config.get_backend(cli_backend='codex')
        assert backend == 'codex'


def test_get_backend_priority_cli_over_config():
    """Test backend priority: CLI > config > default."""
    custom_config = {'backend': 'codex'}
    config_yaml = yaml.dump(custom_config)

    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value=config_yaml):
            # 1. CLI flag has highest priority
            assert config.get_backend(cli_backend='haiku') == 'haiku'

            # 2. Config file used when no CLI flag (reset cache first)
            config._CONFIG_CACHE = None
            assert config.get_backend() == 'codex'

            # 3. Default when neither CLI nor config (reset cache, mock no file)
            config._CONFIG_CACHE = None
            with patch('pathlib.Path.exists', return_value=False):
                assert config.get_backend() == 'claude'
