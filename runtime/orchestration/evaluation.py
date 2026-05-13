from __future__ import annotations

from collections import defaultdict
from typing import Any

from svc.persistence.sqlite_store import SqliteStore


def log_eval_event(
    store: SqliteStore,
    *,
    session_id: str,
    specialist: str,
    task_kind: str,
    success: bool,
    latency_ms: int,
    cost_hint: float = 0.0,
    notes: str = "",
) -> None:
    store.add_agent_eval_log(
        session_id=session_id,
        specialist=specialist,
        task_kind=task_kind,
        success=success,
        latency_ms=latency_ms,
        cost_hint=cost_hint,
        notes=notes,
    )


def eval_summary(store: SqliteStore, *, limit: int = 200) -> dict[str, Any]:
    rows = store.list_agent_eval_logs(limit=limit)
    if not rows:
        return {"total": 0, "success_rate": 0.0, "p95_latency_ms": 0}
    success_cnt = sum(1 for r in rows if bool(r.get("success")))
    lats = sorted(int(r.get("latency_ms") or 0) for r in rows)
    idx = max(0, int(len(lats) * 0.95) - 1)
    by_specialist: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "ok": 0, "lat": []})
    plan_rows = 0
    for r in rows:
        sp = str(r.get("specialist") or "unknown")
        by_specialist[sp]["total"] += 1
        by_specialist[sp]["ok"] += 1 if bool(r.get("success")) else 0
        by_specialist[sp]["lat"].append(int(r.get("latency_ms") or 0))
        if "manager_plan_generated" in str(r.get("notes") or ""):
            plan_rows += 1
    specialist_metrics: dict[str, dict[str, Any]] = {}
    for sp, m in by_specialist.items():
        l = sorted(m["lat"])
        p95_idx = max(0, int(len(l) * 0.95) - 1)
        specialist_metrics[sp] = {
            "total": m["total"],
            "success_rate": round((m["ok"] / m["total"]) if m["total"] else 0.0, 4),
            "p95_latency_ms": l[p95_idx] if l else 0,
        }
    return {
        "total": len(rows),
        "success_rate": round(success_cnt / len(rows), 4),
        "p95_latency_ms": lats[idx],
        "plan_events": plan_rows,
        "by_specialist": specialist_metrics,
    }
