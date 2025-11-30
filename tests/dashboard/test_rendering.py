"""Tests for dashboard rendering components."""
import pytest
from orch.dashboard.rendering import get_status_badge, format_agent_line


def test_get_status_badge_active():
    """Should return green badge for active agents."""
    badge = get_status_badge('active', 'Implementing')
    assert '[ACTIVE]' in badge
    assert 'green' in badge.lower() or badge.startswith('[green]')


def test_get_status_badge_blocked():
    """Should return yellow badge for blocked agents."""
    badge = get_status_badge('blocked', 'Planning')
    assert '[BLOCKED]' in badge


def test_get_status_badge_complete():
    """Should return gray badge for complete agents."""
    badge = get_status_badge('complete', 'Complete')
    assert '[COMPLETE]' in badge


def test_format_agent_line():
    """Should format agent as single line with badge."""
    agent = {
        'agent_id': 'abc123',
        'workspace_name': 'implement-feature-xyz',
        'status': 'active',
        'phase': 'Implementing',
        'last_updated': '2025-11-14T10:00:00Z'
    }

    line = format_agent_line(agent, is_focused=False)

    assert 'implement-feature-xyz' in line
    assert '[ACTIVE]' in line
    assert 'abc123' not in line  # Agent ID should not be shown


def test_format_agent_detail_line():
    """Should format agent detail line with phase and timestamp."""
    from orch.dashboard.rendering import format_agent_detail_line

    agent = {
        'phase': 'Implementing',
        'last_updated': '2025-11-14T10:30:00Z'
    }

    detail = format_agent_detail_line(agent)

    assert 'Phase: Implementing' in detail
    assert 'Updated:' in detail
