from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_config() -> dict[str, Any]:
    cfg_path = _project_root() / "oclaw" / "oclaw.json"
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_wiki_entry(cfg: dict[str, Any]) -> dict[str, Any]:
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else {}
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    entry = entries.get("memory-wiki") if isinstance(entries, dict) else {}
    return entry if isinstance(entry, dict) else {}


def _resolve_runtime(entry: dict[str, Any]) -> tuple[Path, int, int, bool, int, bool]:
    root_cfg = str(entry.get("wiki_root") or "oclaw/docs/memory-system/wiki").strip()
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (_project_root() / root).resolve()
    auto = entry.get("auto") if isinstance(entry.get("auto"), dict) else {}
    inject = auto.get("inject") if isinstance(auto, dict) else {}
    max_chars = int(inject.get("max_chars") or 1800)
    top_k = int(inject.get("top_k") or 6)
    ultra_saver_enabled = bool(inject.get("ultra_saver_enabled", False))
    min_query_chars = int(inject.get("min_query_chars") or 20)
    require_topic_hint = bool(inject.get("require_topic_hint", True))
    return (
        root,
        max(500, min(max_chars, 8000)),
        max(1, min(top_k, 20)),
        ultra_saver_enabled,
        max(1, min(min_query_chars, 500)),
        require_topic_hint,
    )


def _enabled(entry: dict[str, Any]) -> bool:
    auto = entry.get("auto") if isinstance(entry.get("auto"), dict) else {}
    return bool(auto.get("enabled", False))


def _default_topic_rules() -> list[dict[str, Any]]:
    return [
        {"topic": "network", "keywords": ["vlan", "router", "switch", "network", "dns", "gateway"]},
        {"topic": "devops", "keywords": ["deploy", "k8s", "kubernetes", "docker", "ci", "ops"]},
        {"topic": "engineering", "keywords": ["bug", "fix", "todo", "feature", "refactor", "test"]},
    ]


def _resolve_topic_rules(entry: dict[str, Any]) -> list[dict[str, Any]]:
    auto = entry.get("auto") if isinstance(entry.get("auto"), dict) else {}
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


def _query_terms(query: str) -> list[str]:
    return [t for t in re.split(r"\s+", query.strip().lower()) if len(t) >= 2]


def _score_line(*, query: str, terms: list[str], text: str) -> float:
    low = text.lower()
    if not low:
        return 0.0
    score = 0.0
    if query and query in low:
        score += 4.0
    hit_terms = 0
    for term in terms:
        if term in low:
            hit_terms += 1
            score += 1.2
    if hit_terms > 1:
        score += 0.8
    return score


def _line_snippet(lines: list[str], idx: int) -> str:
    parts: list[str] = []
    start = max(0, idx - 1)
    end = min(len(lines), idx + 2)
    for i in range(start, end):
        line = str(lines[i] or "").strip()
        if not line:
            continue
        parts.append(line)
    return " | ".join(parts)


def _load_index_file_set(wiki_root: Path) -> set[str]:
    idx = wiki_root / ".oclaw" / "index.json"
    if not idx.exists():
        return set()
    try:
        obj = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:
        return set()
    files = obj.get("files") if isinstance(obj, dict) else None
    if not isinstance(files, list):
        return set()
    out: set[str] = set()
    for one in files:
        rel = str(one or "").replace("\\", "/").strip().lstrip("/")
        if rel:
            out.add(rel)
    return out


def _load_topic_index(wiki_root: Path) -> dict[str, str]:
    p = wiki_root / ".oclaw" / "topic-index.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    topics = obj.get("topics") if isinstance(obj, dict) else None
    if not isinstance(topics, dict):
        return {}
    out: dict[str, str] = {}
    for topic, meta in topics.items():
        if not isinstance(topic, str) or not isinstance(meta, dict):
            continue
        rel = str(meta.get("path") or "").replace("\\", "/").strip().lstrip("/")
        if rel:
            out[topic.lower()] = rel
    return out


def _query_topic_hints(query: str, rules: list[dict[str, Any]]) -> list[str]:
    low = str(query or "").lower()
    hints: list[str] = []
    for rule in rules:
        topic = str(rule.get("topic") or "").strip().lower()
        kws = rule.get("keywords") if isinstance(rule.get("keywords"), list) else []
        if not topic:
            continue
        if any(str(k).lower() in low for k in kws):
            hints.append(topic)
    return hints


def _candidate_files(wiki_root: Path) -> list[Path]:
    preferred: list[Path] = []
    merged = wiki_root / "inbox" / "merged-turns.md"
    if merged.exists() and merged.is_file():
        preferred.append(merged)
    index_set = _load_index_file_set(wiki_root)
    files = sorted([p for p in wiki_root.rglob("*.md") if p.is_file()])
    if not files:
        return preferred
    if not index_set:
        return preferred + [p for p in files if p not in preferred]
    prioritized = []
    fallback = []
    for p in files:
        if p in preferred:
            continue
        rel = str(p.relative_to(wiki_root)).replace("\\", "/")
        if rel in index_set:
            prioritized.append(p)
        else:
            fallback.append(p)
    return preferred + prioritized + fallback


