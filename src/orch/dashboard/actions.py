"""Action execution for dashboard commands."""
import subprocess
import json
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel


class ActionExecutor:
    """Executes actions on focused agents."""

    def __init__(self, console: Console):
        """Initialize with console for output."""
        self.console = console

    def tail_logs(self, agent: Dict[str, Any]) -> bool:
        """Tail agent logs in new terminal pane.

        Args:
            agent: Agent dict with agent_id

        Returns:
            True if successful, False otherwise
        """
        agent_id = agent.get('agent_id')
        if not agent_id:
            return False

        try:
            # Run orch tail in foreground (blocks until user exits)
            subprocess.run(
                ['orch', 'tail', agent_id],
                check=True,
                timeout=300  # 5 minute timeout
            )
            return True
        except subprocess.TimeoutExpired:
            self.console.print("[yellow]Tail timeout after 5 minutes[/]")
            return False
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error tailing logs: {e}[/]")
            return False

    def check_status(self, agent: Dict[str, Any]) -> Optional[str]:
        """Get detailed status for agent.

        Args:
            agent: Agent dict with agent_id

        Returns:
            Status output string or None if failed
        """
        agent_id = agent.get('agent_id')
        if not agent_id:
            return None

        try:
            result = subprocess.run(
                ['orch', 'status', '--format', 'json'],
                capture_output=True,
                text=True,
                check=True,
                timeout=30  # 30 second timeout
            )
            # TODO: Parse and format status nicely
            return result.stdout
        except subprocess.TimeoutExpired:
            return "Error: Status check timeout"
        except subprocess.CalledProcessError as e:
            return f"Error: {e}"

    def send_message(self, agent: Dict[str, Any]) -> bool:
        """Send interactive message to agent.

        Args:
            agent: Agent dict with agent_id

        Returns:
            True if successful, False otherwise
        """
        agent_id = agent.get('agent_id')
        if not agent_id:
            return False

        try:
            # Run orch send interactively (blocks)
            subprocess.run(
                ['orch', 'send', agent_id, '--interactive'],
                check=True,
                timeout=600  # 10 minute timeout for interactive session
            )
            return True
        except subprocess.TimeoutExpired:
            self.console.print("[yellow]Message timeout after 10 minutes[/]")
            return False
        except subprocess.CalledProcessError:
            return False

    def stop_agent(self, agent: Dict[str, Any]) -> bool:
        """Stop agent after confirmation.

        Args:
            agent: Agent dict with agent_id

        Returns:
            True if stopped, False if cancelled or failed
        """
        agent_id = agent.get('agent_id')
        workspace_name = agent.get('workspace_name', agent_id)

        # Confirm with user
        self.console.print(f"\n[yellow]Stop agent '{workspace_name}'? [y/N]:[/] ", end='')
        response = input().strip().lower()

        if response != 'y':
            self.console.print("[dim]Cancelled[/]")
            return False

        try:
            subprocess.run(
                ['orch', 'stop', agent_id],
                check=True,
                capture_output=True,
                timeout=30  # 30 second timeout
            )
            self.console.print(f"[green]Agent stopped[/]")
            return True
        except subprocess.TimeoutExpired:
            self.console.print("[red]Stop timeout after 30 seconds[/]")
            return False
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error stopping agent: {e}[/]")
            return False

    def complete_agent(self, agent: Dict[str, Any]) -> bool:
        """Complete agent after confirmation.

        Args:
            agent: Agent dict with agent_id

        Returns:
            True if completed, False if cancelled or failed
        """
        agent_id = agent.get('agent_id')
        workspace_name = agent.get('workspace_name', agent_id)

        # Confirm with user
        self.console.print(f"\n[yellow]Complete agent '{workspace_name}'? [y/N]:[/] ", end='')
        response = input().strip().lower()

        if response != 'y':
            self.console.print("[dim]Cancelled[/]")
            return False

        try:
            result = subprocess.run(
                ['orch', 'complete', agent_id],
                check=True,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            self.console.print(f"[green]Agent completed[/]")
            if result.stdout:
                self.console.print(result.stdout)
            return True
        except subprocess.TimeoutExpired:
            self.console.print("[red]Complete timeout after 60 seconds[/]")
            return False
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error completing agent: {e.stderr or e}[/]")
            return False

    def ack_inbox_item(self, item: Dict[str, Any], snooze_minutes: int = 0) -> bool:
        """Acknowledge an inbox item.

        Args:
            item: Inbox item dict with id
            snooze_minutes: Optional snooze duration

        Returns:
            True if acknowledged, False if failed
        """
        item_id = item.get('id')
        if not item_id:
            return False

        try:
            cmd = ['orch', 'inbox', '--ack', item_id]
            if snooze_minutes > 0:
                cmd.extend(['--snooze', str(snooze_minutes)])

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=10
            )
            self.console.print(f"[green]Acknowledged: {item_id}[/]")
            return True
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error acknowledging: {e}[/]")
            return False

    def respond_to_question(self, agent: Dict[str, Any]) -> bool:
        """Respond to agent's pending question with structured input.

        Args:
            agent: Agent dict with agent_id

        Returns:
            True if response sent, False if cancelled or failed
        """
        agent_id = agent.get('agent_id')
        if not agent_id:
            return False

        # First, extract the question
        try:
            result = subprocess.run(
                ['orch', 'question', agent_id],
                capture_output=True,
                text=True,
                timeout=10
            )
            question_text = result.stdout.strip() if result.returncode == 0 else None
        except subprocess.TimeoutExpired:
            question_text = None

        if question_text:
            self.console.print(Panel(question_text, title="Pending Question", border_style="yellow"))
        else:
            self.console.print("[dim]No structured question found. Sending free-form response.[/]")

        # Get response from user
        self.console.print("\n[bold]Your response:[/] ", end='')
        response = input().strip()

        if not response:
            self.console.print("[dim]Cancelled (empty response)[/]")
            return False

        # Send the response
        try:
            subprocess.run(
                ['orch', 'send', agent_id, response],
                check=True,
                capture_output=True,
                timeout=30
            )
            self.console.print(f"[green]Response sent to {agent_id}[/]")
            return True
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error sending response: {e}[/]")
            return False
