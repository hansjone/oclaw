from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

import pandas as pd

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.platform.config.paths import attachments_dir


def _tabular_root() -> Path:
    p = (attachments_dir() / "tabular").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _table_id(attachment_id: str, name: str) -> str:
    raw = f"{attachment_id}:{name}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def _db_path(table_id: str) -> Path:
    return _tabular_root() / f"{table_id}.sqlite"


def _meta_path(table_id: str) -> Path:
    return _tabular_root() / f"{table_id}.meta.json"


def _normalize_columns(raw_cols: list[Any]) -> tuple[list[str], list[dict[str, Any]]]:
    out: list[str] = []
    mapping: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for idx, raw in enumerate(raw_cols):
        original = "" if raw is None else str(raw)
        base = original.strip()
        if not base or base.lower().startswith("unnamed:"):
            base = f"col_{idx + 1}"
        base = re.sub(r"\s+", "_", base)
        base = re.sub(r"\W+", "_", base, flags=re.UNICODE).strip("_")
        if not base:
            base = f"col_{idx + 1}"
        n = int(seen.get(base, 0)) + 1
        seen[base] = n
        name = base if n == 1 else f"{base}__{n}"
        out.append(name)
        mapping.append({"index": idx, "original": original, "normalized": name})
    return out, mapping


def _prepare_writable_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[dict[str, Any]]]:
    raw_cols = [x for x in list(df.columns)]
    cols, col_map = _normalize_columns(raw_cols)
    writable = df.copy()
    writable.columns = cols
    for c in cols:
        writable[c] = writable[c].map(lambda x: "" if x is None else str(x))
    return writable, cols, col_map


def _safe_sheet_table_name(sheet_name: str, idx: int) -> str:
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", str(sheet_name or "").strip()).strip("_").lower()
    if not base:
        base = f"sheet_{idx + 1}"
    return f"sheet_{idx + 1}_{base}"


def _mcp_sqlite_command() -> list[str]:
    raw = str(os.getenv("AIA_MCP_SQLITE_COMMAND") or "").strip()
    if not raw:
        return []
    return [x for x in raw.split(" ") if x]


def _tabular_use_mcp() -> bool:
    raw = str(os.getenv("AIA_TABULAR_USE_MCP") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _tabular_sql_timeout_ms() -> int:
    def _clamp_timeout(raw: Any, default: int = 8_000) -> int:
        try:
            n = int(raw)
        except Exception:
            return default
        return max(100, min(n, 120_000))

    raw = str(os.getenv("AIA_TABULAR_SQL_TIMEOUT_MS") or "").strip()
    if raw:
        return _clamp_timeout(raw)
    cfg_path_raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
    cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else (Path(PROJECT_ROOT) / "oclaw" / "oclaw.json").resolve()
    if not cfg_path.is_absolute():
        cfg_path = (Path(PROJECT_ROOT) / cfg_path).resolve()
    try:
        obj = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return 8_000
    tabular_cfg = (
        (((obj or {}).get("plugins") or {}).get("entries") or {}).get("memory-wiki", {}).get("auto", {}).get("attachments", {}).get("tabular", {}) or {}
    )
    if not isinstance(tabular_cfg, dict):
        return 8_000
    return _clamp_timeout(tabular_cfg.get("sql_timeout_ms"), 8_000)


def _extract_rows_from_mcp_result(res: dict[str, Any]) -> list[dict[str, Any]] | None:
    if not isinstance(res, dict) or not bool(res.get("ok")):
        return None
    data = res.get("data") if isinstance(res.get("data"), dict) else res.get("result")
    if isinstance(data, dict):
        direct_rows = data.get("rows")
        if isinstance(direct_rows, list):
            out: list[dict[str, Any]] = []
            for r in direct_rows:
                if isinstance(r, dict):
                    out.append({str(k): r[k] for k in r.keys()})
            return out
        content = data.get("content")
        if isinstance(content, list):
            for it in content:
                if not isinstance(it, dict):
                    continue
                txt = str(it.get("text") or "").strip()
                if not txt:
                    continue
                try:
                    obj = json.loads(txt)
                except Exception:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("rows"), list):
                    rows = obj.get("rows")
                    out: list[dict[str, Any]] = []
                    for r in rows:
                        if isinstance(r, dict):
                            out.append({str(k): r[k] for k in r.keys()})
                    return out
    return None


