"""OpenAI Chat Completions transport: DeepSeek DSML stream filter and recovery."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from svc.llm.transports.openai_chat_completions import (
    OpenAIChatModel,
    _promote_dsml_in_llm_response,
    _should_recover_dsml_tool_calls,
)
from svc.llm.transports.base import LLMToolCall


def test_should_recover_dsml_for_deepseek_url() -> None:
    assert _should_recover_dsml_tool_calls("deepseek-chat", "https://api.deepseek.com/v1")


def test_should_not_recover_for_unrelated_gateway() -> None:
    assert not _should_recover_dsml_tool_calls("gpt-4o-mini", "https://api.openai.com/v1")


def test_should_recover_when_env_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_DSML_TEXT_TOOLS", "1")
    assert _should_recover_dsml_tool_calls("local-model", "http://127.0.0.1:8000/v1")


def test_promote_dsml_in_llm_response() -> None:
    dsml = (
        "prefix\n"
        "<||DSML||tool_calls>\n"
        "<||DSML||invoke name=\"run_command\">\n"
        "<||DSML||parameter name=\"command\" string=\"true\">echo hi</||DSML||parameter>\n"
        "</||DSML||invoke>\n"
        "</||DSML||tool_calls>"
    )
    content, reasoning, calls = _promote_dsml_in_llm_response(dsml, "", [])
    assert len(calls) == 1
    assert calls[0].name == "run_command"
    assert calls[0].arguments == {"command": "echo hi"}
    assert "DSML" not in content
    assert "prefix" in content
    assert reasoning == ""


def test_promote_skips_when_native_tool_calls_present() -> None:
    dsml = '<||DSML||tool_calls><||DSML||invoke name="x"></||DSML||invoke></||DSML||tool_calls>'
    native = [LLMToolCall(id="call_1", name="native_tool", arguments={})]
    content, _, calls = _promote_dsml_in_llm_response(dsml, "", native)
    assert calls is native
    assert "DSML" in content


def test_chat_stream_filters_dsml_and_promotes_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = OpenAIChatModel(
        model="deepseek-chat",
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
    )
    dsml_text = (
        "hello "
        "<||DSML||tool_calls>"
        "<||DSML||invoke name=\"run_command\">"
        "<||DSML||parameter name=\"command\" string=\"true\">echo</||DSML||parameter>"
        "</||DSML||invoke>"
        "</||DSML||tool_calls>"
    )

    def fake_stream(_norm_msgs, _tools, *, stream: bool):  # noqa: ANN001, ARG001
        assert stream is True
        chunks = []
        for i in range(0, len(dsml_text), 4):
            delta = SimpleNamespace(
                content=dsml_text[i : i + 4],
                tool_calls=None,
                reasoning_content="",
            )
            chunks.append(SimpleNamespace(choices=[SimpleNamespace(delta=delta)]))
        return iter(chunks)

    model._create_chat_completion = fake_stream  # type: ignore[method-assign]
    seen: list[str] = []
    resp = model.chat([], [], on_token=seen.append)
    assert "hello" in resp.content
    assert "DSML" not in resp.content
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "run_command"
    assert resp.tool_calls[0].arguments == {"command": "echo"}
    joined = "".join(seen)
    assert "DSML" not in joined
    assert "hello" in joined


def test_llm_response_from_completion_promotes_dsml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = OpenAIChatModel(
        model="deepseek-chat",
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
    )
    dsml = (
        "<||DSML||tool_calls>"
        "<||DSML||invoke name=\"read_file\"></||DSML||invoke>"
        "</||DSML||tool_calls>"
    )
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=dsml, reasoning_content="", tool_calls=None),
            )
        ]
    )
    seen: list[str] = []
    resp = model._llm_response_from_completion(completion, on_token=seen.append)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "read_file"
    assert "DSML" not in resp.content
    assert "DSML" not in "".join(seen)


def test_chat_stream_handles_terminal_message_chunk_with_null_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    """mytokenland-style gateways may finish tool streams with delta=None and message populated."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = OpenAIChatModel(
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.mytokenland.com/v1",
    )

    delta_tool = SimpleNamespace(
        content=None,
        reasoning_content="",
        tool_calls=[
            SimpleNamespace(
                index=0,
                id="call_function_test_1",
                function=SimpleNamespace(name="system_time", arguments="{}"),
            )
        ],
    )
    terminal_message = SimpleNamespace(
        content="",
        reasoning_content="thinking about time",
        tool_calls=[
            SimpleNamespace(
                index=0,
                id="call_function_test_1",
                function=SimpleNamespace(name="system_time", arguments="{}"),
            )
        ],
    )

    def fake_stream(_norm_msgs, _tools, *, stream: bool):  # noqa: ANN001, ARG001
        assert stream is True
        return iter(
            [
                SimpleNamespace(choices=[SimpleNamespace(delta=delta_tool)]),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=None, finish_reason="tool_calls", message=terminal_message)
                    ]
                ),
            ]
        )

    model._create_chat_completion = fake_stream  # type: ignore[method-assign]
    resp = model.chat([], [], on_token=lambda _s: None)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "system_time"
    assert resp.tool_calls[0].arguments == {}
    assert resp.reasoning_content == "thinking about time"
