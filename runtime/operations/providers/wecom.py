from __future__ import annotations

import argparse
import os
import secrets
import sys
from argparse import _SubParsersAction

from interfaces.channels.wecom.longconn_runner import run_forever as run_wecom_longconn
from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store

from .base import ChannelProvider

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


def _store() -> SqliteStore:
    return get_assistant_store()


class WecomProvider(ChannelProvider):
    @property
    def name(self) -> str:
        return "wecom"

    def register(self, channel_subparsers: _SubParsersAction) -> None:
        p = channel_subparsers.add_parser(self.name, help="WeCom channel operations")
        sub = p.add_subparsers(dest="channel_action", required=True)

        start = sub.add_parser("start", help="Start WeCom long connection runner")
        start.add_argument("--mode", choices=["ws", "pull", "mock"], help="Runner mode")
        start.add_argument("--interval", type=float, help="Polling interval for non-ws modes")
        start.add_argument("--deliver-outbound", action=argparse.BooleanOptionalAction, default=None)
        start.add_argument("--ws-url", help="Override websocket URL")
        start.add_argument("--pull-url", help="Pull mode URL")
        start.set_defaults(func=self._cmd_start)

        status = sub.add_parser("status", help="Show WeCom status snapshot")
        status.set_defaults(func=self._cmd_status)

        doctor = sub.add_parser("doctor", help="Run lightweight environment checks")
        doctor.set_defaults(func=self._cmd_doctor)

        config = sub.add_parser("config", help="Configure WeCom credentials")
        config_sub = config.add_subparsers(dest="config_cmd", required=True)
        conf_set = config_sub.add_parser("set", help="Set bot credentials (bot_api)")
        conf_set.add_argument("--bot-id", required=True)
        conf_set.add_argument("--bot-secret", required=True)
        conf_set.set_defaults(func=self._cmd_config_set)

        auto_bind = sub.add_parser("auto-bind", help="Manage auto bind behavior")
        auto_bind.add_argument("action", choices=["on", "off", "show"])
        auto_bind.add_argument("tenant_name", nargs="?")
        auto_bind.add_argument("role", nargs="?")
        auto_bind.set_defaults(func=self._cmd_auto_bind)

        smoke = sub.add_parser("smoke", help="Run smoke test")
        smoke.add_argument("--ws", action="store_true", help="Run bot websocket subscribe smoke")
        smoke.set_defaults(func=self._cmd_smoke)

        create_bind = sub.add_parser("create-bind", help="Create a bind code")
        create_bind.add_argument("--role", default="member")
        create_bind.set_defaults(func=self._cmd_create_bind)

        unbind = sub.add_parser("unbind", help="Clear local wecom config and wecom bindings")
        unbind.set_defaults(func=self._cmd_unbind)

        switch = sub.add_parser("switch-bot", help="Switch to a new bot quickly")
        switch.add_argument("bot_id")
        switch.add_argument("bot_secret")
        switch.set_defaults(func=self._cmd_switch)

    def _cmd_start(self, args: argparse.Namespace) -> int:
        if args.mode:
            os.environ["WECOM_LONGCONN_MODE"] = args.mode
        if args.interval is not None:
            os.environ["WECOM_LONGCONN_INTERVAL_SEC"] = str(args.interval)
        if args.deliver_outbound is not None:
            os.environ["WECOM_LONGCONN_DELIVER_OUTBOUND"] = "1" if args.deliver_outbound else "0"
        if args.ws_url:
            os.environ["WECOM_LONGCONN_WS_URL"] = args.ws_url
        if args.pull_url:
            os.environ["WECOM_LONGCONN_PULL_URL"] = args.pull_url
        return run_wecom_longconn()

    def _cmd_status(self, _args: argparse.Namespace) -> int:
        from runtime.operations.scripts.wecom_status import main as status_main

        return status_main()

    def _cmd_doctor(self, _args: argparse.Namespace) -> int:
        s = _store()
        print("ok=1")
        print(f"db_path={db_path()}")
        mode = str(s.get_setting("wecom_mode") or "").strip() or "auto"
        print(f"mode_setting={mode}")
        print(f"bot_id_set={1 if s.get_setting('wecom_bot_id') else 0}")
        print(f"bot_secret_set={1 if s.get_secret('wecom_bot_secret') else 0}")
        try:
            import websocket  # type: ignore  # noqa: F401

            print("websocket_client=ok")
        except Exception as exc:
            print(f"websocket_client=missing ({type(exc).__name__})")
        return 0

    def _cmd_config_set(self, args: argparse.Namespace) -> int:
        s = _store()
        s.set_setting("wecom_mode", "bot_api")
        s.set_setting("wecom_bot_id", args.bot_id)
        s.set_secret("wecom_bot_secret", args.bot_secret)
        s.delete_setting("wecom_access_token_cache")
        print("ok=1")
        print("mode=bot_api")
        return 0

    def _cmd_auto_bind(self, args: argparse.Namespace) -> int:
        s = _store()
        if args.action == "show":
            print("ok=1")
            print(f"enabled={str(s.get_setting('wecom_auto_bind_enabled') or '1').strip()}")
            print(f"tenant_name={str(s.get_setting('wecom_auto_bind_tenant_name') or 'Team').strip() or 'Team'}")
            print(f"role={str(s.get_setting('wecom_auto_bind_role') or 'member').strip() or 'member'}")
            return 0
        enabled = "1" if args.action == "on" else "0"
        s.set_setting("wecom_auto_bind_enabled", enabled)
        if args.tenant_name:
            s.set_setting("wecom_auto_bind_tenant_name", args.tenant_name.strip())
        if args.role:
            s.set_setting("wecom_auto_bind_role", args.role.strip())
        print("ok=1")
        print(f"enabled={enabled}")
        return 0

    def _cmd_smoke(self, args: argparse.Namespace) -> int:
        from runtime.operations.scripts.wecom_smoke_test import main as smoke_main

        old = sys.argv
        try:
            argv = ["wecom_smoke_test.py"]
            if args.ws:
                argv.append("--ws")
            sys.argv = argv
            return smoke_main()
        finally:
            sys.argv = old

    def _cmd_create_bind(self, args: argparse.Namespace) -> int:
        s = _store()
        tenants = s.list_tenants(limit=1)
        if tenants:
            tenant_id = tenants[0]["id"]
            tenant_name = tenants[0]["name"]
        else:
            t = s.create_tenant("Team")
            tenant_id = t["id"]
            tenant_name = t["name"]
        role = args.role or "member"
        code = secrets.token_urlsafe(6)
        s.create_bind_code(tenant_id=tenant_id, role=role, code=code)
        print(f"tenant={tenant_name} ({tenant_id})")
        print(f"role={role}")
        print(f"bind_code={code}")
        print(f"wecom_cmd=bind {code}")
        return 0

    def _cmd_unbind(self, _args: argparse.Namespace) -> int:
        s = _store()
        with s._connect() as conn:
            cur_ident = conn.execute("DELETE FROM channel_identity WHERE channel = ?", ("wecom",))
            ident_deleted = int(cur_ident.rowcount or 0)
            cur_sess = conn.execute("DELETE FROM channel_session WHERE channel = ?", ("wecom",))
            sess_deleted = int(cur_sess.rowcount or 0)
        for k in _CLEAR_KEYS:
            s.delete_setting(k)
        print("ok=1")
        print(f"deleted_channel_identity={ident_deleted}")
        print(f"deleted_channel_session={sess_deleted}")
        return 0

    def _cmd_switch(self, args: argparse.Namespace) -> int:
        s = _store()
        s.set_setting("wecom_mode", "bot_api")
        s.set_setting("wecom_bot_id", args.bot_id)
        s.set_secret("wecom_bot_secret", args.bot_secret)
        for k in _CLEAR_KEYS:
            if k not in ("wecom_bot_id", "wecom_bot_secret", "wecom_mode"):
                s.delete_setting(k)
        print("ok=1")
        print("mode=bot_api")
        print(f"bot_id={args.bot_id}")
        print("next=python -m runtime.operations channel wecom start")
        return 0

