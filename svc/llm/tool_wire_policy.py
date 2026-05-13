"""Graduated OpenAI ``tools[]`` shaping + usage-aware omission / per-tool admin policies.

Uses ``tool_log`` aggregates, ``app_setting`` for admin config / per-tool levels / penalty state.
Wire payload differs from local :class:`~src.tools.base.ToolSpec`; validation still uses full schemas.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from svc.llm.tool_schema import MIN_OPENAI_FUNCTION_PARAMETERS, complete_openai_tools_wire_parameters

logger = logging.getLogger(__name__)

SETTINGS_KEY_PENALTY_STATE = "mcp_tool_wire_penalty_state"
SETTINGS_KEY_TOOL_POLICIES = "mcp_tool_wire_tool_policies"
SETTINGS_KEY_ADMIN_CONFIG = "mcp_tool_wire_admin_config"

# Role-scoped (per expert) overrides. Shape:
# - policies: { "<role>": { "mcp__server__tool": <int level> } }
# - penalty:  { "<role>": { "mcp__server__tool": <penalty state dict> } }
SETTINGS_KEY_PENALTY_STATE_BY_ROLE = "mcp_tool_wire_penalty_state_by_role"
SETTINGS_KEY_TOOL_POLICIES_BY_ROLE = "mcp_tool_wire_tool_policies_by_role"
SETTINGS_KEY_ROLE_MODE_BY_ROLE = "mcp_tool_wire_role_mode_by_role"

_MIN_PARAMETERS: dict[str, Any] = dict(MIN_OPENAI_FUNCTION_PARAMETERS)


def _env_prefixed(name_suffix: str, default: str = "") -> str:
    raw = str(os.getenv(f"AIA_{name_suffix}") or "").strip()
    if raw:
        return raw
    raw = str(os.getenv(f"OPS_{name_suffix}") or "").strip()
    if raw:
        return raw
    return str(default).strip()


def wire_policy_enabled(base_url: str | None) -> bool:
    raw = _env_prefixed("MCP_WIRE_USAGE_POLICY", "").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    u = (base_url or "").lower()
    return "dashscope.aliyuncs.com" in u


def penalty_disabled() -> bool:
    return _env_prefixed("MCP_WIRE_PENALTY_DISABLE", "").lower() in ("1", "true", "yes", "on")


def _admin_defaults_from_env() -> dict[str, Any]:
    return {
        "wire_policy": "inherit",
        "top_n_full": int(_env_prefixed("MCP_WIRE_TOP_N_FULL", "20") or "20"),
        "stale_hours": float(_env_prefixed("MCP_WIRE_STALE_HOURS", "3") or "3"),
        "penalty_minutes": float(_env_prefixed("MCP_WIRE_PENALTY_MINUTES", "30") or "30"),
        "medium_rank_start": int(_env_prefixed("MCP_WIRE_MEDIUM_RANK_START", "21") or "21"),
        "medium_rank_end": int(_env_prefixed("MCP_WIRE_MEDIUM_RANK_END", "50") or "50"),
        "medium_desc_chars": int(_env_prefixed("MCP_WIRE_MEDIUM_DESC_CHARS", "520") or "520"),
        "minimal_desc_cap": int(_env_prefixed("MCP_WIRE_MINIMAL_DESC_CAP", "80") or "80"),
        "penalty_disable": False,
    }


def load_merged_admin_config(store: Any) -> dict[str, Any]:
    out = _admin_defaults_from_env()
    try:
        raw = store.get_setting(SETTINGS_KEY_ADMIN_CONFIG)
        if not raw:
            return out
        d = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(d, dict):
            for k, v in d.items():
                if k in out or k == "wire_policy":
                    out[k] = v
    except Exception:
        pass
    pd = out.get("penalty_disable")
    if isinstance(pd, str):
        out["penalty_disable"] = pd.strip().lower() in ("1", "true", "yes", "on")
    return out


def load_tool_policies_dict(store: Any) -> dict[str, int]:
    try:
        raw = store.get_setting(SETTINGS_KEY_TOOL_POLICIES) or "{}"
        d = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}
    if not isinstance(d, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in d.items():
        nm = str(k or "").strip()
        if not nm.startswith("mcp__"):
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n == 9999:
            out[nm] = 9999
        elif n <= 0:
            out[nm] = 0
        else:
            out[nm] = min(n, 9998)
    return out


def load_tool_policies_dict_for_role(store: Any, *, role: str | None) -> dict[str, int]:
    """Role-scoped policies; falls back to global if absent/unparseable."""
    r = str(role or "").strip().lower()
    if not r:
        return load_tool_policies_dict(store)
    try:
        raw = store.get_setting(SETTINGS_KEY_TOOL_POLICIES_BY_ROLE) or "{}"
        outer = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        outer = {}
    if not isinstance(outer, dict):
        return load_tool_policies_dict(store)
    inner = outer.get(r)
    if not isinstance(inner, dict):
        return load_tool_policies_dict(store)
    # Reuse same coercion rules as global loader.
    out: dict[str, int] = {}
    for k, v in inner.items():
        nm = str(k or "").strip()
        if not nm.startswith("mcp__"):
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n == 9999:
            out[nm] = 9999
        elif n <= 0:
            out[nm] = 0
        else:
            out[nm] = min(n, 9998)
    return out


def load_penalty_state_for_role(store: Any, *, role: str | None) -> dict[str, Any]:
    """Role-scoped penalty state; falls back to global if absent/unparseable."""
    r = str(role or "").strip().lower()
    if not r:
        raw_pen = store.get_setting(SETTINGS_KEY_PENALTY_STATE) or "{}"
        try:
            pen = json.loads(raw_pen) if isinstance(raw_pen, str) else {}
        except Exception:
            pen = {}
        if not isinstance(pen, dict):
            pen = {}
        return migrate_legacy_penalty_store(pen)
    try:
        raw = store.get_setting(SETTINGS_KEY_PENALTY_STATE_BY_ROLE) or "{}"
        outer = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        outer = {}
    if not isinstance(outer, dict):
        return load_penalty_state_for_role(store, role=None)
    inner = outer.get(r)
    if not isinstance(inner, dict):
        return load_penalty_state_for_role(store, role=None)
    return migrate_legacy_penalty_store(inner)


def _persist_penalty_state_for_role(store: Any, *, role: str | None, penalty_state: dict[str, Any]) -> None:
    r = str(role or "").strip().lower()
    clean: dict[str, Any] = {}
    for k, v in (penalty_state or {}).items():
        if v is None:
            continue
        if isinstance(v, dict):
            clean[str(k)] = v
    if not r:
        store.set_setting(SETTINGS_KEY_PENALTY_STATE, json.dumps(clean, ensure_ascii=False))
        return
    try:
        raw = store.get_setting(SETTINGS_KEY_PENALTY_STATE_BY_ROLE) or "{}"
        outer = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        outer = {}
    if not isinstance(outer, dict):
        outer = {}
    outer[r] = clean
    store.set_setting(SETTINGS_KEY_PENALTY_STATE_BY_ROLE, json.dumps(outer, ensure_ascii=False))


def wire_graduation_effective(base_url: str | None, admin: dict[str, Any]) -> bool:
    mode = str(admin.get("wire_policy") or "inherit").strip().lower()
    if mode in ("always", "on", "true", "1", "yes"):
        return True
    if mode in ("never", "off", "false", "0", "no"):
        return False
    return wire_policy_enabled(base_url)


def penalty_effective_disabled(admin: dict[str, Any]) -> bool:
    if bool(admin.get("penalty_disable")):
        return True
    return penalty_disabled()


def migrate_legacy_penalty_store(raw: dict[str, Any]) -> dict[str, Any]:
    """Older rows used ``omit_until`` without ``phase``; add ``kind`` for global tier."""
    out: dict[str, Any] = {}
    for k, v in (raw or {}).items():
        if not isinstance(v, dict):
            continue
        v2 = dict(v)
        if str(v2.get("phase") or "") in ("active", "done"):
            if "kind" not in v2:
                v2["kind"] = "d"
            out[str(k)] = v2
            continue
        ou_s = str(v2.get("omit_until") or "")
        ws = str(v2.get("wave_ts") or "")
        ou = _parse_iso(ou_s)
        if ou_s and ou:
            if _utc_now() < ou:
                v2 = {"phase": "active", "omit_until": ou_s, "wave_ts": ws, "kind": v2.get("kind") or "d"}
            else:
                v2 = {"phase": "done", "wave_ts": ws, "kind": v2.get("kind") or "d"}
        elif ws:
            v2 = {"phase": "done", "wave_ts": ws, "kind": v2.get("kind") or "d"}
        else:
            continue
        out[str(k)] = v2
    return out


def _parse_iso(ts: str) -> datetime | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _wire_json_size(tools: list[dict[str, Any]]) -> int:
    try:
        return len(json.dumps(tools, ensure_ascii=False, default=str))
    except Exception:
        return 0


def _strip_nested_descriptions(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k) == "description":
                continue
            out[str(k)] = _strip_nested_descriptions(v)
        return out
    if isinstance(obj, list):
        return [_strip_nested_descriptions(x) for x in obj]
    return obj


def _tier_medium(fn: dict[str, Any], *, cfg: dict[str, Any]) -> dict[str, Any]:
    mid_desc_len = int(cfg.get("medium_desc_chars") or 520)
    mid_desc_len = max(80, min(mid_desc_len, 4000))
    desc = str(fn.get("description") or "")[:mid_desc_len]
    params = fn.get("parameters")
    if isinstance(params, dict):
        params_out = dict(_strip_nested_descriptions(params))
    else:
        params_out = dict(_MIN_PARAMETERS)
    return {"name": fn.get("name"), "description": desc, "parameters": params_out}


def _tier_minimal(fn: dict[str, Any], *, desc_cap: int) -> dict[str, Any]:
    desc = str(fn.get("description") or "")[: max(0, desc_cap)]
    return {"name": fn.get("name"), "description": desc, "parameters": dict(_MIN_PARAMETERS)}


def _clone_tool_entry(t: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(t, ensure_ascii=False, default=str))
    except Exception:
        return dict(t)


def _is_builtin_tool_name(name: str) -> bool:
    return not str(name).startswith("mcp__")


def _normalize_role_mode(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in {"unrestricted", "forbidden", "restricted"}:
        return s
    return "restricted"


def load_role_mode_for_role(store: Any, *, role: str | None) -> str:
    r = str(role or "").strip().lower()
    if not r:
        return "restricted"
    try:
        raw = store.get_setting(SETTINGS_KEY_ROLE_MODE_BY_ROLE) or "{}"
        obj = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        return "restricted"
    return _normalize_role_mode(obj.get(r))


def _is_stale_hours(last_ts_iso: str | None, stale_hours: float) -> bool:
    if not last_ts_iso:
        return False
    dt = _parse_iso(last_ts_iso)
    if dt is None:
        return False
    return (_utc_now() - dt).total_seconds() > stale_hours * 3600.0


def _idle_minutes_exceeded(last_ts_iso: str | None, idle_minutes: float) -> bool:
    if not last_ts_iso:
        return False
    dt = _parse_iso(last_ts_iso)
    if dt is None:
        return False
    return (_utc_now() - dt).total_seconds() > idle_minutes * 60.0


def _wave_penalty_omit(
    name: str,
    last_ts: str | None,
    idle_hit: bool,
    penalty_minutes: float,
    st_nm: Any,
    out_penalty_updates: dict[str, Any],
    *,
    kind: str,
) -> bool:
    pw = last_ts or ""
    mins = max(1.0, min(float(penalty_minutes), 24 * 60))
    if not idle_hit:
        return False
    prev = out_penalty_updates.get(name)
    if isinstance(prev, dict) and str(prev.get("kind") or "") != str(kind):
        out_penalty_updates.pop(name, None)
        st_nm = None
    else:
        st_nm = prev

    omit = False
    if isinstance(st_nm, dict) and str(st_nm.get("phase") or "") == "active":
        ou = _parse_iso(str(st_nm.get("omit_until") or ""))
        if ou and _utc_now() < ou:
            omit = True
        else:
            out_penalty_updates[name] = {"phase": "done", "wave_ts": pw, "kind": str(kind)}
    elif isinstance(st_nm, dict) and str(st_nm.get("phase") or "") == "done" and str(st_nm.get("wave_ts") or "") == pw:
        pass
    else:
        until = (_utc_now() + timedelta(minutes=mins)).isoformat()
        out_penalty_updates[name] = {"phase": "active", "omit_until": until, "wave_ts": pw, "kind": str(kind)}
        omit = True
    return omit


def filter_permanent_ban_mcp_tools(tools: list[dict[str, Any]], policies: dict[str, int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in tools:
        if not isinstance(entry, dict) or str(entry.get("type") or "") != "function":
            out.append(entry)
            continue
        fn = entry.get("function")
        if not isinstance(fn, dict):
            out.append(entry)
            continue
        name = str(fn.get("name") or "").strip()
        if not name or _is_builtin_tool_name(name):
            out.append(entry)
            continue
        if policies.get(name) == 9999:
            continue
        out.append(entry)
    return out


def prepare_openai_tools_for_llm_api(
    tools: list[dict[str, Any]],
    *,
    base_url: str | None,
    max_json_bytes: int | None,
    store: Any | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    """Build wire ``tools[]``: optional graduated policy + byte cap."""

    def _fallback_shrink(raw: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
        from svc.llm.tool_schema import shrink_openai_tools_payload_for_api

        return shrink_openai_tools_payload_for_api(raw, max_json_bytes=cap)

    if not tools:
        return tools

    tools = complete_openai_tools_wire_parameters(tools)

    def _finalize(result: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Re-apply completion after tier/shrink/squeeze (those paths emit fresh ``parameters`` dicts)."""
        return complete_openai_tools_wire_parameters(result)

    policies: dict[str, int] = {}
    admin: dict[str, Any] = _admin_defaults_from_env()
    role_mode = "restricted"
    try:
        if store is None:
            from svc.config.paths import db_path
            from svc.persistence.sqlite_store import SqliteStore

            store = SqliteStore(db_path())
        # Role-scoped policies if configured; otherwise fall back to global.
        policies = load_tool_policies_dict_for_role(store, role=str(role or "").strip().lower() or None)
        admin = load_merged_admin_config(store)
        role_mode = load_role_mode_for_role(store, role=str(role or "").strip().lower() or None)
    except Exception as exc:
        logger.warning("tool_wire_policy: load admin/policies (%s)", exc)

    def _filter_mcp_out(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict) or str(entry.get("type") or "") != "function":
                out.append(entry)
                continue
            fn = entry.get("function")
            if not isinstance(fn, dict):
                out.append(entry)
                continue
            nm = str(fn.get("name") or "").strip()
            if nm.startswith("mcp__"):
                continue
            out.append(entry)
        return out

    tools_pass1 = filter_permanent_ban_mcp_tools(tools, policies)

    if role_mode == "forbidden":
        out = _filter_mcp_out(tools)
        if max_json_bytes is not None and max_json_bytes > 0:
            return _finalize(_fallback_shrink(out, max_json_bytes))
        return _finalize(out)
    if role_mode == "unrestricted":
        if max_json_bytes is not None and max_json_bytes > 0:
            return _finalize(_fallback_shrink(tools_pass1, max_json_bytes))
        return _finalize(tools_pass1)

    if not wire_graduation_effective(base_url, admin):
        if max_json_bytes is not None and max_json_bytes > 0:
            return _finalize(_fallback_shrink(tools_pass1, max_json_bytes))
        return _finalize(tools_pass1)

    top_n = int(admin.get("top_n_full") or 20)
    top_n = max(3, min(top_n, 80))
    stale_h = float(admin.get("stale_hours") or 3)
    stale_h = max(0.25, min(stale_h, 720.0))
    penalty_min_global = float(admin.get("penalty_minutes") or 30)
    penalty_min_global = max(1.0, min(penalty_min_global, 24 * 60))
    medium_floor = int(admin.get("medium_rank_start") or 21)
    medium_ceiling = int(admin.get("medium_rank_end") or 50)
    if medium_floor > medium_ceiling:
        medium_floor, medium_ceiling = medium_ceiling, medium_floor

    usage_map: dict[str, dict[str, Any]] = {}
    penalty_state: dict[str, Any] = {}
    try:
        usage_map = store.list_mcp_tool_aggregate_usage()
        penalty_state = load_penalty_state_for_role(store, role=str(role or "").strip().lower() or None)
    except Exception as exc:
        logger.warning("tool_wire_policy: usage store unavailable (%s); fallback shrink only", exc)
        if max_json_bytes is not None and max_json_bytes > 0:
            return _finalize(_fallback_shrink(tools_pass1, max_json_bytes))
        return _finalize(tools_pass1)

    ranked = sorted(
        usage_map.items(),
        key=lambda kv: (-int(kv[1].get("count") or 0), str(kv[1].get("last_ts") or "")),
    )
    rank_by_name = {nm: idx + 1 for idx, (nm, _) in enumerate(ranked)}
    top_full = {nm for nm, _ in ranked[:top_n]}

    out_penalty_updates: dict[str, Any] = dict(penalty_state)
    omit_set: set[str] = set()

    for nm in list(out_penalty_updates.keys()):
        meta = usage_map.get(nm)
        cur_ts = str(meta.get("last_ts") or "") if meta else ""
        st = out_penalty_updates.get(nm)
        if not isinstance(st, dict):
            continue
        w_ts = str(st.get("wave_ts") or "")
        if w_ts and cur_ts and w_ts != cur_ts:
            out_penalty_updates.pop(nm, None)

    pen_glob = penalty_effective_disabled(admin)
    built: list[dict[str, Any]] = []
    for entry in tools_pass1:
        if not isinstance(entry, dict) or str(entry.get("type") or "") != "function":
            built.append(entry)
            continue
        fn = entry.get("function")
        if not isinstance(fn, dict):
            built.append(entry)
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            built.append(entry)
            continue

        if _is_builtin_tool_name(name):
            built.append(_clone_tool_entry(entry))
            continue

        usage = usage_map.get(name) or {}
        last_ts = str(usage.get("last_ts") or "") or None
        rk = rank_by_name.get(name)

        policy_lv = policies.get(name)
        st_nm = out_penalty_updates.get(name)

        # policy_lv semantics (punishment only):
        # - None: inherit global graduation + idle penalty.
        # - 0: exempt this tool from idle penalty (but still participates in graduation tiers).
        # - 1..9998: per-tool idle/penalty tuning (N * 10 minutes) + still participates in graduation tiers.
        # - 9999: permanent ban (filtered earlier in filter_permanent_ban_mcp_tools).
        omit = False
        if policy_lv == 0:
            omit = False
        elif policy_lv is not None and policy_lv >= 1:
            idle_m = float(policy_lv) * 10.0
            pen_m = float(policy_lv) * 10.0
            idle_hit = _idle_minutes_exceeded(last_ts, idle_m)
            kind = f"L{int(policy_lv)}"
            if not pen_glob:
                omit = _wave_penalty_omit(
                    name, last_ts, idle_hit, pen_m, st_nm, out_penalty_updates, kind=kind
                )
        else:
            idle_hit = _is_stale_hours(last_ts, stale_h)
            exempt = name in top_full
            if not pen_glob and idle_hit and not exempt:
                omit = _wave_penalty_omit(
                    name,
                    last_ts,
                    idle_hit,
                    penalty_min_global,
                    st_nm,
                    out_penalty_updates,
                    kind="d",
                )

        if omit:
            omit_set.add(name)
            continue

        tier = "minimal"
        if name in top_full:
            tier = "full"
        elif rk is not None and medium_floor <= rk <= medium_ceiling:
            tier = "medium"
        else:
            tier = "minimal"

        if tier == "full":
            built.append(_clone_tool_entry(entry))
        elif tier == "medium":
            mf = _tier_medium(fn, cfg=admin)
            built.append({"type": "function", "function": mf})
        else:
            cap0 = int(admin.get("minimal_desc_cap") or 80)
            cap0 = max(0, min(cap0, 2000))
            mf = _tier_minimal(fn, desc_cap=cap0)
            built.append({"type": "function", "function": mf})

    try:
        _persist_penalty_state_for_role(
            store,
            role=str(role or "").strip().lower() or None,
            penalty_state=out_penalty_updates,
        )
    except Exception as exc:
        logger.warning("tool_wire_policy: persist penalty state failed: %s", exc)

    if omit_set:
        logger.info(
            "tool_wire_policy: omitted %d MCP tools during penalty window: %s",
            len(omit_set),
            sorted(omit_set)[:12],
        )

    if max_json_bytes is not None and max_json_bytes > 0 and _wire_json_size(built) > max_json_bytes:
        return _finalize(_squeeze_to_budget(built, max_json_bytes, admin=admin))

    return _finalize(built)


