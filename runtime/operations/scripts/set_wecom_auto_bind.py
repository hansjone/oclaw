from __future__ import annotations

import sys

from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store


def _to_bool(v: str) -> str:
    return "1" if str(v).strip().lower() in ("1", "true", "yes", "on") else "0"


def main() -> int:
    args = [str(x).strip() for x in sys.argv[1:]]
    if not args:
        print("usage:")
        print("  python -m scripts.set_wecom_auto_bind on|off")
        print("  python -m scripts.set_wecom_auto_bind on <tenant_name> <role>")
        print("  python -m scripts.set_wecom_auto_bind show")
        return 2

    cmd = args[0].lower()
    store = get_assistant_store()

    if cmd == "show":
        enabled = str(store.get_setting("wecom_auto_bind_enabled") or "1").strip()
        tenant_name = str(store.get_setting("wecom_auto_bind_tenant_name") or "Team").strip() or "Team"
        role = str(store.get_setting("wecom_auto_bind_role") or "member").strip() or "member"
        print("ok=1")
        print(f"enabled={enabled}")
        print(f"tenant_name={tenant_name}")
        print(f"role={role}")
        return 0

    if cmd not in ("on", "off"):
        print("error=invalid_command")
        return 2

    enabled = _to_bool("1" if cmd == "on" else "0")
    tenant_name = (args[1] if len(args) >= 2 else "Team").strip() or "Team"
    role = (args[2] if len(args) >= 3 else "member").strip() or "member"

    store.set_setting("wecom_auto_bind_enabled", enabled)
    store.set_setting("wecom_auto_bind_tenant_name", tenant_name)
    store.set_setting("wecom_auto_bind_role", role)

    print("ok=1")
    print(f"enabled={enabled}")
    print(f"tenant_name={tenant_name}")
    print(f"role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
