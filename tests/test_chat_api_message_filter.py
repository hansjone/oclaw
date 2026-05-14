from __future__ import annotations

from types import SimpleNamespace

from interfaces.admin.chat_api import _filter_internal_instruction_user_messages


def test_filter_internal_instruction_user_messages_hides_polluted_user_row() -> None:
    polluted_text = "请检查并修复网关启动失败。"
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content=polluted_text),
        SimpleNamespace(
            role="assistant",
            event_type="reasoning",
            content=f"任务分配\nspecialist=ops\ninstruction:\n{polluted_text}",
        ),
        SimpleNamespace(role="assistant", event_type="assistant_text", content="已修复"),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 2
    assert [str(getattr(x, "event_type", "")) for x in out] == ["reasoning", "assistant_text"]


def test_filter_internal_instruction_user_messages_hides_from_assistant_event_payload() -> None:
    polluted_text = "请检查并修复网关启动失败。"
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content=polluted_text),
        SimpleNamespace(
            role="assistant",
            event_type="assistant_text",
            content="已修复",
            event_payload={
                "reasoning_content": f"任务分配\nspecialist=ops\ninstruction:\n{polluted_text}"
            },
        ),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 1
    assert str(getattr(out[0], "event_type", "")) == "assistant_text"


def test_filter_internal_instruction_user_messages_keeps_normal_user_rows() -> None:
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content="你好"),
        SimpleNamespace(role="assistant", event_type="assistant_text", content="你好，有什么我可以帮你？"),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 2
    assert str(getattr(out[0], "content", "")) == "你好"


def test_filter_hides_user_when_en_task_assignment_block() -> None:
    polluted_text = "Fix the gateway."
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content=polluted_text),
        SimpleNamespace(
            role="assistant",
            event_type="reasoning",
            content=f"Task assignment\nspecialist=ops\ninstruction:\n{polluted_text}",
        ),
        SimpleNamespace(role="assistant", event_type="assistant_text", content="done"),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 2
    assert [str(getattr(x, "event_type", "")) for x in out] == ["reasoning", "assistant_text"]


def test_filter_keeps_user_when_reasoning_echoes_instruction_without_dispatch_header() -> None:
    """Thinking traces may contain ``instruction:\\n`` + the user's words without a 任务分配 block."""
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content="几点了"),
        SimpleNamespace(
            role="assistant",
            event_type="assistant_text",
            content="",
            event_payload={"reasoning_content": "用户问几点了。\ninstruction:\n几点了"},
        ),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 2
    assert str(getattr(out[0], "content", "")) == "几点了"
