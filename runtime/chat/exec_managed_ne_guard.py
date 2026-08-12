"""Guards for mcp__netx__execManagedNe / netx_exec_managed_ne spam on field turns."""

from __future__ import annotations

import json
import os
from typing import Any


def _env_int(name: str, default: int, *, min_v: int = 1, max_v: int = 50) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        n = int(raw)
    except Exception:
        return default
    return max(min_v, min(int(n), max_v))


def exec_managed_ne_single_budget() -> int:
    """Max single-NE execManagedNe calls per turn before requiring ne_ids/ume_ne_ids batch."""
    return _env_int("AIA_EXEC_MANAGED_NE_SINGLE_BUDGET", 6, min_v=2, max_v=30)


def exec_managed_ne_fail_budget() -> int:
    """Max failed execManagedNe (any mode) per turn before blocking further single-NE calls."""
    return _env_int("AIA_EXEC_MANAGED_NE_FAIL_BUDGET", 5, min_v=2, max_v=30)


def is_exec_managed_ne_tool(name: str) -> bool:
    raw = str(name or "").strip()
    if not raw:
        return False
    if "__" in raw:
        raw = raw.rsplit("__", 1)[-1]
    key = raw.strip().lower().replace("-", "_")
    return key in {"execmanagedne", "netx_exec_managed_ne", "exec_managed_ne"}


def is_batch_exec_args(args: dict[str, Any] | None) -> bool:
    a = args if isinstance(args, dict) else {}
    for key in ("ne_ids", "ume_ne_ids", "targets"):
        val = a.get(key)
        if isinstance(val, list) and len(val) > 0:
            return True
    return False


def normalize_exec_managed_ne_args(args: dict[str, Any] | None) -> dict[str, Any]:
    """Default / clamp read_timeout_sec so agents stop hitting 30s walls."""
    out = dict(args or {})
    rts = out.get("read_timeout_sec")
    if rts is None or str(rts).strip() == "":
        out["read_timeout_sec"] = 60
    else:
        try:
            out["read_timeout_sec"] = max(10, min(120, int(rts)))
        except Exception:
            out["read_timeout_sec"] = 60
    return out


def _parse_json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def load_turn_exec_managed_ne_stats(
    store: Any,
    *,
    session_id: str,
    turn_uuid: str,
) -> tuple[int, int, int]:
    """Return (single_calls, batch_calls, fail_calls) already persisted this turn."""
    tu = str(turn_uuid or "").strip()
    sid = str(session_id or "").strip()
    single = batch = fails = 0
    if not tu or not sid:
        return single, batch, fails
    try:
        rows = store.get_messages(session_id=sid, limit=500)
    except Exception:
        return single, batch, fails
    for m in rows or []:
        if str(getattr(m, "role", "") or "").strip().lower() != "tool":
            continue
        if str(getattr(m, "turn_uuid", "") or "").strip() != tu:
            continue
        ep = _parse_json_obj(getattr(m, "event_payload", None))
        name = str(ep.get("tool_name") or "").strip()
        if not name:
            raw_tc = getattr(m, "tool_calls", None)
            tc = _parse_json_obj(raw_tc)
            name = str(tc.get("name") or "").strip()
        if not is_exec_managed_ne_tool(name):
            continue
        mode = str(ep.get("exec_ne_mode") or "").strip().lower()
        if mode == "batch":
            batch += 1
        else:
            # Missing mode (older rows) → treat as single (conservative).
            single += 1
        if ep.get("ok") is False:
            fails += 1
            continue
        try:
            payload = json.loads(str(getattr(m, "content", "") or "") or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict) and payload.get("ok") is False:
            fails += 1
    return single, batch, fails


def budget_block_payload(
    *,
    reason: str,
    lang: str = "en",
    single_used: int,
    single_budget: int,
    fail_used: int = 0,
    fail_budget: int = 0,
) -> dict[str, Any]:
    en = str(lang or "").strip().lower().startswith("en")
    if reason == "fail_budget":
        code = "cli_fail_budget_exceeded"
        hint = (
            f"execManagedNe already failed {fail_used}/{fail_budget} times this turn. "
            "Stop one-NE loops; use ONE execManagedNe batch: "
            "ne_ids|ume_ne_ids + shared commands, or targets=[{ume_ne_id, commands},…] when commands differ — "
            "or summarize reachable failures; do not keep probing."
            if en
            else f"本轮 execManagedNe 已失败 {fail_used}/{fail_budget} 次。"
            "停止单台循环；改用一次 batch："
            "同命令用 ne_ids/ume_ne_ids，每台命令不同用 targets=[{ume_ne_id, commands},…]；"
            "或汇总可达性失败，勿继续盲探。"
        )
        err = "cli_fail_budget_exceeded"
    else:
        code = "cli_call_budget_exceeded"
        hint = (
            f"Single-NE execManagedNe budget exhausted ({single_used}/{single_budget} this turn). "
            "For more NEs call ONE execManagedNe batch: "
            "ne_ids[]/ume_ne_ids[] + shared commands, OR targets=[{ume_ne_id|ne_id, commands:[…]}, …] "
            "when each NE needs different CLI. Do not loop one-NE execManagedNe."
            if en
            else f"单台 execManagedNe 预算已用尽（本轮 {single_used}/{single_budget}）。"
            "更多网元请一次 batch：同命令用 ne_ids[]/ume_ne_ids[]；"
            "每台命令不同用 targets=[{ume_ne_id|ne_id, commands:[…]}, …]。禁止逐台循环。"
        )
        err = "cli_call_budget_exceeded"
    return {
        "ok": False,
        "error_code": code,
        "failure_class": "retry_guard",
        "error": err,
        "hint": hint,
        "example": {
            "ume_ne_ids": ["<id1>", "<id2>", "<id3>"],
            "commands": ["show version"],
            "read_timeout_sec": 90,
            "concurrency": 4,
        },
        "example_hetero_targets": {
            "targets": [
                {"ume_ne_id": "<huawei-id>", "commands": ["display optical-module brief"]},
                {"ume_ne_id": "<cisco-id>", "commands": ["show interface transceiver"]},
            ],
            "read_timeout_sec": 90,
            "concurrency": 4,
        },
        "single_used": int(single_used),
        "single_budget": int(single_budget),
        "fail_used": int(fail_used),
        "fail_budget": int(fail_budget),
    }


__all__ = [
    "budget_block_payload",
    "exec_managed_ne_fail_budget",
    "exec_managed_ne_single_budget",
    "is_batch_exec_args",
    "is_exec_managed_ne_tool",
    "load_turn_exec_managed_ne_stats",
    "normalize_exec_managed_ne_args",
]
