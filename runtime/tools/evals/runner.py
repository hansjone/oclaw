from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from runtime.agents.factory import build_gateway_executor
from svc.persistence.sqlite_store import SqliteStore
from runtime.orchestration.evaluation import eval_summary
from svc.config.paths import db_path
from runtime.gateway import OclawGateway
from runtime.types import StandardMessage


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    input_text: str
    assert_contains: list[str]
    assert_not_contains: list[str]


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    ok: bool
    latency_ms: int
    failures: list[str]


def _load_dataset(dataset_path: str) -> list[EvalCase]:
    ds = Path(dataset_path)
    if not ds.exists():
        raise FileNotFoundError(dataset_path)
    cases: list[EvalCase] = []
    with ds.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            input_text = str(row.get("input") or "").strip()
            if not input_text:
                continue
            case_id = str(row.get("id") or row.get("case_id") or f"line-{idx}").strip()
            ac = row.get("assert_contains") or []
            anc = row.get("assert_not_contains") or []
            assert_contains = [str(x) for x in ac if str(x).strip()]
            assert_not_contains = [str(x) for x in anc if str(x).strip()]
            cases.append(
                EvalCase(
                    case_id=case_id,
                    input_text=input_text,
                    assert_contains=assert_contains,
                    assert_not_contains=assert_not_contains,
                )
            )
    return cases


def run_eval(
    dataset_path: str,
    *,
    report_path: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run a simple offline regression eval.

    Dataset format: JSONL, each line:
      {"id": "...", "input": "...", "assert_contains": ["..."], "assert_not_contains": ["..."]}
    """
    store = SqliteStore(db_path())
    agent = build_gateway_executor(store)
    session = store.create_session("offline-eval")
    gw = OclawGateway(store=store)
    cases = _load_dataset(dataset_path)
    if limit is not None:
        cases = cases[: max(0, int(limit))]

    results: list[EvalCaseResult] = []
    for c in cases:
        t0 = time.perf_counter()
        msg = StandardMessage(
            session_id=str(session.id),
            tenant_id="",
            user_id="",
            role="owner",
            channel="eval",
            text=str(c.input_text or ""),
            attachments=[],
            metadata={"channel": "eval"},
        )
        out = str(gw.handle_turn(msg=msg, lang="zh", executor=agent).reply_text or "")
        latency_ms = int((time.perf_counter() - t0) * 1000)
        failures: list[str] = []
        for must in c.assert_contains:
            if must not in out:
                failures.append(f"missing_substring:{must}")
        for bad in c.assert_not_contains:
            if bad in out:
                failures.append(f"unexpected_substring:{bad}")
        results.append(EvalCaseResult(case_id=c.case_id, ok=not failures, latency_ms=latency_ms, failures=failures))

    passed = sum(1 for r in results if r.ok)
    report = {
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": passed,
        "pass_rate": round((passed / len(results)) if results else 0.0, 4),
        "results": [
            {"id": r.case_id, "ok": r.ok, "latency_ms": r.latency_ms, "failures": r.failures} for r in results
        ],
        "agent_metrics": eval_summary(store, limit=5000),
    }
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_eval("data/eval/mvp_tasks.jsonl", report_path="data/eval/report.json")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False, indent=2))
