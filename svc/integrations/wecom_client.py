from __future__ import annotations

from svc.persistence.sqlite_store import SqliteStore


class WeComClient:
    """WeCom AI bot (websocket / bot_api only)."""

    def __init__(self, store: SqliteStore):
        self.store = store

    def _bot_cfg(self) -> tuple[str, str]:
        bot_id = str(self.store.get_setting("wecom_bot_id") or "").strip()
        bot_secret = str(self.store.get_secret("wecom_bot_secret") or self.store.get_setting("wecom_bot_secret") or "").strip()
        if bot_id and bot_secret:
            return bot_id, bot_secret
        if bot_id:
            row = self.store.find_user_by_channel_account(channel="wecom", account_id=bot_id)
            if row:
                tid = str(row["tenant_id"])
                uid = str(row["user_id"])
                sk = f"wecom:bot_secret:{tid}:{uid}:{bot_id}"
                sec = str(self.store.get_secret(sk) or "").strip()
                if sec:
                    return bot_id, sec
        try:
            tenants = self.store.list_tenants(limit=1)
            tenant_id = str((tenants[0] or {}).get("id") or "") if tenants else ""
            if not tenant_id:
                return bot_id, bot_secret
            admin = self.store.get_user_by_username(tenant_id=tenant_id, username="administrator")
            user_id = str((admin or {}).get("id") or "")
            if not user_id:
                return bot_id, bot_secret
            accounts = self.store.list_user_channel_accounts(
                tenant_id=tenant_id, user_id=user_id, channel="wecom", include_inactive=False
            )
            if not accounts:
                return bot_id, bot_secret
            aid = str(accounts[0].get("account_id") or "").strip()
            if not aid:
                return bot_id, bot_secret
            scoped_key = f"wecom:bot_secret:{tenant_id}:{user_id}:{aid}"
            sec = str(self.store.get_secret(scoped_key) or "").strip()
            if aid and sec:
                return aid, sec
        except Exception:
            return bot_id, bot_secret
        return bot_id, bot_secret

    def mode_for_account(self, account_id: str) -> str:  # noqa: ARG002
        return "bot_api"

    def mode(self) -> str:
        return "bot_api"

    def get_bot_credentials(self) -> tuple[str, str]:
        bot_id, bot_secret = self._bot_cfg()
        if not bot_id or not bot_secret:
            raise RuntimeError("missing wecom bot config: wecom_bot_id / wecom_bot_secret")
        return bot_id, bot_secret


__all__ = ["WeComClient"]
