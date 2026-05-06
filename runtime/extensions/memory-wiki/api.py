from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_plugin_config_schema(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "wiki_root": {
                "type": "string",
                "description": "Wiki root directory relative to workspace root.",
                "default": "docs/memory-system/wiki",
            },
            "max_search_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 20,
            },
            "max_get_lines": {
                "type": "integer",
                "minimum": 20,
                "maximum": 5000,
                "default": 800,
            },
        },
        "additionalProperties": True,
    }


@dataclass(frozen=True)
class WikiRuntime:
    wiki_root: Path
    max_search_results: int
    max_get_lines: int


def _resolve_runtime(api: Any) -> WikiRuntime:
    cfg = dict(getattr(api, "plugin_config", {}) or {})
    root_cfg = str(cfg.get("wiki_root") or "docs/memory-system/wiki").strip()
    if not root_cfg:
        root_cfg = "docs/memory-system/wiki"
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (_project_root() / root).resolve()
    max_search_results = int(cfg.get("max_search_results") or 20)
    max_get_lines = int(cfg.get("max_get_lines") or 800)
    max_search_results = max(1, min(max_search_results, 200))
    max_get_lines = max(20, min(max_get_lines, 5000))
    return WikiRuntime(wiki_root=root, max_search_results=max_search_results, max_get_lines=max_get_lines)


def _safe_path(rt: WikiRuntime, rel_path: str) -> Path:
    raw = str(rel_path or "").strip()
    raw = raw.replace("\\", "/")
    raw = raw.lstrip("./")
    if not raw:
        raise ValueError("path_required")

    root = rt.wiki_root.resolve()

    # 1) Absolute path: accept if it's under wiki_root.
    try:
        cand = Path(raw)
        if cand.is_absolute():
            p = cand.resolve()
            if p.suffix.lower() != ".md":
                raise ValueError("only_markdown_supported")
            if p != root and root not in p.parents:
                raise ValueError("path_outside_wiki_root")
            return p
    except Exception:
        # fall through to relative/normalized handling
        pass

    # 2) Relative path: normalize common "data/wiki/..." prefixes to wiki_root-relative paths.
    rp = raw.lstrip("/")

    prefixes: list[str] = []
    # Legacy/default prefix.
    prefixes.append("data/wiki/")

    # If wiki_root is configured under project root, allow stripping its relative prefix too.
    try:
        root_rel = rt.wiki_root.resolve().relative_to(_project_root().resolve()).as_posix()
        if root_rel:
            prefixes.append(str(root_rel).lstrip("/") + "/")
    except Exception:
        pass

    # Allow stripping the wiki_root folder name (e.g., "wiki/xxx.md") if user passes it.
    prefixes.append(f"{root.name}/")

    rp_lower = rp.lower()
    stripped = rp
    for pref in prefixes:
        pref_l = str(pref or "").strip().lower()
        if not pref_l:
            continue
        if rp_lower.startswith(pref_l):
            stripped = rp[len(pref) :]
            break

    p = (rt.wiki_root / stripped).resolve()
    if p.suffix.lower() != ".md":
        raise ValueError("only_markdown_supported")
    if p != root and root not in p.parents:
        raise ValueError("path_outside_wiki_root")
    return p


def _list_md_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*.md") if p.is_file()])


def _read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return text.splitlines()


def _clip_text(s: str, *, max_chars: int = 240) -> str:
    t = str(s or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max(1, max_chars - 15)] + "...<truncated>"


def _tokens_for_query(raw_query: str) -> list[str]:
    q = str(raw_query or "").strip()
    if not q:
        return []
    # Keep CJK runs, alpha words, and numbers.
    parts = re.findall(r"[\u4e00-\u9fff]+|[A-Za-z]+|\d+", q)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        tok = str(p or "").strip()
        key = tok.lower()
        if not tok or key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


def _expand_query_variants(raw_query: str) -> list[str]:
    query = str(raw_query or "").strip()
    if not query:
        return []
    variants: list[str] = [query]
    synonym_map: dict[str, list[str]] = {
        "用户": ["创作者", "项目所有者", "owner", "profile", "identity"],
        "身份": ["角色", "identity", "profile"],
        "创建者": ["创作者", "所有者", "owner"],
        "owner": ["所有者", "项目所有者", "创作者"],
        "creator": ["创作者", "创建者", "项目所有者"],
        "name": ["名字", "姓名"],
    }
    toks = _tokens_for_query(query)
    for tok in toks:
        for syn in synonym_map.get(tok.lower(), []):
            if syn not in variants:
                variants.append(syn)
    if len(toks) > 1:
        joined = " ".join(toks)
        if joined not in variants:
            variants.append(joined)
    return variants