def _squeeze_to_budget(
    built: list[dict[str, Any]], max_json_bytes: int, *, admin: dict[str, Any]
) -> list[dict[str, Any]]:
    work = json.loads(json.dumps(built, ensure_ascii=False, default=str))

    def sz() -> int:
        return _wire_json_size(work)

    if sz() <= max_json_bytes:
        return work
    for i, ent in enumerate(work):
        fn = ent.get("function") if isinstance(ent.get("function"), dict) else {}
        ps = fn.get("parameters")
        if isinstance(ps, dict) and len(json.dumps(ps, ensure_ascii=False)) > 400:
            nm = str(fn.get("name") or "")
            if nm.startswith("mcp__"):
                cap = int(admin.get("minimal_desc_cap") or 80)
                work[i] = {
                    "type": "function",
                    "function": _tier_minimal(fn, desc_cap=max(0, cap)),
                }
        if sz() <= max_json_bytes:
            return work

    for cap in (60, 40, 24, 12, 8, 4, 0):
        for i, ent in enumerate(work):
            fn = ent.get("function") if isinstance(ent.get("function"), dict) else {}
            nm = str(fn.get("name") or "")
            if nm.startswith("mcp__"):
                work[i] = {"type": "function", "function": _tier_minimal(fn, desc_cap=cap)}
        if sz() <= max_json_bytes:
            return work

    idxs = [i for i, e in enumerate(work) if str((e.get("function") or {}).get("name") or "").startswith("mcp__")]
    for i in reversed(idxs):
        if sz() <= max_json_bytes:
            break
        work.pop(i)

    if sz() > max_json_bytes:
        from svc.llm.tool_schema import shrink_openai_tools_payload_for_api

        work = shrink_openai_tools_payload_for_api(work, max_json_bytes=max_json_bytes)
    return work


