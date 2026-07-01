from __future__ import annotations

import os
from typing import Any


def resolve_whatsapp_tenant_id(store: Any, *, account_id: str) -> str:
    account = store.find_user_by_channel_account(channel="whatsapp", account_id=str(account_id or "").strip())
    if account and str(account.get("tenant_id") or "").strip():
        return str(account["tenant_id"])
    return str(os.getenv("OCLAW_DEFAULT_TENANT_ID") or "default").strip() or "default"


__all__ = ["resolve_whatsapp_tenant_id"]