def _build_line_hit(
    *,
    lines: list[str],
    line_idx: int,
    rel_path: str,
    matched_query: str,
    context_lines: int,
) -> dict[str, Any]:
    before_start = max(0, line_idx - context_lines)
    before_lines = lines[before_start:line_idx]
    after_end = min(len(lines), line_idx + 1 + context_lines)
    after_lines = lines[line_idx + 1 : after_end]
    return {
        "path": rel_path,
        "line": int(line_idx + 1),
        "text": _clip_text(lines[line_idx]),
        "before": [_clip_text(x) for x in before_lines],
        "after": [_clip_text(x) for x in after_lines],
        "matched_query": str(matched_query or ""),
    }


def _wiki_status(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    del args
    files = _list_md_files(rt.wiki_root)
    return {
        "ok": True,
        "wiki_root": str(rt.wiki_root),
        "exists": bool(rt.wiki_root.exists()),
        "file_count": len(files),
        "max_search_results": rt.max_search_results,
        "max_get_lines": rt.max_get_lines,
    }


def _wiki_get(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    path = _safe_path(rt, str(args.get("path") or ""))
    if not path.exists():
        return {"ok": False, "error_code": "wiki_not_found", "error": f"file not found: {path}"}
    start = int(args.get("start_line") or 1)
    end = int(args.get("end_line") or 0)
    lines = _read_lines(path)
    n = len(lines)
    start = max(1, min(start, n if n > 0 else 1))
    if end <= 0:
        end = min(n, start + rt.max_get_lines - 1)
    end = max(start, min(end, n))
    out_lines = lines[start - 1 : end]
    return {
        "ok": True,
        "path": str(path.relative_to(rt.wiki_root)),
        "start_line": start,
        "end_line": end,
        "content": "\n".join(out_lines),
    }


def _wiki_search(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error_code": "query_required", "error": "query is required"}
    case_sensitive = bool(args.get("case_sensitive"))
    is_regex = bool(args.get("is_regex"))
    req_limit = int(args.get("limit") or rt.max_search_results)
    limit = max(1, min(req_limit, rt.max_search_results))
    offset = max(0, int(args.get("offset") or 0))
    context_lines = max(0, min(int(args.get("context_lines") or 0), 5))
    path_prefix = str(args.get("path_prefix") or "").strip().replace("\\", "/").lstrip("/")
    expand_query = bool(args.get("expand_query")) and not is_regex
    max_rounds = max(1, min(int(args.get("max_rounds") or 2), 5))

    queries = [query]
    if expand_query:
        queries = _expand_query_variants(query)[:max_rounds]

    flags = 0 if case_sensitive else re.IGNORECASE
    hits_all: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()
    files_scanned = 0

    for qv in queries:
        pattern = re.compile(qv if is_regex else re.escape(qv), flags=flags)
        for fp in _list_md_files(rt.wiki_root):
            rel = str(fp.relative_to(rt.wiki_root)).replace("\\", "/")
            if path_prefix and not rel.startswith(path_prefix):
                continue
            files_scanned += 1
            lines = _read_lines(fp)
            for idx, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                key = (rel, int(idx + 1))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                hits_all.append(
                    _build_line_hit(
                        lines=lines,
                        line_idx=idx,
                        rel_path=rel,
                        matched_query=qv,
                        context_lines=context_lines,
                    )
                )

    hits_page = hits_all[offset : offset + limit]
    next_offset = offset + len(hits_page)
    truncated = next_offset < len(hits_all)
    query_used = str(hits_page[0].get("matched_query") or query) if hits_page else query

    # Backward-compatible fields remain: ok/query/hits/truncated.
    # New fields are additive diagnostics/controls for iterative search flows.
    return {
        "ok": True,
        "query": query,
        "hits": hits_page,
        "truncated": bool(truncated),
        "query_used": query_used,
        "queries_attempted": queries,
        "total_hits_estimate": len(hits_all),
        "offset": offset,
        "next_offset": next_offset if truncated else None,
        "limit": limit,
        "context_lines": context_lines,
        "path_prefix": path_prefix,
        "files_scanned": files_scanned,
        "expanded": bool(expand_query),
    }


def _wiki_lint(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("path") or "").strip()
    files = [_safe_path(rt, target)] if target else _list_md_files(rt.wiki_root)
    issues: list[dict[str, Any]] = []
    for fp in files:
        if not fp.exists():
            issues.append({"path": str(fp), "line": 1, "level": "error", "code": "wiki_not_found"})
            continue
        rel = str(fp.relative_to(rt.wiki_root)).replace("\\", "/")
        lines = _read_lines(fp)
        h1_count = 0
        prev_level = 0
        for idx, line in enumerate(lines, start=1):
            m = re.match(r"^\s*(#{1,6})\s+\S+", line)
            if m:
                level = len(m.group(1))
                if level == 1:
                    h1_count += 1
                if prev_level > 0 and level > prev_level + 1:
                    issues.append(
                        {
                            "path": rel,
                            "line": idx,
                            "level": "warn",
                            "code": "heading_jump",
                            "message": f"heading jump h{prev_level} -> h{level}",
                        }
                    )
                prev_level = level
            if line.rstrip(" \t") != line:
                issues.append({"path": rel, "line": idx, "level": "warn", "code": "trailing_whitespace"})
        if h1_count > 1:
            issues.append({"path": rel, "line": 1, "level": "warn", "code": "multiple_h1", "count": h1_count})
    errors = [x for x in issues if str(x.get("level")) == "error"]
    return {"ok": len(errors) == 0, "issue_count": len(issues), "issues": issues}


def _wiki_apply(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "write").strip().lower()
    path = _safe_path(rt, str(args.get("path") or ""))
    content = str(args.get("content") or "")
    path.parent.mkdir(parents=True, exist_ok=True)
    if action == "delete":
        if not path.exists():
            return {"ok": False, "error_code": "wiki_not_found", "error": f"file not found: {path}"}
        path.unlink()
        return {"ok": True, "action": "delete", "path": str(path.relative_to(rt.wiki_root))}
    if action == "append":
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        sep = "" if not old or old.endswith("\n") else "\n"
        path.write_text(old + sep + content, encoding="utf-8")
        return {"ok": True, "action": "append", "path": str(path.relative_to(rt.wiki_root))}
    if action == "write":
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "action": "write", "path": str(path.relative_to(rt.wiki_root))}
    return {"ok": False, "error_code": "invalid_action", "error": f"unsupported action: {action}"}


def build_wiki_tool_specs(api: Any) -> list[dict[str, Any]]:
    rt = _resolve_runtime(api)

    def _wrap(fn: Callable[[WikiRuntime, dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def _handler(args: dict[str, Any]) -> dict[str, Any]:
            try:
                return fn(rt, dict(args or {}))
            except ValueError as exc:
                return {"ok": False, "error_code": "invalid_arguments", "error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error_code": "wiki_runtime_error", "error": f"{type(exc).__name__}: {exc}"}

        return _handler

    base_obj = {"type": "object", "additionalProperties": False}
    return [
        {
            "name": "wiki_status",
            "description": "Show wiki plugin status and basic file counts.",
            "parameters": {**base_obj, "properties": {}},
            "handler": _wrap(_wiki_status),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_get",
            "description": "Read a markdown file from wiki root with optional line range.",
            "parameters": {
                **base_obj,
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
            "handler": _wrap(_wiki_get),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_search",
            "description": "Search markdown files under wiki root.",
            "parameters": {
                **base_obj,
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "is_regex": {"type": "boolean"},
                    "case_sensitive": {"type": "boolean"},
                    "context_lines": {"type": "integer"},
                    "path_prefix": {"type": "string"},
                    "expand_query": {"type": "boolean"},
                    "max_rounds": {"type": "integer"},
                },
                "required": ["query"],
            },
            "handler": _wrap(_wiki_search),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_lint",
            "description": "Lint wiki markdown files (headings and formatting checks).",
            "parameters": {
                **base_obj,
                "properties": {"path": {"type": "string"}},
            },
            "handler": _wrap(_wiki_lint),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_apply",
            "description": "Apply write/append/delete on a wiki markdown file.",
            "parameters": {
                **base_obj,
                "properties": {
                    "action": {"type": "string", "enum": ["write", "append", "delete"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["action", "path"],
            },
            "handler": _wrap(_wiki_apply),
            "tags": ["memory", "wiki", "write"],
            "read_only": False,
            "risk_level": "high",
        },
    ]