def _run_select_via_mcp(*, db_path: Path, sql: str, params: list[Any]) -> list[dict[str, Any]] | None:
    if not _tabular_use_mcp():
        return None
    cmd = _mcp_sqlite_command()
    if not cmd:
        return None

    def _call_once(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            return {"ok": False}
        try:
            if p.stdin is None or p.stdout is None:
                return {"ok": False}
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "oclaw-tabular", "version": "0.1.0"},
                },
            }
            p.stdin.write(json.dumps(init_req, ensure_ascii=False) + "\n")
            p.stdin.flush()
            _ = p.stdout.readline()
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, ensure_ascii=False) + "\n")
            p.stdin.flush()
            call_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": str(tool_name), "arguments": arguments},
            }
            p.stdin.write(json.dumps(call_req, ensure_ascii=False) + "\n")
            p.stdin.flush()
            line = p.stdout.readline()
            if not line:
                return {"ok": False}
            obj = json.loads(line)
            if not isinstance(obj, dict):
                return {"ok": False}
            if isinstance(obj.get("error"), dict):
                return {"ok": False}
            return {"ok": True, "result": obj.get("result")}
        except Exception:
            return {"ok": False}
        finally:
            try:
                p.terminate()
            except Exception:
                pass

    # Probe several common sqlite MCP tool names/argument shapes.
    attempts: list[tuple[str, dict[str, Any]]] = [
        ("query", {"database": str(db_path), "sql": sql, "params": params}),
        ("query", {"db_path": str(db_path), "sql": sql, "params": params}),
        ("execute_sql", {"database": str(db_path), "sql": sql, "params": params}),
        ("read_query", {"database": str(db_path), "query": sql, "params": params}),
        ("sqlite_query", {"database": str(db_path), "sql": sql, "params": params}),
    ]
    for tool_name, args in attempts:
        res = _call_once(tool_name=tool_name, arguments=args)
        rows = _extract_rows_from_mcp_result(res if isinstance(res, dict) else {})
        if rows is not None:
            return rows
    return None


def _run_select_sql(
    *,
    db_path: Path,
    sql: str,
    params: list[Any],
    timeout_ms: int | None = None,
) -> tuple[list[dict[str, Any]], str]:
    rows = _run_select_via_mcp(db_path=db_path, sql=sql, params=params)
    if rows is not None:
        return rows, "mcp_sqlite"
    out_rows: list[dict[str, Any]] = []
    timeout_ms_eff = max(100, int(timeout_ms or _tabular_sql_timeout_ms()))
    deadline = time.perf_counter() + (float(timeout_ms_eff) / 1000.0)
    timed_out = {"hit": False}
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        def _progress_cb() -> int:
            if time.perf_counter() > deadline:
                timed_out["hit"] = True
                return 1
            return 0

        conn.set_progress_handler(_progress_cb, 1000)
        try:
            for r in conn.execute(sql, params).fetchall():
                out_rows.append({k: r[k] for k in r.keys()})
        except sqlite3.OperationalError as exc:
            if timed_out["hit"] and "interrupted" in str(exc).lower():
                raise TimeoutError(f"tabular_sql_timeout_ms={timeout_ms_eff}") from exc
            raise
        finally:
            conn.set_progress_handler(None, 0)
    return out_rows, "builtin_sqlite"


def save_dataframe(*, attachment_id: str, name: str, df: pd.DataFrame) -> dict[str, Any]:
    return save_workbook(attachment_id=attachment_id, name=name, sheets={"Sheet1": df})


