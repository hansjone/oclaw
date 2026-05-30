from __future__ import annotations

from svc.llm.chat_models import LLMResponse
from runtime.router import decide_route
from runtime.types import StandardMessage, normalize_interaction_mode, normalize_requested_specialist


def _msg(text: str, attachments: list[dict] | None = None) -> StandardMessage:
    return StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text=text,
        attachments=attachments or [],
        metadata={},
    )


def test_router_async_for_multi_step_send_flow() -> None:
    d = decide_route(_msg("帮我总结并发送到项目群"))
    assert d.mode == "async_task"
    assert d.reason == "multi_step_send_flow"


def test_router_sync_for_short_default_message() -> None:
    d = decide_route(_msg("你好，今天怎么样"))
    assert d.mode == "sync_direct"
    assert d.reason == "default_sync"


class _RouterJsonModel:
    def __init__(self, content: str) -> None:
        self._content = content

    def chat(self, messages, tools, *, on_token=None):
        return LLMResponse(content=self._content, tool_calls=[])


def test_router_llm_json_mode_uses_model() -> None:
    class Store:
        def get_setting(self, key: str) -> str:
            if key == "AIA_OCLAW_ROUTER_MODE":
                return "llm_json"
            return ""

    d = decide_route(
        _msg("short"),
        store=Store(),
        model=_RouterJsonModel('{"mode":"async_task","reason":"user asked for batch"}'),
    )
    assert d.mode == "async_task"
    assert "batch" in d.reason


def test_router_llm_json_invalid_json_falls_back_to_rule() -> None:
    class Store:
        def get_setting(self, key: str) -> str:
            if key == "AIA_OCLAW_ROUTER_MODE":
                return "llm_json"
            return ""

    d = decide_route(_msg("你好，今天怎么样"), store=Store(), model=_RouterJsonModel("not json"))
    assert d.mode == "sync_direct"
    assert d.reason == "default_sync"


def test_router_llm_json_tolerates_extra_dynamic_agent_fields() -> None:
    class Store:
        def get_setting(self, key: str) -> str:
            if key == "AIA_OCLAW_ROUTER_MODE":
                return "llm_json"
            return ""

    d = decide_route(
        _msg("plan this"),
        store=Store(),
        model=_RouterJsonModel('{"mode":"sync_direct","reason":"ok","dynamic_agent":{"name":"x"}}'),
    )
    assert d.mode == "sync_direct"
    assert d.reason == "ok"


def test_router_skill_signal_from_metadata() -> None:
    msg = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="你好",
        attachments=[],
        metadata={"skills_total": 4},
    )
    d = decide_route(msg)
    assert d.skill_signal == "skills=4"


def test_interaction_mode_normalization_supports_legacy_values() -> None:
    assert normalize_interaction_mode("comprehensive") == "comprehensive"
    assert normalize_interaction_mode("expert") == "expert"
    assert normalize_interaction_mode("specialist") == "expert"
    assert normalize_interaction_mode("composite") == "comprehensive"


def test_requested_specialist_normalization_defaults_to_generalist() -> None:
    assert normalize_requested_specialist("ops") == "ops"
    # "stock" is a dynamic specialist discovered from runtime workspaces.
    assert normalize_requested_specialist("stock") == "stock"
    assert normalize_requested_specialist("image") == "image"
    # Unknown ids fall back to generalist.
    assert normalize_requested_specialist("memory") == "memory"
    assert normalize_requested_specialist("unknown") == "generalist"


def test_router_video_expert_sync_despite_long_attachments() -> None:
    long_text = "x" * 150
    msg = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text=long_text,
        attachments=[{"type": "image_ref", "attachment_id": "a" * 64}],
        metadata={"interaction_mode": "expert", "selected_specialist": "video"},
    )
    d = decide_route(msg)
    assert d.mode == "sync_direct"
    assert d.reason == "video_expert_legacy_lane"
    assert d.requested_specialist == "video"


def test_router_carries_interaction_mode_and_requested_specialist() -> None:
    msg = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="你好",
        attachments=[],
        metadata={"interaction_mode": "expert", "selected_specialist": "ops"},
    )
    d = decide_route(msg)
    assert d.interaction_mode == "expert"
    assert d.requested_specialist == "ops"

