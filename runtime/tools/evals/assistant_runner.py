from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.application.gateway import process_inbound_payload_usecase
from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store


@dataclass(frozen=True)
class Case:
    case_id: str
    kind: str
    payload: dict[str, Any]
    assert_contains: list[str]
    assert_not_contains: list[str]


def _load_cases(path: str) -> list[Case]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    out: list[Case] = []
    for idx, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        row = json.loads(raw)
        cid = str(row.get("id") or f"line-{idx}")
        kind = str(row.get("kind") or "gateway")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        ac = row.get("assert_contains") or []
        anc = row.get("assert_not_contains") or []
        out.append(
            Case(
                case_id=cid,
                kind=kind,
                payload=payload,
                assert_contains=[str(x) for x in ac if str(x).strip()],
                assert_not_contains=[str(x) for x in anc if str(x).strip()],
            )
        )
    return out


def _extract_reply_text(resp: dict[str, Any]) -> str:
    try:
        replies = resp.get("replies")
        if isinstance(replies, list) and replies:
            first = replies[0]
            if isinstance(first, dict):
                return str(first.get("text") or "")
    except Exception:
        pass
    return ""


def run_gateway_eval(dataset_path: str) -> dict[str, Any]:
    store = get_assistant_store()
    # Seed a tenant + bind code for tests
    tenants = store.list_tenants(limit=1)
    if tenants:
        tenant_id = tenants[0]["id"]
    else:
        tenant_id = store.create_tenant("Eval")["id"]
    code = "EVALCODE"
    try:
        store.create_bind_code(tenant_id=tenant_id, role="member", code=code)
    except Exception:
        pass

    # Binding creates the user; we will use external ids in payloads.
    cases = _load_cases(dataset_path)
    results = []
    passed = 0
    for c in cases:
        payload = dict(c.payload)
        # inject tenant/code shortcuts
        payload.setdefault("channel", "wecom")
        payload.setdefault("chat_id", "room_eval")
        payload.setdefault("user_id", "wxid_eval_u1")
        payload.setdefault("is_group", True)
        payload["text"] = str(payload.get("text") or "").replace("EVALCODE", code)
        resp = process_inbound_payload_usecase(payload)
        text = _extract_reply_text(resp)
        failures = []
        for must in c.assert_contains:
            if must not in text:
                failures.append(f"missing:{must}")
        for bad in c.assert_not_contains:
            if bad in text:
                failures.append(f"unexpected:{bad}")
        ok = not failures
        passed += 1 if ok else 0
        results.append({"id": c.case_id, "ok": ok, "text": text, "failures": failures})
    return {"total": len(results), "passed": passed, "pass_rate": (passed / len(results)) if results else 0.0, "results": results}


if __name__ == "__main__":
    rep = run_gateway_eval("data/eval/assistant_gateway.jsonl")
    print(json.dumps({k: v for k, v in rep.items() if k != "results"}, ensure_ascii=False, indent=2))

