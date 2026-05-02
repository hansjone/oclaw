from __future__ import annotations

from types import SimpleNamespace

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.direct_loop import run_oclaw_direct_loop
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


class _Model:
    base_url = ""
    thinking_mode_enabled = False

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        return SimpleNamespace(content="", reasoning_content="", tool_calls=[])


def test_direct_loop_keeps_empty_assistant_without_stub(tmp_path) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="x",
        model=_Model(),
        tools=ToolRegistry([]),
        user_text="hi",
        persist_user_message=True,
        max_tool_rounds=1,
    )
    assert out.final_text == ""
    rows = store.get_messages(session_id=sess.id, limit=10)
    assistant = [r for r in rows if getattr(r, "role", "") == "assistant"]
    assert not any("空响应" in str(getattr(r, "content", "") or "") for r in assistant)


class _ModelRetryOnce:
    base_url = ""
    thinking_mode_enabled = False

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(content="", reasoning_content="", tool_calls=[])
        return SimpleNamespace(content="ok-after-retry", reasoning_content="", tool_calls=[])


def test_direct_loop_retries_once_before_stub(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    model = _ModelRetryOnce()
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_MAX", "1")
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS", "0")
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="x",
        model=model,
        tools=ToolRegistry([]),
        user_text="hi",
        persist_user_message=True,
        max_tool_rounds=1,
    )
    assert out.final_text == "ok-after-retry"
    assert model.calls == 2
    rows = store.get_messages(session_id=sess.id, limit=10)
    assistant = [r for r in rows if getattr(r, "role", "") == "assistant"]
    assert not any("空响应" in str(getattr(r, "content", "") or "") for r in assistant)
    monkeypatch.delenv("AIA_EMPTY_ASSISTANT_RETRY_MAX", raising=False)
    monkeypatch.delenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS", raising=False)


class _ModelDsmlThenText:
    base_url = ""
    thinking_mode_enabled = False

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                content='<||DSML||tool_calls><||DSML||invoke name="run_command"></||DSML||invoke></||DSML||tool_calls>',
                reasoning_content="",
                tool_calls=[],
            )
        return SimpleNamespace(content="native-tools-recovered", reasoning_content="", tool_calls=[])


def test_direct_loop_retries_when_dsml_text_tool_call(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    model = _ModelDsmlThenText()
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_MAX", "1")
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS", "0")
    dummy_tool = ToolSpec(
        name="run_command",
        description="dummy",
        parameters={"type": "object", "properties": {}, "additionalProperties": True},
        handler=lambda args: {"ok": True, "args": args},
        read_only=True,
    )
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="x",
        model=model,
        tools=ToolRegistry([dummy_tool]),
        user_text="hi",
        persist_user_message=True,
        max_tool_rounds=1,
    )
    assert out.final_text == "native-tools-recovered"
    assert model.calls == 2


class _ModelAlwaysDsml:
    base_url = ""
    thinking_mode_enabled = False

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        return SimpleNamespace(
            content='<||DSML||tool_calls><||DSML||invoke name="read_file"></||DSML||invoke></||DSML||tool_calls>',
            reasoning_content="",
            tool_calls=[],
        )


def test_direct_loop_dsml_text_persisted_as_failed_tool_pair(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    model = _ModelAlwaysDsml()
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_MAX", "1")
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS", "0")
    dummy_tool = ToolSpec(
        name="read_file",
        description="dummy",
        parameters={"type": "object", "properties": {}, "additionalProperties": True},
        handler=lambda args: {"ok": True, "args": args},
        read_only=True,
    )
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="x",
        model=model,
        tools=ToolRegistry([dummy_tool]),
        user_text="hi",
        persist_user_message=True,
        max_tool_rounds=1,
    )
    assert out.final_text == ""
    rows = store.get_messages(session_id=sess.id, limit=20)
    tool_rows = [r for r in rows if getattr(r, "role", "") == "tool"]
    assert tool_rows
    assert any("model_protocol_mismatch_dsml" in str(getattr(r, "content", "") or "") for r in tool_rows)


class _ModelMixedTextualToolIntent:
    base_url = ""
    thinking_mode_enabled = False

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        return SimpleNamespace(
            content=(
                "输出没抓到。再来：\n\n"
                "<||DSML||tool_calls>\n"
                "<||DSML||invoke name=\"run_command\">\n"
                "<||DSML||parameter name=\"command\" string=\"true\">echo test</||DSML||parameter>\n"
                "</||DSML||invoke>\n"
                "</||DSML||tool_calls>"
            ),
            reasoning_content="",
            tool_calls=[],
        )


def test_direct_loop_mixed_text_with_tool_intent_is_blocked(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    model = _ModelMixedTextualToolIntent()
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_MAX", "1")
    monkeypatch.setenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS", "0")
    dummy_tool = ToolSpec(
        name="run_command",
        description="dummy",
        parameters={"type": "object", "properties": {}, "additionalProperties": True},
        handler=lambda args: {"ok": True, "args": args},
        read_only=True,
    )
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="x",
        model=model,
        tools=ToolRegistry([dummy_tool]),
        user_text="hi",
        persist_user_message=True,
        max_tool_rounds=1,
    )
    assert out.final_text == ""
    rows = store.get_messages(session_id=sess.id, limit=20)
    tool_rows = [r for r in rows if getattr(r, "role", "") == "tool"]
    assert tool_rows
    assert any("run_command" in str(getattr(r, "tool_calls", "") or "") for r in tool_rows)

