from __future__ import annotations

from typing import Any

from .agent_scope import (
    resolve_agent_id_by_workspace_path,
    resolve_agent_id_from_session_key,
    resolve_agent_ids_by_workspace_path,
    resolve_agent_workspace_dir,
    resolve_default_agent_id,
    resolve_session_agent_id,
    resolve_session_agent_ids,
)
from .subagent_registry import init_subagent_registry

__all__ = [
    "build_gateway_executor",
    "build_ops_agent",
    "NetworkOpsAgent",
    "resolve_default_agent_id",
    "resolve_agent_workspace_dir",
    "resolve_agent_id_from_session_key",
    "resolve_session_agent_id",
    "resolve_session_agent_ids",
    "resolve_agent_id_by_workspace_path",
    "resolve_agent_ids_by_workspace_path",
    "init_subagent_registry",
]


def __getattr__(name: str) -> Any:
    if name in {"build_gateway_executor", "build_ops_agent"}:
        from .factory import build_gateway_executor, build_ops_agent

        return {"build_gateway_executor": build_gateway_executor, "build_ops_agent": build_ops_agent}[name]
    if name == "NetworkOpsAgent":
        from .network_ops_agent import NetworkOpsAgent

        return NetworkOpsAgent
    raise AttributeError(f"module 'src.agents' has no attribute {name!r}")