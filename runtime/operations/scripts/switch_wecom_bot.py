from __future__ import annotations

import sys

from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore


_CLEAR_KEYS = [
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
    args = [str(x).strip() for x in sys.argv[1:]]
    if len(args) < 2:
        print("usage: python -m scripts.switch_wecom_bot <bot_id> <bot_secret>")
        return 2
    bot_id, bot_secret = args[0], args[1]
    if not bot_id or not bot_secret:
        print("error=missing_required_args")
        return 2

    store = SqliteStore(db_path())
    store.set_setting("wecom_mode", "bot_api")
    store.set_setting("wecom_bot_id", bot_id)
    store.set_secret("wecom_bot_secret", bot_secret)
    for k in _CLEAR_KEYS:
        store.delete_setting(k)

    print("ok=1")
    print("mode=bot_api")
    print(f"bot_id={bot_id}")
    print("cleared=" + ",".join(_CLEAR_KEYS))
    print("next=python -m runtime.operations stack up --channel wecom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
