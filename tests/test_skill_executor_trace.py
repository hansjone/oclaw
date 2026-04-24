from __future__ import annotations

from types import SimpleNamespace

from oclaw.runtime.skill_executor import SkillExecutionContext, SkillExecutor
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


class _DummyStore:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.logs: list[dict] = []
        self.messages: list[dict] = []

    def add_trace_event(self, **kwargs):  # noqa: ANN003
        self.events.append(dict(kwargs))

    def add_tool_log(self, **kwargs):  # noqa: ANN003
        self.logs.append(dict(kwargs))

    def add_message(self, **kwargs):  # noqa: ANN003
        self.messages.append(dict(kwargs))
        return SimpleNamespace(id=len(self.messages))


def test_skill_executor_emits_skill_trace_events() -> None:
    store = _DummyStore()
    reg = ToolRegistry(
        [
            ToolSpec(
                name="echo_skill",
                description="echo",
                parameters={"type": "object", "properties": {"x": {"type": "string"}}},
                handler=lambda a: {"ok": True, "x": a.get("x")},
                read_only=True,
            )
        ]
    )
    ex = SkillExecutor()
    uses = [SimpleNamespace(id="call_1", name="echo_skill", arguments={"x": "1"})]
    ex.execute_skill_uses(
        ctx=SkillExecutionContext(store=store, tools=reg, session_id="s1", trace_id="t1"),
        assistant_msg_id=1,
        skill_uses=uses,
    )
    et = [str((e.get("event_type") or "")) for e in store.events]
    assert "skill_selected" in et
    assert "skill_executed" in et

