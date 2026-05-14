"""persist_assistant_text_if_turn_missing"""

from __future__ import annotations

import uuid
from svc.persistence.sqlite_store import SqliteStore
from runtime.chat.persist_terminal_fallback import persist_assistant_text_if_turn_missing


def test_fallback_inserts_when_missing(tmp_path) -> None:
    db = tmp_path / "t.sqlite"
    store = SqliteStore(str(db))
    t = store.create_tenant("T")
    tid = str(t["id"])
    store.create_user_account(
        tenant_id=tid,
        username="u",
        display_name="U",
        role="owner",
        password_hash="x",
        is_active=True,
    )
    uid = str(store.get_user_by_username(tenant_id=tid, username="u")["id"])
    s = store.create_session_for_user(title="s", tenant_id=tid, user_id=uid)
    sid = str(s.id)
    tu = uuid.uuid4().hex
    store.add_message(session_id=sid, role="user", content="hi", turn_uuid=tu, event_type="user_text")
    assert persist_assistant_text_if_turn_missing(
        store=store,
        session_id=sid,
        turn_uuid=tu,
        final_text="fallback body",
        log_prefix="test_fallback",
    )
    msgs = store.get_messages(sid, limit=20)
    assert any(getattr(m, "role", "") == "assistant" and "fallback" in str(getattr(m, "content", "")) for m in msgs)


def test_fallback_skips_when_present(tmp_path) -> None:
    db = tmp_path / "u.sqlite"
    store = SqliteStore(str(db))
    t = store.create_tenant("T2")
    tid = str(t["id"])
    store.create_user_account(
        tenant_id=tid,
        username="u2",
        display_name="U",
        role="owner",
        password_hash="x",
        is_active=True,
    )
    uid = str(store.get_user_by_username(tenant_id=tid, username="u2")["id"])
    s = store.create_session_for_user(title="s", tenant_id=tid, user_id=uid)
    sid = str(s.id)
    tu = uuid.uuid4().hex
    store.add_message(session_id=sid, role="user", content="hi", turn_uuid=tu, event_type="user_text")
    store.add_message(session_id=sid, role="assistant", content="already", turn_uuid=tu, event_type="assistant_text")
    assert not persist_assistant_text_if_turn_missing(
        store=store,
        session_id=sid,
        turn_uuid=tu,
        final_text="would duplicate",
        log_prefix="test_skip",
    )
