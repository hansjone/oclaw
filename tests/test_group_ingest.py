from __future__ import annotations

import pytest

from runtime.orchestration.group_ingest import (
    GROUP_SESSION_USER_SENTINEL,
    build_group_sender_context,
    normalize_jid,
    resolve_group_policy,
    session_user_key,
    should_process_group_inbound,
)
from runtime.application.gateway.inbound_service import process_inbound_payload
from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "group_ingest.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_normalize_jid_strips_device_suffix() -> None:
    assert normalize_jid("123456:12@s.whatsapp.net") == "123456@s.whatsapp.net"


def test_should_process_direct_messages_always() -> None:
    assert should_process_group_inbound(is_group=False, text="hi", mentions=[], bot_jid="bot@s.whatsapp.net") is True


def test_should_drop_group_without_mention_or_trigger() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="大家好",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            triggers=["/oclaw"],
        )
        is False
    )


def test_should_accept_group_when_bot_mentioned() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["999:0@s.whatsapp.net"],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
        )
        is True
    )


def test_should_accept_group_trigger_without_mention() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="/oclaw 查天气",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            triggers=["/oclaw"],
        )
        is True
    )


def test_session_user_key_group_sentinel() -> None:
    assert session_user_key(is_group=True, external_user_id="111@s.whatsapp.net") == GROUP_SESSION_USER_SENTINEL
    assert session_user_key(is_group=False, external_user_id="111@s.whatsapp.net") == "111@s.whatsapp.net"


def test_resolve_group_policy_from_account_config() -> None:
    policy = resolve_group_policy(
        account={
            "config": {
                "group_policy": {
                    "require_mention": False,
                    "triggers": ["!ask"],
                }
            }
        }
    )
    assert policy.require_mention is False
    assert policy.triggers == ("!ask",)


def test_build_group_sender_context() -> None:
    ctx = build_group_sender_context(
        metadata={"raw": {"pushName": "Alice"}},
        external_user_id="111@s.whatsapp.net",
    )
    assert "Alice" in ctx
    assert "111@s.whatsapp.net" in ctx


def test_shared_group_session_for_multiple_senders(fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    tenant = store.create_tenant("WA")
    chat_id = "120363012345678@g.us"
    sid_a = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(is_group=True, external_user_id="111@s.whatsapp.net"),
        session_title="whatsapp|test+Family",
    )
    sid_b = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(is_group=True, external_user_id="222@s.whatsapp.net"),
        session_title="whatsapp|test+Family",
    )
    assert sid_a == sid_b


def _setup_whatsapp_identity(store: SqliteStore, *, extra_user_ids: list[str] | None = None) -> tuple[str, str]:
    tenant = store.create_tenant("WA")
    tenant_id = str(tenant["id"])
    user = store.create_user(tenant_id=tenant_id, display_name="Admin", role="owner")
    user_id = str(user["id"])
    store.upsert_user_channel_account(
        tenant_id=tenant_id,
        user_id=user_id,
        channel="whatsapp",
        account_id="wa-default",
        name="wa-default",
        config={"group_policy": {"require_mention": True, "triggers": ["/oclaw"]}},
        is_active=True,
    )
    for ext_uid in ["111@s.whatsapp.net", *(extra_user_ids or [])]:
        store.upsert_channel_identity_v2(
            tenant_id=tenant_id,
            channel="whatsapp",
            account_id="wa-default",
            external_user_id=ext_uid,
            user_id=user_id,
        )
    return tenant_id, user_id


def test_inbound_group_without_mention_is_silent(monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "大家晚上好",
            "is_group": True,
            "mentions": [],
            "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
        }
    )
    assert out.get("ok") is True
    assert out.get("replies") == []


def test_inbound_dm_still_processes_without_mention(monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    captured: dict[str, str] = {}

    class _Turn:
        turn_uuid = "turn-1"
        reply_text = "pong"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "111@s.whatsapp.net",
            "text": "ping",
            "is_group": False,
            "mentions": [],
            "metadata": {"bot_jid": "999@s.whatsapp.net"},
        }
    )
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies and str(replies[0].get("text") or "") == "pong"
    assert "[群成员:" not in captured.get("text", "")


def test_inbound_group_mention_uses_shared_session_and_sender_prefix(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, user_id = _setup_whatsapp_identity(store, extra_user_ids=["222@s.whatsapp.net"])
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    captured: dict[str, str] = {}
    session_ids: list[str] = []

    class _Turn:
        turn_uuid = "turn-g"
        reply_text = "group-ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            session_ids.append(str(getattr(msg, "session_id", "") or ""))
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    chat_id = "120363012345678@g.us"
    base = {
        "channel": "whatsapp",
        "account_id": "wa-default",
        "chat_id": chat_id,
        "is_group": True,
        "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
    }

    process_inbound_payload(
        {
            **base,
            "user_id": "111@s.whatsapp.net",
            "text": "@bot hi",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Alice"}},
        }
    )
    process_inbound_payload(
        {
            **base,
            "user_id": "222@s.whatsapp.net",
            "text": "@bot again",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Bob"}},
        }
    )

    assert len(session_ids) == 2
    assert session_ids[0] == session_ids[1]
    assert "[群成员:" in captured["text"]
    assert "Bob" in captured["text"]

    sid = store.get_or_create_channel_session_v2(
        tenant_id=tenant_id,
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=GROUP_SESSION_USER_SENTINEL,
        session_title="whatsapp|wa-default+Family",
    )
    assert sid == session_ids[0]

    _ = tenant_id, user_id
