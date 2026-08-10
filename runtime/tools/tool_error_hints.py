from __future__ import annotations

import difflib
from typing import Any, Iterable


def suggest_tool_names(requested: str, available: Iterable[str], *, n: int = 5) -> list[str]:
    """Suggest close tool names for unregistered-tool errors."""
    name = str(requested or "").strip()
    pool = [str(x).strip() for x in available if str(x).strip()]
    if not name or not pool:
        return []
    # Prefer substring matches (mcp__netx__foo vs netx__foo / queryUmeAlarmsRaw).
    low = name.lower()
    substr = [p for p in pool if low in p.lower() or p.lower() in low]
    close = difflib.get_close_matches(name, pool, n=max(n, 8), cutoff=0.45)
    out: list[str] = []
    for x in substr + close:
        if x not in out:
            out.append(x)
        if len(out) >= n:
            break
    return out


def format_unregistered_tool_error(
    tool_name: str,
    available: Iterable[str],
    *,
    lang: str = "en",
) -> dict[str, Any]:
    suggestions = suggest_tool_names(tool_name, available)
    if str(lang or "").startswith("zh"):
        err = f"未注册的工具: {tool_name}"
        hint = (
            "请改用 suggestions 中的工具名，或检查该专家的 MCP 绑定/启用状态。"
            if suggestions
            else "当前工具目录中无此工具；请检查 MCP 是否启用及专家绑定。"
        )
    else:
        err = f"Unregistered tool: {tool_name}"
        hint = (
            "Use one of suggestions, or refresh MCP tools for this specialist."
            if suggestions
            else "Tool is not in the current registry; check MCP enablement / specialist binding."
        )
    out: dict[str, Any] = {
        "ok": False,
        "error_code": "tool_not_registered",
        "error": err,
        "hint": hint,
    }
    if suggestions:
        out["suggestions"] = suggestions
    return out


def enrich_mcp_scope_error(result: dict[str, Any]) -> dict[str, Any]:
    """Rewrite insufficient_scope MCP errors into actionable ops guidance."""
    if not isinstance(result, dict) or result.get("ok") is not False:
        return result
    err = str(result.get("error") or "")
    code = str(result.get("error_code") or "")
    blob = f"{err} {code}".lower()
    if "insufficient_scope" not in blob and "insufficient_scope" not in err:
        return result
    scope = ""
    marker = "insufficient_scope:"
    if marker in err:
        scope = err.split(marker, 1)[1].strip().split()[0].strip("\"'")
    elif marker in code:
        scope = code.split(marker, 1)[1].strip()
    out = dict(result)
    out["error_code"] = "insufficient_scope"
    if scope:
        out["required_scope"] = scope
    out["error"] = f"insufficient_scope:{scope}" if scope else "insufficient_scope"
    if scope == "sql:query":
        out["hint"] = (
            "Current netx token lacks sql:query. Do not retry sqlQueryUme. "
            "Prefer aggregateUmeAlarms / queryUmeAlarmsRaw / ume_alarm_xlsx_report; "
            "ask an admin to grant sql:query only if SQL is truly required."
        )
        out["fallback_tools"] = [
            "mcp__netx__aggregateUmeAlarms",
            "mcp__netx__queryUmeAlarmsRaw",
            "ume_alarm_xlsx_report",
        ]
        out["user_facing_hint"] = (
            "SQL query is not enabled for this bot token. "
            "I will use alarm aggregate/report tools instead, or an admin can grant sql:query."
        )
    else:
        out["hint"] = (
            f"Current netx token lacks scope {scope or '(unknown)'}. "
            "Do not retry the same tool; ask an admin to grant it, or use tools that do not need this scope."
        )
        out["user_facing_hint"] = (
            f"Permission missing ({scope or 'scope'}). An admin needs to grant this on the netx API token."
        )
    out["failure_class"] = "auth"
    out["retry_forbidden"] = True
    return out


def _unwrap_nested_error_blob(raw: Any) -> tuple[str, str]:
    """Best-effort unwrap double-encoded MCP/netx error payloads."""
    import json

    text = str(raw or "").strip()
    code = ""
    if not text:
        return "", ""
    cur: Any = text
    for _ in range(3):
        if isinstance(cur, dict):
            code = str(cur.get("error_code") or cur.get("code") or code or "")
            nested = cur.get("error")
            if nested is None and cur.get("data") is not None:
                nested = cur.get("data")
            if isinstance(nested, (dict, list)):
                cur = nested
                continue
            if nested is not None:
                text = str(nested)
                cur = nested
                if isinstance(cur, str) and cur.strip().startswith("{"):
                    try:
                        cur = json.loads(cur)
                        continue
                    except Exception:
                        break
            break
        if isinstance(cur, str) and cur.strip().startswith("{"):
            try:
                cur = json.loads(cur)
                continue
            except Exception:
                text = cur
                break
        if isinstance(cur, str):
            text = cur
        break
    if isinstance(cur, dict):
        text = str(cur.get("error") or cur.get("message") or text)
        code = str(cur.get("error_code") or cur.get("code") or code or "")
    return str(text or "").strip(), str(code or "").strip()


