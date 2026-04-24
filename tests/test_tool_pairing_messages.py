from __future__ import annotations

import json

from oclaw.runtime.chat.agent_messages import build_llm_messages
from oclaw.platform.llm.chat_models import RuleBasedChatModel


class _Msg:
    def __init__(
        self,
        role: str,
        content: str = "",
        tool_calls: str | None = None,
        *,
        event_type: str | None = None,
        turn_uuid: str | None = None,
    ):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.attachments = None
        self.event_type = event_type
        self.turn_uuid = turn_uuid


def test_build_llm_messages_unpaired_tool_rows_downgrade_to_assistant_text() -> None:
    model = RuleBasedChatModel()
    rows = [
        _Msg("user", "hi"),
        _Msg(
            "assistant",
            "ok",
            tool_calls=json.dumps(
                [
                    {
                        "id": "call_1",
                        "name": "t",
                        "arguments": {},
                    }
                ],
                ensure_ascii=False,
            ),
        ),
        _Msg(
            "tool",
            '{"ok":false,"error":"x"}',
            tool_calls=json.dumps({"tool_call_id": "missing_call_id", "name": "t"}, ensure_ascii=False),
        ),
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    assert not any(m.get("role") == "tool" for m in msgs), msgs
    assistant_texts = [str(m.get("content") or "") for m in msgs if m.get("role") == "assistant"]
    assert any("[tool_use_result" in t for t in assistant_texts)


def test_build_llm_messages_user_relay_pointer_as_text_meta() -> None:
    model = RuleBasedChatModel()
    u = _Msg("user", "see shared file")
    u.attachments = [
        {
            "type": "relay_pointer",
            "pointer_uri": "relay://attachments/scope_1/abcdef123456",
            "rel_path": "attachments/a.txt",
            "mime": "text/plain",
            "bytes": 12,
            "sha256": "f" * 64,
        }
    ]
    msgs = build_llm_messages(store_messages=[u], system_prompt="s", model=model, lang="zh")
    user_rows = [m for m in msgs if m.get("role") == "user"]
    assert user_rows
    c = user_rows[0].get("content")
    assert isinstance(c, list)
    joined = "\n".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
    assert "relay://attachments/scope_1/abcdef123456" in joined


def test_build_llm_messages_skips_reasoning_event_rows() -> None:
    model = RuleBasedChatModel()
    rows = [
        _Msg("user", "hi", event_type="user_text", turn_uuid="turn-1"),
        _Msg("assistant", "internal", event_type="reasoning", turn_uuid="turn-1"),
        _Msg("assistant", "visible answer", event_type="assistant_text", turn_uuid="turn-1"),
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    assistant_texts = [str(m.get("content") or "") for m in msgs if m.get("role") == "assistant"]
    assert assistant_texts == ["visible answer"]


def test_build_llm_messages_strips_think_blocks_from_legacy_assistant_content() -> None:
    model = RuleBasedChatModel()
    rows = [_Msg("assistant", "<think>\nsecret plan\n</think>\n\nfinal answer")]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    assistant_rows = [m for m in msgs if m.get("role") == "assistant"]
    assert assistant_rows
    assert "secret plan" not in str(assistant_rows[0].get("content") or "")
    assert "final answer" in str(assistant_rows[0].get("content") or "")


def test_build_llm_messages_only_keeps_recent_3_tool_rounds_full() -> None:
    model = RuleBasedChatModel()
    rows: list[_Msg] = []
    for idx in range(1, 5):
        tcid = f"call_{idx}"
        rows.append(
            _Msg(
                "assistant",
                "",
                tool_calls=json.dumps([{"id": tcid, "name": "tool_x", "arguments": {"n": idx}}], ensure_ascii=False),
                event_type="tool_call",
                turn_uuid=f"turn-{idx}",
            )
        )
        rows.append(
            _Msg(
                "tool",
                json.dumps({"ok": True, "blob": "x" * 3000, "idx": idx}, ensure_ascii=False),
                tool_calls=json.dumps({"tool_call_id": tcid, "name": "tool_x"}, ensure_ascii=False),
                event_type="tool_result",
                turn_uuid=f"turn-{idx}",
            )
        )
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    tool_by_id = {str(m.get("tool_call_id")): str(m.get("content") or "") for m in msgs if m.get("role") == "tool"}
    assert tool_by_id["call_1"].find("_history_summarized") >= 0
    assert tool_by_id["call_4"].find("_history_summarized") < 0


def test_signature_metadata_not_replayed_by_default_for_non_whitelist_model() -> None:
    model = RuleBasedChatModel()
    rows = [
        _Msg(
            "assistant",
            "",
            tool_calls=json.dumps(
                [{"id": "call_1", "name": "t", "arguments": {}, "thought_signature": "sig_abc"}],
                ensure_ascii=False,
            ),
            event_type="tool_call",
        )
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    assistant = [m for m in msgs if m.get("role") == "assistant"][0]
    tc = (assistant.get("tool_calls") or [])[0]
    assert "extra_content" not in tc


def test_signature_metadata_can_be_forced_on_via_env(monkeypatch) -> None:
    monkeypatch.setenv("AIA_REPLAY_REASONING_SIGNATURE_POLICY", "on")
    model = RuleBasedChatModel()
    rows = [
        _Msg(
            "assistant",
            "",
            tool_calls=json.dumps(
                [{"id": "call_1", "name": "t", "arguments": {}, "thought_signature": "sig_abc"}],
                ensure_ascii=False,
            ),
            event_type="tool_call",
        )
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=model, lang="zh")
    assistant = [m for m in msgs if m.get("role") == "assistant"][0]
    tc = (assistant.get("tool_calls") or [])[0]
    assert tc.get("extra_content", {}).get("google", {}).get("thought_signature") == "sig_abc"

