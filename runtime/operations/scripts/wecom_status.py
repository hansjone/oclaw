from __future__ import annotations

import json
from datetime import datetime, timezone

from svc.config.paths import db_path
from svc.integrations.wecom_client import WeComClient
from svc.persistence.sqlite_store import SqliteStore


def _fmt_ts(ts: str) -> str:
    try:
        n = int(str(ts).strip())
        return datetime.fromtimestamp(n, tz=timezone.utc).astimezone().isoformat()
    except Exception:
        return ""


def main() -> int:
    store = SqliteStore(db_path())
    client = WeComClient(store)
    print("ok=1")
    print(f"mode={client.mode()}")
    bot_id = str(store.get_setting("wecom_bot_id") or "").strip()
    print(f"bot_id={bot_id}")

    auto_bind = str(store.get_setting("wecom_auto_bind_enabled") or "1").strip()
    auto_tenant = str(store.get_setting("wecom_auto_bind_tenant_name") or "Team").strip() or "Team"
    auto_role = str(store.get_setting("wecom_auto_bind_role") or "member").strip() or "member"
    print(f"auto_bind_enabled={auto_bind}")
    print(f"auto_bind_tenant={auto_tenant}")
    print(f"auto_bind_role={auto_role}")

    last_ts = str(store.get_setting("wecom_last_msg_ts") or "").strip()
    last_user = str(store.get_setting("wecom_last_from_user") or "").strip()
    last_cmd = str(store.get_setting("wecom_last_cmd") or "").strip()
    last_raw_from_user = str(store.get_setting("wecom_last_raw_from_user") or "").strip()
    last_parse_error = str(store.get_setting("wecom_last_parse_error") or "").strip()
    last_outbound_mode = str(store.get_setting("wecom_last_outbound_mode") or "").strip()
    last_outbound_error = str(store.get_setting("wecom_last_outbound_error") or "").strip()
    print(f"last_from_user={last_user}")
    print(f"last_raw_from_user={last_raw_from_user}")
    print(f"last_cmd={last_cmd}")
    print(f"last_parse_error={last_parse_error}")
    print(f"last_outbound_mode={last_outbound_mode}")
    print(f"last_outbound_error={last_outbound_error}")
    print(f"last_msg_ts={last_ts}")
    print(f"last_msg_local={_fmt_ts(last_ts)}")

    raw_recent = str(store.get_setting("wecom_recent_from_users") or "[]")
    try:
        recent = json.loads(raw_recent)
    except Exception:
        recent = []
    if not isinstance(recent, list):
        recent = []
    print("recent_from_users=" + json.dumps(recent[:20], ensure_ascii=False))

    idents = store.list_channel_identities(channel="wecom", limit=50)
    print(f"bound_identities={len(idents)}")
    for x in idents[:20]:
        print(
            "identity="
            + json.dumps(
                {
                    "external_user_id": x.get("external_user_id"),
                    "display_name": x.get("display_name"),
                    "role": x.get("role"),
                    "tenant_id": x.get("tenant_id"),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
