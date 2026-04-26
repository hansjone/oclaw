from __future__ import annotations

import json
import os
import time
import importlib.util
import hashlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT, db_path
from oclaw.platform.persistence.sqlite_store import OclawTask, SqliteStore


def _load_oclaw_config() -> dict[str, Any]:
    cfg_path = (Path(PROJECT_ROOT) / "oclaw.json").resolve()
    if not cfg_path.exists():
        return {}
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _wiki_plugin_config(cfg: dict[str, Any]) -> dict[str, Any]:
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else {}
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    entry = entries.get("memory-wiki") if isinstance(entries, dict) else {}
    return entry if isinstance(entry, dict) else {}


def _is_worker_enabled(entry: dict[str, Any]) -> bool:
    auto = entry.get("auto") if isinstance(entry.get("auto"), dict) else {}
    worker = auto.get("worker") if isinstance(auto.get("worker"), dict) else {}
    return bool(auto.get("enabled", False) and worker.get("enabled", False))


def _resolve_wiki_root(plugin_cfg: dict[str, Any]) -> Path:
    root_cfg = str(plugin_cfg.get("wiki_root") or "docs/memory-system/wiki").strip()
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (Path(PROJECT_ROOT) / root).resolve()
    return root


def _default_topic_rules() -> list[dict[str, Any]]:
    return [
        {"topic": "network", "keywords": ["vlan", "router", "switch", "network", "dns", "gateway"]},
        {"topic": "devops", "keywords": ["deploy", "k8s", "kubernetes", "docker", "ci", "ops"]},
        {"topic": "engineering", "keywords": ["bug", "fix", "todo", "feature", "refactor", "test"]},
    ]