def save_workbook(*, attachment_id: str, name: str, sheets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    tid = _table_id(attachment_id=attachment_id, name=name)
    db = _db_path(tid)
    meta = _meta_path(tid)
    sheet_rows: list[dict[str, Any]] = []
    default_table = "rows_data"
    default_columns: list[str] = []
    default_rows = 0
    default_cols = 0
    with sqlite3.connect(str(db)) as conn:
        for idx, (sheet_name, df) in enumerate((sheets or {}).items()):
            writable, cols, col_map = _prepare_writable_df(df)
            table_name = _safe_sheet_table_name(str(sheet_name or f"Sheet{idx + 1}"), idx)
            writable.to_sql(table_name, conn, if_exists="replace", index=False)
            if idx == 0:
                # backward compatibility: old queries use rows_data
                writable.to_sql("rows_data", conn, if_exists="replace", index=False)
                default_table = table_name
                default_columns = list(cols)
                default_rows = int(len(writable.index))
                default_cols = int(len(cols))
            sheet_rows.append(
                {
                    "sheet_name": str(sheet_name or f"Sheet{idx + 1}"),
                    "table_name": table_name,
                    "rows": int(len(writable.index)),
                    "cols": int(len(cols)),
                    "columns": list(cols),
                    "column_map": col_map,
                }
            )
    payload = {
        "table_id": tid,
        "attachment_id": str(attachment_id or ""),
        "name": str(name or ""),
        "rows": int(default_rows),
        "cols": int(default_cols),
        "columns": default_columns,
        "default_table": default_table,
        "sheets": sheet_rows,
        "db_path": str(db),
    }
    meta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def get_table_meta(table_id: str) -> dict[str, Any] | None:
    p = _meta_path(str(table_id or "").strip())
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _resolve_sheet_table(meta: dict[str, Any], sheet: str | None) -> str:
    default_table = str(meta.get("default_table") or "rows_data")
    if not sheet:
        return default_table
    target = str(sheet).strip()
    if not target:
        return default_table
    sheets = meta.get("sheets") if isinstance(meta.get("sheets"), list) else []
    for row in sheets:
        if not isinstance(row, dict):
            continue
        if str(row.get("sheet_name") or "") == target or str(row.get("table_name") or "") == target:
            return str(row.get("table_name") or default_table)
    return ""


def _columns_for_sheet(meta: dict[str, Any], table_name: str) -> list[str]:
    sheets = meta.get("sheets") if isinstance(meta.get("sheets"), list) else []
    for row in sheets:
        if not isinstance(row, dict):
            continue
        if str(row.get("table_name") or "") == str(table_name):
            cols = row.get("columns")
            if isinstance(cols, list):
                return [str(x) for x in cols]
    cols = meta.get("columns")
    if isinstance(cols, list):
        return [str(x) for x in cols]
    return []


def query_table(
    *,
    table_id: str,
    columns: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    where_contains: dict[str, str] | None = None,
    sheet: str | None = None,
) -> dict[str, Any]:
    meta = get_table_meta(table_id)
    if not isinstance(meta, dict):
        return {"ok": False, "error": "table_not_found"}
    db = Path(str(meta.get("db_path") or ""))
    if not db.exists():
        return {"ok": False, "error": "table_store_missing"}
    table_name = _resolve_sheet_table(meta, sheet)
    if not table_name:
        return {"ok": False, "error": "sheet_not_found"}
    known_cols = _columns_for_sheet(meta, table_name)
    use_cols = [c for c in (columns or known_cols) if c in known_cols]
    if not use_cols:
        use_cols = known_cols[: min(10, len(known_cols))]
    lim = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    select_sql = ", ".join([f'"{c}"' for c in use_cols]) if use_cols else "*"
    where_sql = ""
    params: list[Any] = []
    wc = where_contains if isinstance(where_contains, dict) else {}
    wc_col = str(wc.get("column") or "").strip()
    wc_kw = str(wc.get("keyword") or "").strip()
    if wc_col and wc_kw and wc_col in known_cols:
        where_sql = f' WHERE "{wc_col}" LIKE ? '
        params.append(f"%{wc_kw}%")
    sql = f'SELECT {select_sql} FROM "{table_name}"{where_sql} LIMIT ? OFFSET ?'
    params.extend([lim, off])
    out_rows: list[dict[str, Any]] = []
    total = 0
    out_rows, engine = _run_select_sql(db_path=db, sql=sql, params=params)
    with sqlite3.connect(str(db)) as conn:
        total = int(conn.execute(f'SELECT COUNT(1) AS n FROM "{table_name}"').fetchone()[0] or 0)
    return {
        "ok": True,
        "table_id": str(table_id),
        "name": str(meta.get("name") or ""),
        "sheet": str(sheet or ""),
        "table_name": table_name,
        "rows_total": total,
        "columns": use_cols,
        "rows": out_rows,
        "limit": lim,
        "offset": off,
        "engine": engine,
    }


def aggregate_table(
    *,
    table_id: str,
    metric: str,
    target_column: str | None = None,
    group_by: str | None = None,
    where_contains: dict[str, str] | None = None,
    top_n: int = 20,
    sheet: str | None = None,
) -> dict[str, Any]:
    meta = get_table_meta(table_id)
    if not isinstance(meta, dict):
        return {"ok": False, "error": "table_not_found"}
    db = Path(str(meta.get("db_path") or ""))
    if not db.exists():
        return {"ok": False, "error": "table_store_missing"}
    table_name = _resolve_sheet_table(meta, sheet)
    if not table_name:
        return {"ok": False, "error": "sheet_not_found"}
    known_cols = _columns_for_sheet(meta, table_name)
    mt = str(metric or "").strip().lower()
    if mt not in {"count", "sum", "avg"}:
        return {"ok": False, "error": "invalid_metric"}
    grp = str(group_by or "").strip()
    if grp and grp not in known_cols:
        return {"ok": False, "error": "invalid_group_by"}
    tgt = str(target_column or "").strip()
    if mt in {"sum", "avg"} and tgt not in known_cols:
        return {"ok": False, "error": "target_column_required"}
    where_sql = ""
    params: list[Any] = []
    wc = where_contains if isinstance(where_contains, dict) else {}
    wc_col = str(wc.get("column") or "").strip()
    wc_kw = str(wc.get("keyword") or "").strip()
    if wc_col and wc_kw and wc_col in known_cols:
        where_sql = f' WHERE "{wc_col}" LIKE ? '
        params.append(f"%{wc_kw}%")
    lim = max(1, min(int(top_n or 20), 200))
    if mt == "count":
        metric_sql = "COUNT(1)"
    else:
        metric_sql = f'{"SUM" if mt == "sum" else "AVG"}(CAST(NULLIF("{tgt}", \'\') AS REAL))'
    if grp:
        sql = (
            f'SELECT "{grp}" AS group_key, {metric_sql} AS metric_value '
            f'FROM "{table_name}"{where_sql} GROUP BY "{grp}" '
            "ORDER BY metric_value DESC LIMIT ?"
        )
        params.append(lim)
        raw_rows, engine = _run_select_sql(db_path=db, sql=sql, params=params)
        rows: list[dict[str, Any]] = []
        for r in raw_rows:
            rows.append(
                {
                    "group": r.get("group_key"),
                    "value": float(r.get("metric_value") or 0.0),
                }
            )
        return {
            "ok": True,
            "table_id": str(table_id),
            "sheet": str(sheet or ""),
            "table_name": table_name,
            "metric": mt,
            "target_column": tgt if mt in {"sum", "avg"} else None,
            "group_by": grp,
            "rows": rows,
            "top_n": lim,
            "engine": engine,
        }
    sql = f'SELECT {metric_sql} AS metric_value FROM "{table_name}"{where_sql} '
    raw_rows, engine = _run_select_sql(db_path=db, sql=sql, params=params)
    row = raw_rows[0] if raw_rows else {}
    return {
        "ok": True,
        "table_id": str(table_id),
        "sheet": str(sheet or ""),
        "table_name": table_name,
        "metric": mt,
        "target_column": tgt if mt in {"sum", "avg"} else None,
        "group_by": "",
        "value": float((row.get("metric_value") if isinstance(row, dict) else 0.0) or 0.0),
        "engine": engine,
    }


def run_table_sql(
    *,
    table_id: str,
    sql: str,
    limit: int = 200,
    sheet: str | None = None,
) -> dict[str, Any]:
    meta = get_table_meta(table_id)
    if not isinstance(meta, dict):
        return {"ok": False, "error": "table_not_found"}
    db = Path(str(meta.get("db_path") or ""))
    if not db.exists():
        return {"ok": False, "error": "table_store_missing"}
    table_name = _resolve_sheet_table(meta, sheet)
    if not table_name:
        return {"ok": False, "error": "sheet_not_found"}
    raw = str(sql or "").strip()
    if not raw:
        return {"ok": False, "error": "sql_required"}
    lowered = raw.lower()
    deny = ("insert ", "update ", "delete ", "drop ", "alter ", "attach ", "detach ", "pragma ", "create ")
    if any(k in lowered for k in deny):
        return {"ok": False, "error": "sql_not_readonly"}
    if ";" in raw:
        return {"ok": False, "error": "sql_multiple_statements_forbidden"}
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        return {"ok": False, "error": "sql_must_start_with_select_or_with"}
    lim = max(1, min(int(limit or 200), 500))
    auto_limited = " limit " not in lowered
    sql_targeted = re.sub(r"(?i)\brows_data\b", f'"{table_name}"', raw)
    safe_sql = sql_targeted if not auto_limited else f"{sql_targeted}\nLIMIT {lim}"
    timeout_ms = _tabular_sql_timeout_ms()
    try:
        rows, engine = _run_select_sql(db_path=db, sql=safe_sql, params=[], timeout_ms=timeout_ms)
    except TimeoutError:
        return {
            "ok": False,
            "error": "sql_timeout",
            "table_id": str(table_id),
            "name": str(meta.get("name") or ""),
            "sheet": str(sheet or ""),
            "table_name": table_name,
            "input_sql": raw,
            "executed_sql": safe_sql,
            "sql_guard": {
                "readonly_enforced": True,
                "multi_statement_forbidden": True,
                "auto_limit_applied": bool(auto_limited),
                "result_row_cap": lim,
                "timeout_ms": int(timeout_ms),
                "timeout_hit": True,
            },
        }
    out_rows = rows[:lim]
    return {
        "ok": True,
        "table_id": str(table_id),
        "name": str(meta.get("name") or ""),
        "sheet": str(sheet or ""),
        "table_name": table_name,
        "input_sql": raw,
        "executed_sql": safe_sql,
        "sql_guard": {
            "readonly_enforced": True,
            "multi_statement_forbidden": True,
            "auto_limit_applied": bool(auto_limited),
            "result_row_cap": lim,
            "timeout_ms": int(timeout_ms),
            "timeout_hit": False,
        },
        "rows": out_rows,
        "rows_returned": int(len(out_rows)),
        "limit": lim,
        "engine": engine,
    }


def analyze_table_full_scan(
    *,
    table_id: str,
    columns: list[str] | None = None,
    sheet: str | None = None,
    top_values_limit: int = 3,
) -> dict[str, Any]:
    meta = get_table_meta(table_id)
    if not isinstance(meta, dict):
        return {"ok": False, "error": "table_not_found"}
    db = Path(str(meta.get("db_path") or ""))
    if not db.exists():
        return {"ok": False, "error": "table_store_missing"}
    table_name = _resolve_sheet_table(meta, sheet)
    if not table_name:
        return {"ok": False, "error": "sheet_not_found"}
    known_cols = _columns_for_sheet(meta, table_name)
    if not known_cols:
        return {"ok": False, "error": "table_columns_missing"}
    use_cols = [c for c in (columns or known_cols) if c in known_cols]
    if not use_cols:
        return {"ok": False, "error": "columns_not_found"}
    top_lim = max(0, min(int(top_values_limit or 0), 10))
    started = time.perf_counter()
    with sqlite3.connect(str(db)) as conn:
        total_rows = int(conn.execute(f'SELECT COUNT(1) FROM "{table_name}"').fetchone()[0] or 0)
        col_stats: list[dict[str, Any]] = []
        for col in use_cols:
            row = conn.execute(
                (
                    f'SELECT '
                    f'SUM(CASE WHEN NULLIF(TRIM("{col}"), \'\') IS NOT NULL THEN 1 ELSE 0 END) AS non_empty_rows, '
                    f'COUNT(DISTINCT NULLIF(TRIM("{col}"), \'\')) AS distinct_values '
                    f'FROM "{table_name}"'
                )
            ).fetchone()
            non_empty_rows = int((row[0] if row else 0) or 0)
            distinct_values = int((row[1] if row else 0) or 0)
            item: dict[str, Any] = {
                "column": col,
                "non_empty_rows": non_empty_rows,
                "empty_rows": max(0, int(total_rows - non_empty_rows)),
                "distinct_values": distinct_values,
                "coverage_ratio": (float(non_empty_rows) / float(total_rows)) if total_rows > 0 else 0.0,
            }
            if top_lim > 0:
                tops = conn.execute(
                    (
                        f'SELECT "{col}" AS val, COUNT(1) AS n '
                        f'FROM "{table_name}" '
                        f'WHERE NULLIF(TRIM("{col}"), \'\') IS NOT NULL '
                        f'GROUP BY "{col}" ORDER BY n DESC LIMIT ?'
                    ),
                    [top_lim],
                ).fetchall()
                item["top_values"] = [{"value": str(r[0]), "count": int(r[1] or 0)} for r in tops]
            col_stats.append(item)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": True,
        "table_id": str(table_id),
        "name": str(meta.get("name") or ""),
        "sheet": str(sheet or ""),
        "table_name": table_name,
        "rows_scanned": int(total_rows),
        "columns_analyzed": list(use_cols),
        "column_stats": col_stats,
        "scan_audit": {
            "full_scan": True,
            "rows_scanned": int(total_rows),
            "columns_count": int(len(use_cols)),
            "elapsed_ms": int(elapsed_ms),
        },
        "engine": "builtin_sqlite_fullscan",
    }


__all__ = [
    "save_dataframe",
    "save_workbook",
    "get_table_meta",
    "query_table",
    "aggregate_table",
    "run_table_sql",
    "analyze_table_full_scan",
]

