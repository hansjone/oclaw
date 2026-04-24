from __future__ import annotations

from oclaw.gateway.server_methods.agent import agent_handlers
from oclaw.gateway.server_methods.chat import chat_handlers
from oclaw.gateway.server_methods.commands import commands_handlers
from oclaw.gateway.server_methods.connect import connect_handlers
from oclaw.gateway.server_methods.sessions import sessions_handlers
from oclaw.gateway.server_methods.skills import skills_handlers
from oclaw.gateway.server_methods.shared_types import GatewayRequestHandlers


def build_gateway_method_handlers() -> GatewayRequestHandlers:
    """Build a flat method->handler map for gateway dispatch."""
    merged: GatewayRequestHandlers = {}
    for group in (
        connect_handlers,
        commands_handlers,
        chat_handlers,
        sessions_handlers,
        skills_handlers,
        agent_handlers,
    ):
        for method, handler in (group or {}).items():
            merged[str(method)] = handler
    # Backward-compatible alias.
    if "agent" in merged and "agent.run" not in merged:
        merged["agent.run"] = merged["agent"]
    return merged


def method_names() -> list[str]:
    return sorted(build_gateway_method_handlers().keys())


__all__ = ["build_gateway_method_handlers", "method_names"]