def _resolve_topic_rules(plugin_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    auto = plugin_cfg.get("auto") if isinstance(plugin_cfg.get("auto"), dict) else {}
    routing = auto.get("topic_routing") if isinstance(auto.get("topic_routing"), dict) else {}
    rules = routing.get("rules")
    if not isinstance(rules, list):
        return _default_topic_rules()
    out: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        topic = str(rule.get("topic") or "").strip().lower()
        kws = rule.get("keywords")
        if not topic or not isinstance(kws, list):
            continue
        keywords = [str(k).strip().lower() for k in kws if str(k).strip()]
        if not keywords:
            continue
        out.append({"topic": topic, "keywords": keywords})
    return out or _default_topic_rules()


def _tool_handlers(plugin_cfg: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        (Path(PROJECT_ROOT) / "runtime" / "extensions" / "memory-wiki" / "api.py").resolve(),
        (Path(PROJECT_ROOT) / "extensions" / "memory-wiki" / "api.py").resolve(),
    ]
    api_path = next((p for p in candidates if p.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("oclaw_memory_wiki_api_worker", str(api_path))
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    build_wiki_tool_specs = getattr(mod, "build_wiki_tool_specs", None)
    if not callable(build_wiki_tool_specs):
        return {}
    specs = build_wiki_tool_specs(SimpleNamespace(plugin_config=plugin_cfg))
    out: dict[str, Any] = {}
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or "").strip()
        handler = spec.get("handler")
        if name and callable(handler):
            out[name] = handler
    return out


def _payload(task: OclawTask) -> dict[str, Any]:
    try:
        obj = json.loads(task.payload or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _safe_token(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip())
    out = out.strip("._-")
    return out[:120] or "unknown"


def _normalize_for_hash(content: str) -> str:
    lines = []
    for raw in str(content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("### turn "):
            continue
        lines.append(line)
    return " ".join(" ".join(lines).split()).strip().lower()


def _state_file(wiki_root: Path) -> Path:
    return wiki_root / ".oclaw" / "merge-state.json"


def _load_merge_state(wiki_root: Path) -> dict[str, Any]:
    path = _state_file(wiki_root)
    if not path.exists():
        return {"processed_files": [], "seen_hashes": []}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed_files": [], "seen_hashes": []}
    if not isinstance(obj, dict):
        return {"processed_files": [], "seen_hashes": []}
    processed = obj.get("processed_files")
    hashes = obj.get("seen_hashes")
    return {
        "processed_files": processed if isinstance(processed, list) else [],
        "seen_hashes": hashes if isinstance(hashes, list) else [],
    }


def _save_merge_state(wiki_root: Path, state: dict[str, Any]) -> None:
    sdir = wiki_root / ".oclaw"
    sdir.mkdir(parents=True, exist_ok=True)
    path = _state_file(wiki_root)
    processed = [str(x) for x in list(state.get("processed_files") or [])][-20000:]
    hashes = [str(x) for x in list(state.get("seen_hashes") or [])][-20000:]
    path.write_text(
        json.dumps({"processed_files": processed, "seen_hashes": hashes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _capture_after_turn(*, wiki_root: Path, task: OclawTask, payload: dict[str, Any]) -> dict[str, Any]:
    turn_uuid = str(payload.get("turn_uuid") or "").strip()
    user_text = str(payload.get("user_text") or "").strip()
    assistant_text = str(payload.get("assistant_text") or "").strip()
    if not user_text and not assistant_text:
        return {"ok": True, "capture": "skipped_empty"}
    session_key = _safe_token(str(payload.get("session_id") or task.session_id or "session"))
    turn_key = _safe_token(turn_uuid or task.id)
    stage_dir = wiki_root / ".oclaw" / "staging" / session_key
    stage_dir.mkdir(parents=True, exist_ok=True)
    stage_file = stage_dir / f"{turn_key}.md"
    block = [
        f"### turn {turn_uuid or task.id}",
        "",
        f"- user: {user_text[:1200]}",
        f"- assistant: {assistant_text[:2400]}",
        "",
    ]
    stage_file.write_text("\n".join(block).strip() + "\n", encoding="utf-8")
    rel = str(stage_file.relative_to(wiki_root)).replace("\\", "/")
    return {"ok": True, "staged": rel}


def _dedup_merge(*, wiki_root: Path, topic_rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    state = _load_merge_state(wiki_root)
    processed_files = set(str(x) for x in list(state.get("processed_files") or []))
    seen_hashes = set(str(x) for x in list(state.get("seen_hashes") or []))
    staging_dir = wiki_root / ".oclaw" / "staging"
    merged_file = wiki_root / "inbox" / "merged-turns.md"
    merged_file.parent.mkdir(parents=True, exist_ok=True)
    merged_count = 0
    skipped_dup = 0
    topic_counts: dict[str, int] = {}

    rules = topic_rules or _default_topic_rules()

    def _detect_topic(text: str) -> str:
        low = str(text or "").lower()
        for rule in rules:
            topic = str(rule.get("topic") or "").strip().lower()
            kws = rule.get("keywords") if isinstance(rule.get("keywords"), list) else []
            if topic and any(str(k).lower() in low for k in kws):
                return topic
        return "general"

    if staging_dir.exists():
        for fp in sorted(staging_dir.rglob("*.md")):
            rel = str(fp.relative_to(wiki_root)).replace("\\", "/")
            if rel in processed_files:
                continue
            try:
                content = fp.read_text(encoding="utf-8")
            except Exception:
                processed_files.add(rel)
                continue
            digest = hashlib.sha1(_normalize_for_hash(content).encode("utf-8")).hexdigest()
            processed_files.add(rel)
            if digest in seen_hashes:
                skipped_dup += 1
                continue
            seen_hashes.add(digest)
            old = merged_file.read_text(encoding="utf-8") if merged_file.exists() else ""
            sep = "" if not old or old.endswith("\n\n") else "\n"
            topic = _detect_topic(content)
            topic_file = wiki_root / "topics" / f"auto-{topic}.md"
            topic_file.parent.mkdir(parents=True, exist_ok=True)
            merged_file.write_text(
                old + sep + f"<!-- source:{rel} hash:{digest} -->\n" + content.strip() + "\n\n",
                encoding="utf-8",
            )
            old_topic = topic_file.read_text(encoding="utf-8") if topic_file.exists() else ""
            sep_topic = "" if not old_topic or old_topic.endswith("\n\n") else "\n"
            topic_file.write_text(
                old_topic + sep_topic + f"<!-- source:{rel} hash:{digest} -->\n" + content.strip() + "\n\n",
                encoding="utf-8",
            )
            topic_counts[topic] = int(topic_counts.get(topic, 0)) + 1
            merged_count += 1
    _save_merge_state(
        wiki_root,
        {
            "processed_files": sorted(processed_files),
            "seen_hashes": sorted(seen_hashes),
        },
    )
    topic_index = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topics": {
            k: {"path": f"topics/auto-{k}.md", "merged_count": int(v)}
            for k, v in sorted(topic_counts.items())
        },
    }
    state_dir = wiki_root / ".oclaw"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "topic-index.json").write_text(json.dumps(topic_index, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "merged_count": merged_count,
        "duplicate_count": skipped_dup,
        "topic_counts": topic_counts,
    }


def _update_index(*, plugin_cfg: dict[str, Any]) -> dict[str, Any]:
    wiki_root = _resolve_wiki_root(plugin_cfg)
    files = []
    if wiki_root.exists():
        files = sorted(str(p.relative_to(wiki_root)).replace("\\", "/") for p in wiki_root.rglob("*.md"))
    state_dir = wiki_root / ".oclaw"
    state_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_count": len(files),
        "files": files[:5000],
        "staging_count": len(list((wiki_root / ".oclaw" / "staging").rglob("*.md")))
        if (wiki_root / ".oclaw" / "staging").exists()
        else 0,
    }
    (state_dir / "index.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "index_file_count": len(files)}


def _lint_report(*, handlers: dict[str, Any]) -> dict[str, Any]:
    lint = handlers["wiki_lint"]({})
    issues = list((lint or {}).get("issues") or [])
    lines = ["# Wiki Lint Report", "", f"- issue_count: {len(issues)}", ""]
    for issue in issues[:300]:
        path = str(issue.get("path") or "")
        line = int(issue.get("line") or 1)
        code = str(issue.get("code") or "")
        lines.append(f"- {path}:{line} {code}")
    handlers["wiki_apply"]({"action": "write", "path": ".oclaw/LINT_REPORT.md", "content": "\n".join(lines).strip() + "\n"})
    return {"ok": True, "issue_count": len(issues)}


def _process_task(*, task: OclawTask, handlers: dict[str, Any], plugin_cfg: dict[str, Any]) -> dict[str, Any]:
    wiki_root = _resolve_wiki_root(plugin_cfg)
    wiki_root.mkdir(parents=True, exist_ok=True)
    payload = _payload(task)
    capture = _capture_after_turn(wiki_root=wiki_root, task=task, payload=payload)
    merge = _dedup_merge(wiki_root=wiki_root, topic_rules=_resolve_topic_rules(plugin_cfg))
    index = _update_index(plugin_cfg=plugin_cfg)
    lint = _lint_report(handlers=handlers)
    return {"ok": True, "capture": capture, "dedupMerge": merge, "updateIndex": index, "lintReport": lint}


def run_worker() -> int:
    interval_s = max(2, min(int(os.getenv("AIA_WIKI_WORKER_POLL_SECONDS", "4")), 60))
    worker_id = str(os.getenv("AIA_WIKI_WORKER_ID") or "wiki-worker-main").strip() or "wiki-worker-main"
    store = SqliteStore(db_path())
    while True:
        cfg = _load_oclaw_config()
        plugin_cfg = _wiki_plugin_config(cfg)
        if not _is_worker_enabled(plugin_cfg):
            time.sleep(interval_s)
            continue
        handlers = _tool_handlers(plugin_cfg)
        if not {"wiki_apply", "wiki_lint"}.issubset(set(handlers.keys())):
            time.sleep(interval_s)
            continue
        task = store.oclaw_task_claim(worker_id=worker_id, lease_seconds=120, task_type="wiki_capture")
        if task is None:
            time.sleep(interval_s)
            continue
        try:
            result = _process_task(task=task, handlers=handlers, plugin_cfg=plugin_cfg)
            store.oclaw_task_finish(task_id=task.id, result=result)
        except Exception as exc:
            store.oclaw_task_fail(task_id=task.id, error=f"{type(exc).__name__}: {exc}", result={"ok": False})
            time.sleep(interval_s)


if __name__ == "__main__":
    raise SystemExit(run_worker())
