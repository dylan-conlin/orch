"""Tests for backends/base.py - Backend abstract base class."""

import pytest
from pathlib import Path
from abc import ABC
from typing import Dict

from orch.backends.base import Backend
from orch.spawn import SpawnConfig


def test_backend_is_abstract():
    """Test that Backend cannot be instantiated directly (it's abstract)."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class Backend"):
        Backend()


def test_backend_requires_all_methods():
    """Test that concrete implementations must implement all abstract methods."""

    # Create incomplete implementation (missing wait_for_ready)
    class IncompleteBackend(Backend):
        def build_command(self, prompt: str, options=None) -> str:
            return "test"

        def get_env_vars(self, config, workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
            return {}

        def get_config_dir(self) -> Path:
            return Path.home() / ".test"

        @property
        def name(self) -> str:
            return "test"

    # Should fail because wait_for_ready is not implemented
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteBackend()


def test_complete_backend_implementation():
    """Test that a complete implementation can be instantiated."""

    class CompleteBackend(Backend):
        def build_command(self, prompt: str, options=None) -> str:
            return f"test-cli {prompt}"

        def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
            return True

        def get_env_vars(self, config, workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
            return {
                "TEST_CONTEXT": "worker",
                "TEST_WORKSPACE": str(workspace_abs),
                "TEST_PROJECT": str(config.project_dir),
                "TEST_DELIVERABLES": deliverables_list,
            }

        def get_config_dir(self) -> Path:
            return Path.home() / ".test"

        @property
        def name(self) -> str:
            return "test"

    # Should succeed - all methods implemented
    backend = CompleteBackend()
    assert backend is not None
    assert isinstance(backend, Backend)


def test_backend_interface_methods():
    """Test that Backend interface methods have correct signatures."""

    class TestBackend(Backend):
        def build_command(self, prompt: str, options=None) -> str:
            return f"cli {prompt}"

        def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
            return True

        def get_env_vars(self, config, workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
            return {"KEY": "value"}

        def get_config_dir(self) -> Path:
            return Path("/test")

        @property
        def name(self) -> str:
            return "test"

    backend = TestBackend()

    # Test build_command
    cmd = backend.build_command("test prompt")
    assert isinstance(cmd, str)
    assert "test prompt" in cmd

    # Test wait_for_ready
    ready = backend.wait_for_ready("session:1")
    assert isinstance(ready, bool)

    # Test get_env_vars
    config = SpawnConfig(
        task="test task",
        project="test-project",
        project_dir=Path("/test/project"),
        workspace_name="test-workspace"
    )
    workspace_abs = Path("/test/workspace")
    deliverables = "workspace,investigation"

    env_vars = backend.get_env_vars(config, workspace_abs, deliverables)
    assert isinstance(env_vars, dict)
    assert all(isinstance(k, str) for k in env_vars.keys())
    assert all(isinstance(v, str) for v in env_vars.values())

    # Test get_config_dir
    config_dir = backend.get_config_dir()
    assert isinstance(config_dir, Path)

    # Test name property
    backend_name = backend.name
    assert isinstance(backend_name, str)
    assert len(backend_name) > 0


def test_backend_inheritance():
    """Test that Backend properly inherits from ABC."""
    assert issubclass(Backend, ABC)
    assert hasattr(Backend, '__abstractmethods__')

    # Verify all expected methods are abstract
    abstract_methods = Backend.__abstractmethods__
    assert 'build_command' in abstract_methods
    assert 'wait_for_ready' in abstract_methods
    assert 'get_env_vars' in abstract_methods
    assert 'get_config_dir' in abstract_methods
    assert 'name' in abstract_methods


def test_backend_options_parameter():
    """Test that build_command options parameter works correctly."""

    class TestBackend(Backend):
        def build_command(self, prompt: str, options=None) -> str:
            base_cmd = f"cli {prompt}"
            if options:
                if options.get('allowed_tools'):
                    base_cmd += f" --allowed-tools {options['allowed_tools']}"
                if options.get('model'):
                    base_cmd += f" --model {options['model']}"
            return base_cmd

        def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
            return True

        def get_env_vars(self, config, workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
            return {}

        def get_config_dir(self) -> Path:
            return Path("/test")

        @property
        def name(self) -> str:
            return "test"

    backend = TestBackend()

    # Test without options
    cmd_no_opts = backend.build_command("test")
    assert cmd_no_opts == "cli test"

    # Test with options
    cmd_with_opts = backend.build_command("test", {
        'allowed_tools': '*',
        'model': 'sonnet'
    })
    assert "--allowed-tools *" in cmd_with_opts
    assert "--model sonnet" in cmd_with_opts


def test_backend_timeout_parameter():
    """Test that wait_for_ready timeout parameter works correctly."""

    class TestBackend(Backend):
        def build_command(self, prompt: str, options=None) -> str:
            return "cli"

        def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
            # Return timeout value for testing
            return timeout == 10.0

        def get_env_vars(self, config, workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
            return {}

        def get_config_dir(self) -> Path:
            return Path("/test")

        @property
        def name(self) -> str:
            return "test"

    backend = TestBackend()

    # Test with default timeout
    assert backend.wait_for_ready("session:1") is False

    # Test with custom timeout
    assert backend.wait_for_ready("session:1", timeout=10.0) is True
