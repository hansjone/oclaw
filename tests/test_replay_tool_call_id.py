"""Regression tests for OpenClaw-style tool_call_id replay (see src/platform/llm/tool_call_id.py)."""

from __future__ import annotations

from oclaw.platform.llm.replay_policy import apply_replay_policy_to_messages, resolve_replay_policy
from oclaw.platform.llm.tool_call_id import repair_orphan_tool_messages, rewrite_openai_chat_messages_tool_ids


def test_rewrite_pairs_assistant_and_tool_ids() -> None:
    msgs = [
        {"role": "user", "content": "list files"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_function_2aij35g1tffl_1",
                    "type": "function",
                    "function": {"name": "get_system_time", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_function_2aij35g1tffl_1", "content": '{"ok":true}'},
    ]
    out = rewrite_openai_chat_messages_tool_ids(msgs, max_len=40)
    assert out[1]["tool_calls"][0]["id"]
    tid = out[1]["tool_calls"][0]["id"]
    assert out[2]["tool_call_id"] == tid
    assert tid.isalnum() or all(c.isalnum() for c in tid if c)


def test_repair_strips_dangling_tool_call_id() -> None:
    msgs = [
        {"role": "assistant", "content": "x", "tool_calls": [{"id": "onlyhere", "type": "function", "function": {"name": "a", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "unknown", "content": "{}"},
    ]
    out = repair_orphan_tool_messages(msgs)
    assert "tool_call_id" not in out[1] or out[1].get("tool_call_id") in ("",)


def test_apply_replay_policy_full_pipeline() -> None:
    policy = resolve_replay_policy("https://example.com/v1", "mimo-v2-omni")
    assert policy.enabled
    assert policy.sanitize_tool_call_ids
    msgs = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "weird|id:here", "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "weird|id:here", "content": "{}"},
    ]
    out = apply_replay_policy_to_messages(msgs, policy)
    assert out[0]["tool_calls"][0]["id"] == out[1]["tool_call_id"]
