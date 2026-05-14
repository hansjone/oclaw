#!/usr/bin/env python3
"""对「正在运行」的网关发一条与控制台 Chat 相同的 HTTP 消息，并打印模型 / 会话模式 / 响应 / 库尾行。

本机执行（需网关已启动，且与浏览器访问的是同一 ``--base-url``）::

    # 方式一：用密码登录（tenant 可省略，默认取库里第一个团队）
    set AIA_LIVE_CHAT_PASSWORD=你的控制台密码
    python runtime/operations/scripts/live_chat_probe.py --session-id <浏览器地址栏里的会话id>

    # 方式二：从浏览器开发者工具复制 Bearer token
    python runtime/operations/scripts/live_chat_probe.py --session-id <id> --token <jwt>

可选：加 ``--dump-db`` 时，会再读 ``_local/system.env`` 里的 ``AIA_ASSISTANT_*``，直连同一 PG/SQLite 打印该会话最近几条 ``chat_message``（用于对照「HTTP 成功但库里没有 assistant」）。

注意：Cursor 里的 AI **不能**替你连本机浏览器或 WebSocket；此脚本等价于你自己在 Network 里手动 POST，只是自动带上当前「选用模型」与会话模式字段。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_local_env_for_db_only() -> None:
    root = _repo_root()
    p = root / "_local" / "system.env"
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, rest = s.partition("=")
        key = k.strip()
        if not key or key in os.environ:
            continue
        if not key.startswith("AIA_ASSISTANT_") and key not in (
            "OPS_ASSISTANT_DB_BACKEND",
            "OPS_ASSISTANT_DATABASE_URL",
            "OPS_ASSISTANT_DB_PATH",
        ):
            continue
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        os.environ[key] = val


def _dump_db_messages(session_id: str, limit: int) -> None:
    _load_local_env_for_db_only()
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import func, select

    from svc.persistence.db.engine import clear_assistant_engine_cache, get_assistant_engine
    from svc.persistence.assistant_store import reset_assistant_store_singleton
    from svc.persistence.db.tables import chat_message

    clear_assistant_engine_cache()
    reset_assistant_store_singleton()
    eng = get_assistant_engine()
    print("\n--- DB (same env as _local/system.env assistant store) ---")
    print("engine:", str(eng.url).split("@")[-1])
    tc_len = func.length(func.coalesce(chat_message.c.tool_calls, ""))
    stmt = (
        select(
            chat_message.c.id,
            chat_message.c.role,
            chat_message.c.event_type,
            func.length(func.coalesce(chat_message.c.content, "")).label("content_len"),
            (tc_len > 2).label("has_tc"),
        )
        .where(chat_message.c.session_id == session_id)
        .order_by(chat_message.c.id.desc())
        .limit(limit)
    )
    with eng.connect() as c:
        n = c.execute(
            select(func.count()).select_from(chat_message).where(chat_message.c.session_id == session_id)
        ).scalar()
        print("chat_message count:", int(n or 0))
        rows = list(c.execute(stmt).mappings())
    for r in reversed(rows):
        print(dict(r))


def _auth_header(token: str) -> dict[str, str]:
    t = str(token or "").strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return {"authorization": f"Bearer {t}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Live HTTP chat probe against running gateway")
    ap.add_argument("--base-url", default=os.getenv("AIA_LIVE_CHAT_BASE_URL", "http://127.0.0.1:8787").rstrip("/"))
    ap.add_argument("--session-id", required=True, help="当前 Chat 会话 id（与浏览器一致）")
    ap.add_argument("--text", default="请用一句话回复：当前探针在测试落库。", help="发送的正文")
    ap.add_argument("--token", default=os.getenv("AIA_LIVE_CHAT_TOKEN", "").strip(), help="Bearer token（可设环境变量）")
    ap.add_argument("--tenant-id", default=os.getenv("AIA_LIVE_CHAT_TENANT_ID", "").strip())
    ap.add_argument("--username", default=os.getenv("AIA_LIVE_CHAT_USERNAME", "administrator").strip())
    ap.add_argument("--password", default=os.getenv("AIA_LIVE_CHAT_PASSWORD", "").strip())
    ap.add_argument("--dump-db", action="store_true", help="发送后再读本地 assistant 库该会话消息尾")
    ap.add_argument("--db-tail", type=int, default=8, help="--dump-db 时打印最近几条")
    args = ap.parse_args()

    try:
        import httpx
    except ImportError:
        print("需要 httpx: pip install httpx", file=sys.stderr)
        return 2

    sid = str(args.session_id).strip()
    if not sid:
        print("session-id 为空", file=sys.stderr)
        return 2

    base = str(args.base_url).strip().rstrip("/")
    timeout = httpx.Timeout(300.0, connect=15.0)

    with httpx.Client(base_url=base, timeout=timeout) as client:
        token = str(args.token or "").strip()
        if not token:
            pw = str(args.password or "").strip()
            if not pw:
                print(
                    "未提供 token：请设置 --password 或环境变量 AIA_LIVE_CHAT_PASSWORD，"
                    "或 --token / AIA_LIVE_CHAT_TOKEN",
                    file=sys.stderr,
                )
                return 2
            r0 = client.post("/admin/api/auth/bootstrap", json={})
            if r0.status_code != 200:
                print("bootstrap", r0.status_code, r0.text, file=sys.stderr)
                return 1
            body: dict[str, Any] = {
                "username": str(args.username),
                "password": pw,
                "purpose": "console",
            }
            tid = str(args.tenant_id or "").strip()
            if tid:
                body["tenant_id"] = tid
            lr = client.post("/admin/api/auth/login", json=body)
            if lr.status_code != 200:
                print("login http", lr.status_code, lr.text, file=sys.stderr)
                return 1
            lj = lr.json()
            if not lj.get("ok"):
                print("login", lj, file=sys.stderr)
                return 1
            token = str(lj.get("token") or "").strip()
            if not token:
                print("login 无 token", lj, file=sys.stderr)
                return 1
            sess = lj.get("session") or {}
            print(
                "login ok tenant_id=",
                str(sess.get("tenant_id") or ""),
                "user_id=",
                str(sess.get("user_id") or ""),
                "username=",
                str(sess.get("username") or ""),
            )

        h = _auth_header(token)

        mr = client.get("/admin/api/models", headers=h)
        if mr.status_code != 200:
            print("GET /models", mr.status_code, mr.text, file=sys.stderr)
            return 1
        mj = mr.json()
        if not mj.get("ok"):
            print("models", mj, file=sys.stderr)
            return 1
        active = str(mj.get("active_llm_profile_id") or "")
        profiles = mj.get("profiles") or []
        name = ""
        mode = ""
        model = ""
        for p in profiles:
            if isinstance(p, dict) and str(p.get("id") or "") == active:
                name = str(p.get("name") or "")
                mode = str(p.get("mode") or "")
                model = str(p.get("model") or "")
                break
        print("\n--- 当前选用模型（与控制台一致） ---")
        print("active_llm_profile_id:", active)
        print("profile:", name, "| mode:", mode, "| model:", model)
        dbp = mj.get("db_path")
        if dbp is not None:
            print("gateway reports db_path:", dbp)

        gr = client.get(f"/admin/api/chat/sessions/{sid}/mode", headers=h)
        if gr.status_code != 200:
            print("GET session/mode", gr.status_code, gr.text, file=sys.stderr)
            return 1
        gj = gr.json()
        if not gj.get("ok"):
            print("session/mode", gj, file=sys.stderr)
            return 1
        print("\n--- 当前会话模式（将原样带入 POST） ---")
        print(json.dumps({k: gj.get(k) for k in ("interaction_mode", "specialist", "memory_mode", "execution_mode", "confirm_strategy", "plan_agent_version") if k in gj}, ensure_ascii=False))

        payload = {
            "text": str(args.text),
            "interaction_mode": gj.get("interaction_mode"),
            "specialist": gj.get("specialist"),
            "memory_mode": gj.get("memory_mode"),
            "execution_mode": gj.get("execution_mode"),
        }
        pr = client.post(f"/admin/api/chat/sessions/{sid}/messages", headers=h, json=payload)
        if pr.status_code != 200:
            print("POST messages", pr.status_code, pr.text, file=sys.stderr)
            return 1
        pj = pr.json()
        print("\n--- POST /messages 响应 ---")
        print(json.dumps(pj, ensure_ascii=False, indent=2)[:8000])
        if not pj.get("ok"):
            return 1
        reply = str(pj.get("reply") or "")
        print("\nreply 非空:", bool(reply.strip()), "len=", len(reply))

        lr2 = client.get(f"/admin/api/chat/sessions/{sid}/messages?limit=50", headers=h)
        if lr2.status_code == 200:
            lj2 = lr2.json()
            msgs = lj2.get("messages") or []
            roles = [str(m.get("role") or "") for m in msgs if isinstance(m, dict)]
            print("\n--- GET messages（接口返回，最多 50 条） ---")
            print("count=", len(msgs), "roles=", roles[-12:])

    if args.dump_db:
        try:
            _dump_db_messages(sid, max(1, int(args.db_tail)))
        except Exception as e:
            print("\n--dump-db 失败（可忽略）:", type(e).__name__, e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
