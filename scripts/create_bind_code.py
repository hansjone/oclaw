from __future__ import annotations

import secrets
import sys

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore


def main() -> int:
    store = SqliteStore(db_path())
    tenants = store.list_tenants(limit=1)
    if tenants:
        tenant_id = tenants[0]["id"]
        tenant_name = tenants[0]["name"]
    else:
        created = store.create_tenant("Team")
        tenant_id = created["id"]
        tenant_name = created["name"]

    role = "member"
    if len(sys.argv) >= 2 and str(sys.argv[1]).strip():
        role = str(sys.argv[1]).strip()

    code = secrets.token_urlsafe(6)
    store.create_bind_code(tenant_id=tenant_id, role=role, code=code)

    print(f"tenant={tenant_name} ({tenant_id})")
    print(f"role={role}")
    print(f"bind_code={code}")
    print(f"wecom_cmd=bind {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

