"""turn_uuid recovery / final payload alignment for WS turn runner."""

from __future__ import annotations

import uuid

from interfaces.ws.turn_runner import _latest_turn_uuid
from svc.persistence.sqlite_store import SqliteStore


def _seed_session(store: SqliteStore) -> str:
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
    return str(s.id)


def test_latest_turn_uuid_prefers_latest_user(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.sqlite"))
    sid = _seed_session(store)
    older = uuid.uuid4().hex
    newer = uuid.uuid4().hex
    store.add_message(session_id=sid, role="user", content="a", turn_uuid=older, event_type="user_text")
    store.add_message(
        session_id=sid, role="assistant", content="ok", turn_uuid=older, event_type="assistant_text"
    )
    store.add_message(session_id=sid, role="user", content="b", turn_uuid=newer, event_type="user_text")
    assert _latest_turn_uuid(store, sid) == newer


def test_latest_turn_uuid_falls_back_to_assistant(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "u.sqlite"))
    sid = _seed_session(store)
    tu = uuid.uuid4().hex
    store.add_message(
        session_id=sid, role="assistant", content="partial", turn_uuid=tu, event_type="assistant_text"
    )
    assert _latest_turn_uuid(store, sid) == tu


def test_latest_turn_uuid_empty_session(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "e.sqlite"))
    sid = _seed_session(store)
    assert _latest_turn_uuid(store, sid) == ""
