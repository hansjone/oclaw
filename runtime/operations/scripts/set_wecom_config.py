from __future__ import annotations

import sys

from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore


def main() -> int:
    args = [str(x).strip() for x in sys.argv[1:]]
    if not args:
        print("usage:")
        print("  python -m scripts.set_wecom_config <bot_id> <bot_secret>")
        return 2

    store = SqliteStore(db_path())
    if len(args) < 2:
        print("error=missing_required_args")
        return 2
    bot_id, bot_secret = args[0], args[1]
    if not bot_id or not bot_secret:
        print("error=missing_required_args")
        return 2
    store.set_setting("wecom_mode", "bot_api")
    store.set_setting("wecom_bot_id", bot_id)
    store.set_secret("wecom_bot_secret", bot_secret)
    store.delete_setting("wecom_access_token_cache")
    print("ok=1")
    print("mode=bot_api")
    print("saved=wecom_bot_id,wecom_bot_secret(secret)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
