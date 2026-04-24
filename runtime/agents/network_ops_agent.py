from __future__ import annotations

from typing import Any

from oclaw.runtime.chat.agent import Agent
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.prompts.loader import render_runtime_prompt
from oclaw.runtime.tools import default_registry

NETWORK_SYSTEM_PROMPT_ZH = render_runtime_prompt("roles/specialists/ops/system.md", strict=True)


class NetworkOpsAgent(Agent):
    """网络运维专家 Agent：固定专家提示词与专家工具目录。"""

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
            expert="network_ops",
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            store=store,
        )
        super().__init__(
            store=store,
            tools=tools,
            model=model,
            system_prompt=(system_prompt or render_runtime_prompt("roles/specialists/ops/system.md", strict=True)),
            lang=lang,
            llm_profile_mode=llm_profile_mode,
        )


__all__ = ["NetworkOpsAgent", "NETWORK_SYSTEM_PROMPT_ZH"]
