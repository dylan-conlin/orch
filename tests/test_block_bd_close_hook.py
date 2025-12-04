"""
Tests for block-bd-close.py PreToolUse hook.

This hook prevents workers from running 'bd close' commands directly,
which would bypass the 'orch complete' verification process.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hooks directory to path so we can import the module
hooks_dir = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))


@pytest.fixture
def hook_module():
    """Import the hook module dynamically."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "block_bd_close",
        hooks_dir / "block-bd-close.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBlockBdClose:
    """Tests for blocking bd close in worker context."""

    def test_blocks_bd_close_in_worker_context(self, hook_module):
        """bd close should be blocked when CLAUDE_CONTEXT=worker."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "bd close orch-cli-abc123"}
        }

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
            result = hook_module.check_command(input_data)

        assert result["permissionDecision"] == "deny"
        assert "bd close" in result["permissionDecisionReason"].lower()
        assert "orch complete" in result["permissionDecisionReason"].lower() or "bd comment" in result["permissionDecisionReason"].lower()

    def test_blocks_bd_close_with_reason_flag(self, hook_module):
        """bd close with --reason flag should also be blocked."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'bd close issue-123 --reason "done"'}
        }

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
            result = hook_module.check_command(input_data)

        assert result["permissionDecision"] == "deny"

    def test_allows_bd_close_in_orchestrator_context(self, hook_module):
        """bd close should be allowed when CLAUDE_CONTEXT is not worker."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "bd close orch-cli-abc123"}
        }

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'orchestrator'}, clear=False):
            result = hook_module.check_command(input_data)

        assert result is None  # None means allow

    def test_allows_bd_close_without_context(self, hook_module):
        """bd close should be allowed when CLAUDE_CONTEXT is not set."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "bd close orch-cli-abc123"}
        }

        # Clear CLAUDE_CONTEXT env var
        env = {'CLAUDE_CONTEXT': ''}
        with patch.dict('os.environ', env, clear=False):
            # Also need to actually remove it
            import os
            original = os.environ.pop('CLAUDE_CONTEXT', None)
            try:
                result = hook_module.check_command(input_data)
            finally:
                if original:
                    os.environ['CLAUDE_CONTEXT'] = original

        assert result is None  # None means allow

    def test_allows_other_bd_commands(self, hook_module):
        """Other bd commands should be allowed in worker context."""
        allowed_commands = [
            "bd comment issue-123 'Phase: Complete'",
            "bd show issue-123",
            "bd list",
            "bd ready",
            "bd stats",
        ]

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
            for cmd in allowed_commands:
                input_data = {
                    "tool_name": "Bash",
                    "tool_input": {"command": cmd}
                }
                result = hook_module.check_command(input_data)
                assert result is None, f"Command '{cmd}' should be allowed but was blocked"

    def test_allows_non_bash_tools(self, hook_module):
        """Non-Bash tools should be allowed regardless of context."""
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file"}
        }

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
            result = hook_module.check_command(input_data)

        assert result is None

    def test_allows_close_in_other_commands(self, hook_module):
        """Commands containing 'close' but not 'bd close' should be allowed."""
        allowed_commands = [
            "git close-stale-issues",
            "close_connection.py",
            "echo 'bd close is blocked'",  # quoted string, not actual bd close
        ]

        with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
            for cmd in allowed_commands:
                input_data = {
                    "tool_name": "Bash",
                    "tool_input": {"command": cmd}
                }
                result = hook_module.check_command(input_data)
                assert result is None, f"Command '{cmd}' should be allowed"


class TestMainFunction:
    """Tests for the main() entry point."""

    def test_main_outputs_deny_json_for_bd_close(self, hook_module, capsys):
        """main() should output deny JSON when blocking bd close."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "bd close issue-123"}
        }

        with patch('sys.stdin', MagicMock()):
            with patch('json.load', return_value=input_data):
                with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
                    with pytest.raises(SystemExit) as exc_info:
                        hook_module.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_main_silent_for_allowed_commands(self, hook_module, capsys):
        """main() should exit silently for allowed commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "bd comment issue-123 'done'"}
        }

        with patch('sys.stdin', MagicMock()):
            with patch('json.load', return_value=input_data):
                with patch.dict('os.environ', {'CLAUDE_CONTEXT': 'worker'}):
                    with pytest.raises(SystemExit) as exc_info:
                        hook_module.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""  # No output for allowed commands


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
