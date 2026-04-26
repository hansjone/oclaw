from __future__ import annotations

import json
import sqlite3


def main() -> None:
    db = r"D:\project\chatgpt\oclaw\data\ai_ops.sqlite"
    con = sqlite3.connect(db)
    cur = con.cursor()

    print("== latest response_sent trace_event ==")
    rows = cur.execute(
        """
        select id, session_id, trace_id, payload, timestamp
        from trace_event
        where event_type='response_sent'
        order by id desc
        limit 10
        """
    ).fetchall()
    for rid, sid, tid, payload, ts in rows:
        try:
            obj = json.loads(payload) if isinstance(payload, str) else {}
        except Exception:
            obj = {}
        print(
            {
                "id": rid,
                "session_id": sid,
                "trace_id": tid,
                "mode": obj.get("mode"),
                "elapsed_ms": obj.get("elapsed_ms"),
                "ts": ts,
            }
        )

    print("\n== latest chat_message ==")
    rows = cur.execute(
        """
        select id, session_id, role, substr(content,1,120), timestamp
        from chat_message
        order by id desc
        limit 12
        """
    ).fetchall()
    for row in rows:
        print(row)

    con.close()


if __name__ == "__main__":
    main()

