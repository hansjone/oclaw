from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from svc.config.paths import PROJECT_ROOT, db_path
from svc.persistence.sqlite_store import SqliteStore


def _load_cfg() -> dict:
    cfg_file = (Path(PROJECT_ROOT) / "oclaw.json").resolve()
    if not cfg_file.exists():
        return {}
    try:
        obj = json.loads(cfg_file.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _wiki_root_from_cfg(cfg: dict) -> Path:
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else {}
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    mw = entries.get("memory-wiki") if isinstance(entries, dict) else {}
    root_cfg = str((mw or {}).get("wiki_root") or "docs/memory-system/wiki").strip()
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (Path(PROJECT_ROOT) / root).resolve()
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for wiki auto pipeline.")
    parser.add_argument("--timeout-s", type=int, default=30, help="Task wait timeout in seconds.")
    args = parser.parse_args()

    cfg = _load_cfg()
    wiki_root = _wiki_root_from_cfg(cfg)
    store = SqliteStore(db_path())

    suffix = uuid.uuid4().hex[:8]
    payload = {
        "kind": "captureAfterTurn",
        "session_id": f"smoke-session-{suffix}",
        "tenant_id": "default",
        "user_id": "smoke-user",
        "turn_uuid": f"smoke-turn-{suffix}",
        "user_text": "smoke router vlan check",
        "assistant_text": "smoke response for wiki worker",
    }
    task = store.oclaw_task_create(
        tenant_id="default",
        session_id=payload["session_id"],
        task_type="wiki_capture",
        payload=payload,
    )
    print(f"[smoke] created task: {task.id}")

    deadline = time.time() + max(5, int(args.timeout_s))
    final = task
    while time.time() < deadline:
        got = store.oclaw_task_get(task_id=task.id)
        if got is None:
            print("[smoke] task missing")
            return 2
        final = got
        if final.status in {"done", "failed"}:
            break
        time.sleep(1.0)

    print(f"[smoke] final status: {final.status}")
    if final.status not in {"done", "failed"}:
        print("[smoke] timeout waiting for worker")
        return 3

    artifacts = {
        "merged_turns": wiki_root / "inbox" / "merged-turns.md",
        "topic_index": wiki_root / ".oclaw" / "topic-index.json",
        "index": wiki_root / ".oclaw" / "index.json",
        "lint_report": wiki_root / ".oclaw" / "LINT_REPORT.md",
    }
    for name, fp in artifacts.items():
        print(f"[smoke] {name}: {'ok' if fp.exists() else 'missing'} ({fp})")

    if final.status == "failed":
        print(f"[smoke] worker error: {final.last_error}")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
