from __future__ import annotations

from types import SimpleNamespace

from oclaw.interfaces.admin.chat_api import _filter_internal_instruction_user_messages


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


def test_filter_internal_instruction_user_messages_keeps_normal_user_rows() -> None:
    rows = [
        SimpleNamespace(role="user", event_type="user_text", content="你好"),
        SimpleNamespace(role="assistant", event_type="assistant_text", content="你好，有什么我可以帮你？"),
    ]
    out = _filter_internal_instruction_user_messages(rows)
    assert len(out) == 2
    assert str(getattr(out[0], "content", "")) == "你好"
