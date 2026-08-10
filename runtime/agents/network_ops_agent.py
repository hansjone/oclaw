from __future__ import annotations

"""Ops specialist helpers.

Prefer ``build_gateway_executor(specialist=\"ops\")``. This module keeps the
legacy ``NetworkOpsAgent`` name as a thin ``Agent`` factory for older imports.
"""

from typing import Any

from runtime.agent_context import build_role_system_context
from runtime.chat.agent import Agent
from svc.persistence.sqlite_store import SqliteStore
from runtime.tools import default_registry

# Ops 专家走与 specialists 相同的工作区框架：runtime/workspaces/ops/{SOUL,ROLE_SYSTEM}.md
NETWORK_SYSTEM_PROMPT_ZH = build_role_system_context("ops")


class NetworkOpsAgent(Agent):
    """Compatibility alias: ops specialist with network_ops(+memory) tool catalog.

    New code should use ``runtime.agents.factory.build_gateway_executor(specialist=\"ops\")``.
    """

    def __init__(
        self,
        *,
        store: SqliteStore,
        model: Any,
        lang: str = "zh",
        llm_profile_mode: str | None = None,
        system_prompt: str | None = None,
        policy_session_id: str | None = None,
        path_policy_tenant_id: str | None = None,
        path_policy_user_id: str | None = None,
    ) -> None:
        tools = default_registry(
            expert="network_ops+memory",
            specialist="ops",
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            store=store,
        )
        super().__init__(
            store=store,
            tools=tools,
            model=model,
            system_prompt=(system_prompt or NETWORK_SYSTEM_PROMPT_ZH),
            lang=lang,
            llm_profile_mode=llm_profile_mode,
        )


__all__ = ["NetworkOpsAgent", "NETWORK_SYSTEM_PROMPT_ZH"]
