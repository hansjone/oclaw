from __future__ import annotations

import pytest

from runtime.orchestration.group_ingest import (
    GROUP_SESSION_USER_SENTINEL,
    build_group_sender_context,
    build_whatsapp_group_reply_metadata,
    infer_is_group_from_chat_id,
    is_nonsend_channel_reply_text,
    normalize_jid,
    resolve_group_policy,
    session_user_key,
    should_process_group_inbound,
    text_mentions_bot,
)
from interfaces.channels.base import InboundMessage
from runtime.application.gateway.inbound_service import _parse_generic_inbound, process_inbound_payload
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


def test_should_accept_group_mention_with_lid_phone_match() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["999@lid"],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
        )
        is True
    )


def test_should_accept_group_mention_with_bot_lid_identity() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["176944565977182@lid"],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={"bot_lid": "176944565977182:2@lid"},
        )
        is True
    )


def test_jids_same_user_lid_device_suffix() -> None:
    from runtime.orchestration.group_ingest import jids_same_user

    assert jids_same_user("176944565977182@lid", "176944565977182:2@lid") is True


def test_should_accept_group_when_sidecar_reports_mentions_bot() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="hi",
            mentions=["unknown-lid@lid"],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            metadata={"mentions_bot": True, "raw": {"mentionsBot": True}},
        )
        is True
    )


def test_should_accept_group_reply_to_bot() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="follow up",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            metadata={"raw": {"quotedParticipant": "999:0@s.whatsapp.net", "isReplyToBot": True}},
        )
        is True
    )


def test_text_mentions_bot_phone_fallback() -> None:
    assert text_mentions_bot(text="@1234567890 hello", bot_jid="1234567890@s.whatsapp.net") is True
    assert text_mentions_bot(text="hello", bot_jid="1234567890@s.whatsapp.net") is False


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


def test_infer_is_group_from_chat_id() -> None:
    assert infer_is_group_from_chat_id("120363012345678@g.us") is True
    assert infer_is_group_from_chat_id("111@s.whatsapp.net") is False


def test_parse_generic_inbound_infers_whatsapp_group() -> None:
    inbound = _parse_generic_inbound(
        "whatsapp",
        {
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "hello",
        },
    )
    assert inbound.is_group is True


def test_is_nonsend_channel_reply_text() -> None:
    assert is_nonsend_channel_reply_text("") is True
    assert is_nonsend_channel_reply_text("(silent)") is True
    assert is_nonsend_channel_reply_text("（silent）") is True
    assert is_nonsend_channel_reply_text("NO_REPLY") is True
    assert is_nonsend_channel_reply_text("你好") is False


def test_inbound_group_without_is_group_flag_is_still_silent(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "Test alarm",
            "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
        }
    )
    assert out.get("replies") == []


def test_inbound_suppresses_silent_llm_reply(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    class _Turn:
        turn_uuid = "turn-s"
        reply_text = "(silent)"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
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
            "metadata": {"bot_jid": "999@s.whatsapp.net"},
        }
    )
    assert out.get("replies") == []


def test_build_group_sender_context() -> None:
    ctx = build_group_sender_context(
        metadata={"raw": {"pushName": "Alice"}},
        external_user_id="111@s.whatsapp.net",
    )
    assert "Alice" in ctx
    assert "111@s.whatsapp.net" in ctx


def test_build_whatsapp_group_reply_metadata() -> None:
    inbound = InboundMessage(
        channel="whatsapp",
        external_user_id="111:12@s.whatsapp.net",
        external_chat_id="120363012345678@g.us",
        text="明天几点？",
        is_group=True,
        metadata={
            "raw": {
                "id": "MSG123",
                "participant": "111:12@s.whatsapp.net",
                "pushName": "Alice",
            }
        },
    )
    meta = build_whatsapp_group_reply_metadata(inbound=inbound)
    assert meta["quote_stanza_id"] == "MSG123"
    assert meta["mention_jids"] == ["111:12@s.whatsapp.net"]
    assert meta["quote_text"] == "明天几点？"
    assert meta["quote_participant"] == "111:12@s.whatsapp.net"


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


def test_inbound_group_reply_includes_quote_and_mention_metadata(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    class _Turn:
        turn_uuid = "turn-g"
        reply_text = "下午三点"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@bot 明天几点？",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "999@s.whatsapp.net",
                "raw": {"id": "ABC123", "participant": "111@s.whatsapp.net", "pushName": "Alice"},
            },
        }
    )
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies
    meta = replies[0].get("metadata") if isinstance(replies[0], dict) else {}
    assert isinstance(meta, dict)
    assert meta.get("quote_stanza_id") == "ABC123"
    assert meta.get("mention_jids") == ["111@s.whatsapp.net"]
    assert meta.get("quote_text") == "@bot 明天几点？"
