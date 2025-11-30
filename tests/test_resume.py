"""
Tests for orch resume functionality.
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
        """Test error when workspace file doesn't exist."""
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
        assert 'workspace file not found' in result.output.lower()

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
    """Tests for workspace parsing logic."""

    def test_parse_resume_context_extracts_next_step(self):
        """Test extracting Next Step from Summary section."""
        from orch.resume import parse_resume_context

        workspace_content = """
## Summary (Top 3)

- **Current Goal:** Implementing feature
- **Next Step:** Task 5 - Write documentation
- **Blocking Issue:** None
"""

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value=workspace_content):
                context = parse_resume_context(Path('/tmp/WORKSPACE.md'))

        assert 'next_step' in context
        assert 'Task 5 - Write documentation' in context['next_step']

    def test_parse_resume_context_extracts_last_completed(self):
        """Test extracting last completed task."""
        from orch.resume import parse_resume_context

        workspace_content = """
## Progress Tracking

- [x] Task 1: Setup environment
- [x] Task 2: Write tests
- [ ] Task 3: Implement feature
"""

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value=workspace_content):
                context = parse_resume_context(Path('/tmp/WORKSPACE.md'))

        assert 'last_completed' in context
        assert 'Task 2: Write tests' in context['last_completed']

    def test_parse_resume_context_extracts_phase(self):
        """Test extracting phase information."""
        from orch.resume import parse_resume_context

        workspace_content = """
**Phase:** Implementation
"""

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value=workspace_content):
                context = parse_resume_context(Path('/tmp/WORKSPACE.md'))

        assert 'phase' in context
        assert context['phase'] == 'Implementation'

    def test_parse_resume_context_missing_workspace(self):
        """Test parsing returns empty dict when workspace missing."""
        from orch.resume import parse_resume_context

        with patch('pathlib.Path.exists', return_value=False):
            context = parse_resume_context(Path('/tmp/WORKSPACE.md'))

        assert context == {}


class TestTimestampUpdates:
    """Tests for workspace timestamp update logic."""

    def test_update_workspace_timestamps_adds_resumed_at(self, tmp_path):
        """Test adding Resumed At timestamp."""
        from orch.resume import update_workspace_timestamps

        workspace_content = """
**Owner:** Agent
**Started:** 2025-11-14
**Last Updated:** 2025-11-14 10:00
"""

        # Create temporary workspace file
        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text(workspace_content)

        update_workspace_timestamps(workspace_file)

        # Read updated content
        updated_content = workspace_file.read_text()
        assert 'Resumed At:' in updated_content
        # ISO timestamp format check
        assert '2025-' in updated_content or '2024-' in updated_content
        assert 'T' in updated_content  # ISO format has T separator
        assert 'Z' in updated_content  # UTC timezone

    def test_update_workspace_timestamps_updates_last_activity(self, tmp_path):
        """Test updating Last Activity in Session Scope section."""
        from orch.resume import update_workspace_timestamps

        workspace_content = """
## Session Scope & Checkpoint Plan

**Last Activity:** 2025-11-14T10:00:00Z
"""

        # Create temporary workspace file
        workspace_file = tmp_path / "WORKSPACE.md"
        workspace_file.write_text(workspace_content)

        update_workspace_timestamps(workspace_file)

        # Read updated content
        updated_content = workspace_file.read_text()
        # Should have updated timestamp (different from original)
        assert updated_content != workspace_content
        # Should contain an ISO timestamp (with T and Z)
        assert 'T' in updated_content
        assert 'Z' in updated_content

    def test_update_workspace_timestamps_missing_file_raises_error(self, tmp_path):
        """Test error when workspace file doesn't exist."""
        from orch.resume import update_workspace_timestamps

        # Path to non-existent file
        missing_file = tmp_path / "nonexistent" / "WORKSPACE.md"

        with pytest.raises(FileNotFoundError):
            update_workspace_timestamps(missing_file)


class TestContinuationMessageGeneration:
    """Tests for continuation message generation."""

    def test_generate_continuation_message_with_context(self):
        """Test auto-generated message includes workspace context."""
        from orch.resume import generate_continuation_message

        context = {
            'last_completed': 'Task 2: Write tests',
            'next_step': 'Task 3 - Implement feature',
            'phase': 'Implementation'
        }

        message = generate_continuation_message('test-workspace', context)

        assert 'Resuming work' in message
        assert 'Task 2: Write tests' in message
        assert 'Task 3 - Implement feature' in message

    def test_generate_continuation_message_custom_overrides(self):
        """Test custom message overrides auto-generation."""
        from orch.resume import generate_continuation_message

        context = {
            'next_step': 'Task 3',
            'last_completed': 'Task 2'
        }

        custom_message = "Please skip to Task 5"
        message = generate_continuation_message('test-workspace', context, custom_message)

        assert message == custom_message
        # Should NOT include context info
        assert 'Task 2' not in message
        assert 'Task 3' not in message

    def test_generate_continuation_message_minimal_context(self):
        """Test message generation with minimal context."""
        from orch.resume import generate_continuation_message

        context = {}  # Empty context

        message = generate_continuation_message('test-workspace', context)

        assert 'Resuming work' in message
        assert 'continue where you left off' in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
