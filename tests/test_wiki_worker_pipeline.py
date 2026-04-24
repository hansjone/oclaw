from __future__ import annotations

import json
from pathlib import Path

from oclaw.platform.persistence.sqlite_store import OpenClawTask
from oclaw.wiki_worker.main import _capture_after_turn, _dedup_merge, _process_task


def _task(task_id: str = "t1") -> OpenClawTask:
    return OpenClawTask(
        id=task_id,
        tenant_id="tenant-1",
        session_id="session-1",
        task_type="wiki_capture",
        status="claimed",
        payload="{}",
        result="{}",
        attempt_count=1,
        claimed_by="worker",
        lease_expires_at=None,
        last_error="",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        finished_at=None,
    )


def test_capture_and_dedup_merge_are_incremental(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    task = _task("t-cap")
    payload = {
        "session_id": "s-a",
        "turn_uuid": "turn-1",
        "user_text": "hello",
        "assistant_text": "world",
    }
    cap = _capture_after_turn(wiki_root=wiki_root, task=task, payload=payload)
    assert cap["ok"] is True
    assert str(cap["staged"]).endswith(".md")

    merge1 = _dedup_merge(wiki_root=wiki_root)
    assert merge1["ok"] is True
    assert int(merge1["merged_count"]) == 1

    # A second staging file with identical content should be treated as duplicate.
    payload2 = {
        "session_id": "s-a",
        "turn_uuid": "turn-2",
        "user_text": "hello",
        "assistant_text": "world",
    }
    _capture_after_turn(wiki_root=wiki_root, task=task, payload=payload2)
    merge2 = _dedup_merge(wiki_root=wiki_root)
    assert merge2["ok"] is True
    assert int(merge2["merged_count"]) == 0
    assert int(merge2["duplicate_count"]) >= 1


def test_process_task_writes_index_and_lint_report(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    plugin_cfg = {"wiki_root": str(wiki_root)}
    payload = {
        "kind": "captureAfterTurn",
        "session_id": "s-b",
        "turn_uuid": "turn-3",
        "user_text": "query",
        "assistant_text": "answer",
    }
    task = _task("t-proc")
    task = OpenClawTask(**{**task.__dict__, "payload": json.dumps(payload, ensure_ascii=False)})

    def _wiki_apply(args: dict) -> dict:
        rel = str(args.get("path") or "").replace("\\", "/").strip("/")
        fp = wiki_root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        action = str(args.get("action") or "").strip()
        content = str(args.get("content") or "")
        if action == "write":
            fp.write_text(content, encoding="utf-8")
        elif action == "append":
            old = fp.read_text(encoding="utf-8") if fp.exists() else ""
            sep = "" if not old or old.endswith("\n") else "\n"
            fp.write_text(old + sep + content, encoding="utf-8")
        return {"ok": True}

    def _wiki_lint(_args: dict) -> dict:
        return {"ok": True, "issues": []}

    out = _process_task(task=task, handlers={"wiki_apply": _wiki_apply, "wiki_lint": _wiki_lint}, plugin_cfg=plugin_cfg)
    assert out["ok"] is True
    assert (wiki_root / ".oclaw" / "index.json").exists()
    assert (wiki_root / ".oclaw" / "LINT_REPORT.md").exists()


def test_dedup_merge_routes_into_topic_pages(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    task = _task("t-topic")
    payload = {
        "session_id": "s-topic",
        "turn_uuid": "turn-topic",
        "user_text": "please check router vlan",
        "assistant_text": "network fix applied",
    }
    _capture_after_turn(wiki_root=wiki_root, task=task, payload=payload)
    out = _dedup_merge(wiki_root=wiki_root)
    assert out["ok"] is True
    assert int(out["merged_count"]) >= 1
    assert int((out.get("topic_counts") or {}).get("network", 0)) >= 1
    assert (wiki_root / "topics" / "auto-network.md").exists()
    assert (wiki_root / ".oclaw" / "topic-index.json").exists()


def test_dedup_merge_honors_configured_topic_rules(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    task = _task("t-custom-topic")
    payload = {
        "session_id": "s-custom",
        "turn_uuid": "turn-custom",
        "user_text": "please use terraform module",
        "assistant_text": "terraform plan applied",
    }
    _capture_after_turn(wiki_root=wiki_root, task=task, payload=payload)
    out = _dedup_merge(
        wiki_root=wiki_root,
        topic_rules=[{"topic": "iac", "keywords": ["terraform", "ansible"]}],
    )
    assert out["ok"] is True
    assert int((out.get("topic_counts") or {}).get("iac", 0)) >= 1
    assert (wiki_root / "topics" / "auto-iac.md").exists()
