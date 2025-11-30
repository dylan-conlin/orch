import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from orch.monitor import check_agent_status, Scenario
from orch.registry import AgentRegistry
from orch.session import format_relative_time


@dataclass
class InboxItem:
    """Represents a single inbox item to surface to orchestrators."""
    id: str
    type: str  # blocked|question|ready|review|pattern|feedback
    severity: str  # critical|warning|info
    title: str
    workspace: str
    project: str
    age: Optional[str] = None
    recommendation: Optional[str] = None
    actions: Optional[List[str]] = None
    source: Optional[str] = None
    stale: bool = False
    raw: Optional[Dict[str, Any]] = None  # Optional payload for consumers


def _hash_item(item: InboxItem) -> str:
    """Create a stable hash of the item for ack change detection."""
    payload = f"{item.id}|{item.type}|{item.severity}|{item.title}|{item.recommendation}|{item.project}|{item.workspace}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class InboxState:
    """Persist acknowledgements/snoozes for inbox items."""

    def __init__(self, state_path: Path = None):
        if state_path is None:
            state_path = Path.home() / ".orch" / "inbox-state.json"
        self.state_path = Path(state_path)
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2))

    def is_acknowledged(self, item: InboxItem) -> bool:
        entry = self._state.get(item.id)
        if not entry:
            return False

        # Snooze expiry check
        snooze_until = entry.get("snooze_until")
        if snooze_until:
            try:
                if datetime.fromisoformat(snooze_until) < datetime.now():
                    return False
            except ValueError:
                return False

        # If hash changed, re-surface
        current_hash = _hash_item(item)
        return entry.get("hash") == current_hash

    def ack(self, item: InboxItem, snooze_minutes: int = 0):
        entry = {
            "hash": _hash_item(item),
            "acknowledged_at": datetime.now().isoformat()
        }
        if snooze_minutes > 0:
            entry["snooze_until"] = (datetime.now() + timedelta(minutes=snooze_minutes)).isoformat()
        self._state[item.id] = entry
        self.save()


def _format_age(timestamp: Optional[str]) -> Optional[str]:
    if not timestamp:
        return None
    try:
        return format_relative_time(datetime.fromisoformat(timestamp))
    except (ValueError, TypeError):
        return None


def _item_actions(agent_id: str, workspace: str, project: str, extra: Optional[List[str]] = None) -> List[str]:
    actions = [
        f"orch check {agent_id}",
        f"orch tail {agent_id}",
        f"open {Path(project) / workspace / 'WORKSPACE.md'}"
    ]
    if extra:
        actions.extend(extra)
    return actions


def _add_blocked_items(items: List[InboxItem], agent_info: Dict[str, Any], status_obj):
    for alert in status_obj.alerts:
        if alert.get("type") in ["blocked", "question"]:
            items.append(
                InboxItem(
                    id=f"{alert.get('type', 'blocked')}:{agent_info['id']}",
                    type=alert.get("type", "blocked"),
                    severity="critical",
                    title=alert.get("message", "Agent needs attention"),
                    workspace=agent_info.get("workspace", ""),
                    project=str(agent_info.get("project_dir", "")),
                    age=_format_age(agent_info.get("spawned_at")),
                    recommendation="Investigate and unblock" if alert.get("type") == "blocked" else "Respond to question",
                    actions=_item_actions(agent_info["id"], agent_info.get("workspace", ""), str(agent_info.get("project_dir", ""))),
                    raw={"alert": alert, "phase": status_obj.phase}
                )
            )


def _add_ready_items(items: List[InboxItem], agent_info: Dict[str, Any], status_obj):
    if status_obj.scenario in [Scenario.READY_COMPLETE, Scenario.READY_CLEAN]:
        items.append(
            InboxItem(
                id=f"ready:{agent_info['id']}",
                type="ready",
                severity="info",
                title=status_obj.recommendation or "Ready to complete",
                workspace=agent_info.get("workspace", ""),
                project=str(agent_info.get("project_dir", "")),
                age=_format_age(agent_info.get("completed_at") or agent_info.get("spawned_at")),
                recommendation="Run `orch complete`" if status_obj.scenario == Scenario.READY_COMPLETE else "Run `orch clean`",
                actions=_item_actions(agent_info["id"], agent_info.get("workspace", ""), str(agent_info.get("project_dir", "")), extra=["orch complete --dry-run {id}".format(id=agent_info["id"])]),
                stale=getattr(status_obj, "is_stale", False),
                raw={"scenario": status_obj.scenario.value, "recommendation": status_obj.recommendation}
            )
        )