def enrich_exec_managed_ne_error(result: dict[str, Any]) -> dict[str, Any]:
    """Classify execManagedNe failures so agents stop blind-retrying."""
    if not isinstance(result, dict) or result.get("ok") is not False:
        return result
    out = dict(result)
    raw_err = out.get("error")
    raw_code = str(out.get("error_code") or "")
    unwrapped, nested_code = _unwrap_nested_error_blob(raw_err)
    if unwrapped and unwrapped != str(raw_err or "").strip():
        out["error_detail"] = unwrapped
    code = (nested_code or raw_code or "").strip()
    blob = f"{unwrapped} {code} {raw_err}".lower()

    error_class = "exec_failed"
    hint = (
        "CLI failed. Check ne_id/ume_ne_id, avoid identical blind retries, "
        "and prefer batching show commands in one execManagedNe call."
    )
    if "timeout" in blob or code in {"tool_timeout_or_failed", "read_timeout", "deadline_exceeded"}:
        error_class = "timeout"
        hint = (
            "CLI timed out. Raise read_timeout_sec (60–120), reduce commands, "
            "or reuse prior listCliTargets ids — do not blind-retry identical calls."
        )
    elif any(
        x in blob
        for x in (
            "unreachable",
            "connection refused",
            "no route",
            "timed out connecting",
            "host unreachable",
            "network is unreachable",
            "connect_failed",
            "ssh_connect",
        )
    ):
        error_class = "unreachable"
        hint = (
            "Device unreachable / connect failed. Do not spam retries; report the NE as unreachable "
            "and try another target or verify UME→CLI credentials/jump host."
        )
    elif any(x in blob for x in ("auth", "permission denied", "login failed", "authentication", "password")):
        error_class = "auth"
        hint = (
            "CLI authentication failed. Do not retry the same credentials; "
            "fix UME→CLI / managed-NE credentials instead."
        )
    elif any(x in blob for x in ("command", "syntax", "invalid input", "ambiguous command", "%error")):
        error_class = "command_error"
        hint = (
            "Command rejected by the device. Fix the CLI syntax or vendor dialect; "
            "do not retry the identical command string."
        )

    out["error_class"] = error_class
    if code and not out.get("error_code"):
        out["error_code"] = code
    out["hint"] = hint
    return out


def classify_tool_failure(result: dict[str, Any]) -> str:
    """Coarse failure class for analytics / retry guards (English field ops)."""
    if not isinstance(result, dict) or result.get("ok") is not False:
        return ""
    existing = str(result.get("failure_class") or result.get("error_class") or "").strip().lower()
    if existing:
        return existing
    code = str(result.get("error_code") or "").strip().lower()
    err = str(result.get("error") or "").strip().lower()
    hint = str(result.get("hint") or "").strip().lower()
    blob = f"{code} {err} {hint}"
    if code in {"tool_invalid_arguments", "invalid_arguments"} or "invalid arguments" in blob or "参数不合法" in err:
        return "schema_validation"
    if "insufficient_scope" in blob or code == "insufficient_scope":
        return "scope"
    if "timeout" in blob or code == "tool_timeout_or_failed":
        return "timeout"
    if any(x in blob for x in ("unreachable", "connect_failed", "connection refused", "no route")):
        return "unreachable"
    if any(x in blob for x in ("auth", "permission denied", "authentication", "login failed")):
        return "auth"
    if code in {
        "tool_loop_guard",
        "identical_retry_blocked",
        "retry_forbidden_blocked",
        "cli_call_budget_exceeded",
        "cli_fail_budget_exceeded",
        "shell_call_budget_exceeded",
        "shell_fail_budget_exceeded",
    }:
        return "retry_guard"
    if code in {"tool_not_registered"}:
        return "not_registered"
    return "runtime"


def stamp_tool_failure_class(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("ok") is not False:
        return result if isinstance(result, dict) else {"ok": False, "error": "tool_result_not_dict"}
    out = dict(result)
    klass = classify_tool_failure(out)
    if klass:
        out["failure_class"] = klass
        if not str(out.get("error_class") or "").strip():
            out["error_class"] = klass
    return out


def build_finalize_system_suffix(
    *,
    lang: str = "en",
    hit_tool_round_limit: bool = False,
    user_facing_hints: list[str] | None = None,
) -> str:
    """Nudge the model to stop tools and answer when the turn must finalize."""
    hints = [str(h).strip() for h in (user_facing_hints or []) if str(h).strip()]
    # de-dupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for h in hints:
        key = h.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
        if len(unique) >= 4:
            break

    is_zh = str(lang or "").strip().lower().startswith("zh")
    lines: list[str] = []
    if hit_tool_round_limit:
        if is_zh:
            lines.append(
                "[工具轮次已达上限：禁止再调用任何工具。请基于已有工具结果，"
                "用简洁中文直接回复用户（WhatsApp 现场用语）。]"
            )
        else:
            lines.append(
                "[Tool-round limit reached: do NOT call any more tools. "
                "Answer the user now in concise English from results already obtained.]"
            )
    elif unique:
        if is_zh:
            lines.append("[收束：如无必要请停止工具调用，直接给出可发送的答复。]")
        else:
            lines.append("[Finalize: stop tool calls if possible and deliver a sendable answer.]")
    if unique:
        if is_zh:
            lines.append("工具给出的用户可读约束：")
        else:
            lines.append("User-facing constraints from tools:")
        lines.extend(f"- {h}" for h in unique)
    return "\n".join(lines).strip()


__all__ = [
    "build_finalize_system_suffix",
    "classify_tool_failure",
    "enrich_exec_managed_ne_error",
    "enrich_mcp_scope_error",
    "format_unregistered_tool_error",
    "stamp_tool_failure_class",
    "suggest_tool_names",
]