def _candidate_files_for_query(wiki_root: Path, query: str, topic_rules: list[dict[str, Any]]) -> list[Path]:
    preferred: list[Path] = []
    topic_map = _load_topic_index(wiki_root)
    for hint in _query_topic_hints(query, topic_rules):
        rel = topic_map.get(hint)
        if not rel:
            continue
        p = wiki_root / rel
        if p.exists() and p.is_file() and p not in preferred:
            preferred.append(p)
    merged = wiki_root / "inbox" / "merged-turns.md"
    if merged.exists() and merged.is_file() and merged not in preferred:
        preferred.append(merged)
    rest = _candidate_files(wiki_root)
    return preferred + [p for p in rest if p not in preferred]


def _collect_snippets(
    wiki_root: Path,
    query: str,
    max_chars: int,
    top_k: int,
    topic_rules: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if not wiki_root.exists():
        return "", []
    q = query.strip().lower()
    if not q:
        return "", []
    terms = _query_terms(query)
    if not terms and len(query) < 2:
        return "", []
    rules = topic_rules or _default_topic_rules()
    candidates: list[tuple[float, int, str, int, str]] = []
    for source_rank, fp in enumerate(_candidate_files_for_query(wiki_root, query, rules)):
        rel = str(fp.relative_to(wiki_root)).replace("\\", "/")
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            txt = line.strip()
            if not txt:
                continue
            score = _score_line(query=q, terms=terms, text=txt)
            if score <= 0:
                continue
            snippet = _line_snippet(lines, idx - 1)
            one = f"- {rel}:{idx} {snippet}"
            candidates.append((score, int(source_rank), rel, idx, one))
    if not candidates:
        return "", []
    candidates.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
    blocks: list[str] = []
    meta: list[dict[str, Any]] = []
    total = 0
    truncated = False
    for score, _rank, _rel, _idx, one in candidates[: top_k * 10]:
        if any(one == exist for exist in blocks):
            continue
        if total + len(one) + 1 > max_chars:
            truncated = True
            break
        blocks.append(one)
        meta.append({"source": _rel, "line": int(_idx), "score": round(float(score), 3)})
        total += len(one) + 1
        if len(blocks) >= top_k:
            truncated = len(candidates) > len(meta)
            break
    if truncated:
        for item in meta:
            item["truncated"] = True
    return "\n".join(blocks).strip(), meta


def handle(event: Any) -> None:
    if getattr(event, "type", None) != "llm" or getattr(event, "action", None) != "before_prompt_build":
        return
    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        return
    memory_mode = str(ctx.get("memory_mode") or "default").strip().lower()
    if memory_mode == "store_only":
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": "store_only",
            "skip_reason": "memory_mode_store_only",
        }
        return
    manager_gate = ctx.get("need_wiki_inject")
    if isinstance(manager_gate, bool) and not manager_gate:
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "skip_reason": "manager_gate_off",
        }
        return
    manager_query = str(ctx.get("wiki_query") or "").strip()
    if isinstance(manager_gate, bool) and manager_gate and not manager_query:
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "skip_reason": "manager_wiki_query_missing",
        }
        return
    cfg = _load_config()
    entry = _resolve_wiki_entry(cfg)
    if not _enabled(entry):
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "skip_reason": "auto_disabled",
        }
        return
    wiki_root, max_chars, top_k, ultra_saver_enabled, min_query_chars, require_topic_hint = _resolve_runtime(entry)
    topic_rules = _resolve_topic_rules(entry)
    query = str(ctx.get("userText") or "").strip()
    if ultra_saver_enabled and not isinstance(manager_gate, bool) and len(query) < min_query_chars:
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "ultra_saver_enabled": True,
            "skip_reason": "short_query",
            "min_query_chars": int(min_query_chars),
            "query_len": int(len(query)),
        }
        return
    if ultra_saver_enabled and not isinstance(manager_gate, bool) and require_topic_hint and not _query_topic_hints(query, topic_rules):
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "ultra_saver_enabled": True,
            "skip_reason": "no_topic_hint",
        }
        return
    snippets, inject_meta = _collect_snippets(
        wiki_root,
        query,
        max_chars=max_chars,
        top_k=top_k,
        topic_rules=topic_rules,
    )
    if not snippets:
        ctx["wiki_inject_meta"] = {
            "enabled": False,
            "memory_mode": memory_mode,
            "top_k": int(top_k),
            "max_chars": int(max_chars),
            "ultra_saver_enabled": bool(ultra_saver_enabled),
            "skip_reason": "no_snippets",
        }
        return
    ctx["wiki_inject_meta"] = {
        "enabled": True,
        "memory_mode": memory_mode,
        "top_k": int(top_k),
        "max_chars": int(max_chars),
        "ultra_saver_enabled": bool(ultra_saver_enabled),
        "hits": inject_meta,
    }
    ctx["prepend_system_context"] = (
        "## Wiki Context (Auto Inject)\n"
        "Use as background context only; prefer latest user request when conflicts exist.\n\n"
        f"{snippets}"
    )
