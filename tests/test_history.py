"""Tests for agent history and analytics."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
from orch.registry import AgentRegistry


class TestAgentHistory:
    """Test agent history tracking and analytics."""

    def test_get_completed_agents_with_duration(self):
        """Test getting completed agents with duration calculation."""
        # Create temporary registry
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            registry_path = Path(f.name)

        try:
            # Create registry with completed agent
            spawn_time = datetime(2025, 11, 8, 10, 0, 0)
            complete_time = datetime(2025, 11, 8, 10, 30, 0)

            registry_data = {
                'agents': [{
                    'id': 'test-agent',
                    'task': 'Implement feature X',
                    'window': 'orchestrator:5',
                    'window_id': '@1001',
                    'project_dir': '/Users/test/project',
                    'workspace': 'test-workspace',
                    'spawned_at': spawn_time.isoformat(),
                    'completed_at': complete_time.isoformat(),
                    'status': 'completed'
                }]
            }

            with open(registry_path, 'w') as f:
                json.dump(registry_data, f)

            # Load registry and get history
            registry = AgentRegistry(registry_path)
            history = registry.get_history()

            # Verify we got one agent
            assert len(history) == 1

            # Verify duration is calculated
            agent = history[0]
            assert agent['duration_minutes'] == 30

        finally:
            registry_path.unlink(missing_ok=True)

    def test_reconcile_adds_completed_at_timestamp(self):
        """Test that reconcile() adds completed_at timestamp when marking agents as completed."""
        # Create temporary registry
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            registry_path = Path(f.name)

        try:
            # Create registry with active agent
            spawn_time = datetime(2025, 11, 8, 10, 0, 0)

            registry_data = {
                'agents': [{
                    'id': 'test-agent',
                    'task': 'Implement feature X',
                    'window': 'orchestrator:5',
                    'window_id': '@1001',
                    'project_dir': '/Users/test/project',
                    'workspace': 'test-workspace',
                    'spawned_at': spawn_time.isoformat(),
                    'status': 'active'
                }]
            }

            with open(registry_path, 'w') as f:
                json.dump(registry_data, f)

            # Load registry and reconcile (agent window no longer exists)
            registry = AgentRegistry(registry_path)
            before_reconcile = datetime.now()
            registry.reconcile([])  # Empty list means no windows exist
            after_reconcile = datetime.now()

            # Verify agent is marked completed
            agents = registry.list_agents()
            assert len(agents) == 1
            agent = agents[0]
            assert agent['status'] == 'completed'

            # Verify completed_at timestamp was added
            assert 'completed_at' in agent
            completed_at = datetime.fromisoformat(agent['completed_at'])

            # Verify timestamp is reasonable (between before and after reconcile)
            assert before_reconcile <= completed_at <= after_reconcile

        finally:
            registry_path.unlink(missing_ok=True)

    def test_get_analytics_groups_by_task_type(self):
        """Test getting analytics grouped by task type."""
        # Create temporary registry
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            registry_path = Path(f.name)

        try:
            # Create registry with agents of different types
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
                    },
                    {
                        'id': 'debug-1',
                        'task': 'Debug issue Z',
                        'window': 'orchestrator:7',
                        'window_id': '@1003',
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

            # Load registry and get analytics
            registry = AgentRegistry(registry_path)
            analytics = registry.get_analytics()

            # Verify grouping by task type
            assert 'implement' in analytics
            assert 'debug' in analytics

            # Verify counts
            assert analytics['implement']['count'] == 2
            assert analytics['debug']['count'] == 1

            # Verify average durations
            assert analytics['implement']['avg_duration_minutes'] == 40  # (30 + 50) / 2
            assert analytics['debug']['avg_duration_minutes'] == 20

        finally:
            registry_path.unlink(missing_ok=True)
