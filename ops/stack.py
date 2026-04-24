from __future__ import annotations

import argparse
import sys
from typing import Any

from .mcp_env import gateway_mcp_env_extras
from .runtime import default_python_command, start_service, status_services, stop_all


def cmd_stack_up(args: argparse.Namespace) -> int:
    started: list[tuple[str, int]] = []
    gateway_cmd = default_python_command(
        [
            "-m",
            "oclaw.ops",
            "gateway",
            "start",
            "--host",
            args.gateway_host,
            "--port",
            str(args.gateway_port),
        ]
    )
    started.append(("gateway", start_service(name="gateway", command=gateway_cmd, env=gateway_mcp_env_extras())))

    channel_cmd = default_python_command(
        [
            "-m",
            "oclaw.ops",
            "channel",
            args.channel,
            "start",
            "--mode",
            args.channel_mode,
            "--interval",
            str(args.channel_interval),
            "--deliver-outbound" if args.deliver_outbound else "--no-deliver-outbound",
        ]
    )
    if args.channel_mode == "pull" and args.pull_url:
        channel_cmd.extend(["--pull-url", args.pull_url])
    started.append((f"channel:{args.channel}", start_service(name=f"channel:{args.channel}", command=channel_cmd)))

    if args.with_ui:
        print(
            "hint=--with-ui ignored: Streamlit is disabled; use Ops Chat at "
            f"http://127.0.0.1:{int(args.gateway_port)}/chat",
            file=sys.stderr,
        )
    print("ok=1")
    for name, pid in started:
        print(f"{name}_pid={pid}")
    print("hint=use `python -m oclaw.ops stack status` to check running services")
    return 0


def cmd_stack_status(_args: argparse.Namespace) -> int:
    rows = status_services()
    print("ok=1")
    print(f"services={len(rows)}")
    for r in rows:
        print(f"service={r.name} pid={r.pid} running={1 if r.running else 0}")
    return 0


def cmd_stack_down(_args: argparse.Namespace) -> int:
    stopped = stop_all()
    print("ok=1")
    print(f"stopped={','.join(stopped)}")
    return 0


def register_stack_parser(root_subparsers: Any) -> None:
    stack = root_subparsers.add_parser("stack", help="Manage local multi-service stack")
    sub = stack.add_subparsers(dest="stack_cmd", required=True)
    up = sub.add_parser("up", help="Start gateway + channel worker")
    up.add_argument("--channel", default="wecom")
    up.add_argument("--channel-mode", choices=["ws", "pull", "mock"], default="ws")
    up.add_argument("--channel-interval", type=float, default=3.0)
    up.add_argument("--deliver-outbound", action=argparse.BooleanOptionalAction, default=True)
    up.add_argument("--pull-url", default=None)
    up.add_argument("--gateway-host", default="0.0.0.0")
    up.add_argument("--gateway-port", type=int, default=8787)
    up.add_argument("--with-ui", action="store_true", help="Ignored (deprecated): legacy Streamlit; use http://127.0.0.1:<gateway-port>/chat")
    up.add_argument("--ui-port", type=int, default=8501, help="Unused (reserved for compatibility)")
    up.set_defaults(func=cmd_stack_up)
    status = sub.add_parser("status", help="Show stack service status")
    status.set_defaults(func=cmd_stack_status)
    down = sub.add_parser("down", help="Stop all stack services started by ops runtime")
    down.set_defaults(func=cmd_stack_down)