def _add_action_needed_items(items: List[InboxItem], agent_info: Dict[str, Any], status_obj):
    if status_obj.scenario == Scenario.ACTION_NEEDED:
        items.append(
            InboxItem(
                id=f"review:{agent_info['id']}",
                type="review",
                severity="warning",
                title=status_obj.recommendation or "Action needed before completion",
                workspace=agent_info.get("workspace", ""),
                project=str(agent_info.get("project_dir", "")),
                age=_format_age(agent_info.get("completed_at") or agent_info.get("spawned_at")),
                recommendation="Address pending next-actions or validation items",
                actions=_item_actions(agent_info["id"], agent_info.get("workspace", ""), str(agent_info.get("project_dir", ""))),
                raw={"scenario": status_obj.scenario.value, "recommendation": status_obj.recommendation}
            )
        )


def _add_pattern_items(items: List[InboxItem], agent_info: Dict[str, Any], status_obj):
    for violation in status_obj.violations:
        # Only surface warning/critical
        if violation.severity not in ["critical", "warning"]:
            continue
        items.append(
            InboxItem(
                id=f"pattern:{violation.type}:{agent_info['id']}",
                type="pattern",
                severity=violation.severity,
                title=violation.message,
                workspace=agent_info.get("workspace", ""),
                project=str(agent_info.get("project_dir", "")),
                age=_format_age(agent_info.get("spawned_at")),
                recommendation="Resolve pattern violation",
                actions=_item_actions(agent_info["id"], agent_info.get("workspace", ""), str(agent_info.get("project_dir", ""))),
                raw={"pattern": violation.type, "severity": violation.severity}
            )
        )


def generate_inbox_items(
    registry: Optional[AgentRegistry] = None,
    project_filter: Optional[str] = None,
) -> List[InboxItem]:
    """Generate inbox items from current registry + workspace signals."""
    if registry is None:
        registry = AgentRegistry()

    agents = registry.list_agents()
    if project_filter:
        project_filter_lower = project_filter.lower()
        agents = [
            a for a in agents
            if project_filter_lower in str(a.get("project_dir", "")).lower()
               or project_filter_lower in Path(a.get("project_dir", "")).name.lower()
        ]

    items: List[InboxItem] = []
    for agent in agents:
        status_obj = check_agent_status(agent)
        _add_blocked_items(items, agent, status_obj)
        _add_ready_items(items, agent, status_obj)
        _add_action_needed_items(items, agent, status_obj)
        _add_pattern_items(items, agent, status_obj)
        # Feedback alerts will be added when feedback command is available

    return items


def filter_acknowledged(items: List[InboxItem], state: InboxState) -> List[InboxItem]:
    """Filter out items that are acknowledged/snoozed with unchanged content."""
    return [item for item in items if not state.is_acknowledged(item)]


def serialize_items(items: List[InboxItem]) -> List[Dict[str, Any]]:
    """Convert inbox items to JSON-serializable structures."""
    return [
        {
            "id": item.id,
            "type": item.type,
            "severity": item.severity,
            "title": item.title,
            "workspace": item.workspace,
            "project": item.project,
            "age": item.age,
            "recommendation": item.recommendation,
            "actions": item.actions,
            "source": item.source,
            "stale": item.stale,
            "raw": item.raw,
        }
        for item in items
    ]


def group_items(items: List[InboxItem]) -> Dict[str, List[InboxItem]]:
    grouped: Dict[str, List[InboxItem]] = {
        "blocked": [],
        "question": [],
        "ready": [],
        "review": [],
        "pattern": [],
        "feedback": []
    }
    for item in items:
        if item.type in grouped:
            grouped[item.type].append(item)
        else:
            grouped.setdefault(item.type, []).append(item)
    return grouped


def render_human(grouped: Dict[str, List[InboxItem]]) -> str:
    sections_order = ["blocked", "question", "ready", "review", "pattern", "feedback"]
    lines: List[str] = []
    for section in sections_order:
        if grouped.get(section):
            header = section.capitalize()
            lines.append(f"{header} ({len(grouped[section])})")
            for item in grouped[section]:
                badge = {
                    "critical": "🔴",
                    "warning": "🟡",
                    "info": "⚪"
                }.get(item.severity, "⚪")
                age_str = f" • {item.age}" if item.age else ""
                stale_str = " • ⏰ stale" if item.stale else ""
                lines.append(f"  {badge} {item.title}{age_str}{stale_str}")
                lines.append(f"    workspace: {item.workspace}")
                if item.recommendation:
                    lines.append(f"    → {item.recommendation}")
            lines.append("")  # blank line between sections
    if not lines:
        return "Inbox clear ✅"
    return "\n".join(lines).strip()
