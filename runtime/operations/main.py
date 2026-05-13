from __future__ import annotations

import argparse
import os
import sys

from runtime.operations.hooks_cmd import register_hooks_parser
from runtime.operations.memory import register_memory_parser
from runtime.operations.providers.registry import build_channel_registry
from runtime.operations.stack import register_stack_parser


def _cmd_gateway_start(args: argparse.Namespace) -> int:
    if args.host:
        os.environ["AIA_ASSISTANT_GATEWAY_HOST"] = args.host
    if args.port is not None:
        os.environ["AIA_ASSISTANT_GATEWAY_PORT"] = str(args.port)
    from runtime.operations.mcp_env import apply_gateway_mcp_env_to_os

    apply_gateway_mcp_env_to_os()
    from interfaces.http.fastapi_app import main as fastapi_main

    return fastapi_main()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m runtime.operations", description="Unified operational CLI")
    root_sub = p.add_subparsers(dest="root_cmd", required=True)

    registry = build_channel_registry()
    channel = root_sub.add_parser("channel", help="Channel operations")
    channel_sub = channel.add_subparsers(dest="channel_name", required=True)
    channel_list = channel_sub.add_parser("list", help="List available channel providers")
    channel_list.set_defaults(func=lambda _a: (print("channels=" + ",".join(sorted(registry.keys()))) or 0))
    for provider in registry.values():
        provider.register(channel_sub)

    gateway = root_sub.add_parser("gateway", help="Gateway operations")
    gateway_sub = gateway.add_subparsers(dest="gateway_cmd", required=True)
    gateway_start = gateway_sub.add_parser("start", help="Start inbound HTTP gateway")
    gateway_start.add_argument("--host", default=None, help="Bind host")
    gateway_start.add_argument("--port", type=int, default=None, help="Bind port")
    gateway_start.set_defaults(func=_cmd_gateway_start)

    register_memory_parser(root_sub)
    register_stack_parser(root_sub)
    register_hooks_parser(root_sub)
    return p


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    if argv and len(argv) >= 1 and argv[0] == "wecom":
        argv = ["channel", "wecom", *argv[1:]]
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if not callable(func):
        parser.print_help()
        return 2
    return int(func(args) or 0)


__all__ = ["main"]
