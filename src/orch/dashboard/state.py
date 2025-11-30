"""State management for dashboard."""
from typing import Dict, List, Any, Optional


class DashboardState:
    """Manages dashboard UI state."""

    def __init__(self, agents: List[Dict[str, Any]]):
        """Initialize state with agent list."""
        self.agents = agents
        self.cursor_position = 0
        self.expanded_groups: Dict[str, bool] = {}
        self.filter_query = ""
        self.filter_mode = "all"  # 'all', 'active', 'blocked', etc.
        # Panel focus: 'agents' or 'inbox'
        self.active_panel = "agents"
        self.inbox_cursor = 0
        self.inbox_items: List[Dict[str, Any]] = []

    def set_inbox_items(self, items: List[Dict[str, Any]]):
        """Set inbox items for navigation."""
        self.inbox_items = items
        if self.inbox_cursor >= len(items):
            self.inbox_cursor = max(0, len(items) - 1)

    def switch_panel(self):
        """Toggle between agents and inbox panels."""
        self.active_panel = "inbox" if self.active_panel == "agents" else "agents"

    def get_focused_inbox_item(self) -> Optional[Dict[str, Any]]:
        """Get currently focused inbox item."""
        if 0 <= self.inbox_cursor < len(self.inbox_items):
            return self.inbox_items[self.inbox_cursor]
        return None

    def move_inbox_cursor_down(self):
        """Move inbox cursor down."""
        if self.inbox_cursor < len(self.inbox_items) - 1:
            self.inbox_cursor += 1

    def move_inbox_cursor_up(self):
        """Move inbox cursor up."""
        if self.inbox_cursor > 0:
            self.inbox_cursor -= 1

    def move_cursor_down(self):
        """Move cursor to next visible item."""
        if self.cursor_position < len(self.agents) - 1:
            self.cursor_position += 1

    def move_cursor_up(self):
        """Move cursor to previous visible item."""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def get_focused_agent(self) -> Optional[Dict[str, Any]]:
        """Get currently focused agent."""
        if 0 <= self.cursor_position < len(self.agents):
            return self.agents[self.cursor_position]
        return None

    def jump_to_first(self):
        """Jump cursor to first item."""
        self.cursor_position = 0

    def jump_to_last(self):
        """Jump cursor to last item."""
        if self.agents:
            self.cursor_position = len(self.agents) - 1

    def is_group_expanded(self, top_level: str, project: str) -> bool:
        """Check if group is expanded."""
        key = f"{top_level}/{project}"
        return self.expanded_groups.get(key, False)

    def toggle_group(self, top_level: str, project: str):
        """Toggle group expanded/collapsed state."""
        key = f"{top_level}/{project}"
        self.expanded_groups[key] = not self.expanded_groups.get(key, False)

    def get_focused_group(self, groups: Dict) -> tuple:
        """Get the group that the cursor is currently in.

        Args:
            groups: Grouped agents dict from grouping.group_agents()

        Returns:
            (top_level, project) tuple or (None, None) if no focus
        """
        focused_agent = self.get_focused_agent()
        if not focused_agent:
            return (None, None)

        # Find which group this agent belongs to
        for top_level in groups:
            for project in groups[top_level]:
                for agent in groups[top_level][project]:
                    if agent['agent_id'] == focused_agent['agent_id']:
                        return (top_level, project)

        return (None, None)

    def set_filter(self, query: str):
        """Set filter query."""
        self.filter_query = query.lower()

    def clear_filter(self):
        """Clear filter query."""
        self.filter_query = ""

    def matches_filter(self, agent: Dict[str, Any]) -> bool:
        """Check if agent matches current filter.

        Args:
            agent: Agent dict to check

        Returns:
            True if matches filter (or no filter set)
        """
        if not self.filter_query:
            return True

        # Search in workspace name, phase, status, working_dir
        searchable = ' '.join([
            agent.get('workspace_name', ''),
            agent.get('phase', ''),
            agent.get('status', ''),
            agent.get('working_dir', '')
        ]).lower()

        return self.filter_query in searchable

    def ensure_cursor_valid(self):
        """Ensure cursor position is within bounds."""
        if self.cursor_position >= len(self.agents):
            self.cursor_position = max(0, len(self.agents) - 1)
        if self.cursor_position < 0:
            self.cursor_position = 0
