from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _print_rows(title: str, rows: list[tuple], limit: int = 20) -> None:
    print(f"\n== {title} (showing {min(len(rows), limit)}/{len(rows)}) ==")
    for r in rows[:limit]:
        try:
            print(r)
        except Exception:
            print(repr(r))


def main() -> None:
    db = Path(r"D:\project\chatgpt\oclaw\data\ai_ops.sqlite")
    if not db.exists():
        raise SystemExit(f"db not found: {db}")
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name").fetchall()]

    # If we have a trace table with expected columns, show recent gateway_received/router_decision/manager_decision/response_sent.
    trace_table = None
    for t in tables:
        if t.lower() in ("trace_events", "trace_event", "oclaw_trace_events", "trace"):
            trace_table = t
            break
    if trace_table:
        cols = [c[1] for c in cur.execute(f"pragma table_info({trace_table})").fetchall()]
        if {"event_type", "payload"}.issubset(set(cols)):
            q2 = f"""
            select event_type, payload
            from {trace_table}
            where event_type in ('manager_decision')
            order by rowid desc
            limit 50
            """
            rows2 = cur.execute(q2).fetchall()
            parsed2 = []
            for et, pl in rows2:
                try:
                    obj = json.loads(pl) if isinstance(pl, str) and pl.strip().startswith(("{", "[")) else pl
                except Exception:
                    obj = pl
                if isinstance(obj, dict):
                    parsed2.append(
                        (
                            et,
                            {
                                "manager_selected_specialist": obj.get("manager_selected_specialist"),
                                "manager_self_mode": obj.get("manager_self_mode"),
                                "dispatch_reason": obj.get("dispatch_reason"),
                                "instruction_chars": obj.get("instruction_chars"),
                                "dynamic_agent_used": obj.get("dynamic_agent_used"),
                                "dynamic_agent_name": obj.get("dynamic_agent_name"),
                            },
                        )
                    )
                else:
                    parsed2.append((et, obj))
            _print_rows("recent manager_decision summary", parsed2, limit=50)

            q = f"""
            select event_type, payload
            from {trace_table}
            where event_type in ('router_decision','gateway_received','response_sent')
            order by rowid desc
            limit 50
            """
            rows = cur.execute(q).fetchall()
            parsed = []
            for et, pl in rows:
                try:
                    obj = json.loads(pl) if isinstance(pl, str) and pl.strip().startswith(("{", "[")) else pl
                except Exception:
                    obj = pl
                parsed.append((et, obj))
            _print_rows("recent trace events (type,payload)", parsed, limit=50)

    con.close()


if __name__ == "__main__":
    main()

