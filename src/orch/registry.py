"""
Agent Registry - Minimal agent tracking for tmux windows.

Simplified version: tracks agent_id ↔ window_id mapping for tmux operations.
Beads is the source of truth for agent state and lifecycle.
"""

import json
import fcntl
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from orch.logging import OrchLogger


class AgentRegistry:
    """
    Manages persistent state for spawned agents with file locking.

    Minimal tracking for tmux window management:
    - Agent ID ↔ window_id mapping
    - Basic agent metadata (project_dir, beads_id)
    - Status tracking (active, completed, abandoned, deleted)

    Uses fcntl file locking to prevent race conditions.
    Note: File locking requires Unix-like systems.
    """

    def __init__(self, registry_path: Path = None):
        if registry_path is None:
            registry_path = Path.home() / '.orch' / 'agent-registry.json'
        self.registry_path = Path(registry_path)
        self._agents = []
        self._logger = OrchLogger()
        self._lock_timeout = 10  # seconds
        self._load()

    def _load(self):
        """Load registry from disk with shared lock (allows concurrent reads)."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    data = json.load(f)
                    self._agents = data.get('agents', [])
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def save(self):
        """Persist registry to disk with exclusive lock and merge logic."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        while True:
            try:
                mode = 'r+' if self.registry_path.exists() else 'w+'
                with open(self.registry_path, mode) as f:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        if time.time() - start_time > self._lock_timeout:
                            raise TimeoutError(
                                f"Could not acquire registry lock after {self._lock_timeout}s"
                            )
                        time.sleep(0.01)
                        continue

                    try:
                        # Re-read and merge to prevent concurrent overwrites
                        f.seek(0)
                        content = f.read()
                        if content.strip():
                            current_data = json.loads(content)
                            current_agents = current_data.get('agents', [])
                        else:
                            current_agents = []

                        merged_agents = self._merge_agents(current_agents, self._agents)

                        f.seek(0)
                        f.truncate()
                        json.dump({'agents': merged_agents}, f, indent=2)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    break

            except FileNotFoundError:
                continue

    def _merge_agents(self, current: List[Dict[str, Any]], ours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge concurrent registry changes using ID-based deduplication.
        Newer entries (by spawned_at) win in conflicts.
        """
        merged = {}

        # Index our agents
        ours_by_id = {a['id']: a for a in ours}

        # Process current agents from disk
        for current_agent in current:
            agent_id = current_agent['id']
            our_agent = ours_by_id.get(agent_id)

            if our_agent:
                # Compare timestamps, newer wins
                current_ts = current_agent.get('spawned_at', '')
                our_ts = our_agent.get('spawned_at', '')
                if current_ts >= our_ts:
                    merged[agent_id] = current_agent
                else:
                    merged[agent_id] = our_agent
            else:
                merged[agent_id] = current_agent

        # Add agents only we have
        for our_agent in ours:
            if our_agent['id'] not in merged:
                merged[our_agent['id']] = our_agent

        return list(merged.values())

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return all non-deleted agents."""
        return [a for a in self._agents if a.get('status') != 'deleted']

    def list_active_agents(self) -> List[Dict[str, Any]]:
        """Return only active agents."""
        return [a for a in self._agents if a['status'] == 'active']

    def find(self, agent_id: str) -> Dict[str, Any] | None:
        """Find agent by ID."""
        for agent in self._agents:
            if agent['id'] == agent_id:
                return agent
        return None

    def _find_by_window_id(self, window_id: str) -> Dict[str, Any] | None:
        """Find active agent by window_id."""
        if not window_id:
            return None
        for agent in self._agents:
            if agent['status'] == 'active' and agent.get('window_id') == window_id:
                return agent
        return None

    def register(
        self,
        agent_id: str,
        task: str,
        window: str,
        project_dir: str,
        workspace: str,
        window_id: str = None,
        is_interactive: bool = False,
        skill: str = None,
        primary_artifact: str = None,
        backend: str = None,
        session_id: str = None,
        stashed: bool = False,
        feature_id: str = None,
        beads_id: str = None,
        beads_db_path: str = None,
        origin_dir: str = None
    ) -> Dict[str, Any]:
        """
        Register a new agent.

        Core fields:
        - agent_id, window_id: For tmux operations
        - project_dir, workspace: For file operations
        - beads_id: For lifecycle tracking

        Optional metadata preserved for compatibility.
        """
        # Check for duplicate
        existing = self.find(agent_id)
        if existing:
            raise ValueError(f"Agent '{agent_id}' already registered.")

        # Check for window_id reuse
        if window_id:
            existing_window = self._find_by_window_id(window_id)
            if existing_window:
                now = datetime.now().isoformat()
                existing_window['status'] = 'abandoned'
                existing_window['abandoned_at'] = now
                self.save()

        now = datetime.now().isoformat()
        agent = {
            'id': agent_id,
            'task': task,
            'window': window,
            'window_id': window_id,
            'project_dir': str(Path(project_dir).expanduser()),
            'workspace': workspace,
            'spawned_at': now,
            'status': 'active',
            'is_interactive': is_interactive
        }

        # Optional fields
        if skill:
            agent['skill'] = skill
        if primary_artifact:
            agent['primary_artifact'] = primary_artifact
        if backend:
            agent['backend'] = backend
        if session_id:
            agent['session_id'] = session_id
        if stashed:
            agent['stashed'] = True
        if feature_id:
            agent['feature_id'] = feature_id
        if beads_id:
            agent['beads_id'] = beads_id
        if beads_db_path:
            agent['beads_db_path'] = beads_db_path
        if origin_dir:
            agent['origin_dir'] = str(Path(origin_dir).expanduser())

        self._agents.append(agent)
        self.save()

        self._logger.log_event("registry", f"Agent registered: {agent_id}", {
            "agent_id": agent_id,
            "window_id": window_id,
            "beads_id": beads_id
        }, level="INFO")

        return agent

    def remove(self, agent_id: str) -> bool:
        """Mark agent as deleted (tombstone pattern)."""
        for agent in self._agents:
            if agent.get('id') == agent_id:
                now = datetime.now().isoformat()
                agent['status'] = 'deleted'
                agent['deleted_at'] = now
                return True
        return False

    def abandon_agent(self, agent_id: str, reason: str = None) -> bool:
        """Mark agent as abandoned."""
        agent = self.find(agent_id)
        if not agent:
            return False

        now = datetime.now().isoformat()
        agent['status'] = 'abandoned'
        agent['abandoned_at'] = now
        if reason:
            agent['abandon_reason'] = reason

        self._logger.log_event("registry", f"Agent abandoned: {agent_id}", {
            "agent_id": agent_id,
            "reason": reason or "no_reason_provided"
        }, level="INFO")

        return True

    def reconcile(self, active_windows: List[str]):
        """
        Reconcile registry with tmux reality.

        Simplified: window closure = completion.
        Beads tracks the actual completion state.
        """
        active_window_set = set(active_windows)

        completed_count = 0
        for agent in self._agents:
            if agent['status'] == 'active':
                # Skip non-tmux backends
                if agent.get('backend') == 'opencode':
                    continue

                if agent.get('window_id') not in active_window_set:
                    now = datetime.now().isoformat()
                    agent['status'] = 'completed'
                    agent['completed_at'] = now

                    self._logger.log_event("registry",
                        f"Agent completed (window closed): {agent['id']}", {
                        "agent_id": agent['id'],
                        "window_id": agent.get('window_id')
                    }, level="INFO")

                    completed_count += 1

        if completed_count > 0:
            self._logger.log_event("registry",
                f"Reconciliation: {completed_count} completed", {
                "completed_count": completed_count
            }, level="INFO")
            self.save()