def penalty_row_status(
    *,
    wire_name: str,
    policy_level: int | None,
    penalty: dict[str, Any] | None,
    last_ts: str | None,
) -> dict[str, Any]:
    """Human-readable row for Admin UI."""
    if policy_level is None:
        return {
            "phase": "inherit",
            "omit_until": None,
            "unblock_hint": "未配置：走全局线侧与闲置惩罚（与显式写入 0 不同）",
            "kind": None,
        }
    if policy_level == 9999:
        return {
            "phase": "permanent_ban",
            "omit_until": None,
            "unblock_hint": "永久不上送（需将策略改为非 9999）",
            "kind": None,
        }
    if policy_level == 0:
        return {
            "phase": "exempt",
            "omit_until": None,
            "unblock_hint": "策略 0：不参与闲置惩罚（仍可能受线侧分层/压缩影响）",
            "kind": None,
        }
    st = penalty.get(wire_name) if isinstance(penalty, dict) else None
    if not isinstance(st, dict):
        return {"phase": "none", "omit_until": None, "unblock_hint": "-", "kind": None}
    ph = str(st.get("phase") or "")
    ou = str(st.get("omit_until") or "")
    kd = str(st.get("kind") or "")
    if ph == "active" and ou:
        dt = _parse_iso(ou)
        hint = f"惩罚中，预计解封（omit_until）: {ou}"
        if dt and _utc_now() >= dt:
            hint = "惩罚窗口应已结束；下次请求会写入 done"
        return {"phase": "active", "omit_until": ou, "unblock_hint": hint, "kind": kd}
    if ph == "done":
        return {
            "phase": "done",
            "omit_until": None,
            "unblock_hint": "本轮已服完刑；再次闲置达到阈值后会重新惩罚",
            "kind": kd,
        }
    return {"phase": ph or "unknown", "omit_until": ou or None, "unblock_hint": "-", "kind": kd or None}


