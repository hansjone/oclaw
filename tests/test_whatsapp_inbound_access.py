from __future__ import annotations

from typing import Any

from runtime.application.gateway.whatsapp_inbound_access import handle_whatsapp_access


class _AccessStore:
    def __init__(self) -> None:
        self.contacts: dict[str, dict[str, Any]] = {}
        self.pending: list[dict[str, Any]] = []
        self.outbound: list[dict[str, Any]] = []
        self.config: dict[str, Any] = {"access_mode": "blacklist", "lang": "en"}
        self.identities: dict[str, dict[str, Any]] = {}
        self.users: list[dict[str, Any]] = []
        self.notify_map: dict[tuple[str, str], str] = {}
        self._pending_seq = 0

    def get_whatsapp_access_config(self, *, tenant_id: str, account_id: str) -> dict[str, Any]:
        return dict(self.config)

    def upsert_whatsapp_access_config(self, **kwargs: Any) -> dict[str, Any]:
        self.config.update({k: v for k, v in kwargs.items() if k in {"access_mode", "lang"}})
        return dict(self.config)

    def apply_whatsapp_contact_access(self, **kwargs: Any) -> dict[str, Any]:
        return self.upsert_whatsapp_contact(**kwargs)

    def find_whatsapp_contact_for_sender(self, **kwargs: Any) -> dict[str, Any] | None:
        from runtime.extensions.whatsapp.access_control import (
            contact_phone_key,
            resolve_sender_phone,
            whatsapp_users_match,
        )

        jid = str(kwargs.get("external_user_id") or "")
        alt = str(kwargs.get("participant_alt") or "")
        remote_alt = str(kwargs.get("remote_jid_alt") or "")
        sender_phone = resolve_sender_phone(jid, alt, remote_alt)
        for row in self.contacts.values():
            if not row.get("list_type"):
                continue
            if sender_phone and contact_phone_key(row) == sender_phone:
                return row
            cj = str(row.get("external_user_id") or "")
            if whatsapp_users_match(cj, jid) or (alt and whatsapp_users_match(cj, alt)):
                return row
        return None

    def resolve_whatsapp_pending_for_sender(self, **kwargs: Any) -> int:
        return 0

    def upsert_whatsapp_contact(self, **kwargs: Any) -> dict[str, Any]:
        jid = str(kwargs.get("external_user_id") or "")
        row = dict(self.contacts.get(jid) or {})
        row.update({k: v for k, v in kwargs.items() if v is not None})
        if kwargs.get("list_type") is None and jid in self.contacts:
            row["list_type"] = self.contacts[jid].get("list_type")
        self.contacts[jid] = row
        return row

    def list_whatsapp_contacts(self, *, tenant_id: str, account_id: str, list_type: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        rows = list(self.contacts.values())
        if list_type:
            rows = [r for r in rows if str(r.get("list_type") or "") == list_type]
        return rows

    def create_whatsapp_access_pending(self, **kwargs: Any) -> str:
        self._pending_seq += 1
        pending_id = f"pending{self._pending_seq}"
        for row in self.pending:
            if row.get("status") == "pending" and row.get("external_user_id") == kwargs.get("external_user_id"):
                return str(row.get("id") or pending_id)
        self.pending.append(
            {
                "id": pending_id,
                "external_user_id": kwargs.get("external_user_id"),
                "push_name": kwargs.get("push_name"),
                "phone": kwargs.get("phone"),
                "request_text": kwargs.get("request_text"),
                "status": "pending",
            }
        )
        return pending_id

    def list_whatsapp_access_pending(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [r for r in self.pending if r.get("status") == kwargs.get("status", "pending")]

    def get_whatsapp_access_pending_by_id(self, *, pending_id: str) -> dict[str, Any] | None:
        for row in self.pending:
            if str(row.get("id") or "") == str(pending_id or ""):
                return dict(row)
        return None

    def find_whatsapp_pending_by_notify_stanza(
        self,
        *,
        tenant_id: str,
        account_id: str,
        admin_chat_id: str,
        notify_stanza_id: str,
    ) -> str | None:
        return self.notify_map.get((str(admin_chat_id), str(notify_stanza_id)))

    def delete_whatsapp_pending_notify_for_pending(self, *, pending_id: str) -> int:
        removed = 0
        for key, pid in list(self.notify_map.items()):
            if pid == pending_id:
                del self.notify_map[key]
                removed += 1
        return removed

    def resolve_whatsapp_access_pending(self, **kwargs: Any) -> bool:
        for row in self.pending:
            if row.get("id") == kwargs.get("pending_id"):
                row["status"] = kwargs.get("status")
                return True
        return False

    def enqueue_channel_outbound_message(self, **kwargs: Any) -> str:
        self.outbound.append(dict(kwargs))
        return "out1"

    def resolve_user_by_channel_identity_v2(self, **kwargs: Any) -> dict[str, Any] | None:
        return self.identities.get(str(kwargs.get("external_user_id") or ""))

    def create_user_account(self, **kwargs: Any) -> dict[str, Any]:
        user = {"id": "guest1", "role": kwargs.get("role", "guest")}
        self.users.append(user)
        return user

    def upsert_channel_identity_v2(self, **kwargs: Any) -> None:
        jid = str(kwargs.get("external_user_id") or "")
        self.identities[jid] = {
            "tenant_id": kwargs.get("tenant_id"),
            "user_id": kwargs.get("user_id"),
            "role": "guest",
        }

    def get_user_by_username(self, **kwargs: Any) -> dict[str, Any] | None:
        return {"id": "admin1", "role": "owner"}


class _Inbound:
    channel = "whatsapp"
    external_user_id = "8615601877957@s.whatsapp.net"
    external_chat_id = "8615601877957@s.whatsapp.net"
    metadata = {"raw": {"pushName": "Bob"}}


class _InboundGroup:
    channel = "whatsapp"
    is_group = True
    external_user_id = "91010910658657@lid"
    external_chat_id = "999@g.us"
    metadata = {
        "raw": {
            "pushName": "oliver",
            "id": "stanza_1",
            "participant": "91010910658657@lid",
            "participantAlt": "8618142387786@s.whatsapp.net",
        }
    }


class _InboundAdmin:
    channel = "whatsapp"
    external_user_id = "111@s.whatsapp.net"
    external_chat_id = "111@s.whatsapp.net"
    metadata: dict[str, Any] = {"raw": {}}


def _setup_admin_store() -> _AccessStore:
    store = _AccessStore()
    store.contacts["111@s.whatsapp.net"] = {
        "external_user_id": "111@s.whatsapp.net",
        "phone": "111",
        "list_type": "admin",
    }
    return store


def test_handle_whatsapp_access_admin_yes_without_quote_passes_to_llm(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _setup_admin_store()
    store.pending.append(
        {
            "id": "pending1",
            "external_user_id": "8615601877957@s.whatsapp.net",
            "push_name": "Bob",
            "phone": "8615601877957",
            "status": "pending",
        }
    )
    out = handle_whatsapp_access(store, inbound=_InboundAdmin(), account_id="wa-default", text="yes")
    assert out is None
    assert store.pending[0]["status"] == "pending"


def test_handle_whatsapp_access_admin_quoted_notify_without_intent_passes_to_llm(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _setup_admin_store()
    store.pending.append(
        {
            "id": "pending2",
            "external_user_id": "8615601877957@s.whatsapp.net",
            "push_name": "Bob",
            "phone": "8615601877957",
            "status": "pending",
        }
    )
    store.notify_map[("111@s.whatsapp.net", "notify_stanza_2")] = "pending2"
    inbound = type("_InboundAdminQuoteHello", (), {
        "channel": "whatsapp",
        "external_user_id": "111@s.whatsapp.net",
        "external_chat_id": "111@s.whatsapp.net",
        "metadata": {
            "raw": {
                "quotedStanzaId": "notify_stanza_2",
                "quotedText": "[oclaw] Unauthorized access request",
            }
        },
    })()
    out = handle_whatsapp_access(store, inbound=inbound, account_id="wa-default", text="hello")
    assert out is None
    assert store.pending[0]["status"] == "pending"


def test_handle_whatsapp_access_admin_yes_with_stanza_mapping(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _setup_admin_store()
    store.pending.append(
        {
            "id": "pending2",
            "external_user_id": "8615601877957@s.whatsapp.net",
            "push_name": "Bob",
            "phone": "8615601877957",
            "status": "pending",
        }
    )
    store.notify_map[("111@s.whatsapp.net", "notify_stanza_2")] = "pending2"
    inbound = type("_InboundAdminQuote", (), {
        "channel": "whatsapp",
        "external_user_id": "111@s.whatsapp.net",
        "external_chat_id": "111@s.whatsapp.net",
        "metadata": {
            "raw": {
                "id": "admin_reply_1",
                "participant": "111@s.whatsapp.net",
                "quotedStanzaId": "notify_stanza_2",
                "quotedText": "[oclaw] Unauthorized access request",
            }
        },
    })()
    out = handle_whatsapp_access(store, inbound=inbound, account_id="wa-default", text="yes")
    assert out is not None
    assert store.pending[0]["status"] == "approved"
    assert store.contacts.get("8615601877957", {}).get("list_type") == "whitelist"
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    md = replies[0].get("metadata") if replies and isinstance(replies[0], dict) else {}
    assert md.get("quote_stanza_id") == "admin_reply_1"


def test_handle_whatsapp_access_admin_yes_with_quoted_text_fallback(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _setup_admin_store()
    store.pending.append(
        {
            "id": "abcdef0123456789abcdef0123456789",
            "external_user_id": "8615601877957@s.whatsapp.net",
            "push_name": "Bob",
            "phone": "8615601877957",
            "status": "pending",
        }
    )
    inbound = type("_InboundAdminQuoteText", (), {
        "channel": "whatsapp",
        "external_user_id": "111@s.whatsapp.net",
        "external_chat_id": "111@s.whatsapp.net",
        "metadata": {
            "raw": {
                "id": "admin_reply_2",
                "participant": "111@s.whatsapp.net",
                "quotedStanzaId": "missing_stanza",
                "quotedText": "[oclaw] Unauthorized access request\nRequest: abcdef0123456789abcdef0123456789\n",
            }
        },
    })()
    out = handle_whatsapp_access(store, inbound=inbound, account_id="wa-default", text="no")
    assert out is not None
    assert store.pending[0]["status"] == "denied"
    assert store.contacts.get("8615601877957", {}).get("list_type") == "blacklist"


def test_handle_whatsapp_access_denied_enqueues_notify_with_pending_source(monkeypatch) -> None:
    import json
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _AccessStore()
    store.contacts["111@s.whatsapp.net"] = {
        "external_user_id": "111@s.whatsapp.net",
        "list_type": "admin",
    }
    out = handle_whatsapp_access(store, inbound=_Inbound(), account_id="wa-default", text="hello")
    assert out is not None
    assert store.outbound
    source = store.outbound[0].get("source")
    parsed = json.loads(str(source))
    assert parsed.get("kind") == "whatsapp_access_pending"
    assert parsed.get("pending_id")


def test_handle_whatsapp_access_allows_admin_via_lid_alias(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _AccessStore()
    store.contacts["8618142387786@s.whatsapp.net"] = {
        "external_user_id": "8618142387786@s.whatsapp.net",
        "phone": "8618142387786",
        "list_type": "admin",
    }
    out = handle_whatsapp_access(store, inbound=_InboundGroup(), account_id="wa-default", text="hello")
    assert out is None


def test_handle_whatsapp_access_denied_unknown_user(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _AccessStore()
    store.contacts["111@s.whatsapp.net"] = {"external_user_id": "111@s.whatsapp.net", "list_type": "admin"}
    out = handle_whatsapp_access(store, inbound=_Inbound(), account_id="wa-default", text="hello")
    assert out is not None
    assert out.get("whatsapp_access") == "denied"
    assert "8615601877957@s.whatsapp.net" not in store.contacts
    assert store.pending
    assert store.pending[0].get("phone") == "8615601877957"
    assert store.outbound
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies and "denied" in str(replies[0].get("text") or "").lower()


def test_handle_whatsapp_access_allows_whitelisted_user(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _AccessStore()
    store.contacts["8615601877957@s.whatsapp.net"] = {
        "external_user_id": "8615601877957@s.whatsapp.net",
        "phone": "8615601877957",
        "list_type": "whitelist",
    }
    out = handle_whatsapp_access(store, inbound=_Inbound(), account_id="wa-default", text="hello")
    assert out is None
    assert store.identities.get("8615601877957@s.whatsapp.net")


def test_handle_whatsapp_access_denied_group_includes_mention_and_quote(monkeypatch) -> None:
    import runtime.application.gateway.whatsapp_inbound_access as mod

    monkeypatch.setattr(mod, "resolve_whatsapp_tenant_id", lambda store, account_id: "tenant1")
    store = _AccessStore()
    inbound = type("_InboundGroupDenied", (), {
        "channel": "whatsapp",
        "is_group": True,
        "external_user_id": "333@s.whatsapp.net",
        "external_chat_id": "999@g.us",
        "metadata": {"raw": {"pushName": "Bob", "id": "stanza_1", "participant": "333@s.whatsapp.net"}},
    })()
    out = handle_whatsapp_access(store, inbound=inbound, account_id="wa-default", text="hello")
    assert out is not None
    assert out.get("whatsapp_access") == "denied"
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies and isinstance(replies[0], dict)
    md = replies[0].get("metadata") if isinstance(replies[0].get("metadata"), dict) else {}
    assert md.get("mention_jids") == ["333@s.whatsapp.net"]
    assert md.get("quote_remote_jid") == "999@g.us"
    assert md.get("quote_stanza_id") == "stanza_1"
    assert md.get("quote_participant") == "333@s.whatsapp.net"
