from __future__ import annotations

from types import SimpleNamespace

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.direct_loop import run_oclaw_direct_loop
from oclaw.runtime.tools.base import ToolRegistry


class _Model:
    base_url = ""
    thinking_mode_enabled = False

    def chat(self, msgs, tools, on_token=None):  # noqa: ANN001,ARG002
        return SimpleNamespace(content="", reasoning_content="", tool_calls=[])


def test_direct_loop_persists_stub_on_empty_assistant(tmp_path) -> None:  # noqa: ANN001
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
    assert out.final_text
    rows = store.get_messages(session_id=sess.id, limit=10)
    assistant = [r for r in rows if getattr(r, "role", "") == "assistant"]
    assert any("空响应" in str(getattr(r, "content", "") or "") for r in assistant)

