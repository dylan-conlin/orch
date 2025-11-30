"""Agent grouping logic for dashboard."""
from collections import defaultdict
from typing import Dict, List, Any


def group_agents(agents: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Group agents by project hierarchy.

    Args:
        agents: List of agent dicts with working_dir, etc.

    Returns:
        Nested dict: {top_level: {project: [agents]}}
        Example: {'work/SendCutSend': {'scs-special-projects/pdf-generator': [...]}}
    """
    groups = defaultdict(lambda: defaultdict(list))

    for agent in agents:
        path = agent['working_dir']

        # Extract project segments
        if '/Documents/work/' in path:
            segments = path.split('/Documents/work/')[1].split('/')
            top_level = 'work/' + segments[0]
            project = '/'.join(segments[1:]) if len(segments) > 1 else 'root'
        elif '/Documents/personal/' in path:
            segments = path.split('/Documents/personal/')[1].split('/')
            top_level = 'personal'
            project = segments[0]
        else:
            top_level = 'uncategorized'
            project = 'other'

        groups[top_level][project].append(agent)

    # Sort agents within each project by last_updated (most recent first)
    for top_level in groups:
        for project in groups[top_level]:
            groups[top_level][project].sort(
                key=lambda a: a.get('last_updated', ''),
                reverse=True
            )

    return dict(groups)
