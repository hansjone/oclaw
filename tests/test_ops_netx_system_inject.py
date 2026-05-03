from __future__ import annotations

from pathlib import Path

import pytest

from oclaw.platform.llm.chat_models import RuleBasedChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.direct_loop import _build_model_context


def test_ops_role_injects_netx_batch_anchor_into_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import oclaw.runtime.tools.experts.network_ops.netx_tools as nt

    def _fake_latest() -> dict:
        return {
            "ok": True,
            "batch_id": "batch-inject-test",
            "batch_row": {
                "created_at": "2026-05-01T00:00:00",
                "source_file": "alarms.xlsx",
                "status": "ok",
                "total_rows": 42,
            },
        }

    monkeypatch.setattr(nt, "_resolve_latest_import_batch_id", _fake_latest)
    nt._OPS_NETX_SYS_CTX_CACHE.clear()  # type: ignore[attr-defined]

    store = SqliteStore(str(tmp_path / "n.sqlite"))
    sess = store.create_session("s")
    store.add_message(session_id=sess.id, role="user", content="hello")

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=20,
        system_prompt="BASE",
        model=RuleBasedChatModel(),
        lang="zh",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        skill_binding_role="ops",
        user_text="hello",
    )
    assert msgs and msgs[0].get("role") == "system"
    sys_text = str(msgs[0].get("content") or "")
    assert "batch-inject-test" in sys_text
    assert "alarms.xlsx" in sys_text


def test_non_ops_role_skips_netx_inject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"n": 0}

    def _spy_latest() -> dict:
        calls["n"] += 1
        return {"ok": True, "batch_id": "x", "batch_row": {}}

    import oclaw.runtime.tools.experts.network_ops.netx_tools as nt

    monkeypatch.setattr(nt, "_resolve_latest_import_batch_id", _spy_latest)

    store = SqliteStore(str(tmp_path / "g.sqlite"))
    sess = store.create_session("s")
    store.add_message(session_id=sess.id, role="user", content="hi")

    _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=20,
        system_prompt="BASE_ONLY",
        model=RuleBasedChatModel(),
        lang="zh",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        skill_binding_role="generalist",
        user_text="hi",
    )
    assert calls["n"] == 0
