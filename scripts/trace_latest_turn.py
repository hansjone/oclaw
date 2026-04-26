from __future__ import annotations

import json
import sqlite3


def main() -> None:
    db = r"D:\project\chatgpt\oclaw\data\ai_ops.sqlite"
    con = sqlite3.connect(db)
    cur = con.cursor()

    row = cur.execute(
        "select trace_id,payload,timestamp from trace_event where event_type='response_sent' order by id desc limit 1"
    ).fetchone()
    print("latest_response_sent:", row[2] if row else None)
    if not row:
        con.close()
        return

    trace_id = str(row[0] or "")
    print("trace_id:", trace_id)

    evts = cur.execute(
        """
        select event_type,payload,timestamp
        from trace_event
        where trace_id=?
          and event_type in (
            'gateway_received','model_chat_start','ws_first_token',
            'manager_decision','router_decision','response_sent'
          )
        order by id asc
        """,
        (trace_id,),
    ).fetchall()

    keep_keys = [
        "elapsed_ms_since_gateway_start",
        "elapsed_ms",
        "interaction_mode",
        "requested_specialist",
        "manager_selected_specialist",
        "dispatch_reason",
        "manager_self_mode",
        "instruction_chars",
        "ws_client_send_ms",
        "ws_first_token_ms",
        "channel",
        "run_id",
    ]
    for et, pl, ts in evts:
        try:
            obj = json.loads(pl) if isinstance(pl, str) else pl
        except Exception:
            obj = pl
        if isinstance(obj, dict):
            pick = {k: obj.get(k) for k in keep_keys if k in obj}
            print(et, ts, pick)
        else:
            print(et, ts, obj)

    con.close()


if __name__ == "__main__":
    main()

