import json
import fcntl
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from orch.logging import OrchLogger
from orch.workspace import parse_workspace
from orch.frontmatter import extract_metadata_from_file

class AgentRegistry:
    """
    Manages persistent state for spawned agents with file locking.

    Uses fcntl file locking to prevent race conditions during concurrent operations:
    - Shared locks (LOCK_SH) for reads - allows concurrent reads
    - Exclusive locks (LOCK_EX) for writes - serializes write operations
    - Automatic merge of concurrent changes to prevent data loss

    Note: File locking requires Unix-like systems (Linux, macOS).
    Not compatible with Windows.
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
                    # Acquire shared lock (multiple readers allowed)
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    data = json.load(f)
                    self._agents = data.get('agents', [])
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def save(self, skip_merge: bool = False):
        """Persist registry to disk with exclusive lock and optional merge logic.

        Args:
            skip_merge: If True, write our state directly without merging.
                       Use when removing agents to prevent re-adding them.
        """
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Try to acquire exclusive lock with timeout
        start_time = time.time()
        while True:
            try:
                # Open in r+ mode to read current state, or create if doesn't exist
                mode = 'r+' if self.registry_path.exists() else 'w+'
                with open(self.registry_path, mode) as f:
                    # Try to acquire exclusive lock (non-blocking)
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        # Lock held by another process
                        if time.time() - start_time > self._lock_timeout:
                            raise TimeoutError(
                                f"Could not acquire registry lock after {self._lock_timeout}s"
                            )
                        time.sleep(0.01)  # Wait 10ms before retry
                        continue

                    try:
                        if skip_merge:
                            # Write our state directly (used when removing agents)
                            merged_agents = self._agents
                        else:
                            # Re-read to get latest state (merge concurrent changes)
                            f.seek(0)
                            content = f.read()
                            if content.strip():
                                current_data = json.loads(content)
                                current_agents = current_data.get('agents', [])
                            else:
                                current_agents = []

                            # Merge our changes with current state
                            merged_agents = self._merge_agents(current_agents, self._agents)

                        # Write merged state
                        f.seek(0)
                        f.truncate()
                        json.dump({'agents': merged_agents}, f, indent=2)
                    finally:
                        # Release lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                    break  # Success, exit retry loop

            except FileNotFoundError:
                # File was deleted between exists check and open - retry
                continue

    def _merge_agents(self, current: List[Dict[str, Any]], ours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge concurrent registry changes using timestamp-based conflict resolution.

        Strategy:
        - For agents in both: newer timestamp wins (prevents stale overwrites)
        - For agents only in current: include (added by other process)
        - For agents only in ours: include (added by us)

        This prevents the "re-animation" race condition where completed/deleted
        agents are re-added by stale in-memory copies.

        Args:
            current: Agents currently on disk (from other operations)
            ours: Our in-memory agents (what we want to save)

        Returns:
            Merged list of agents with no duplicates by ID
        """
        merged = {}

        # Index our agents by ID for lookup
        ours_by_id = {a['id']: a for a in ours}

        # Process all current agents from disk
        for current_agent in current:
            agent_id = current_agent['id']
            our_agent = ours_by_id.get(agent_id)

            if our_agent:
                # Agent exists in both - compare timestamps (newer wins)
                current_ts = self._get_agent_timestamp(current_agent)
                our_ts = self._get_agent_timestamp(our_agent)

                if current_ts >= our_ts:
                    # Disk version is newer or equal - prefer disk
                    merged[agent_id] = current_agent
                else:
                    # Our version is newer
                    merged[agent_id] = our_agent
            else:
                # Agent only on disk - keep it (added by another process)
                merged[agent_id] = current_agent

        # Add agents that only we have (new agents we registered)
        for our_agent in ours:
            if our_agent['id'] not in merged:
                merged[our_agent['id']] = our_agent

        return list(merged.values())

    def _get_agent_timestamp(self, agent: Dict[str, Any]) -> datetime:
        """Get the most recent timestamp for an agent (updated_at or spawned_at fallback)."""
        ts_str = agent.get('updated_at') or agent.get('spawned_at')
        if ts_str:
            return datetime.fromisoformat(ts_str)
        # Fallback to epoch for agents without any timestamp
        return datetime.min

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return all non-deleted agents.

        Filters out deleted (tombstone) agents from results.
        Tombstones are preserved internally for merge conflict resolution.
        """
        return [a for a in self._agents if a.get('status') != 'deleted']

    def remove(self, agent_id: str) -> bool:
        """Mark an agent as deleted (tombstone) in the registry.

        Uses tombstone pattern instead of physical deletion to prevent
        re-animation race conditions. Deleted agents are filtered out of
        query results but preserved for merge conflict resolution.

        Returns True if marked as deleted, False if not found.
        Does not persist automatically; caller should invoke save().
        """
        for agent in self._agents:
            if agent.get('id') == agent_id:
                # Tombstone pattern: mark as deleted instead of removing
                now = datetime.now().isoformat()
                agent['status'] = 'deleted'
                agent['deleted_at'] = now
                agent['updated_at'] = now
                return True
        return False

    def abandon_agent(self, agent_id: str, reason: str = None) -> bool:
        """Mark an agent as abandoned in the registry.

        Args:
            agent_id: Agent ID to abandon
            reason: Optional reason for abandonment

        Returns:
            True if agent was found and abandoned, False if not found.
            Does not persist automatically; caller should invoke save().
        """
        agent = self.find(agent_id)
        if not agent:
            return False

        # Mark as abandoned
        now = datetime.now().isoformat()
        agent['status'] = 'abandoned'
        agent['abandoned_at'] = now
        agent['updated_at'] = now  # For timestamp-based merge
        if reason:
            agent['abandon_reason'] = reason

        # Log abandonment
        self._logger.log_event("registry", f"Agent abandoned: {agent_id}", {
            "agent_id": agent_id,
            "reason": reason or "no_reason_provided"
        }, level="INFO")

        return True

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

        Args:
            window_id: Stable tmux window ID (e.g., "@1008") for reliable window tracking
            is_interactive: True for interactive sessions (human-directed), False for autonomous agents
                           NOTE: This is metadata-only. The flag is stored but not currently used
                           for conditional behavior. Interactive sessions now use full workspace tracking
                           like autonomous agents. Flag preserved for potential future filtering/reporting.
            backend: Backend type ('claude', 'codex', 'opencode') - for routing status/send/complete
            session_id: OpenCode session ID (only for opencode backend)
            stashed: True if git changes were stashed before spawn (auto-unstash on complete)
            feature_id: Feature ID from backlog.json for lifecycle tracking
            beads_id: Beads issue ID for lifecycle tracking (auto-close on complete)
            beads_db_path: Absolute path to beads db (for cross-repo spawning)
            origin_dir: Directory where spawn was invoked (for cross-repo workspace sync on complete)

        Raises:
            ValueError: If agent_id already exists in registry
        """
        # Check for duplicate agent_id
        existing = self.find(agent_id)
        if existing:
            raise ValueError(
                f"Agent '{agent_id}' already registered. "
                f"Status: {existing['status']}, Window: {existing['window']}"
            )

        # Check for window_id reuse - mark old agent as abandoned (tmux backends only)
        if window_id:
            existing_window = self._find_by_window_id(window_id)
            if existing_window:
                # Window was closed and reused - mark old agent as abandoned
                abandon_now = datetime.now().isoformat()
                existing_window['status'] = 'abandoned'
                existing_window['abandoned_at'] = abandon_now
                existing_window['updated_at'] = abandon_now  # For timestamp-based merge

                # Log abandoned agent
                self._logger.log_event("registry", f"Agent abandoned (window reused): {existing_window['id']}", {
                    "agent_id": existing_window['id'],
                    "window_id": window_id,
                    "reason": "window_reused",
                    "new_agent_id": agent_id
                }, level="INFO")

                # Save immediately to persist status change
                self.save()

        # Agent structure explanation:
        # - window: Human-readable target like "orchestrator:2" (UNSTABLE - changes when tmux renumbers)
        # - window_id: Stable tmux identifier like "@1008" (STABLE - never changes for window lifetime)
        # - backend: Backend type for routing (default: None = tmux-based claude)
        # - session_id: OpenCode session ID (for opencode backend only)
        #
        # IMPORTANT: Always prefer window_id over window for tmux targeting operations.
        # Tmux automatically renumbers windows when gaps appear (if renumber-windows is on),
        # making window indices unreliable. Use: agent.get('window_id', agent['window'])
        now = datetime.now().isoformat()
        agent = {
            'id': agent_id,
            'task': task,
            'window': window,  # UNSTABLE index (e.g., "orchestrator:2") - DO NOT use for targeting
            'window_id': window_id,  # STABLE ID (e.g., "@1008") - ALWAYS prefer for targeting
            'project_dir': str(Path(project_dir).expanduser()),  # Expand ~ in paths
            'workspace': workspace,
            'spawned_at': now,
            'updated_at': now,  # For timestamp-based merge conflict resolution
            'status': 'active',
            'is_interactive': is_interactive
        }
        # Store skill metadata when available (used for deliverables and investigation agents)
        if skill:
            agent['skill'] = skill
        # Optional primary artifact (e.g., investigation file path) for non-workspace agents
        if primary_artifact:
            agent['primary_artifact'] = primary_artifact
        # Backend metadata for routing (opencode, codex, etc.)
        if backend:
            agent['backend'] = backend
        # OpenCode session ID for API-based operations
        if session_id:
            agent['session_id'] = session_id
        # Track stashed git changes for auto-unstash on complete
        if stashed:
            agent['stashed'] = True
        # Track feature ID for backlog.json lifecycle
        if feature_id:
            agent['feature_id'] = feature_id
        # Track beads issue ID for auto-close on complete
        if beads_id:
            agent['beads_id'] = beads_id
        # Track beads db path for cross-repo spawning
        if beads_db_path:
            agent['beads_db_path'] = beads_db_path
        # Track origin directory for cross-repo workspace sync on complete
        if origin_dir:
            agent['origin_dir'] = str(Path(origin_dir).expanduser())
        self._agents.append(agent)
        self.save()

        # Log new agent registration
        log_data = {
            "agent_id": agent_id,
            "project_dir": project_dir,
            "is_interactive": is_interactive
        }
        if backend == "opencode":
            log_data["backend"] = backend
            log_data["session_id"] = session_id
            self._logger.log_event("registry", f"Agent registered (OpenCode): {agent_id}", log_data, level="INFO")
        else:
            log_data["window"] = window
            log_data["window_id"] = window_id
            self._logger.log_event("registry", f"Agent registered: {agent_id}", log_data, level="INFO")

        return agent

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

    def reconcile(self, active_windows: List[str]):
        """
        Reconcile registry with tmux reality.

        Args:
            active_windows: List of stable window IDs that exist in tmux
                           (e.g., ['@39', '@40'])
                           TODO: Consider renaming to active_window_ids for API consistency
        """
        # Convert to set for O(1) membership checks
        active_window_set = set(active_windows)

        completed_count = 0
        terminated_count = 0
        for agent in self._agents:
            if agent['status'] == 'active':
                # Skip opencode agents - they don't use tmux windows
                # Their lifecycle is managed via OpenCode API, not tmux reconciliation
                if agent.get('backend') == 'opencode':
                    continue

                # Use stable window_id instead of window target (which changes when tmux renumbers)
                # Fall back to None for old registry entries without window_id
                if agent.get('window_id') not in active_window_set:
                    # Window closed - check coordination artifact to determine if work was completed
                    # Check primary_artifact first (for investigation agents), then workspace
                    workspace_rel = agent.get('workspace')
                    primary_artifact = agent.get('primary_artifact')
                    phase = None

                    project_dir = Path(agent.get('project_dir', '.'))

                    # First: Check primary_artifact for completion (investigation agents)
                    # primary_artifact takes precedence because it's the coordination artifact
                    # for workspace-less investigation agents
                    primary_artifact_checked = False
                    if primary_artifact:
                        primary_path = Path(primary_artifact).expanduser()
                        if not primary_path.is_absolute():
                            primary_path = (project_dir / primary_path).resolve()

                        if primary_path.exists():
                            # Extract Status from investigation file
                            # Investigation files use **Status:** not **Phase:**
                            metadata = extract_metadata_from_file(primary_path)
                            # Check both status and phase (investigations use status, workspaces use phase)
                            artifact_status = metadata.status or metadata.phase
                            if artifact_status and artifact_status.lower() == 'complete':
                                phase = 'Complete'  # Normalize for completion check
                            elif artifact_status:
                                phase = artifact_status  # Keep original for logging
                            primary_artifact_checked = True

                    # Second: Fall back to workspace check if no primary_artifact or not checked
                    workspace_exists = False
                    workspace_path = None

                    if not primary_artifact_checked and workspace_rel:
                        workspace_path = project_dir / workspace_rel
                        if workspace_path.is_dir():
                            workspace_exists = (workspace_path / "WORKSPACE.md").exists()
                        else:
                            workspace_exists = workspace_path.exists()

                        if workspace_exists:
                            # Parse workspace to get Phase
                            signal = parse_workspace(workspace_path)
                            phase = signal.phase

                    # Determine if any coordination artifact exists
                    coordination_artifact_exists = primary_artifact_checked or workspace_exists

                    # Backward-compatible behavior:
                    # - If coordination artifact exists, only mark as 'completed' if Phase/Status is 'Complete'.
                    # - If no coordination artifact on disk (no directory/file), treat as 'completed' (legacy agents).

                    if coordination_artifact_exists and phase and phase.lower() == 'complete':
                        now = datetime.now().isoformat()
                        agent['status'] = 'completed'
                        agent['completed_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge

                        # Log state transition to completed
                        artifact_type = "primary_artifact" if primary_artifact_checked else "workspace"
                        self._logger.log_event("registry", f"Agent completed (window closed, {artifact_type} Phase: Complete): {agent['id']}", {
                            "agent_id": agent['id'],
                            "window": agent['window'],
                            "window_id": agent.get('window_id'),
                            "phase": phase,
                            "artifact_type": artifact_type,
                            "reason": "window_closed_phase_complete"
                        }, level="INFO")

                        completed_count += 1
                    elif not coordination_artifact_exists:
                        # No coordination artifact on disk – treat as completed (legacy agents)
                        now = datetime.now().isoformat()
                        agent['status'] = 'completed'
                        agent['completed_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge

                        self._logger.log_event("registry", f"Agent completed (window closed, no coordination artifact): {agent['id']}", {
                            "agent_id": agent['id'],
                            "window": agent['window'],
                            "window_id": agent.get('window_id'),
                            "phase": phase or 'unknown',
                            "reason": "window_closed_no_artifact"
                        }, level="INFO")

                        completed_count += 1
                    else:
                        # Window closed but Phase/Status is not Complete - mark as terminated
                        now = datetime.now().isoformat()
                        agent['status'] = 'terminated'
                        agent['terminated_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge

                        # Log state transition to terminated
                        artifact_type = "primary_artifact" if primary_artifact_checked else "workspace"
                        self._logger.log_event("registry", f"Agent terminated (window closed, {artifact_type} Phase: {phase or 'unknown'}): {agent['id']}", {
                            "agent_id": agent['id'],
                            "window": agent['window'],
                            "window_id": agent.get('window_id'),
                            "phase": phase or 'unknown',
                            "artifact_type": artifact_type,
                            "reason": "window_closed_phase_incomplete"
                        }, level="INFO")

                        terminated_count += 1

        # Log reconciliation summary if any changes
        if completed_count > 0 or terminated_count > 0:
            self._logger.log_event("registry", f"Reconciliation: {completed_count} completed, {terminated_count} terminated", {
                "completed_count": completed_count,
                "terminated_count": terminated_count,
                "active_windows_count": len(active_windows)
            }, level="INFO")

        self.save()

    def reconcile_opencode(self) -> None:
        """
        Reconcile opencode agents with OpenCode server.

        Checks if opencode sessions still exist and updates agent status accordingly.
        Should be called after standard tmux reconcile for opencode-aware status.
        """
        # Get active opencode agents
        opencode_agents = [
            a for a in self._agents
            if a['status'] == 'active' and a.get('backend') == 'opencode'
        ]

        if not opencode_agents:
            return

        try:
            from orch.backends.opencode import OpenCodeClient, discover_server

            # Discover server
            server_url = discover_server()
            if not server_url:
                # Server not running - can't verify sessions
                self._logger.log_event("registry", "OpenCode server not found during reconciliation", {
                    "opencode_agents": len(opencode_agents)
                }, level="WARNING")
                return

            # Check each opencode agent
            # Note: Sessions are scoped by project directory, so we check each agent
            # with a client scoped to its project
            completed_count = 0
            terminated_count = 0

            for agent in opencode_agents:
                session_id = agent.get('session_id')
                if not session_id:
                    continue

                # Create client scoped to this agent's project directory
                project_dir = agent.get('project_dir', '.')
                client = OpenCodeClient(server_url, directory=project_dir)

                # Check if session exists
                try:
                    session = client.get_session(session_id)
                    session_exists = session is not None
                except Exception:
                    session_exists = False

                if not session_exists:
                    # Session no longer exists - check workspace phase
                    workspace_rel = agent.get('workspace')
                    phase = None

                    project_dir_path = Path(project_dir)
                    workspace_path = project_dir_path / workspace_rel if workspace_rel else None
                    workspace_exists = False

                    if workspace_path:
                        if workspace_path.is_dir():
                            workspace_exists = (workspace_path / "WORKSPACE.md").exists()

                    if workspace_exists:
                        signal = parse_workspace(workspace_path)
                        phase = signal.phase

                    if workspace_exists and phase and phase.lower() == 'complete':
                        now = datetime.now().isoformat()
                        agent['status'] = 'completed'
                        agent['completed_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge
                        completed_count += 1
                    elif not workspace_exists:
                        now = datetime.now().isoformat()
                        agent['status'] = 'completed'
                        agent['completed_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge
                        completed_count += 1
                    else:
                        now = datetime.now().isoformat()
                        agent['status'] = 'terminated'
                        agent['terminated_at'] = now
                        agent['updated_at'] = now  # For timestamp-based merge
                        terminated_count += 1

            if completed_count > 0 or terminated_count > 0:
                self._logger.log_event("registry",
                    f"OpenCode reconciliation: {completed_count} completed, {terminated_count} terminated",
                    {"completed": completed_count, "terminated": terminated_count},
                    level="INFO")
                self.save()

        except ImportError:
            # OpenCode backend not available
            pass

    def list_active_agents(self) -> List[Dict[str, Any]]:
        """Return only active agents."""
        return [a for a in self._agents if a['status'] == 'active']

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get completed agents with duration calculations.

        Returns:
            List of completed agents with 'duration_minutes' field added.
        """
        history = []
        for agent in self._agents:
            if agent['status'] == 'completed' and 'completed_at' in agent:
                # Calculate duration
                spawned = datetime.fromisoformat(agent['spawned_at'])
                completed = datetime.fromisoformat(agent['completed_at'])
                duration = (completed - spawned).total_seconds() / 60

                # Create history entry with duration
                entry = agent.copy()
                entry['duration_minutes'] = int(duration)
                history.append(entry)

        return history

    def get_analytics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get analytics grouped by task type.

        Returns:
            Dictionary mapping task type to analytics:
            {
                'implement': {'count': 2, 'avg_duration_minutes': 40},
                'debug': {'count': 1, 'avg_duration_minutes': 20}
            }
        """
        # Get history with durations
        history = self.get_history()

        # Group by task type
        groups = {}
        for agent in history:
            # Extract task type from task description (first word lowercased)
            task_type = agent['task'].split()[0].lower()

            if task_type not in groups:
                groups[task_type] = {'durations': [], 'count': 0}

            groups[task_type]['durations'].append(agent['duration_minutes'])
            groups[task_type]['count'] += 1

        # Calculate averages
        analytics = {}
        for task_type, data in groups.items():
            avg_duration = sum(data['durations']) // len(data['durations'])
            analytics[task_type] = {
                'count': data['count'],
                'avg_duration_minutes': avg_duration
            }

        return analytics
