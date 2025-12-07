"""
Tests for orch resume functionality.

Note: WORKSPACE.md is no longer used for agent state tracking.
Beads is now the source of truth. Resume context now focuses on
SPAWN_CONTEXT.md and primary artifacts.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime


# cli_runner fixture provided by conftest.py


class TestResumeCommand:
    """Tests for the resume command."""

    def test_resume_agent_with_workspace(self, cli_runner):
        """Test resuming an agent with valid workspace."""
        from orch.cli import cli

        # Mock agent with workspace
        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'workspace': 'test-workspace',
            'project': '/tmp/test-project'
        }

        # Mock workspace content
        workspace_content = """
# Workspace: test-workspace

**Phase:** Implementation

## Summary (Top 3)

- **Current Goal:** Implementing feature X
- **Next Step:** Task 3 - Add error handling
- **Blocking Issue:** None

## Progress Tracking

### Phase 1: Planning
- [x] Task 1: Research approach
- [x] Task 2: Design implementation

### Phase 2: Implementation
- [ ] Task 3: Add error handling
"""

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=workspace_content):
                    with patch('orch.resume.update_workspace_timestamps'):
                        with patch('orch.send.send_message_to_agent'):
                            result = cli_runner.invoke(cli, ['resume', 'test-agent'])

        assert result.exit_code == 0
        assert 'resumed successfully' in result.output.lower()

    def test_resume_agent_not_found(self, cli_runner):
        """Test error when agent doesn't exist."""
        from orch.cli import cli

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = None
            mock_registry.list_active_agents.return_value = []
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['resume', 'nonexistent-agent'])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower()

    def test_resume_agent_no_workspace(self, cli_runner):
        """Test error when agent has no workspace configured."""
        from orch.cli import cli

        # Agent without workspace field
        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            result = cli_runner.invoke(cli, ['resume', 'test-agent'])

        assert result.exit_code != 0
        assert 'no workspace' in result.output.lower()

    def test_resume_workspace_file_missing(self, cli_runner):
        """Test error when SPAWN_CONTEXT.md doesn't exist."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'workspace': 'test-workspace',
            'project': '/tmp/test-project'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            with patch('pathlib.Path.exists', return_value=False):
                result = cli_runner.invoke(cli, ['resume', 'test-agent'])

        assert result.exit_code != 0
        assert 'spawn_context.md not found' in result.output.lower()

    def test_resume_with_custom_message(self, cli_runner):
        """Test resume with custom message overrides auto-generation."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'workspace': 'test-workspace',
            'project': '/tmp/test-project'
        }

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value='# Workspace'):
                    with patch('orch.resume.update_workspace_timestamps'):
                        with patch('orch.send.send_message_to_agent') as mock_send:
                            result = cli_runner.invoke(
                                cli,
                                ['resume', 'test-agent', '-m', 'Skip to Task 5']
                            )

        assert result.exit_code == 0
        assert 'custom message' in result.output.lower()
        # Verify custom message was passed to send
        mock_send.assert_called_once()
        assert 'Skip to Task 5' in mock_send.call_args[0][1]

    def test_resume_dry_run(self, cli_runner):
        """Test dry-run mode doesn't send or update workspace."""
        from orch.cli import cli

        mock_agent = {
            'id': 'test-agent',
            'window': 'orchestrator:5',
            'workspace': 'test-workspace',
            'project': '/tmp/test-project'
        }

        workspace_content = """
# Workspace: test-workspace

## Summary (Top 3)

- **Next Step:** Task 3 - Add tests
"""

        with patch('orch.monitoring_commands.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = mock_agent
            MockRegistry.return_value = mock_registry

            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=workspace_content):
                    with patch('orch.resume.update_workspace_timestamps') as mock_update:
                        with patch('orch.send.send_message_to_agent') as mock_send:
                            result = cli_runner.invoke(cli, ['resume', 'test-agent', '--dry-run'])

        assert result.exit_code == 0
        assert 'dry-run' in result.output.lower()
        # Verify workspace NOT updated and message NOT sent
        mock_update.assert_not_called()
        mock_send.assert_not_called()


class TestResumeWorkspaceParsing:
    """Tests for workspace parsing logic.

    Note: WORKSPACE.md is no longer used. parse_resume_context now reads
    from SPAWN_CONTEXT.md for task info only.
    """

    def test_parse_resume_context_extracts_task(self, tmp_path):
        """Test extracting task from SPAWN_CONTEXT.md."""
        from orch.resume import parse_resume_context

        # Create workspace directory
        workspace_dir = tmp_path / "test-workspace"
        workspace_dir.mkdir()

        # Create SPAWN_CONTEXT.md
        spawn_context = workspace_dir / "SPAWN_CONTEXT.md"
        spawn_context.write_text("""# SPAWN_CONTEXT

## Task

Implement feature X with proper error handling.

## Skill
feature-impl
""")

        context = parse_resume_context(workspace_dir)

        assert 'task' in context
        assert 'Implement feature X' in context['task']

    def test_parse_resume_context_missing_workspace(self, tmp_path):
        """Test parsing returns empty dict when workspace missing."""
        from orch.resume import parse_resume_context

        missing_dir = tmp_path / "nonexistent"
        context = parse_resume_context(missing_dir)

        assert context == {}


class TestTimestampUpdates:
    """Tests for workspace timestamp update logic.

    Note: WORKSPACE.md is no longer used. update_workspace_timestamps
    is now a no-op for backward compatibility.
    """

    def test_update_workspace_timestamps_is_noop(self, tmp_path):
        """Test that update_workspace_timestamps is a no-op."""
        from orch.resume import update_workspace_timestamps

        workspace_dir = tmp_path / "test-workspace"
        workspace_dir.mkdir()

        # Should not raise, even if directory exists
        update_workspace_timestamps(workspace_dir)
        # Function is a no-op, just verify it doesn't crash


class TestContinuationMessageGeneration:
    """Tests for continuation message generation."""

    def test_generate_continuation_message_with_task(self):
        """Test auto-generated message includes task from context."""
        from orch.resume import generate_continuation_message

        context = {
            'task': 'Implement feature X with proper error handling'
        }

        message = generate_continuation_message('test-workspace', context)

        assert 'Resuming work' in message
        assert 'Implement feature X' in message

    def test_generate_continuation_message_custom_overrides(self):
        """Test custom message overrides auto-generation."""
        from orch.resume import generate_continuation_message

        context = {
            'task': 'Implement feature X'
        }

        custom_message = "Please skip to Task 5"
        message = generate_continuation_message('test-workspace', context, custom_message)

        assert message == custom_message
        # Should NOT include context info
        assert 'feature X' not in message

    def test_generate_continuation_message_minimal_context(self):
        """Test message generation with minimal context."""
        from orch.resume import generate_continuation_message

        context = {}  # Empty context

        message = generate_continuation_message('test-workspace', context)

        assert 'Resuming work' in message
        assert 'continue where you left off' in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
