"""访问密码解析（环境变量 + 数据库）；Streamlit secrets 在认证模块中处理。"""

from __future__ import annotations

import os

from oclaw.platform.persistence.sqlite_store import SqliteStore


def load_expected_password(store: SqliteStore, *, extra_candidate: str | None = None) -> str | None:
    pwd = (os.getenv("AIA_ASSISTANT_PASSWORD") or "").strip()
    if not pwd:
        pwd = (os.getenv("OPS_ASSISTANT_PASSWORD") or "").strip()
    if not pwd and extra_candidate:
        pwd = extra_candidate.strip()
    if not pwd:
        pwd = (store.get_secret("auth_password") or "").strip()
    return pwd if pwd else None


__all__ = ["load_expected_password"]
