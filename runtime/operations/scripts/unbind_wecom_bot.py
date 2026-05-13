from __future__ import annotations

from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore


_CLEAR_KEYS = [
    "wecom_mode",
    "wecom_bot_id",
    "wecom_bot_secret",
    "wecom_corp_id",
    "wecom_agent_id",
    "wecom_agent_secret",
    "wecom_access_token_cache",
    "wecom_last_msg_ts",
    "wecom_last_from_user",
    "wecom_recent_from_users",
    "wecom_last_cmd",
    "wecom_last_unknown_cmd_payload",
    "wecom_last_raw_body",
    "wecom_last_raw_from_user",
    "wecom_last_parse_error",
]


def main() -> int:
    store = SqliteStore(db_path())
    with store._connect() as conn:  # internal cleanup script; safe to use store connection helper
        cur_ident = conn.execute("DELETE FROM channel_identity WHERE channel = ?", ("wecom",))
        ident_deleted = int(cur_ident.rowcount or 0)
        cur_sess = conn.execute("DELETE FROM channel_session WHERE channel = ?", ("wecom",))
        sess_deleted = int(cur_sess.rowcount or 0)

    for k in _CLEAR_KEYS:
        store.delete_setting(k)

    print("ok=1")
    print("action=unbind_wecom_bot")
    print(f"deleted_channel_identity={ident_deleted}")
    print(f"deleted_channel_session={sess_deleted}")
    print("cleared_settings=" + ",".join(_CLEAR_KEYS))
    print("next=python -m runtime.operations channel wecom config set --type bot --bot-id <bot_id> --bot-secret <bot_secret>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
