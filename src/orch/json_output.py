"""
JSON output formatting for orch commands.

Provides utilities for serializing orch dataclasses to JSON with schema versioning.
"""

import json
from typing import Dict, Any, Optional
from dataclasses import asdict
from orch.monitor import AgentStatus
from orch.context import ContextInfo
from orch.git_utils import CommitInfo


# Schema version for JSON output (follows semantic versioning)
SCHEMA_VERSION = "1.0.0"


def serialize_agent_status(status: AgentStatus) -> Dict[str, Any]:
    """
    Serialize AgentStatus to JSON-compatible dictionary.

    Args:
        status: AgentStatus instance to serialize

    Returns:
        Dictionary with all AgentStatus fields serialized
    """
    result = {
        "agent_id": status.agent_id,
        "needs_attention": status.needs_attention,
        "priority": status.priority,
        "alerts": status.alerts,
        "phase": status.phase,
        "violations": [
            {
                "severity": v.severity,
                "message": v.message
            } for v in status.violations
        ] if status.violations else [],
        "commits_since_spawn": status.commits_since_spawn
    }

    # Include context_info if present
    if status.context_info:
        result["context_info"] = serialize_context_info(status.context_info)

    # Include last_commit if present
    if status.last_commit:
        result["last_commit"] = serialize_commit_info(status.last_commit)

    return result


def serialize_context_info(context: ContextInfo) -> Dict[str, Any]:
    """
    Serialize ContextInfo to JSON-compatible dictionary.

    Args:
        context: ContextInfo instance to serialize

    Returns:
        Dictionary with token usage information
    """
    return {
        "tokens_used": context.tokens_used,
        "tokens_total": context.tokens_total,
        "percentage": context.percentage
    }


def serialize_commit_info(commit: CommitInfo) -> Dict[str, Any]:
    """
    Serialize CommitInfo to JSON-compatible dictionary.

    Args:
        commit: CommitInfo instance to serialize

    Returns:
        Dictionary with commit information, timestamp as ISO format string
    """
    return {
        "hash": commit.hash,
        "short_hash": commit.short_hash,
        "message": commit.message,
        "short_message": commit.short_message,
        "author": commit.author,
        "timestamp": commit.timestamp.isoformat()
    }


def output_json(data: Dict[str, Any], pretty: bool = False) -> str:
    """
    Format data as JSON string with schema version.

    Automatically includes schema_version field in output.

    Args:
        data: Dictionary to serialize
        pretty: If True, format with indentation for readability

    Returns:
        JSON string with schema_version included
    """
    # Add schema version to output
    output = {"schema_version": SCHEMA_VERSION, **data}

    if pretty:
        return json.dumps(output, indent=2)
    else:
        return json.dumps(output)
