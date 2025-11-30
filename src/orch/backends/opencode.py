"""OpenCode backend implementation using HTTP API instead of tmux + CLI.

This backend communicates with a running OpenCode server via REST API and SSE,
replacing the tmux-based process management with structured API calls.

Key differences from ClaudeBackend:
- No tmux process management (OpenCode manages its own sessions)
- Structured data via JSON API (no text parsing)
- Real-time monitoring via SSE (no pane capture polling)
- Session-based instead of window-based

Requires: OpenCode server running (e.g., `bun run dev serve --port 4096`)
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urljoin

import requests

from .base import Backend

if TYPE_CHECKING:
    from orch.spawn import SpawnConfig


@dataclass
class OpenCodeSession:
    """Represents an OpenCode session (analogous to a tmux window/agent)."""
    id: str
    project_id: str
    directory: str
    title: str
    created: int
    updated: int
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """Represents a tool invocation from an OpenCode session."""
    id: str
    tool: str
    status: str  # pending, running, completed, error
    input: Dict[str, Any]
    output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[int] = None
    end_time: Optional[int] = None


@dataclass
class Message:
    """Represents a message in an OpenCode session."""
    id: str
    session_id: str
    role: str  # user, assistant
    parts: List[Dict[str, Any]] = field(default_factory=list)
    tokens: Dict[str, int] = field(default_factory=dict)
    cost: float = 0.0


class SSEClient:
    """Simple SSE client for OpenCode event stream."""

    def __init__(self, url: str):
        self.url = url
        self._stop = threading.Event()

    def events(self) -> Iterator[Dict[str, Any]]:
        """Yield events from the SSE stream."""
        with requests.get(self.url, stream=True, headers={'Accept': 'text/event-stream'}) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if self._stop.is_set():
                    break

                if line and line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError:
                        continue

    def stop(self):
        """Stop the event stream."""
        self._stop.set()


class OpenCodeClient:
    """HTTP client for OpenCode server API."""

    def __init__(self, base_url: str = "http://127.0.0.1:4096", directory: Optional[str] = None):
        """
        Initialize OpenCode client.

        Args:
            base_url: OpenCode server URL (default: localhost:4096)
            directory: Optional project directory to scope requests
        """
        self.base_url = base_url.rstrip('/')
        self.directory = directory
        self._session = requests.Session()
        if directory:
            self._session.headers['x-opencode-directory'] = directory

    def _url(self, path: str) -> str:
        """Build full URL for API path."""
        return urljoin(self.base_url + '/', path.lstrip('/'))

    def _get(self, path: str, **kwargs) -> requests.Response:
        """Make GET request."""
        return self._session.get(self._url(path), **kwargs)

    def _post(self, path: str, **kwargs) -> requests.Response:
        """Make POST request."""
        return self._session.post(self._url(path), **kwargs)

    def _patch(self, path: str, **kwargs) -> requests.Response:
        """Make PATCH request."""
        return self._session.patch(self._url(path), **kwargs)

    def _delete(self, path: str, **kwargs) -> requests.Response:
        """Make DELETE request."""
        return self._session.delete(self._url(path), **kwargs)

    # ========== Session Management ==========

    def list_sessions(self) -> List[OpenCodeSession]:
        """List all sessions."""
        resp = self._get('/session')
        resp.raise_for_status()

        return [
            OpenCodeSession(
                id=s['id'],
                project_id=s.get('projectID', ''),
                directory=s.get('directory', ''),
                title=s.get('title', ''),
                created=s.get('time', {}).get('created', 0),
                updated=s.get('time', {}).get('updated', 0),
                summary=s.get('summary', {})
            )
            for s in resp.json()
        ]

    def get_session(self, session_id: str) -> Optional[OpenCodeSession]:
        """Get a specific session by ID."""
        resp = self._get(f'/session/{session_id}')
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        s = resp.json()
        return OpenCodeSession(
            id=s['id'],
            project_id=s.get('projectID', ''),
            directory=s.get('directory', ''),
            title=s.get('title', ''),
            created=s.get('time', {}).get('created', 0),
            updated=s.get('time', {}).get('updated', 0),
            summary=s.get('summary', {})
        )

    def create_session(self, directory: Optional[str] = None) -> OpenCodeSession:
        """Create a new session."""
        params = {}
        if directory:
            params['directory'] = directory

        resp = self._post('/session', params=params)
        resp.raise_for_status()

        s = resp.json()
        return OpenCodeSession(
            id=s['id'],
            project_id=s.get('projectID', ''),
            directory=s.get('directory', ''),
            title=s.get('title', ''),
            created=s.get('time', {}).get('created', 0),
            updated=s.get('time', {}).get('updated', 0),
            summary=s.get('summary', {})
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        resp = self._delete(f'/session/{session_id}')
        return resp.status_code == 200

    # ========== Message Management ==========

    def get_messages(self, session_id: str) -> List[Message]:
        """Get all messages in a session."""
        resp = self._get(f'/session/{session_id}/message')
        resp.raise_for_status()

        messages = []
        for m in resp.json():
            info = m.get('info', {})
            messages.append(Message(
                id=info.get('id', ''),
                session_id=info.get('sessionID', ''),
                role=info.get('role', ''),
                parts=m.get('parts', []),
                tokens=info.get('tokens', {}),
                cost=info.get('cost', 0.0)
            ))
        return messages

    def send_message(self, session_id: str, content: str, agent: str = "build") -> Dict[str, Any]:
        """
        Send a message to a session (prompt the agent).

        Args:
            session_id: Target session ID
            content: Message content (the prompt)
            agent: Agent to use ("build" or "plan")

        Returns:
            Response data from the API
        """
        # OpenCode API expects parts array with typed parts
        payload = {
            'parts': [{'type': 'text', 'text': content}],
            'agent': agent
        }
        resp = self._post(f'/session/{session_id}/prompt_async', json=payload)
        resp.raise_for_status()
        return resp.json()

    def send_message_async(
        self,
        session_id: str,
        content: str,
        agent: str = "build",
        model: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send a message asynchronously (returns immediately, agent processes in background).

        This is the preferred method for spawning - returns immediately while agent works.
        Returns empty dict on success (API returns 204 No Content).

        Args:
            session_id: Target session ID
            content: Message content (the prompt)
            agent: Agent to use ("build" or "plan")
            model: Optional model specification {"providerID": "anthropic", "modelID": "claude-opus-4-5-20250929"}
        """
        # OpenCode API expects parts array with typed parts
        payload = {
            'parts': [{'type': 'text', 'text': content}],
            'agent': agent
        }
        # Add model specification if provided
        if model:
            payload['model'] = model

        resp = self._post(f'/session/{session_id}/prompt_async', json=payload)
        resp.raise_for_status()
        # API returns 204 No Content on success
        if resp.status_code == 204 or not resp.text:
            return {'status': 'accepted', 'session_id': session_id}
        return resp.json()

    # ========== Tool Calls ==========

    def get_tool_calls(self, session_id: str) -> List[ToolCall]:
        """Extract tool calls from session messages."""
        messages = self.get_messages(session_id)
        tool_calls = []

        for msg in messages:
            for part in msg.parts:
                if part.get('type') == 'tool':
                    state = part.get('state', {})
                    tool_calls.append(ToolCall(
                        id=part.get('callID', ''),
                        tool=part.get('tool', ''),
                        status=state.get('status', 'unknown'),
                        input=state.get('input', {}),
                        output=state.get('output'),
                        metadata=state.get('metadata', {}),
                        start_time=state.get('time', {}).get('start'),
                        end_time=state.get('time', {}).get('end')
                    ))

        return tool_calls

    # ========== Status ==========

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get session status (idle, running, etc.)."""
        resp = self._get('/session/status')
        resp.raise_for_status()

        statuses = resp.json()
        for s in statuses:
            if s.get('sessionID') == session_id:
                return s

        return {'sessionID': session_id, 'status': 'unknown'}

    # ========== SSE Events ==========

    def subscribe_events(self) -> SSEClient:
        """
        Subscribe to server events via SSE.

        Returns an SSEClient that yields events. Use in a context or call stop() when done.

        Event types include:
        - server.connected
        - session.created, session.updated
        - message.created, message.updated
        - tool.started, tool.completed, tool.error
        - permission.requested
        """
        return SSEClient(self._url('/event'))

    # ========== Permissions ==========

    def approve_permission(self, session_id: str, permission_id: str) -> bool:
        """Approve a pending permission request."""
        resp = self._post(f'/session/{session_id}/permissions/{permission_id}', json={'approved': True})
        return resp.status_code == 200

    def deny_permission(self, session_id: str, permission_id: str) -> bool:
        """Deny a pending permission request."""
        resp = self._post(f'/session/{session_id}/permissions/{permission_id}', json={'approved': False})
        return resp.status_code == 200

    # ========== Utility ==========

    def health_check(self) -> bool:
        """Check if server is responding."""
        try:
            resp = self._get('/config')
            return resp.status_code == 200
        except requests.RequestException:
            return False


class OpenCodeBackend(Backend):
    """
    Backend implementation using OpenCode HTTP API.

    This backend diverges from the CLI-centric Backend interface because OpenCode
    uses a client-server architecture with REST API instead of tmux + CLI.

    Key differences:
    - build_command() returns None (no CLI command)
    - wait_for_ready() checks API health instead of tmux pane
    - Adds new methods for API-based operations
    """

    def __init__(self, server_url: str = "http://127.0.0.1:4096"):
        """
        Initialize OpenCode backend.

        Args:
            server_url: OpenCode server URL. Can be overridden with OPENCODE_URL env var.
        """
        self.server_url = os.getenv('OPENCODE_URL', server_url)
        self._client: Optional[OpenCodeClient] = None

    @property
    def client(self) -> OpenCodeClient:
        """Get or create the OpenCode client."""
        if self._client is None:
            self._client = OpenCodeClient(self.server_url)
        return self._client

    @property
    def name(self) -> str:
        return "opencode"

    def get_config_dir(self) -> Path:
        """OpenCode config directory."""
        # OpenCode uses ~/.local/share/opencode/ for data
        return Path.home() / ".local" / "share" / "opencode"

    def build_command(self, prompt: str, options: Optional[Dict] = None) -> str:
        """
        Not applicable for OpenCode - it uses HTTP API, not CLI commands.

        Returns empty string. Use spawn_session() instead.
        """
        return ""

    def wait_for_ready(self, window_target: str, timeout: float = 5.0) -> bool:
        """
        Check if OpenCode server is ready (health check).

        For OpenCode, we check API availability instead of tmux pane content.
        The window_target parameter is ignored.
        """
        start = time.time()
        while (time.time() - start) < timeout:
            if self.client.health_check():
                return True
            time.sleep(0.1)
        return False

    def get_env_vars(self, config: "SpawnConfig", workspace_abs: Path, deliverables_list: str) -> Dict[str, str]:
        """
        Get environment variables for OpenCode.

        These are set on the server side via the prompt, not as env vars.
        Returns minimal env vars for compatibility.
        """
        return {
            "OPENCODE_CONTEXT": "worker",
            "OPENCODE_WORKSPACE": str(workspace_abs),
            "OPENCODE_PROJECT": str(config.project_dir),
            "OPENCODE_DELIVERABLES": deliverables_list,
        }

    # ========== OpenCode-Specific Methods ==========

    def spawn_session(
        self,
        prompt: str,
        directory: str,
        agent: str = "build",
        async_mode: bool = True,
        model: Optional[Dict[str, str]] = None
    ) -> OpenCodeSession:
        """
        Spawn a new OpenCode session with an initial prompt.

        This is the OpenCode equivalent of creating a tmux window and sending a prompt.

        Args:
            prompt: Initial prompt for the agent
            directory: Project directory to work in
            agent: Agent to use ("build" or "plan")
            async_mode: If True, return immediately while agent processes
            model: Optional model specification {"providerID": "anthropic", "modelID": "claude-opus-4-5-20250929"}

        Returns:
            The created OpenCodeSession
        """
        # Create session scoped to directory
        client = OpenCodeClient(self.server_url, directory=directory)
        session = client.create_session(directory=directory)

        # Send initial prompt
        if async_mode:
            client.send_message_async(session.id, prompt, agent=agent, model=model)
        else:
            client.send_message(session.id, prompt, agent=agent)

        return session

    def get_session_by_id(self, session_id: str) -> Optional[OpenCodeSession]:
        """Get a session by its ID."""
        return self.client.get_session(session_id)

    def list_active_sessions(self) -> List[OpenCodeSession]:
        """List all active sessions."""
        return self.client.list_sessions()

    def send_message(self, session_id: str, content: str) -> Dict[str, Any]:
        """Send a message to a session (like orch send)."""
        return self.client.send_message(session_id, content)

    def get_messages(self, session_id: str) -> List[Message]:
        """Get all messages from a session."""
        return self.client.get_messages(session_id)

    def get_tool_calls(self, session_id: str) -> List[ToolCall]:
        """Get tool calls from a session."""
        return self.client.get_tool_calls(session_id)

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Get session status."""
        return self.client.get_session_status(session_id)

    def subscribe_events(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> SSEClient:
        """
        Subscribe to real-time events.

        If callback provided, events are passed to it.
        Otherwise, returns SSEClient for manual iteration.
        """
        sse = self.client.subscribe_events()

        if callback:
            def run():
                for event in sse.events():
                    callback(event)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

        return sse

    def delete_session(self, session_id: str) -> bool:
        """Delete a session (cleanup)."""
        return self.client.delete_session(session_id)


# ========== Convenience Functions ==========

def discover_server() -> Optional[str]:
    """
    Try to discover a running OpenCode server.

    Checks common ports and returns the URL if found.
    """
    ports_to_try = [4096, 53615, 8080]  # Common OpenCode ports

    for port in ports_to_try:
        url = f"http://127.0.0.1:{port}"
        try:
            resp = requests.get(f"{url}/config", timeout=1)
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            continue

    return None


def get_backend(server_url: Optional[str] = None) -> OpenCodeBackend:
    """
    Get an OpenCode backend instance.

    If no URL provided, attempts to discover a running server.
    """
    if server_url is None:
        server_url = discover_server()
        if server_url is None:
            raise RuntimeError(
                "No OpenCode server found. Start one with: "
                "cd ~/Documents/personal/opencode && bun run dev serve --port 4096"
            )

    return OpenCodeBackend(server_url)
