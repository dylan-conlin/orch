"""Tests for orch history CLI command."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
from orch.cli import cli


# cli_runner fixture provided by conftest.py


class TestHistoryCLI:
    """Test history CLI command."""

    def test_history_command_shows_completed_agents(self, cli_runner):
        """Test that history command displays completed agents with durations."""
        # Create temporary registry
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            registry_path = Path(f.name)

        try:
            # Create registry with completed agents
            base_time = datetime(2025, 11, 8, 10, 0, 0)

            registry_data = {
                'agents': [
                    {
                        'id': 'implement-feature-x',
                        'task': 'Implement feature X',
                        'window': 'orchestrator:5',
                        'window_id': '@1001',
                        'project_dir': '/Users/test/project',
                        'workspace': 'implement-x',
                        'spawned_at': base_time.isoformat(),
                        'completed_at': (base_time + timedelta(minutes=30)).isoformat(),
                        'status': 'completed'
                    },
                    {
                        'id': 'debug-issue-z',
                        'task': 'Debug issue Z',
                        'window': 'orchestrator:6',
                        'window_id': '@1002',
                        'project_dir': '/Users/test/project',
                        'workspace': 'debug-z',
                        'spawned_at': base_time.isoformat(),
                        'completed_at': (base_time + timedelta(minutes=20)).isoformat(),
                        'status': 'completed'
                    }
                ]
            }

            with open(registry_path, 'w') as f:
                json.dump(registry_data, f)

            # Run history command
            result = cli_runner.invoke(cli, ['history', '--registry', str(registry_path)])

            # Verify output
            assert result.exit_code == 0
            assert 'implement-feature-x' in result.output
            assert 'debug-issue-z' in result.output
            assert '30 min' in result.output
            assert '20 min' in result.output

        finally:
            registry_path.unlink(missing_ok=True)

    def test_history_command_shows_analytics(self, cli_runner):
        """Test that history command displays analytics grouped by task type."""
        # Create temporary registry
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            registry_path = Path(f.name)

        try:
            # Create registry with multiple agents of same type
            base_time = datetime(2025, 11, 8, 10, 0, 0)

            registry_data = {
                'agents': [
                    {
                        'id': 'implement-1',
                        'task': 'Implement feature X',
                        'window': 'orchestrator:5',
                        'window_id': '@1001',
                        'project_dir': '/Users/test/project',
                        'workspace': 'implement-x',
                        'spawned_at': base_time.isoformat(),
                        'completed_at': (base_time + timedelta(minutes=30)).isoformat(),
                        'status': 'completed'
                    },
                    {
                        'id': 'implement-2',
                        'task': 'Implement feature Y',
                        'window': 'orchestrator:6',
                        'window_id': '@1002',
                        'project_dir': '/Users/test/project',
                        'workspace': 'implement-y',
                        'spawned_at': base_time.isoformat(),
                        'completed_at': (base_time + timedelta(minutes=50)).isoformat(),
                        'status': 'completed'
                    }
                ]
            }

            with open(registry_path, 'w') as f:
                json.dump(registry_data, f)

            # Run history command with analytics flag
            result = cli_runner.invoke(cli, ['history', '--analytics', '--registry', str(registry_path)])

            # Verify output shows analytics
            assert result.exit_code == 0
            assert 'implement' in result.output.lower()
            assert '2 agents' in result.output.lower()
            assert '40 min' in result.output  # Average duration

        finally:
            registry_path.unlink(missing_ok=True)