def build_tool_wire_snapshot(store: Any, *, role: str | None = None) -> dict[str, Any]:
    """Aggregate MCP install list + usage + policies for Admin GET."""
    from runtime.tools.mcp.registry import McpRegistry

    admin = load_merged_admin_config(store)
    role_norm = str(role or "").strip().lower() or None
    role_mode = load_role_mode_for_role(store, role=role_norm)
    policies = load_tool_policies_dict_for_role(store, role=role_norm)
    pen = load_penalty_state_for_role(store, role=role_norm)
    usage = store.list_mcp_tool_aggregate_usage()
    servers = McpRegistry(store).list_servers(enabled_only=False)
    tools_out: list[dict[str, Any]] = []
    for s in servers:
        sid = str(s.get("server_id") or "").strip()
        if not sid:
            continue
        for t in store.list_mcp_server_tools(server_id=sid):
            short = str(t.get("tool_name") or "").strip()
            if not short:
                continue
            wire = f"mcp__{sid}__{short}"
            agg = usage.get(wire) or {}
            in_db = wire in policies
            lv = int(policies[wire]) if in_db else None
            st = penalty_row_status(
                wire_name=wire,
                policy_level=lv,
                penalty=pen,
                last_ts=str(agg.get("last_ts") or "") or None,
            )
            tools_out.append(
                {
                    "server_id": sid,
                    "mcp_tool_name": short,
                    "wire_name": wire,
                    "policy_level": lv,
                    "policy_in_db": in_db,
                    "count": int(agg.get("count") or 0),
                    "last_ts": str(agg.get("last_ts") or ""),
                    "penalty": st,
                    "raw_penalty": pen.get(wire) if isinstance(pen.get(wire), dict) else None,
                }
            )
    tools_out.sort(key=lambda x: (x["server_id"], x["wire_name"]))
    return {
        "ok": True,
        "role": role_norm or "",
        "role_mode": role_mode,
        "config": admin,
        "policies": policies,
        "penalty_state": pen,
        "tools": tools_out,
    }


__all__ = [
    "SETTINGS_KEY_PENALTY_STATE",
    "SETTINGS_KEY_TOOL_POLICIES",
    "SETTINGS_KEY_ADMIN_CONFIG",
    "SETTINGS_KEY_PENALTY_STATE_BY_ROLE",
    "SETTINGS_KEY_TOOL_POLICIES_BY_ROLE",
    "SETTINGS_KEY_ROLE_MODE_BY_ROLE",
    "build_tool_wire_snapshot",
    "filter_permanent_ban_mcp_tools",
    "load_merged_admin_config",
    "load_tool_policies_dict",
    "load_tool_policies_dict_for_role",
    "load_penalty_state_for_role",
    "load_role_mode_for_role",
    "migrate_legacy_penalty_store",
    "penalty_row_status",
    "prepare_openai_tools_for_llm_api",
    "wire_policy_enabled",
]
