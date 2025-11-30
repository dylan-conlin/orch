"""Main dashboard UI loop."""
import json
import subprocess
import readchar
from typing import List, Dict, Any
from rich.console import Console
from rich.live import Live
from rich.tree import Tree
from rich.panel import Panel
from rich.layout import Layout
from rich.markup import escape

from orch.dashboard.grouping import group_agents
from orch.dashboard.state import DashboardState
from orch.dashboard.keyboard import KeyHandler, KeyAction
from orch.dashboard.rendering import get_status_badge, format_agent_line, format_agent_detail_line
from orch.dashboard.actions import ActionExecutor


class Dashboard:
    """Terminal UI dashboard for agent monitoring."""

    def __init__(self):
        """Initialize dashboard."""
        self.console = Console()
        self.state = None
        self.groups = {}
        self.inbox_items = []
        self.key_handler = KeyHandler()
        self.actions = ActionExecutor(self.console)
        self.running = False

    def fetch_agents(self) -> List[Dict[str, Any]]:
        """Fetch agent data from orch status --json.

        Returns:
            List of agent dicts transformed to match expected schema
        """
        try:
            result = subprocess.run(
                ['orch', 'status', '--format', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            raw_agents = data.get('agents', [])

            # Transform agent data to match expected schema
            transformed = []
            for agent in raw_agents:
                # Extract workspace name from path
                workspace_path = agent.get('workspace', '')
                workspace_name = workspace_path.split('/')[-1] if workspace_path else agent.get('agent_id', '')

                # Map priority to status
                priority = agent.get('priority', 'ok')
                status_map = {
                    'ok': 'active',
                    'warning': 'blocked',
                    'error': 'failed'
                }
                status = status_map.get(priority, 'active')

                # Check phase for completion
                phase = agent.get('phase', 'Unknown')
                if phase.lower() in ['complete', 'completed']:
                    status = 'complete'

                transformed.append({
                    'agent_id': agent.get('agent_id', ''),
                    'workspace_name': workspace_name,
                    'working_dir': agent.get('project', ''),
                    'phase': phase,
                    'status': status,
                    'last_updated': agent.get('started_at', '')
                })

            return transformed
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.console.print(f"[red]Error fetching agents: {e}[/]")
            return []

    def fetch_inbox(self) -> List[Dict[str, Any]]:
        """Fetch inbox items from orch inbox --json."""
        try:
            result = subprocess.run(
                ['orch', 'inbox', '--format', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            return data.get('items', [])
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.console.print(f"[red]Error fetching inbox: {e}[/]")
            return []

    def _render_inbox_panel(self) -> Panel:
        """Render inbox summary panel with optional focus highlighting."""
        if self.inbox_items is None:
            return Panel("[red]Failed to load inbox[/red]", title="Inbox", border_style="red")

        if not self.inbox_items:
            return Panel("Inbox clear ✅", title="Inbox", border_style="green")

        severity_badge = {
            "critical": "[red]●[/red]",
            "warning": "[yellow]●[/yellow]",
            "info": "[blue]●[/blue]"
        }
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        section_order = ["blocked", "question", "ready", "review", "pattern", "feedback"]

        # Build flat list for cursor tracking
        flat_items: List[Dict[str, Any]] = []
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in self.inbox_items:
            grouped.setdefault(item.get("type", "unknown"), []).append(item)

        for section in section_order:
            if section in grouped:
                for item in sorted(grouped[section],
                                   key=lambda i: (severity_order.get(i.get("severity", "info"), 3), i.get("id", ""))):
                    flat_items.append(item)

        # Update state with flat items for navigation
        if self.state:
            self.state.set_inbox_items(flat_items)

        is_inbox_focused = self.state and self.state.active_panel == "inbox"
        focused_item = self.state.get_focused_inbox_item() if self.state else None

        lines: List[str] = []
        item_idx = 0
        for section in section_order:
            if section not in grouped or not grouped[section]:
                continue
            title = section.capitalize()
            lines.append(f"[bold]{title} ({len(grouped[section])})[/bold]")
            for item in sorted(grouped[section],
                               key=lambda i: (severity_order.get(i.get("severity", "info"), 3), i.get("id", ""))):
                badge = severity_badge.get(item.get("severity", "info"), "●")
                age = f" • {escape(item['age'])}" if item.get("age") else ""
                stale = " • ⏰ stale" if item.get("stale") else ""

                # Highlight focused item
                is_focused = is_inbox_focused and focused_item and item.get("id") == focused_item.get("id")
                if is_focused:
                    title_line = f"  [reverse]{badge} {escape(item.get('title', ''))}{age}{stale}[/reverse]"
                else:
                    title_line = f"  {badge} {escape(item.get('title', ''))}{age}{stale}"
                lines.append(title_line)

                workspace = item.get("workspace")
                if workspace:
                    lines.append(f"     \\[{escape(item.get('project', ''))}] {escape(workspace)}")
                if item.get("recommendation"):
                    lines.append(f"     → {escape(item.get('recommendation'))}")
                item_idx += 1
            lines.append("")

        # Panel border color indicates focus
        border_style = "green" if is_inbox_focused else "cyan"
        title = "Inbox [TAB]" if is_inbox_focused else "Inbox"

        return Panel("\n".join(lines).strip(), title=title, border_style=border_style)

    def build_tree(self) -> Tree:
        """Build Rich Tree from grouped agents.

        Returns:
            Rich Tree object with hierarchical agent display
        """
        tree = Tree("🎯 Agent Dashboard", guide_style="dim")

        if not self.groups:
            tree.add("[dim]No agents found[/]")
            return tree

        # Build tree: top_level -> project -> agents
        for top_level in sorted(self.groups.keys()):
            # Add top-level branch (e.g., "work/SendCutSend", "personal")
            # Escape top_level to prevent Rich markup interpretation (paths with [/])
            top_branch = tree.add(f"[bold]{escape(top_level)}/[/]", guide_style="cyan")

            projects = self.groups[top_level]
            for project in sorted(projects.keys()):
                agents = projects[project]

                # Check if group is expanded
                is_expanded = self.state.is_group_expanded(top_level, project)

                # Count agents by status
                active_count = sum(1 for a in agents if a['status'] == 'active')
                blocked_count = sum(1 for a in agents if a['status'] == 'blocked')
                complete_count = sum(1 for a in agents if a['status'] == 'complete')
                failed_count = sum(1 for a in agents if a['status'] == 'failed')

                # Build summary
                status_parts = []
                if active_count:
                    status_parts.append(f"{active_count} active")
                if blocked_count:
                    status_parts.append(f"{blocked_count} blocked")
                if failed_count:
                    status_parts.append(f"{failed_count} failed")
                if complete_count:
                    status_parts.append(f"{complete_count} complete")

                status_summary = ', '.join(status_parts) if status_parts else 'no agents'

                # Collapsed view: show summary
                if not is_expanded:
                    expand_icon = "▶"
                    # Escape project name to prevent Rich markup interpretation
                    project_line = f"{expand_icon} {escape(project)} ({len(agents)} agents) - {status_summary}"
                    top_branch.add(project_line, guide_style="dim")
                else:
                    # Expanded view: show all agents
                    expand_icon = "▼"
                    # Escape project name to prevent Rich markup interpretation
                    project_line = f"{expand_icon} {escape(project)} ({len(agents)} agents) - {status_summary}"
                    project_branch = top_branch.add(project_line, guide_style="yellow")

                    # Add each agent (filter applied)
                    for idx, agent in enumerate(agents):
                        # Skip if doesn't match filter
                        if not self.state.matches_filter(agent):
                            continue

                        # Check if this agent is focused
                        focused_agent = self.state.get_focused_agent()
                        is_focused = (focused_agent and
                                    focused_agent['agent_id'] == agent['agent_id'])

                        # Format agent line
                        agent_line = format_agent_line(agent, is_focused)
                        agent_branch = project_branch.add(agent_line)

                        # Add detail line
                        detail_line = format_agent_detail_line(agent)
                        agent_branch.add(detail_line, guide_style="dim")

        return tree

    def render_dashboard(self) -> Layout:
        """Render complete dashboard layout.

        Returns:
            Rich Layout with tree and footer
        """
        layout = Layout()

        # Header
        header = Panel(
            "Agent Dashboard | Press ? for help | q to quit",
            style="bold blue"
        )

        # Tree view
        tree = self.build_tree()
        inbox_panel = self._render_inbox_panel()

        # Footer (show filter if active, different hints per panel)
        if self.state and self.state.active_panel == "inbox":
            footer_text = "j/k: navigate | a: ack | c: complete | R: respond | Tab: agents | r: refresh | q: quit"
        else:
            footer_text = "j/k: navigate | c: complete | R: respond | t: tail | Tab: inbox | r: refresh | q: quit"
        if self.state and self.state.filter_query:
            footer_text = f"🔍 Filter: '{self.state.filter_query}' | {footer_text}"

        footer = Panel(footer_text, style="dim")

        body = Layout()
        body.split_row(
            Layout(tree, ratio=2),
            Layout(inbox_panel, ratio=1)
        )

        layout.split_column(
            Layout(header, size=3),
            body,
            Layout(footer, size=3)
        )

        return layout

    def show_help(self):
        """Show help screen with keybindings."""
        help_text = """
[bold cyan]Keyboard Navigation[/]

[yellow]Movement:[/]
  j / ↓     Move cursor down
  k / ↑     Move cursor up
  g         Jump to first item
  G         Jump to last item
  Tab       Switch focus: agents ↔ inbox
  Enter / o Expand/collapse group

[yellow]Control Plane Actions:[/]
  c / 6     Complete agent
  a / 7     Acknowledge inbox item (when inbox focused)
  R / 8     Respond to question (structured)

[yellow]Agent Actions:[/]
  t / 1     Tail logs
  s / 2     Check status
  m / 3     Send message
  i / 4     Show full details
  x / 5     Stop agent

[yellow]Filtering:[/]
  /         Enter filter mode
  Esc       Clear filter

[yellow]Global:[/]
  r         Refresh data
  ?         Show this help
  q         Quit dashboard

[dim]Press any key to close help[/]
"""
        self.console.clear()
        self.console.print(Panel(help_text, title="Dashboard Help", border_style="cyan"))
        readchar.readkey()

    def run(self):
        """Run dashboard main loop with live keyboard input."""
        # Fetch initial data
        agents = self.fetch_agents()
        inbox_items = self.fetch_inbox()
        if not agents:
            self.console.print("[yellow]No agents found. Spawn some agents first![/]")
            return

        self.state = DashboardState(agents)
        self.groups = group_agents(agents)
        self.inbox_items = inbox_items

        # Expand all groups by default for better UX
        for top_level in self.groups:
            for project in self.groups[top_level]:
                self.state.expanded_groups[f"{top_level}/{project}"] = True

        self.running = True

        # Initial render
        self.console.clear()
        layout = self.render_dashboard()
        self.console.print(layout)

        # Keyboard input loop
        try:
            while self.running:
                # Read single keypress
                key = readchar.readkey()

                # Map to action
                action = self.key_handler.handle_key(key)

                # Handle action
                if action == KeyAction.QUIT:
                    self.running = False
                elif action == KeyAction.SWITCH_PANEL:
                    self.state.switch_panel()
                elif action == KeyAction.MOVE_DOWN:
                    # Navigate based on active panel
                    if self.state.active_panel == "inbox":
                        self.state.move_inbox_cursor_down()
                    else:
                        self.state.move_cursor_down()
                elif action == KeyAction.MOVE_UP:
                    if self.state.active_panel == "inbox":
                        self.state.move_inbox_cursor_up()
                    else:
                        self.state.move_cursor_up()
                elif action == KeyAction.JUMP_FIRST:
                    self.state.jump_to_first()
                elif action == KeyAction.JUMP_LAST:
                    self.state.jump_to_last()
                elif action == KeyAction.TOGGLE_EXPAND:
                    # Toggle the group that contains focused agent
                    top_level, project = self.state.get_focused_group(self.groups)
                    if top_level and project:
                        self.state.toggle_group(top_level, project)
                elif action == KeyAction.REFRESH:
                    agents = self.fetch_agents()
                    inbox_items = self.fetch_inbox()
                    self.state = DashboardState(agents)
                    self.groups = group_agents(agents)
                    self.inbox_items = inbox_items
                    self.state.ensure_cursor_valid()
                elif action == KeyAction.TAIL:
                    focused = self.state.get_focused_agent()
                    if focused:
                        # Exit dashboard temporarily for tail
                        self.console.clear()
                        self.actions.tail_logs(focused)
                        # Re-render will happen at end of loop
                        continue
                elif action == KeyAction.STATUS:
                    focused = self.state.get_focused_agent()
                    if focused:
                        # Show status in modal
                        status = self.actions.check_status(focused)
                        self.console.clear()
                        self.console.print(Panel(status or "No status", title="Agent Status"))
                        self.console.print("\n[dim]Press any key to continue...[/]")
                        readchar.readkey()
                elif action == KeyAction.MESSAGE:
                    focused = self.state.get_focused_agent()
                    if focused:
                        # Exit dashboard for interactive message
                        self.console.clear()
                        self.actions.send_message(focused)
                        # Refresh data on return (message may change state)
                        agents = self.fetch_agents()
                        inbox_items = self.fetch_inbox()
                        self.state = DashboardState(agents)
                        self.groups = group_agents(agents)
                        self.inbox_items = inbox_items
                        self.state.ensure_cursor_valid()
                elif action == KeyAction.STOP:
                    focused = self.state.get_focused_agent()
                    if focused:
                        if self.actions.stop_agent(focused):
                            # Refresh data after stopping
                            agents = self.fetch_agents()
                            inbox_items = self.fetch_inbox()
                            self.state = DashboardState(agents)
                            self.groups = group_agents(agents)
                            self.inbox_items = inbox_items
                            self.state.ensure_cursor_valid()
                elif action == KeyAction.INFO:
                    focused = self.state.get_focused_agent()
                    if focused:
                        # Show full agent details
                        details = json.dumps(focused, indent=2)
                        self.console.clear()
                        self.console.print(Panel(details, title="Agent Details"))
                        self.console.print("\n[dim]Press any key to continue...[/]")
                        readchar.readkey()
                elif action == KeyAction.FILTER:
                    # Enter filter mode
                    self.console.clear()
                    self.console.print("[bold]Filter agents:[/] ", end='')
                    query = input()
                    self.state.set_filter(query)
                elif action == KeyAction.CLEAR_FILTER:
                    self.state.clear_filter()
                elif action == KeyAction.HELP:
                    self.show_help()
                elif action == KeyAction.COMPLETE:
                    # Complete focused agent (works from either panel)
                    focused = self.state.get_focused_agent()
                    if focused:
                        self.console.clear()
                        if self.actions.complete_agent(focused):
                            # Refresh data after completion
                            agents = self.fetch_agents()
                            inbox_items = self.fetch_inbox()
                            self.state = DashboardState(agents)
                            self.groups = group_agents(agents)
                            self.inbox_items = inbox_items
                            self.state.ensure_cursor_valid()
                        self.console.print("\n[dim]Press any key to continue...[/]")
                        readchar.readkey()
                elif action == KeyAction.ACK:
                    # Acknowledge focused inbox item
                    if self.state.active_panel == "inbox":
                        focused_item = self.state.get_focused_inbox_item()
                        if focused_item:
                            self.console.clear()
                            self.actions.ack_inbox_item(focused_item)
                            # Refresh inbox
                            inbox_items = self.fetch_inbox()
                            self.inbox_items = inbox_items
                            self.console.print("\n[dim]Press any key to continue...[/]")
                            readchar.readkey()
                elif action == KeyAction.RESPOND:
                    # Respond to question from focused agent
                    focused = self.state.get_focused_agent()
                    if focused:
                        self.console.clear()
                        if self.actions.respond_to_question(focused):
                            # Refresh data after response
                            agents = self.fetch_agents()
                            inbox_items = self.fetch_inbox()
                            self.state = DashboardState(agents)
                            self.groups = group_agents(agents)
                            self.inbox_items = inbox_items
                            self.state.ensure_cursor_valid()
                        self.console.print("\n[dim]Press any key to continue...[/]")
                        readchar.readkey()

                # Re-render
                self.console.clear()
                layout = self.render_dashboard()
                self.console.print(layout)

        except KeyboardInterrupt:
            pass  # Clean exit on Ctrl+C

        self.console.print("\n[dim]Dashboard closed[/]")
