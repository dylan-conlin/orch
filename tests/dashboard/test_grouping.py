"""Tests for agent grouping logic."""
import pytest
from orch.dashboard.grouping import group_agents


def test_groups_agents_by_work_project():
    """Should group agents by work project path."""
    agents = [
        {
            'agent_id': 'agent1',
            'workspace_name': 'test-workspace-1',
            'working_dir': '/Users/dylan/Documents/work/SendCutSend/scs-special-projects/pdf-generator',
            'phase': 'Planning',
            'last_updated': '2025-11-14T10:00:00Z',
            'status': 'active'
        },
        {
            'agent_id': 'agent2',
            'workspace_name': 'test-workspace-2',
            'working_dir': '/Users/dylan/Documents/work/SendCutSend/scs-special-projects/pdf-generator',
            'phase': 'Implementing',
            'last_updated': '2025-11-14T10:05:00Z',
            'status': 'active'
        },
    ]

    groups = group_agents(agents)

    assert 'work/SendCutSend' in groups
    assert 'scs-special-projects/pdf-generator' in groups['work/SendCutSend']
    assert len(groups['work/SendCutSend']['scs-special-projects/pdf-generator']) == 2


def test_groups_agents_by_personal_project():
    """Should group personal project agents."""
    agents = [
        {
            'agent_id': 'agent1',
            'workspace_name': 'test-workspace',
            'working_dir': '/Users/dylan/Documents/personal/context-driven-dev',
            'phase': 'Planning',
            'last_updated': '2025-11-14T10:00:00Z',
            'status': 'active'
        },
    ]

    groups = group_agents(agents)

    assert 'personal' in groups
    assert 'context-driven-dev' in groups['personal']


def test_handles_uncategorized_agents():
    """Should handle agents outside standard directories."""
    agents = [
        {
            'agent_id': 'agent1',
            'workspace_name': 'test-workspace',
            'working_dir': '/tmp/random-project',
            'phase': 'Planning',
            'last_updated': '2025-11-14T10:00:00Z',
            'status': 'active'
        },
    ]

    groups = group_agents(agents)

    assert 'uncategorized' in groups
    assert 'other' in groups['uncategorized']


def test_sorts_agents_by_last_updated():
    """Should sort agents within group by most recent first."""
    agents = [
        {
            'agent_id': 'agent1',
            'workspace_name': 'old-agent',
            'working_dir': '/Users/dylan/Documents/personal/test-project',
            'phase': 'Planning',
            'last_updated': '2025-11-14T10:00:00Z',
            'status': 'active'
        },
        {
            'agent_id': 'agent2',
            'workspace_name': 'new-agent',
            'working_dir': '/Users/dylan/Documents/personal/test-project',
            'phase': 'Implementing',
            'last_updated': '2025-11-14T12:00:00Z',
            'status': 'active'
        },
    ]

    groups = group_agents(agents)

    agents_list = groups['personal']['test-project']
    assert agents_list[0]['agent_id'] == 'agent2'  # Most recent first
    assert agents_list[1]['agent_id'] == 'agent1'
