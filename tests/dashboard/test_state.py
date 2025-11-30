"""Tests for dashboard state management."""
import pytest
from orch.dashboard.state import DashboardState


def test_cursor_starts_at_first_agent():
    """Cursor should start at first visible agent."""
    agents = [
        {'agent_id': 'agent1', 'workspace_name': 'test-1'},
        {'agent_id': 'agent2', 'workspace_name': 'test-2'},
    ]

    state = DashboardState(agents)

    assert state.cursor_position == 0
    assert state.get_focused_agent()['agent_id'] == 'agent1'


def test_move_cursor_down():
    """Should move cursor to next agent."""
    agents = [
        {'agent_id': 'agent1', 'workspace_name': 'test-1'},
        {'agent_id': 'agent2', 'workspace_name': 'test-2'},
    ]

    state = DashboardState(agents)
    state.move_cursor_down()

    assert state.cursor_position == 1
    assert state.get_focused_agent()['agent_id'] == 'agent2'


def test_move_cursor_up():
    """Should move cursor to previous agent."""
    agents = [
        {'agent_id': 'agent1', 'workspace_name': 'test-1'},
        {'agent_id': 'agent2', 'workspace_name': 'test-2'},
    ]

    state = DashboardState(agents)
    state.cursor_position = 1
    state.move_cursor_up()

    assert state.cursor_position == 0


def test_cursor_doesnt_go_below_zero():
    """Cursor should not go below 0."""
    agents = [{'agent_id': 'agent1', 'workspace_name': 'test-1'}]

    state = DashboardState(agents)
    state.move_cursor_up()

    assert state.cursor_position == 0


def test_cursor_doesnt_exceed_agent_count():
    """Cursor should not exceed agent count."""
    agents = [
        {'agent_id': 'agent1', 'workspace_name': 'test-1'},
        {'agent_id': 'agent2', 'workspace_name': 'test-2'},
    ]

    state = DashboardState(agents)
    state.move_cursor_down()
    state.move_cursor_down()
    state.move_cursor_down()  # Try to go past end

    assert state.cursor_position == 1  # Stays at last item


def test_toggle_group_expanded():
    """Should toggle group expanded state."""
    agents = [{'agent_id': 'agent1', 'workspace_name': 'test-1'}]
    state = DashboardState(agents)

    # Groups start collapsed
    assert state.is_group_expanded('work/SendCutSend', 'pdf-generator') is False

    # Toggle to expanded
    state.toggle_group('work/SendCutSend', 'pdf-generator')
    assert state.is_group_expanded('work/SendCutSend', 'pdf-generator') is True

    # Toggle back to collapsed
    state.toggle_group('work/SendCutSend', 'pdf-generator')
    assert state.is_group_expanded('work/SendCutSend', 'pdf-generator') is False
