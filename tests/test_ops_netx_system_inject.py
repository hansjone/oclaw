from __future__ import annotations

from pathlib import Path

import pytest

from svc.llm.chat_models import RuleBasedChatModel
from svc.persistence.sqlite_store import SqliteStore
from runtime.direct_loop import _build_model_context


def test_ops_role_injects_netx_batch_anchor_into_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    def _fake_anchor() -> dict:
        return {
            "ok": True,
            "anchor": {
                "status": "done",
                "trigger_mode": "auto",
                "started_at": "2026-05-01T00:00:00",
                "ended_at": "2026-05-01T00:01:00",
                "pulled_count": 42,
                "inserted_count": 3,
                "updated_count": 5,
            },
        }

    monkeypatch.setattr(nt, "_resolve_ume_anchor", _fake_anchor)
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
    assert "UME告警锚点" in sys_text
    assert "42/3/5" in sys_text


def test_non_ops_role_skips_netx_inject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"n": 0}

    def _spy_anchor() -> dict:
        calls["n"] += 1
        return {"ok": True, "anchor": {}}

    import runtime.tools.experts.network_ops.netx_tools as nt

    monkeypatch.setattr(nt, "_resolve_ume_anchor", _spy_anchor)

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
