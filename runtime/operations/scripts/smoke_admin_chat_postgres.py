#!/usr/bin/env python3
"""HTTP 冒烟：加载 _local/system.env → 用当前配置的 PG → 登录 → 建会话 → POST 一条消息 → 拉历史。

不依赖外网 LLM：强制 ``AIA_ASSISTANT_MODE=rule``（本地规则回复）。

用法（仓库根）::

    python runtime/operations/scripts/smoke_admin_chat_postgres.py

退出码 0 表示全流程成功且 ``messages`` 里同时有 user 与 assistant。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo_root()
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from svc.config.bootstrap_env import load_system_env

    load_system_env(force=True)

    if (os.getenv("AIA_ASSISTANT_DB_BACKEND") or "").strip().lower() not in (
        "postgresql",
        "pg",
        "postgres",
    ):
        print("AIA_ASSISTANT_DB_BACKEND 不是 postgresql，本脚本用于测 PG。", file=sys.stderr)
        return 2

    # 不覆盖已有 shell 变量；仅保证规则模式（免外网）
    os.environ.setdefault("AIA_ASSISTANT_MODE", "rule")
    os.environ["AIA_ASSISTANT_MODE"] = "rule"

    tmp = tempfile.mkdtemp(prefix="oclaw-smoke-ws-")
    os.environ["OPS_WORKSPACE_ROOT"] = tmp

    from svc.config import database as db_cfg
    from svc.persistence.assistant_store import get_assistant_store, reset_assistant_store_singleton
    from svc.persistence.db.engine import clear_assistant_engine_cache

    clear_assistant_engine_cache()
    reset_assistant_store_singleton()

    if db_cfg.assistant_db_backend() != "postgresql":
        print("assistant_db_backend() 不是 postgresql", file=sys.stderr)
        return 2

    from svc.persistence.sqlite_store import (
        LLM_BUILTIN_RULE_PROFILE_ID,
        SqliteStore,
        active_llm_profile_setting_key,
    )

    store = get_assistant_store()
    assert isinstance(store, SqliteStore) and store._use_pg

    tag = uuid.uuid4().hex[:10]
    pw = f"smoke-{tag}"
    t = store.create_tenant(f"pg-smoke-{tag}")
    tenant_id = str(t["id"])
    # 不用 administrator：共享库里会走全局模型池与已导入的 OpenAI profile，易在无 Key 时得到空 reply。
    u = store.create_user_account(
        tenant_id=tenant_id,
        username=f"smoke_{tag}",
        display_name="Smoke",
        role="owner",
        password_hash=hashlib.sha256(pw.encode("utf-8")).hexdigest(),
        is_active=True,
    )
    user_id = str(u.get("id") or "").strip()
    if not user_id:
        print("create_user_account returned no id", u, file=sys.stderr)
        return 1
    store.grant_llm_profile_to_user(
        tenant_id=tenant_id,
        profile_id=LLM_BUILTIN_RULE_PROFILE_ID,
        user_id=user_id,
    )
    store.set_setting(
        active_llm_profile_setting_key(user_id, f"smoke_{tag}"),
        LLM_BUILTIN_RULE_PROFILE_ID,
    )

    from fastapi.testclient import TestClient

    from interfaces.http.fastapi_app import create_app

    client = TestClient(create_app())
    try:
        client.post("/admin/api/auth/bootstrap", json={})
        lr = client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": tenant_id,
                "username": f"smoke_{tag}",
                "password": pw,
                "purpose": "console",
            },
        )
        lj = lr.json()
        if not lj.get("ok"):
            print("login failed:", lr.status_code, lj, file=sys.stderr)
            return 1
        token = str(lj.get("token") or "")
        h = {"authorization": f"Bearer {token}"}

        cr = client.post("/admin/api/chat/sessions", json={"title": f"smoke-{tag}"}, headers=h)
        if cr.status_code != 200:
            print("create session:", cr.status_code, cr.text, file=sys.stderr)
            return 1
        cj = cr.json()
        if not cj.get("ok"):
            print("create session body:", cj, file=sys.stderr)
            return 1
        sid = str((cj.get("session") or {}).get("id") or "")
        if not sid:
            print("no session id", cj, file=sys.stderr)
            return 1

        mr = client.post(
            f"/admin/api/chat/sessions/{sid}/messages",
            json={"text": "ping-smoke-pg"},
            headers=h,
        )
        if mr.status_code != 200:
            print("send message:", mr.status_code, mr.text, file=sys.stderr)
            return 1
        mj = mr.json()
        if not mj.get("ok"):
            print("send message body:", mj, file=sys.stderr)
            return 1
        reply = str(mj.get("reply") or "")
        if not reply.strip():
            print("empty reply (unexpected for rule mode)", mj, file=sys.stderr)
            return 1

        gr = client.get(f"/admin/api/chat/sessions/{sid}/messages", headers=h)
        if gr.status_code != 200:
            print("list messages:", gr.status_code, gr.text, file=sys.stderr)
            return 1
        gj = gr.json()
        msgs = gj.get("messages") or []
        roles = [str(m.get("role") or "") for m in msgs if isinstance(m, dict)]
        if "user" not in roles or "assistant" not in roles:
            print("roles mismatch:", roles, "full ok=", gj.get("ok"), file=sys.stderr)
            return 1

        print("OK smoke_admin_chat_postgres")
        print("  tenant_id=", tenant_id)
        print("  session_id=", sid)
        print("  reply_len=", len(reply))
        print("  message_count=", len(msgs), "roles=", roles)
        return 0
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
